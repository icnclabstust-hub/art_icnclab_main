#!/usr/bin/env python3
"""
多語言查詢翻譯器
支持中文、日文、韓文等多語言查詢轉換為英文
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class MultilingualQueryTranslator:
    """多語言查詢翻譯器"""

    def __init__(self, dictionary_path: str | None = None):
        """初始化翻譯器

        Args:
            dictionary_path: 術語字典路徑，如果為 None 則使用默認路徑
        """
        # 載入術語字典
        if dictionary_path is None:
            # 嘗試多個可能的路徑
            possible_paths = [
                Path(__file__).parent.parent / "../art_history_terms_dictionary.json",
                Path(__file__).parent / "../art_history_terms_dictionary.json",
                Path("/app/art_history_terms_dictionary.json"),
            ]
            dictionary_path = None
            for path in possible_paths:
                if path.exists():
                    dictionary_path = path
                    break

            if dictionary_path is None:
                dictionary_path = possible_paths[0]  # 使用第一個作為默認

        try:
            with open(dictionary_path, encoding="utf-8") as f:
                self.dictionary = json.load(f)
            logger.info(f"✅ 載入術語字典: {dictionary_path}")
        except Exception as e:
            logger.warning(f"⚠️ 無法載入術語字典: {e}，使用空字典")
            self.dictionary = {}

        # 建立反向查詢索引（多語言 -> 英文）
        self.term_index = self._build_term_index()

        # 語言檢測模式
        self.language_patterns = {
            "zh": re.compile(r"[\u4e00-\u9fff]"),  # 中文
            "ja": re.compile(r"[\u3040-\u309f\u30a0-\u30ff]"),  # 日文平假名+片假名
            "ko": re.compile(r"[\uac00-\ud7af]"),  # 韓文
        }

    def _build_term_index(self) -> dict[str, str]:
        """建立術語索引：多語言詞彙 -> 英文關鍵詞；另記錄每個詞條出自哪些語言"""
        index = {}
        self.term_langs: dict[str, set[str]] = {}

        for _category, terms in self.dictionary.items():
            for english_key, translations in terms.items():
                # 英文本身也加入索引
                index[english_key.lower()] = english_key
                self.term_langs.setdefault(english_key.lower(), set()).add("en")

                # 遍歷所有語言的翻譯
                if isinstance(translations, dict):
                    for lang, term_list in translations.items():
                        for term in term_list if isinstance(term_list, list) else [term_list]:
                            if isinstance(term, str):
                                index[term.lower()] = english_key
                                self.term_langs.setdefault(term.lower(), set()).add(lang)

        logger.info(f"✅ 建立術語索引: {len(index)} 個詞條")
        return index

    def _match_allowed(self, text: str, pos: int, term: str, lang: str) -> bool:
        """排除三種誤中：日文專用詞套在中文查詢（「影」→ shadow 切開「影響」）、
        拉丁字母詞出現在更長的字裡（color 切開 colorito）、單一漢字出現在複合詞裡
        （「光」切開「光學」、「銅」把「銅版畫」譯成 bronze）"""
        if self.term_langs.get(term) == {"ja"} and lang != "ja":
            return False
        before = text[pos - 1] if pos > 0 else ""
        after = text[pos + len(term)] if pos + len(term) < len(text) else ""
        if term.isascii():
            return not (before.isascii() and before.isalnum()) and not (
                after.isascii() and after.isalnum()
            )
        if len(term) == 1:
            cjk = self.language_patterns["zh"]
            return not cjk.match(before) and not cjk.match(after)
        return True

    def detect_language(self, text: str) -> str:
        """檢測文本的主要語言

        Args:
            text: 輸入文本

        Returns:
            語言代碼: 'en', 'zh', 'ja', 'ko', 'unknown'
        """
        # 檢查是否包含非英文字符
        has_chinese = bool(self.language_patterns["zh"].search(text))
        has_japanese = bool(self.language_patterns["ja"].search(text))
        has_korean = bool(self.language_patterns["ko"].search(text))

        # 日文也含漢字，先看假名；中文查詢不會有假名
        if has_japanese:
            return "ja"
        elif has_chinese:
            return "zh"
        elif has_korean:
            return "ko"
        elif text.isascii():
            return "en"
        else:
            return "unknown"

    def translate_terms(self, query: str) -> tuple[str, list[str]]:
        """翻譯查詢中的專業術語

        Args:
            query: 原始查詢

        Returns:
            (翻譯後的查詢, 識別的術語列表)
        """
        # 將查詢轉為小寫以匹配索引
        query_lower = query.lower()
        lang = self.detect_language(query)

        # 按詞彙長度排序（先匹配長詞彙）
        sorted_terms = sorted(self.term_index.keys(), key=len, reverse=True)

        # 收集所有需要替換的位置和內容
        replacements = []
        replaced_positions = set()

        for term in sorted_terms:
            if term in query_lower:
                # 找到所有匹配位置
                start = 0
                while True:
                    pos = query_lower.find(term, start)
                    if pos == -1:
                        break

                    # 檢查是否與已找到的替換位置重疊，以及是否為誤中（見 _match_allowed）
                    if not any(
                        pos <= p < pos + len(term) for p in replaced_positions
                    ) and self._match_allowed(query_lower, pos, term, lang):
                        # 獲取英文對應詞
                        english_term = self.term_index[term]
                        original_term = query[pos : pos + len(term)]

                        # 記錄替換
                        replacements.append(
                            {
                                "pos": pos,
                                "length": len(term),
                                "original": original_term,
                                "replacement": english_term,
                            }
                        )

                        # 記錄替換位置
                        for i in range(pos, pos + len(term)):
                            replaced_positions.add(i)

                    start = pos + 1

        # 按位置從後往前排序，這樣替換時不會影響前面的位置
        replacements.sort(key=lambda x: x["pos"], reverse=True)

        # 執行替換
        translated_query = query
        found_terms = []

        for repl in replacements:
            before = translated_query[: repl["pos"]]
            after = translated_query[repl["pos"] + repl["length"] :]
            # 英文替換詞緊貼另一個英數字時補空白，否則「風景畫作品」會變成
            # landscapeartwork，全文檢索當成一個不存在的字
            replacement = repl["replacement"]
            if before and before[-1].isascii() and before[-1].isalnum():
                replacement = " " + replacement
            if after and after[0].isascii() and after[0].isalnum():
                replacement = replacement + " "
            translated_query = before + replacement + after
            found_terms.append(f"{repl['original']} -> {repl['replacement']}")

        # 反轉 found_terms 以保持原始順序
        found_terms.reverse()

        return translated_query, found_terms

    def translate_query(self, query: str, use_llm: bool = False) -> dict[str, any]:
        """翻譯查詢

        Args:
            query: 原始查詢
            use_llm: 是否使用 LLM 進行完整句子翻譯（暫未實現）

        Returns:
            翻譯結果字典，包含：
            - original_query: 原始查詢
            - translated_query: 翻譯後的查詢
            - detected_language: 檢測到的語言
            - found_terms: 識別的術語
            - translation_method: 翻譯方法
        """
        # 檢測語言
        detected_lang = self.detect_language(query)

        # 如果是英文，直接返回
        if detected_lang == "en":
            return {
                "original_query": query,
                "translated_query": query,
                "detected_language": "en",
                "found_terms": [],
                "translation_method": "none",
            }

        # 術語翻譯
        translated_query, found_terms = self.translate_terms(query)

        # 如果沒有找到任何術語，保持原查詢但提供提示
        if not found_terms:
            logger.warning(f"⚠️ 未找到可翻譯的術語: {query}")

        result = {
            "original_query": query,
            "translated_query": translated_query,
            "detected_language": detected_lang,
            "found_terms": found_terms,
            "translation_method": "dictionary",
        }

        logger.info(
            f"翻譯: '{query}' -> '{translated_query}' ({detected_lang}, {len(found_terms)} 個術語)"
        )

        return result

    def get_suggestions(self, partial_query: str, limit: int = 5) -> list[str]:
        """根據部分輸入提供建議

        Args:
            partial_query: 部分查詢
            limit: 最多返回建議數

        Returns:
            建議列表
        """
        partial_lower = partial_query.lower()
        suggestions = []

        for term in self.term_index.keys():
            if term.startswith(partial_lower) or partial_lower in term:
                english_term = self.term_index[term]
                suggestions.append(f"{term} ({english_term})")

                if len(suggestions) >= limit:
                    break

        return suggestions


# 測試代碼
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    translator = MultilingualQueryTranslator()

    # 測試案例
    test_queries = [
        "文藝復興時期的繪畫",
        "巴洛克雕塑",
        "印象派的特點",
        "達文西的作品",
        "Renaissance painting",
        "什麼是古典主義",
        "油畫和水彩的區別",
        "ルネサンス絵画",  # 日文
        "바로크 조각",  # 韓文
    ]

    print("=== 多語言查詢翻譯測試 ===\n")

    for query in test_queries:
        result = translator.translate_query(query)
        print(f"原查詢: {result['original_query']}")
        print(f"語言: {result['detected_language']}")
        print(f"翻譯: {result['translated_query']}")
        if result["found_terms"]:
            print(f"術語: {', '.join(result['found_terms'])}")
        print("-" * 60)
