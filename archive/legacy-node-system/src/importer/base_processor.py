#!/usr/bin/env python3
"""
基礎處理器類別
所有文件處理器的父類別
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """文件處理器基礎類別"""

    def __init__(self):
        self.supported_extensions = []

    @abstractmethod
    def can_process(self, file_path: Path) -> bool:
        """
        檢查是否可以處理該檔案

        Args:
            file_path: 檔案路徑

        Returns:
            bool: 是否支援處理
        """
        pass

    @abstractmethod
    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        處理檔案並提取藝術史資料

        Args:
            file_path: 檔案路徑

        Returns:
            List[Dict]: 標準化的藝術品資料列表
        """
        pass

    def validate_data(self, data: dict[str, Any]) -> bool:
        """
        驗證資料格式

        Args:
            data: 藝術品資料

        Returns:
            bool: 資料是否有效
        """
        # 必要欄位
        required_fields = ["title"]

        # 檢查必要欄位
        for field in required_fields:
            if field not in data or not data[field]:
                logger.warning(f"缺少必要欄位: {field}")
                return False

        return True

    def standardize_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        標準化資料格式

        Args:
            raw_data: 原始資料

        Returns:
            Dict: 標準化後的資料
        """
        standardized = {
            "title": raw_data.get("title", ""),
            "artist": raw_data.get("artist", raw_data.get("creator", "")),
            "date": raw_data.get("date", raw_data.get("year", "")),
            "period": raw_data.get("period", raw_data.get("era", "")),
            "style": raw_data.get("style", ""),
            "medium": raw_data.get("medium", raw_data.get("material", "")),
            "dimensions": raw_data.get("dimensions", raw_data.get("size", "")),
            "location": raw_data.get("location", raw_data.get("museum", "")),
            "description": raw_data.get("description", raw_data.get("content", "")),
            "keywords": raw_data.get("keywords", raw_data.get("tags", [])),
            "image_url": raw_data.get("image_url", raw_data.get("image", "")),
            "source": raw_data.get("source", "local_import"),
            "metadata": {
                "imported_at": raw_data.get("imported_at", ""),
                "original_format": raw_data.get("original_format", ""),
                "file_path": raw_data.get("file_path", ""),
            },
        }

        # 移除空值
        return {k: v for k, v in standardized.items() if v}

    def extract_keywords(self, text: str) -> list[str]:
        """
        從文本提取關鍵詞

        Args:
            text: 文本內容

        Returns:
            List[str]: 關鍵詞列表
        """
        # 藝術史相關關鍵詞
        art_keywords = [
            # 時期
            "文藝復興",
            "Renaissance",
            "巴洛克",
            "Baroque",
            "洛可可",
            "Rococo",
            "新古典",
            "Neoclassical",
            "浪漫主義",
            "Romantic",
            "印象派",
            "Impressionism",
            "現代主義",
            "Modernism",
            "中世紀",
            "Medieval",
            # 風格
            "寫實主義",
            "Realism",
            "立體派",
            "Cubism",
            "抽象",
            "Abstract",
            "超現實",
            "Surrealism",
            "表現主義",
            "Expressionism",
            "野獸派",
            "Fauvism",
            # 媒材
            "油畫",
            "Oil painting",
            "水彩",
            "Watercolor",
            "雕塑",
            "Sculpture",
            "版畫",
            "Print",
            "素描",
            "Drawing",
            "壁畫",
            "Fresco",
            # 主題
            "肖像",
            "Portrait",
            "風景",
            "Landscape",
            "靜物",
            "Still life",
            "宗教",
            "Religious",
            "神話",
            "Mythology",
            "歷史",
            "Historical",
        ]

        found_keywords = []
        text_lower = text.lower()

        for keyword in art_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)

        return list(set(found_keywords))

    def detect_period(self, text: str, date: str = "") -> str:
        """
        偵測藝術時期

        Args:
            text: 文本內容
            date: 日期資訊

        Returns:
            str: 藝術時期
        """
        text_lower = text.lower()

        # 時期關鍵詞對應
        period_keywords = {
            "中世紀": ["medieval", "byzantine", "romanesque", "gothic", "中世紀", "拜占庭"],
            "文藝復興": ["renaissance", "文藝復興", "early renaissance", "high renaissance"],
            "巴洛克": ["baroque", "巴洛克", "caravaggism"],
            "洛可可": ["rococo", "洛可可"],
            "新古典主義": ["neoclassical", "neoclassicism", "新古典"],
            "浪漫主義": ["romantic", "romanticism", "浪漫主義"],
            "印象派": ["impressionism", "impressionist", "印象派"],
            "後印象派": ["post-impressionism", "後印象派"],
            "現代主義": ["modernism", "modern art", "現代主義"],
            "當代藝術": ["contemporary", "當代"],
        }

        for period, keywords in period_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return period

        # 根據年代判斷
        if date:
            try:
                year = int("".join(filter(str.isdigit, date))[:4])
                if 500 <= year < 1400:
                    return "中世紀"
                elif 1400 <= year < 1600:
                    return "文藝復興"
                elif 1600 <= year < 1750:
                    return "巴洛克"
                elif 1750 <= year < 1850:
                    return "新古典主義"
                elif 1850 <= year < 1900:
                    return "印象派"
                elif 1900 <= year < 1950:
                    return "現代主義"
                elif year >= 1950:
                    return "當代藝術"
            except (ValueError, IndexError):
                pass

        return ""
