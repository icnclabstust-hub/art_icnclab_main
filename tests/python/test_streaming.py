"""回答串流文字處理（langchain-rag/streaming.py）。"""

import json

from streaming import SentenceSplitter, ThinkFilter, ndjson, sentence_hook, with_heartbeat


def run_think(chunks):
    f = ThinkFilter()
    out = "".join(f.feed(c) for c in chunks)
    return out + f.finish()


def test_think_removed_in_one_chunk():
    assert run_think(["<think>想一想</think>答案是 1642。"]) == "答案是 1642。"


def test_think_tags_split_across_chunks():
    chunks = ["前言", "<th", "ink>推理", "中…</thi", "nk>正文"]
    assert run_think(chunks) == "前言正文"


def test_unclosed_think_dropped():
    assert run_think(["正文。", "<think>推理被截斷"]) == "正文。"


def test_text_ending_with_lt_kept():
    assert run_think(["a < b", " 成立"]) == "a < b 成立"


def test_no_think_passthrough():
    assert run_think(["林布蘭", "的《夜巡》"]) == "林布蘭的《夜巡》"


def split_all(chunks, first_clause=False):
    s = SentenceSplitter(first_clause=first_clause)
    out = []
    for c in chunks:
        out += s.feed(c)
    return out, s.flush()


def test_chinese_sentences_across_chunks():
    out, rest = split_all(["夜巡完成於", "1642 年。使用", "油彩！還有"])
    assert out == ["夜巡完成於1642 年。", "使用油彩！"]
    assert rest == "還有"


def test_english_period_needs_space_and_decimal_kept():
    out, rest = split_all(["Version 1.5 is fine. Next", " part"])
    assert out == ["Version 1.5 is fine."]
    assert rest == " Next part"


def test_newline_ends_sentence_and_markdown_list():
    out, rest = split_all(["### 標題\n- 第一點", "\n- 第二點"])
    assert out == ["### 標題\n", "- 第一點\n"]
    assert rest == "- 第二點"


def test_hook_is_passthrough_and_ndjson():
    assert sentence_hook("句子。", []) == "句子。"
    line = ndjson({"type": "delta", "text": "林布蘭"})
    assert line.endswith(b"\n") and json.loads(line)["text"] == "林布蘭"


def test_first_clause_sent_early_then_sentences():
    out, rest = split_all(
        ["根據提供的參考資料，林布蘭的", "《夜巡》完成於 1642 年，使用油彩。其後"], True
    )
    assert out == ["根據提供的參考資料，", "林布蘭的《夜巡》完成於 1642 年，使用油彩。"]
    assert rest == "其後"


def test_first_clause_needs_min_length():
    out, _ = split_all(["是，", "林布蘭的作品。"], True)
    assert out == ["是，林布蘭的作品。"]


def test_heartbeat_wrapper_yields_waiting_without_cancelling():
    import asyncio

    async def slow():
        await asyncio.sleep(0.18)
        yield "text", "甲"
        yield "text", "乙"

    async def collect():
        return [x async for x in with_heartbeat(slow(), interval=0.05)]

    out = asyncio.run(collect())
    assert [x for x in out if x[0] == "text"] == [("text", "甲"), ("text", "乙")]
    assert sum(x[0] == "waiting" for x in out) >= 2
