"""回答串流的文字處理（設計 docs/designs/2026-10-14-streaming-response.md §3.3）。

- ThinkFilter：去掉 deepseek-r1 寫進回應的 <think>…</think>（標記可跨 chunk；未閉合者丟棄）
- SentenceSplitter：累積到句尾（中文句末標點、換行、英文 .!? 後接空白）才送出一句；
  第一段可提早在逗號、頓號、冒號送出（已累積 ≥ FIRST_CLAUSE_MIN 字），縮短首句等待
- sentence_hook：每句送出前的檢查點。現在不改內容；守門員改攔截（#15）或分層回答（#12）時接在這裡
"""

import asyncio
import contextlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

_OPEN, _CLOSE = "<think>", "</think>"
# 中文句末標點與換行直接斷句；英文 .!? 需後接空白（避免 1.5、e.g 之類被切開）
_SENTENCE_END = re.compile(r"[。！？；\n]+|[.!?]+(?=\s)")
_CLAUSE_END = re.compile(r"[，、：,:]")
FIRST_CLAUSE_MIN = 8


class ThinkFilter:
    """逐段過濾 <think>…</think>；feed 回傳可顯示的文字。"""

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out = []
        while self._buf:
            if self._in_think:
                end = self._buf.find(_CLOSE)
                if end == -1:
                    # 保留可能是結束標記開頭的尾巴，其餘思考內容丟棄
                    self._buf = self._buf[-(len(_CLOSE) - 1) :]
                    break
                self._buf = self._buf[end + len(_CLOSE) :]
                self._in_think = False
                continue
            start = self._buf.find(_OPEN)
            if start == -1:
                # 尾巴可能是 "<thi" 這類未完整的開始標記，先留著
                keep = next(
                    (k for k in range(len(_OPEN) - 1, 0, -1) if self._buf.endswith(_OPEN[:k])), 0
                )
                out.append(self._buf[: len(self._buf) - keep])
                self._buf = self._buf[len(self._buf) - keep :]
                break
            out.append(self._buf[:start])
            self._buf = self._buf[start + len(_OPEN) :]
            self._in_think = True
        return "".join(out)

    @property
    def in_think(self) -> bool:
        return self._in_think

    def finish(self) -> str:
        """結束時：未閉合的思考段落丟棄；留下的非標記尾巴送出。"""
        rest = "" if self._in_think else self._buf
        self._buf = ""
        return rest


class SentenceSplitter:
    """累積文字，回傳已完整的句子；flush 送出最後不完整的部分。"""

    def __init__(self, first_clause: bool = True) -> None:
        self._buf = ""
        self._first_pending = first_clause

    def feed(self, text: str) -> list[str]:
        self._buf += text
        sentences = []
        pos = 0
        if self._first_pending and not _SENTENCE_END.search(self._buf):
            for m in _CLAUSE_END.finditer(self._buf):
                if m.end() >= FIRST_CLAUSE_MIN:
                    sentences.append(self._buf[: m.end()])
                    pos = m.end()
                    break
        for m in _SENTENCE_END.finditer(self._buf, pos):
            sentences.append(self._buf[pos : m.end()])
            pos = m.end()
        self._buf = self._buf[pos:]
        sentences = [s for s in sentences if s]
        if sentences:
            self._first_pending = False
        return sentences

    def flush(self) -> str:
        rest, self._buf = self._buf, ""
        return rest


def sentence_hook(sentence: str, sources: Sequence[Mapping[str, Any]]) -> str | None:
    """每句送出前的檢查點：回傳要送出的句子，None＝不送。目前原樣送出。"""
    return sentence


def ndjson(obj: Mapping[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


async def with_heartbeat(agen, interval: float = 3.0):
    """包住非同步產生器：等下一段超過 interval 秒時產出 ("waiting", "")（模型載入中）。

    讀取放在獨立 task、以 asyncio.wait 輪詢，逾時不取消讀取（避免中斷與 Ollama 的串流連線）。
    """
    it = agen.__aiter__()
    pending = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(it.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield "waiting", ""
                continue
            task, pending = pending, None
            try:
                yield task.result()
            except StopAsyncIteration:
                return
    finally:
        # 用戶端提早斷線：先取消並等待讀取中的 task，再關閉內層產生器
        # （直接關閉會出現「aclose(): asynchronous generator is already running」）
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(BaseException):  # 取消或結束時的例外不需處理
                await pending
        aclose = getattr(it, "aclose", None)
        if aclose is not None:
            await aclose()
