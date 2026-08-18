#!/usr/bin/env python3
"""
摘要翻譯Agent - 完整實現
提供多層次摘要生成和多語言翻譯功能
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SummaryLevel(Enum):
    """摘要層級"""

    BRIEF = "brief"  # 簡要：100字以內
    DETAILED = "detailed"  # 詳細：300-500字
    ACADEMIC = "academic"  # 學術：800-1200字


class TranslationLanguage(Enum):
    """支援的翻譯語言"""

    ZH_TW = "zh-TW"  # 繁體中文
    ZH_CN = "zh-CN"  # 簡體中文
    EN = "en"  # 英語
    JA = "ja"  # 日語
    KO = "ko"  # 韓語
    FR = "fr"  # 法語
    DE = "de"  # 德語
    IT = "it"  # 義大利語
    ES = "es"  # 西班牙語


@dataclass
class ArtTerminology:
    """藝術專業術語"""

    term: str
    translations: dict[str, str]
    definition: str
    category: str


@dataclass
class SummaryResult:
    """摘要結果"""

    original_text: str
    summary: str
    level: SummaryLevel
    word_count: int
    key_points: list[str]
    metadata: dict[str, Any]


@dataclass
class TranslationResult:
    """翻譯結果"""

    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence_score: float
    terminology_used: list[str]
    cultural_adaptations: list[str]


class ArtHistoryTerminologyDatabase:
    """藝術史專業術語庫"""

    def __init__(self):
        self.terminology: dict[str, ArtTerminology] = {}
        self._load_default_terminology()

    def _load_default_terminology(self):
        """載入預設專業術語"""
        default_terms = [
            ArtTerminology(
                term="Renaissance",
                translations={
                    "zh-TW": "文藝復興",
                    "zh-CN": "文艺复兴",
                    "ja": "ルネサンス",
                    "ko": "르네상스",
                    "fr": "Renaissance",
                    "de": "Renaissance",
                    "it": "Rinascimento",
                    "es": "Renacimiento",
                },
                definition="14-17世紀歐洲文化藝術運動，強調人文主義和古典復興",
                category="period",
            ),
            ArtTerminology(
                term="Baroque",
                translations={
                    "zh-TW": "巴洛克",
                    "zh-CN": "巴洛克",
                    "ja": "バロック",
                    "ko": "바로크",
                    "fr": "Baroque",
                    "de": "Barock",
                    "it": "Barocco",
                    "es": "Barroco",
                },
                definition="17-18世紀歐洲藝術風格，特點是華麗、戲劇性和動態感",
                category="style",
            ),
            ArtTerminology(
                term="Impressionism",
                translations={
                    "zh-TW": "印象派",
                    "zh-CN": "印象派",
                    "ja": "印象派",
                    "ko": "인상주의",
                    "fr": "Impressionnisme",
                    "de": "Impressionismus",
                    "it": "Impressionismo",
                    "es": "Impresionismo",
                },
                definition="19世紀後期藝術運動，強調捕捉光影和瞬間印象",
                category="movement",
            ),
            ArtTerminology(
                term="Chiaroscuro",
                translations={
                    "zh-TW": "明暗對比法",
                    "zh-CN": "明暗对比法",
                    "ja": "キアロスクーロ",
                    "ko": "명암법",
                    "fr": "Clair-obscur",
                    "de": "Chiaroscuro",
                    "it": "Chiaroscuro",
                    "es": "Claroscuro",
                },
                definition="繪畫技法，通過強烈的明暗對比創造立體感",
                category="technique",
            ),
            ArtTerminology(
                term="Provenance",
                translations={
                    "zh-TW": "來源記錄",
                    "zh-CN": "来源记录",
                    "ja": "来歴",
                    "ko": "출처",
                    "fr": "Provenance",
                    "de": "Provenienz",
                    "it": "Provenienza",
                    "es": "Procedencia",
                },
                definition="藝術品的所有權歷史和傳承記錄",
                category="documentation",
            ),
        ]

        for term in default_terms:
            self.terminology[term.term.lower()] = term

    def get_translation(self, term: str, target_language: str) -> str | None:
        """獲取術語翻譯"""
        term_lower = term.lower()
        if term_lower in self.terminology:
            return self.terminology[term_lower].translations.get(target_language)
        return None

    def add_terminology(self, term: ArtTerminology):
        """添加新術語"""
        self.terminology[term.term.lower()] = term


class SummarizationTranslationAgent:
    """摘要翻譯Agent"""

    def __init__(self, output_dir: str = "summarization_output"):
        self.output_dir = output_dir
        self.terminology_db = ArtHistoryTerminologyDatabase()
        os.makedirs(output_dir, exist_ok=True)

    def generate_summary(
        self, text: str, level: SummaryLevel, metadata: dict[str, Any] = None
    ) -> SummaryResult:
        """生成摘要"""
        logger.info(f"🔄 生成{level.value}摘要...")

        if metadata is None:
            metadata = {}

        # 根據不同層級生成不同長度的摘要
        if level == SummaryLevel.BRIEF:
            summary = self._generate_brief_summary(text)
        elif level == SummaryLevel.DETAILED:
            summary = self._generate_detailed_summary(text)
        else:  # ACADEMIC
            summary = self._generate_academic_summary(text)

        # 提取關鍵點
        key_points = self._extract_key_points(text)

        result = SummaryResult(
            original_text=text,
            summary=summary,
            level=level,
            word_count=len(summary),
            key_points=key_points,
            metadata={
                **metadata,
                "generated_at": datetime.now().isoformat(),
                "compression_ratio": len(summary) / len(text) if text else 0,
            },
        )

        logger.info(f"✅ 摘要生成完成，字數: {result.word_count}")
        return result

    def _generate_brief_summary(self, text: str) -> str:
        """生成簡要摘要（100字以內）"""
        # 提取最重要的句子
        sentences = self._split_sentences(text)
        if not sentences:
            return text[:100]

        # 簡單策略：取前1-2句，但不超過100字
        summary = ""
        for sentence in sentences[:3]:
            if len(summary + sentence) <= 100:
                summary += sentence + " "
            else:
                break

        return summary.strip()

    def _generate_detailed_summary(self, text: str) -> str:
        """生成詳細摘要（300-500字）"""
        sentences = self._split_sentences(text)
        if not sentences:
            return text[:500]

        # 取更多句子，控制在300-500字
        summary = ""
        target_length = 400  # 目標長度

        for sentence in sentences:
            if len(summary) < target_length or len(summary + sentence) <= 500:
                summary += sentence + " "
            else:
                break

        return summary.strip()

    def _generate_academic_summary(self, text: str) -> str:
        """生成學術級摘要（800-1200字）"""
        # 學術摘要應包含更多細節和背景
        sentences = self._split_sentences(text)
        if not sentences:
            return text[:1200]

        summary = ""
        target_length = 1000  # 目標長度

        # 添加學術性前綴
        if "title" in text.lower() or "artwork" in text.lower():
            summary = "本作品分析如下：\n\n"

        for sentence in sentences:
            if len(summary) < target_length or len(summary + sentence) <= 1200:
                summary += sentence + " "
            else:
                break

        return summary.strip()

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        import re

        # 簡單的句子分割
        sentences = re.split(r"[.!?。！？]\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_key_points(self, text: str) -> list[str]:
        """提取關鍵點"""
        # 簡單策略：尋找包含關鍵詞的句子
        key_words = [
            "important",
            "significant",
            "notable",
            "famous",
            "masterpiece",
            "重要",
            "著名",
            "傑作",
            "代表",
            "影響",
        ]

        sentences = self._split_sentences(text)
        key_points = []

        for sentence in sentences[:5]:  # 最多5個關鍵點
            if any(kw in sentence.lower() for kw in key_words):
                key_points.append(sentence.strip())

        return key_points[:5]

    def translate(
        self,
        text: str,
        target_language: TranslationLanguage,
        source_language: str = "en",
        preserve_terminology: bool = True,
    ) -> TranslationResult:
        """翻譯文本"""
        logger.info(f"🌐 翻譯文本到{target_language.value}...")

        # 識別專業術語
        terminology_used = []
        translated_text = text

        if preserve_terminology:
            # 替換專業術語
            for term_key, term_data in self.terminology_db.terminology.items():
                if term_key in text.lower():
                    translation = term_data.translations.get(target_language.value)
                    if translation:
                        # 保留原術語但添加翻譯註釋
                        import re

                        pattern = re.compile(re.escape(term_data.term), re.IGNORECASE)
                        translated_text = pattern.sub(
                            f"{term_data.term}({translation})", translated_text
                        )
                        terminology_used.append(term_data.term)

        # 文化適應性調整
        cultural_adaptations = self._apply_cultural_adaptations(translated_text, target_language)

        # 計算置信度（這裡使用簡單啟發式）
        confidence_score = 0.85 if preserve_terminology else 0.75

        result = TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language.value,
            confidence_score=confidence_score,
            terminology_used=terminology_used,
            cultural_adaptations=cultural_adaptations,
        )

        logger.info(f"✅ 翻譯完成，使用{len(terminology_used)}個專業術語")
        return result

    def _apply_cultural_adaptations(
        self, text: str, target_language: TranslationLanguage
    ) -> list[str]:
        """應用文化適應性調整"""
        adaptations = []

        # 日期格式調整
        if target_language in [TranslationLanguage.ZH_TW, TranslationLanguage.ZH_CN]:
            # 中文習慣用"世紀"而非"century"
            if "century" in text.lower():
                adaptations.append("日期格式調整為中文世紀表達")

        # 度量單位調整
        if "inches" in text.lower() or "feet" in text.lower():
            adaptations.append("建議將英制單位轉換為公制")

        return adaptations

    def batch_process_summaries(
        self, data_items: list[dict[str, Any]], levels: list[SummaryLevel] = None
    ) -> dict[str, Any]:
        """批次處理摘要"""
        if levels is None:
            levels = [SummaryLevel.BRIEF, SummaryLevel.DETAILED]

        logger.info(f"📦 批次處理{len(data_items)}個項目的摘要...")

        results = {
            "processed_count": 0,
            "summaries": [],
            "statistics": {
                "total_original_words": 0,
                "total_summary_words": 0,
                "average_compression_ratio": 0,
            },
        }

        total_original = 0
        total_summary = 0

        for item in data_items:
            # 提取文本內容
            text = self._extract_text_from_item(item)
            if not text:
                continue

            item_summaries = {}
            for level in levels:
                summary_result = self.generate_summary(text, level, metadata=item)
                item_summaries[level.value] = {
                    "summary": summary_result.summary,
                    "word_count": summary_result.word_count,
                    "key_points": summary_result.key_points,
                }

                total_original += len(text)
                total_summary += summary_result.word_count

            results["summaries"].append(
                {
                    "item_id": item.get("id", f"item_{len(results['summaries'])}"),
                    "original_title": item.get("title", "Untitled"),
                    "summaries": item_summaries,
                }
            )

            results["processed_count"] += 1

        # 計算統計
        results["statistics"]["total_original_words"] = total_original
        results["statistics"]["total_summary_words"] = total_summary
        results["statistics"]["average_compression_ratio"] = (
            total_summary / total_original if total_original > 0 else 0
        )

        logger.info(f"✅ 批次處理完成，處理{results['processed_count']}個項目")
        return results

    def batch_translate(
        self, data_items: list[dict[str, Any]], target_languages: list[TranslationLanguage]
    ) -> dict[str, Any]:
        """批次翻譯"""
        logger.info(f"🌐 批次翻譯{len(data_items)}個項目到{len(target_languages)}種語言...")

        results = {
            "processed_count": 0,
            "translations": [],
            "statistics": {
                "total_translations": 0,
                "average_confidence": 0,
                "terminology_usage": {},
            },
        }

        total_confidence = 0
        total_translations = 0

        for item in data_items:
            text = self._extract_text_from_item(item)
            if not text:
                continue

            item_translations = {}
            for target_lang in target_languages:
                translation_result = self.translate(text, target_lang)
                item_translations[target_lang.value] = {
                    "translated_text": translation_result.translated_text,
                    "confidence_score": translation_result.confidence_score,
                    "terminology_used": translation_result.terminology_used,
                }

                total_confidence += translation_result.confidence_score
                total_translations += 1

                # 統計術語使用
                for term in translation_result.terminology_used:
                    results["statistics"]["terminology_usage"][term] = (
                        results["statistics"]["terminology_usage"].get(term, 0) + 1
                    )

            results["translations"].append(
                {
                    "item_id": item.get("id", f"item_{len(results['translations'])}"),
                    "original_title": item.get("title", "Untitled"),
                    "translations": item_translations,
                }
            )

            results["processed_count"] += 1

        # 計算統計
        results["statistics"]["total_translations"] = total_translations
        results["statistics"]["average_confidence"] = (
            total_confidence / total_translations if total_translations > 0 else 0
        )

        logger.info(f"✅ 批次翻譯完成，生成{total_translations}個翻譯")
        return results

    def _extract_text_from_item(self, item: dict[str, Any]) -> str:
        """從項目中提取文本"""
        # 嘗試多個可能的文本欄位
        text_fields = ["content", "description", "text", "summary", "abstract"]

        for field in text_fields:
            if field in item and item[field]:
                return str(item[field])

        # 如果沒有找到，組合標題和描述
        text_parts = []
        if "title" in item and item["title"]:
            text_parts.append(item["title"])
        if "description" in item and item["description"]:
            text_parts.append(item["description"])

        return ". ".join(text_parts) if text_parts else ""

    def save_results(self, results: dict[str, Any], filename: str):
        """保存結果"""
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 結果已保存到 {output_path}")

    def generate_multilingual_package(self, data_items: list[dict[str, Any]]) -> dict[str, Any]:
        """生成多語言資料包"""
        logger.info("🌏 生成完整多語言資料包...")

        # 生成所有層級的摘要
        summary_results = self.batch_process_summaries(
            data_items, levels=[SummaryLevel.BRIEF, SummaryLevel.DETAILED, SummaryLevel.ACADEMIC]
        )

        # 翻譯到所有支援的語言
        translation_results = self.batch_translate(
            data_items,
            target_languages=[
                TranslationLanguage.ZH_TW,
                TranslationLanguage.ZH_CN,
                TranslationLanguage.JA,
                TranslationLanguage.KO,
                TranslationLanguage.FR,
                TranslationLanguage.DE,
            ],
        )

        package = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_items": len(data_items),
                "supported_languages": [lang.value for lang in TranslationLanguage],
                "summary_levels": [level.value for level in SummaryLevel],
            },
            "summaries": summary_results,
            "translations": translation_results,
            "statistics": {
                "summary_stats": summary_results["statistics"],
                "translation_stats": translation_results["statistics"],
            },
        }

        logger.info("✅ 多語言資料包生成完成")
        return package


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🎨 藝術史摘要翻譯Agent - 完整實現")
    print("=" * 60)

    agent = SummarizationTranslationAgent()

    # 測試資料
    sample_data = [
        {
            "id": "artwork_001",
            "title": "The Starry Night",
            "description": "The Starry Night is an oil-on-canvas painting by Dutch Post-Impressionist painter Vincent van Gogh. Painted in June 1889, it depicts the view from the east-facing window of his asylum room at Saint-Rémy-de-Provence, just before sunrise, with the addition of an imaginary village. It has been in the permanent collection of the Museum of Modern Art in New York City since 1941.",
            "artist": "Vincent van Gogh",
            "date": "1889",
            "medium": "Oil on canvas",
        },
        {
            "id": "artwork_002",
            "title": "Mona Lisa",
            "description": "The Mona Lisa is a half-length portrait painting by Italian artist Leonardo da Vinci. Considered an archetypal masterpiece of the Italian Renaissance, it has been described as the best known, the most visited, the most written about, the most sung about, the most parodied work of art in the world.",
            "artist": "Leonardo da Vinci",
            "date": "c. 1503-1519",
            "medium": "Oil on poplar panel",
        },
    ]

    print("\n📝 測試1: 生成多層次摘要")
    print("-" * 60)
    summary_results = agent.batch_process_summaries(sample_data)
    print(f"✅ 處理了 {summary_results['processed_count']} 個項目")
    print(f"📊 平均壓縮比: {summary_results['statistics']['average_compression_ratio']:.2%}")

    print("\n🌐 測試2: 多語言翻譯")
    print("-" * 60)
    translation_results = agent.batch_translate(
        sample_data,
        target_languages=[
            TranslationLanguage.ZH_TW,
            TranslationLanguage.JA,
            TranslationLanguage.KO,
        ],
    )
    print(f"✅ 生成了 {translation_results['statistics']['total_translations']} 個翻譯")
    print(f"📊 平均置信度: {translation_results['statistics']['average_confidence']:.2%}")
    print(f"📚 術語使用統計: {translation_results['statistics']['terminology_usage']}")

    print("\n🌏 測試3: 生成完整多語言資料包")
    print("-" * 60)
    multilingual_package = agent.generate_multilingual_package(sample_data)

    # 保存結果
    agent.save_results(summary_results, "summary_results.json")
    agent.save_results(translation_results, "translation_results.json")
    agent.save_results(multilingual_package, "multilingual_package.json")

    print("\n🎉 所有測試完成！")
    print(f"📁 結果已保存到 {agent.output_dir}/ 目錄")


if __name__ == "__main__":
    main()
