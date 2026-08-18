#!/usr/bin/env python3
"""
文字檔處理器
支援TXT、MD等純文本格式
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class TextProcessor(BaseProcessor):
    """文字檔處理器"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = [".txt", ".md", ".markdown"]

    def can_process(self, file_path: Path) -> bool:
        """檢查是否可以處理文字檔"""
        return file_path.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        處理文字檔並提取藝術史資料

        支援格式:
        1. 結構化格式 (標題: 值)
        2. Markdown格式 (## 標題)
        3. 分隔符格式 (--- 分隔多個作品)
        4. 自由文本格式

        Args:
            file_path: 文字檔路徑

        Returns:
            List[Dict]: 提取的藝術品資料列表
        """
        logger.info(f"📄 處理文字檔: {file_path.name}")

        try:
            # 讀取文件
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                logger.warning(f"⚠️  文件為空: {file_path.name}")
                return []

            # 檢測格式並處理
            if self._is_markdown_format(content):
                artworks = self._process_markdown(content, file_path)
            elif self._is_structured_format(content):
                artworks = self._process_structured(content, file_path)
            elif self._has_separators(content):
                artworks = self._process_separated(content, file_path)
            else:
                artworks = self._process_freetext(content, file_path)

            logger.info(f"✅ 從文字檔提取了 {len(artworks)} 件藝術品資料")
            return artworks

        except Exception as e:
            logger.error(f"❌ 處理文字檔失敗: {e}")
            return []

    def _is_markdown_format(self, content: str) -> bool:
        """檢測是否為Markdown格式"""
        return bool(re.search(r"^#{1,6}\s+.+", content, re.MULTILINE))

    def _is_structured_format(self, content: str) -> bool:
        """檢測是否為結構化格式 (標題: 值)"""
        field_patterns = [r"標題[:：]", r"Title[:：]", r"藝術家[:：]", r"Artist[:：]"]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in field_patterns)

    def _has_separators(self, content: str) -> bool:
        """檢測是否有分隔符"""
        return bool(re.search(r"^[-=]{3,}$", content, re.MULTILINE))

    def _process_markdown(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """處理Markdown格式"""
        artworks = []

        # 按標題分割
        sections = re.split(r"\n(?=#{1,6}\s+)", content)

        for section in sections:
            section = section.strip()
            if not section or len(section) < 50:
                continue

            # 提取標題
            title_match = re.match(r"^#{1,6}\s+(.+)", section)
            title = title_match.group(1).strip() if title_match else "未命名作品"

            # 移除標題行
            body = re.sub(r"^#{1,6}\s+.+\n", "", section, count=1)

            artwork = {"title": title, "description": body.strip()}

            # 嘗試從內容提取更多資訊
            artwork.update(self._extract_from_content(body))

            artwork = self._add_metadata(artwork, file_path, "markdown")

            if self.validate_data(artwork):
                artworks.append(self.standardize_data(artwork))

        return artworks

    def _process_structured(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """處理結構化格式"""
        artworks = []

        # 分割成多個區塊
        sections = re.split(r"\n\s*\n", content)

        for section in sections:
            section = section.strip()
            if not section or len(section) < 30:
                continue

            artwork = self._extract_structured_fields(section)

            if artwork:
                artwork = self._add_metadata(artwork, file_path, "structured_text")

                if self.validate_data(artwork):
                    artworks.append(self.standardize_data(artwork))

        return artworks

    def _process_separated(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """處理分隔符格式"""
        artworks = []

        # 用分隔符分割
        sections = re.split(r"\n[-=]{3,}\n", content)

        for section in sections:
            section = section.strip()
            if not section or len(section) < 30:
                continue

            # 嘗試結構化提取
            if self._is_structured_format(section):
                artwork = self._extract_structured_fields(section)
            else:
                # 自由文本提取
                artwork = {
                    "title": self._extract_title(section),
                    "description": section[:1000] if len(section) > 1000 else section,
                }
                artwork.update(self._extract_from_content(section))

            if artwork:
                artwork = self._add_metadata(artwork, file_path, "separated_text")

                if self.validate_data(artwork):
                    artworks.append(self.standardize_data(artwork))

        return artworks

    def _process_freetext(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """處理自由文本格式"""
        # 將整個檔案當作一件作品的描述
        artwork = {
            "title": file_path.stem,  # 使用檔名作為標題
            "description": content[:2000] if len(content) > 2000 else content,
        }

        # 嘗試從內容提取資訊
        artwork.update(self._extract_from_content(content))

        artwork = self._add_metadata(artwork, file_path, "freetext")

        if self.validate_data(artwork):
            return [self.standardize_data(artwork)]
        return []

    def _extract_structured_fields(self, section: str) -> dict[str, Any]:
        """從結構化文本提取欄位"""
        artwork = {}

        field_patterns = {
            "title": [r"標題[:：]\s*(.+)", r"Title[:：]\s*(.+)", r"作品名稱[:：]\s*(.+)"],
            "artist": [r"藝術家[:：]\s*(.+)", r"Artist[:：]\s*(.+)", r"作者[:：]\s*(.+)"],
            "date": [r"日期[:：]\s*(.+)", r"Date[:：]\s*(.+)", r"年代[:：]\s*(.+)"],
            "period": [r"時期[:：]\s*(.+)", r"Period[:：]\s*(.+)"],
            "style": [r"風格[:：]\s*(.+)", r"Style[:：]\s*(.+)"],
            "medium": [r"媒材[:：]\s*(.+)", r"Medium[:：]\s*(.+)", r"材質[:：]\s*(.+)"],
            "dimensions": [r"尺寸[:：]\s*(.+)", r"Dimensions[:：]\s*(.+)"],
            "location": [r"地點[:：]\s*(.+)", r"Location[:：]\s*(.+)", r"館藏[:：]\s*(.+)"],
            "description": [r"描述[:：]\s*(.+)", r"Description[:：]\s*(.+)", r"說明[:：]\s*(.+)"],
        }

        for field, patterns in field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, section, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    # 清理多餘內容
                    value = re.split(r"\n[A-Za-z\u4e00-\u9fff]+[:：]", value)[0].strip()
                    if value:
                        artwork[field] = value
                        break

        return artwork

    def _extract_from_content(self, content: str) -> dict[str, Any]:
        """從內容提取藝術家、日期等資訊"""
        extracted = {}

        # 提取藝術家
        artist = self._extract_artist(content)
        if artist:
            extracted["artist"] = artist

        # 提取日期
        date = self._extract_date(content)
        if date:
            extracted["date"] = date

        return extracted

    def _extract_title(self, text: str) -> str:
        """提取標題 (第一行或最短的行)"""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return "未命名作品"

        # 返回第一個合適長度的行
        for line in lines:
            if 5 < len(line) < 100:
                return line

        return lines[0] if lines else "未命名作品"

    def _extract_artist(self, text: str) -> str:
        """提取藝術家名稱"""
        patterns = [
            r"(?:by|作者|藝術家|artist)[:：]?\s*([A-Za-z\s\.]+)",
            r"([A-Z][a-z]+\s+(?:van\s+|de\s+|da\s+)?[A-Z][a-z]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_date(self, text: str) -> str:
        """提取日期"""
        patterns = [
            r"(\d{4}[-–]\d{4})",
            r"(?:年代|date|year)[:：]?\s*(\d{4})",
            r"((?:14|15|16|17|18|19|20)\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _add_metadata(
        self, artwork: dict[str, Any], file_path: Path, format_type: str
    ) -> dict[str, Any]:
        """添加元資料"""
        artwork["source"] = "local_text_import"
        artwork["metadata"] = {
            "imported_at": datetime.now().isoformat(),
            "original_format": format_type,
            "file_path": str(file_path),
            "file_name": file_path.name,
        }

        # 偵測時期和關鍵詞
        full_text = " ".join(str(v) for v in artwork.values() if isinstance(v, str))
        if not artwork.get("period"):
            artwork["period"] = self.detect_period(full_text, artwork.get("date", ""))
        if not artwork.get("keywords"):
            artwork["keywords"] = self.extract_keywords(full_text)

        return artwork

    def create_template(self, output_path: Path, format_type: str = "structured") -> None:
        """
        建立文本範例模板

        Args:
            output_path: 輸出路徑
            format_type: 格式類型 ('structured', 'markdown', 'separated')
        """
        if format_type == "markdown":
            template = """# 蒙娜麗莎

作者: Leonardo da Vinci
年代: 1503-1519

《蒙娜麗莎》是文藝復興時期最著名的肖像畫之一，以其神秘的微笑而聞名於世。

---

# 夜巡

作者: Rembrandt van Rijn
年代: 1642

《夜巡》是荷蘭黃金時代最重要的群像畫作品。
"""
        elif format_type == "separated":
            template = """蒙娜麗莎
Leonardo da Vinci
1503-1519
文藝復興時期最著名的肖像畫

---

夜巡
Rembrandt van Rijn
1642
荷蘭黃金時代群像畫代表作
"""
        else:  # structured
            template = """標題: 蒙娜麗莎
藝術家: Leonardo da Vinci
日期: 1503-1519
時期: 文藝復興
風格: Italian Renaissance
媒材: Oil on poplar panel
尺寸: 77 cm × 53 cm
地點: Louvre Museum, Paris
描述: 《蒙娜麗莎》是文藝復興時期最著名的肖像畫之一，以其神秘的微笑而聞名於世。

標題: 夜巡
藝術家: Rembrandt van Rijn
日期: 1642
時期: 巴洛克
風格: Dutch Golden Age
媒材: Oil on canvas
尺寸: 363 cm × 437 cm
地點: Rijksmuseum, Amsterdam
描述: 《夜巡》是荷蘭黃金時代最重要的群像畫作品。
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template)

        logger.info(f"✅ 文本範例模板已建立: {output_path}")
