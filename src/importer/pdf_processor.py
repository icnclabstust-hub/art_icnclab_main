#!/usr/bin/env python3
"""
PDF文件處理器
支援從PDF提取藝術史資料
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

try:
    import PyPDF2

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    logger.warning("PyPDF2 未安裝，PDF處理功能受限")

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("pdfplumber 未安裝，PDF處理功能受限")


class PDFProcessor(BaseProcessor):
    """PDF文件處理器"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = [".pdf"]

    def can_process(self, file_path: Path) -> bool:
        """檢查是否可以處理PDF檔案"""
        return file_path.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        處理PDF檔案並提取藝術史資料

        Args:
            file_path: PDF檔案路徑

        Returns:
            List[Dict]: 提取的藝術品資料列表
        """
        logger.info(f"📄 處理PDF檔案: {file_path.name}")

        # 優先使用pdfplumber (更好的文本提取)
        if HAS_PDFPLUMBER:
            text = self._extract_text_pdfplumber(file_path)
        elif HAS_PYPDF2:
            text = self._extract_text_pypdf2(file_path)
        else:
            logger.error("❌ 無法處理PDF: 缺少 PyPDF2 或 pdfplumber")
            logger.info("請安裝: pip install PyPDF2 pdfplumber")
            return []

        if not text:
            logger.warning(f"⚠️  無法從PDF提取文本: {file_path.name}")
            return []

        # 解析文本提取資料
        artworks = self._parse_pdf_content(text, file_path)

        logger.info(f"✅ 從PDF提取了 {len(artworks)} 件藝術品資料")
        return artworks

    def _extract_text_pdfplumber(self, file_path: Path) -> str:
        """使用pdfplumber提取文本"""
        try:
            import pdfplumber

            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"pdfplumber提取失敗: {e}")
            return ""

    def _extract_text_pypdf2(self, file_path: Path) -> str:
        """使用PyPDF2提取文本"""
        try:
            import PyPDF2

            text = ""
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"PyPDF2提取失敗: {e}")
            return ""

    def _parse_pdf_content(self, text: str, file_path: Path) -> list[dict[str, Any]]:
        """
        解析PDF內容提取藝術品資料

        支援多種格式:
        1. 結構化格式 (標題: 值)
        2. 段落格式 (從段落提取資訊)
        3. 列表格式
        """
        artworks = []

        # 嘗試檢測格式
        if self._is_structured_format(text):
            artworks = self._parse_structured_format(text, file_path)
        else:
            artworks = self._parse_paragraph_format(text, file_path)

        return artworks

    def _is_structured_format(self, text: str) -> bool:
        """檢測是否為結構化格式 (如: 標題: 值)"""
        # 檢查是否有常見的欄位標籤
        field_patterns = [
            r"標題[:：]",
            r"Title[:：]",
            r"藝術家[:：]",
            r"Artist[:：]",
            r"作品名稱[:：]",
            r"Artwork[:：]",
        ]

        for pattern in field_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _parse_structured_format(self, text: str, file_path: Path) -> list[dict[str, Any]]:
        """解析結構化格式的PDF"""
        artworks = []

        # 分割成多個作品 (以空行或分隔符區分)
        sections = re.split(r"\n\s*\n|={3,}|-{3,}", text)

        for section in sections:
            section = section.strip()
            if not section or len(section) < 50:
                continue

            artwork = self._extract_fields_from_section(section)

            if artwork and self.validate_data(artwork):
                # 添加元資料
                artwork["source"] = "local_pdf_import"
                artwork["metadata"] = {
                    "imported_at": datetime.now().isoformat(),
                    "original_format": "pdf",
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                }

                # 偵測時期和關鍵詞
                full_text = " ".join(str(v) for v in artwork.values())
                if not artwork.get("period"):
                    artwork["period"] = self.detect_period(full_text, artwork.get("date", ""))
                if not artwork.get("keywords"):
                    artwork["keywords"] = self.extract_keywords(full_text)

                artworks.append(self.standardize_data(artwork))

        return artworks

    def _parse_paragraph_format(self, text: str, file_path: Path) -> list[dict[str, Any]]:
        """解析段落格式的PDF (無結構化標籤)"""
        # 將整個PDF當作一件藝術品描述
        # 嘗試從內容提取資訊

        artwork = {
            "title": self._extract_title_from_text(text),
            "artist": self._extract_artist_from_text(text),
            "date": self._extract_date_from_text(text),
            "description": text[:1000] if len(text) > 1000 else text,  # 取前1000字作為描述
            "source": "local_pdf_import",
            "metadata": {
                "imported_at": datetime.now().isoformat(),
                "original_format": "pdf",
                "file_path": str(file_path),
                "file_name": file_path.name,
                "note": "從非結構化PDF提取",
            },
        }

        # 偵測時期和關鍵詞
        artwork["period"] = self.detect_period(text, artwork.get("date", ""))
        artwork["keywords"] = self.extract_keywords(text)

        if self.validate_data(artwork):
            return [self.standardize_data(artwork)]
        return []

    def _extract_fields_from_section(self, section: str) -> dict[str, Any]:
        """從文本區塊提取欄位"""
        artwork = {}

        # 定義欄位模式
        field_patterns = {
            "title": [
                r"標題[:：]\s*(.+)",
                r"Title[:：]\s*(.+)",
                r"作品名稱[:：]\s*(.+)",
                r"Artwork[:：]\s*(.+)",
                r"Name[:：]\s*(.+)",
            ],
            "artist": [
                r"藝術家[:：]\s*(.+)",
                r"Artist[:：]\s*(.+)",
                r"創作者[:：]\s*(.+)",
                r"Creator[:：]\s*(.+)",
                r"作者[:：]\s*(.+)",
                r"Author[:：]\s*(.+)",
            ],
            "date": [
                r"日期[:：]\s*(.+)",
                r"Date[:：]\s*(.+)",
                r"年代[:：]\s*(.+)",
                r"Year[:：]\s*(.+)",
                r"創作時間[:：]\s*(.+)",
                r"時期[:：]\s*(.+)",
            ],
            "period": [
                r"時期[:：]\s*(.+)",
                r"Period[:：]\s*(.+)",
                r"年代[:：]\s*(.+)",
                r"Era[:：]\s*(.+)",
            ],
            "style": [
                r"風格[:：]\s*(.+)",
                r"Style[:：]\s*(.+)",
                r"流派[:：]\s*(.+)",
                r"School[:：]\s*(.+)",
            ],
            "medium": [
                r"媒材[:：]\s*(.+)",
                r"Medium[:：]\s*(.+)",
                r"材質[:：]\s*(.+)",
                r"Material[:：]\s*(.+)",
                r"技法[:：]\s*(.+)",
                r"Technique[:：]\s*(.+)",
            ],
            "dimensions": [
                r"尺寸[:：]\s*(.+)",
                r"Dimensions[:：]\s*(.+)",
                r"大小[:：]\s*(.+)",
                r"Size[:：]\s*(.+)",
            ],
            "location": [
                r"地點[:：]\s*(.+)",
                r"Location[:：]\s*(.+)",
                r"館藏[:：]\s*(.+)",
                r"Museum[:：]\s*(.+)",
                r"收藏[:：]\s*(.+)",
                r"Collection[:：]\s*(.+)",
            ],
            "description": [
                r"描述[:：]\s*(.+)",
                r"Description[:：]\s*(.+)",
                r"說明[:：]\s*(.+)",
                r"內容[:：]\s*(.+)",
                r"Content[:：]\s*(.+)",
            ],
        }

        # 提取各欄位
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, section, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    # 移除後續的標籤
                    value = re.split(r"\n[A-Za-z\u4e00-\u9fff]+[:：]", value)[0].strip()
                    if value:
                        artwork[field] = value
                        break

        return artwork

    def _extract_title_from_text(self, text: str) -> str:
        """從文本提取標題 (使用檔名或第一行)"""
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line) < 200:
                return line
        return "未命名作品"

    def _extract_artist_from_text(self, text: str) -> str:
        """從文本提取藝術家名稱"""
        # 常見藝術家名稱模式
        artist_patterns = [
            r"(?:by|作者|藝術家|artist)[:：]?\s*([A-Za-z\s\.]+)",
            r"([A-Z][a-z]+\s+(?:van\s+|de\s+|da\s+)?[A-Z][a-z]+)",  # 西方人名
        ]

        for pattern in artist_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_date_from_text(self, text: str) -> str:
        """從文本提取日期"""
        # 日期模式
        date_patterns = [
            r"(\d{4}[-–]\d{4})",  # 1503-1519
            r"(\d{4})",  # 1503
            r"((?:14|15|16|17|18|19|20)\d{2})",  # 世紀年份
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return ""
