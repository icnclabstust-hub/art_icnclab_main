#!/usr/bin/env python3
"""
智能關鍵詞提取器
實現優化的關鍵詞提取策略，包括：
1. 改進的停用詞過濾
2. 術語字典優先匹配
3. 短語識別
4. 查詢日誌記錄
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SmartKeywordExtractor:
    """智能關鍵詞提取器"""

    def __init__(self, translator=None, log_queries: bool = True):
        """
        初始化關鍵詞提取器

        Args:
            translator: 多語言翻譯器實例（用於獲取術語字典）
            log_queries: 是否記錄查詢日誌
        """
        self.translator = translator
        self.log_queries = log_queries
        self.query_log_path = Path("query_logs")

        if self.log_queries:
            self.query_log_path.mkdir(exist_ok=True)

        # 擴展的停用詞列表
        self.stop_words = {
            # 基本停用詞
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "can",
            "could",
            "should",
            "may",
            "might",
            "must",
            # 姓名連接詞（重要！）
            "da",
            "de",
            "di",
            "del",
            "della",
            "van",
            "von",
            "le",
            "la",
            "el",
            # 其他常見詞
            "this",
            "that",
            "these",
            "those",
            "which",
            "what",
            "who",
            "where",
            "when",
            "why",
            "how",
            "all",
            "any",
            "some",
            "much",
            "many",
        }

        # 獲取已知藝術術語
        self.known_art_terms = self._load_art_terms()

        logger.info("✅ 智能關鍵詞提取器初始化完成")
        logger.info(f"   - 停用詞數量: {len(self.stop_words)}")
        logger.info(f"   - 已知藝術術語: {len(self.known_art_terms)}")
        logger.info(f"   - 查詢日誌: {'開啟' if self.log_queries else '關閉'}")

    def _load_art_terms(self) -> set[str]:
        """從翻譯器載入已知藝術術語"""
        terms = set()

        if self.translator and hasattr(self.translator, "term_index"):
            # 獲取所有英文術語（翻譯字典的值）
            for term in self.translator.term_index.values():
                terms.add(term.lower())
                # 也添加多詞術語的每個部分
                for word in term.split():
                    if len(word) >= 3:
                        terms.add(word.lower())

        return terms

    def extract_keywords(
        self, query: str, max_keywords: int = 5, min_word_length: int = 2
    ) -> tuple[list[str], dict[str, any]]:
        """
        從查詢中提取關鍵詞

        Args:
            query: 查詢字符串（可能是混合語言）
            max_keywords: 最大關鍵詞數量
            min_word_length: 最小單詞長度

        Returns:
            (關鍵詞列表, 提取信息字典)
        """
        extraction_info = {
            "original_query": query,
            "method": "smart_extraction",
            "timestamp": datetime.now().isoformat(),
        }

        # 步驟 1: 識別短語（如 "Leonardo da Vinci"）
        phrases = self._extract_phrases(query)
        extraction_info["phrases"] = phrases

        if phrases:
            logger.info(f"🔤 識別到短語: {phrases}")

        # 步驟 2: 提取英文單詞
        # 不用 \b：Python regex 把中文字元也算 \w，英文詞緊貼中文（無空格，
        # 如「Michelangelo天頂畫」）時中間沒有 word boundary，\b 會抓不到；
        # [a-zA-Z]{2,} 用連續字母的最大匹配即可正確切出來
        english_words = re.findall(r"[a-zA-Z]{2,}", query)
        extraction_info["english_words"] = english_words

        # 步驟 3: 分類單詞（術語 vs 普通詞）
        art_term_words = []
        regular_words = []

        for word in english_words:
            word_lower = word.lower()

            # 跳過停用詞
            if word_lower in self.stop_words:
                continue

            # 檢查是否為已知藝術術語
            if word_lower in self.known_art_terms:
                art_term_words.append(word)
            elif len(word) >= min_word_length:
                regular_words.append(word)

        extraction_info["art_term_words"] = art_term_words
        extraction_info["regular_words"] = regular_words

        # 步驟 4: 優先級組合關鍵詞
        keywords = []

        # 優先級 1: 完整短語
        keywords.extend(phrases[:2])  # 最多2個短語

        # 優先級 2: 藝術術語
        remaining_slots = max_keywords - len(keywords)
        keywords.extend(art_term_words[:remaining_slots])

        # 優先級 3: 普通詞（較長的優先）
        remaining_slots = max_keywords - len(keywords)
        if remaining_slots > 0:
            regular_words_sorted = sorted(regular_words, key=len, reverse=True)
            keywords.extend(regular_words_sorted[:remaining_slots])

        # 去重並限制數量
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        final_keywords = unique_keywords[:max_keywords]
        extraction_info["final_keywords"] = final_keywords
        extraction_info["keyword_count"] = len(final_keywords)

        # 記錄日誌
        if self.log_queries:
            self._log_extraction(extraction_info)

        logger.info(
            f"🔍 關鍵詞提取: {len(final_keywords)} 個 "
            f"(短語: {len(phrases)}, 術語: {len(art_term_words)}, 普通詞: {len(regular_words)})"
        )
        logger.info(f"   提取結果: {final_keywords}")

        return final_keywords, extraction_info

    def _extract_phrases(self, query: str) -> list[str]:
        """
        提取短語（如人名、作品名）

        優先識別：
        1. 2-4個連續英文單詞的組合
        2. 在已知術語字典中的短語
        """
        phrases = []
        # 同上，不用 \b，避免中文字緊貼英文詞時漏抓
        english_words = re.findall(r"[a-zA-Z]+", query)

        # 檢查 2-4 個詞的組合
        for n in range(4, 1, -1):  # 從長到短
            for i in range(len(english_words) - n + 1):
                phrase = " ".join(english_words[i : i + n])
                phrase_lower = phrase.lower()

                # 檢查是否為已知術語
                if self.translator and hasattr(self.translator, "term_index"):
                    if (
                        phrase_lower in self.translator.term_index
                        or phrase in self.translator.term_index.values()
                    ):
                        phrases.append(phrase)
                        # 從單詞列表中移除這些詞，避免重複
                        for j in range(i, i + n):
                            if j < len(english_words):
                                english_words[j] = ""  # 標記為已使用

        return phrases

    def _log_extraction(self, info: dict[str, any]):
        """記錄提取信息到日誌文件"""
        try:
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = self.query_log_path / f"extractions_{date_str}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(info, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"⚠️ 無法記錄提取日誌: {e}")

    def get_extraction_stats(self, date: str | None = None) -> dict[str, any]:
        """
        獲取提取統計信息

        Args:
            date: 日期字符串（YYYYMMDD），默認為今天
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        log_file = self.query_log_path / f"extractions_{date}.jsonl"

        if not log_file.exists():
            return {"error": "No log file found", "date": date}

        stats = {
            "date": date,
            "total_queries": 0,
            "total_keywords": 0,
            "total_phrases": 0,
            "total_art_terms": 0,
            "avg_keywords_per_query": 0,
            "most_common_keywords": {},
            "most_common_phrases": {},
        }

        keyword_counts = {}
        phrase_counts = {}

        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    stats["total_queries"] += 1
                    stats["total_keywords"] += data.get("keyword_count", 0)
                    stats["total_phrases"] += len(data.get("phrases", []))
                    stats["total_art_terms"] += len(data.get("art_term_words", []))

                    # 統計關鍵詞頻率
                    for kw in data.get("final_keywords", []):
                        keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

                    # 統計短語頻率
                    for phrase in data.get("phrases", []):
                        phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

            if stats["total_queries"] > 0:
                stats["avg_keywords_per_query"] = stats["total_keywords"] / stats["total_queries"]

            # 最常見的關鍵詞（前10）
            stats["most_common_keywords"] = dict(
                sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            )

            # 最常見的短語（前10）
            stats["most_common_phrases"] = dict(
                sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            )

        except Exception as e:
            logger.error(f"❌ 無法讀取統計信息: {e}")
            stats["error"] = str(e)

        return stats


# 測試代碼
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 測試不同的查詢
    test_queries = [
        "Leonardo da Vinci的masterpiece品有哪些",
        "文藝復興時期的Renaissance著名藝術家",
        "Baroque painting characteristics",
        "Rembrandt self-portraits",
        "比較Leonardo da Vinci和Michelangelo的作品風格",
    ]

    extractor = SmartKeywordExtractor()

    print("=" * 80)
    print("智能關鍵詞提取測試")
    print("=" * 80)

    for query in test_queries:
        print(f"\n查詢: {query}")
        keywords, info = extractor.extract_keywords(query)
        print(f"關鍵詞: {keywords}")
        print(f"短語: {info.get('phrases', [])}")
        print(f"藝術術語: {info.get('art_term_words', [])}")
        print("-" * 80)
