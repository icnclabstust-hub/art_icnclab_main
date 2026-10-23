#!/usr/bin/env python3
"""
JSON文件處理器
支援標準JSON和多種JSON格式
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class JSONProcessor(BaseProcessor):
    """JSON文件處理器"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = [".json", ".jsonl"]

    def can_process(self, file_path: Path) -> bool:
        """檢查是否可以處理JSON檔案"""
        return file_path.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        處理JSON檔案並提取藝術史資料

        支援格式:
        1. 單一物件: {"title": "...", "artist": "..."}
        2. 物件陣列: [{"title": "..."}, {"title": "..."}]
        3. 包裝格式: {"artworks": [...], "data": [...]}
        4. JSONL格式: 每行一個JSON物件

        Args:
            file_path: JSON檔案路徑

        Returns:
            List[Dict]: 提取的藝術品資料列表
        """
        logger.info(f"📄 處理JSON檔案: {file_path.name}")

        try:
            if file_path.suffix.lower() == ".jsonl":
                artworks = self._process_jsonl(file_path)
            else:
                artworks = self._process_json(file_path)

            # 標準化和驗證
            standardized_artworks = []
            for artwork in artworks:
                # 添加元資料
                artwork["source"] = "local_json_import"
                artwork["metadata"] = {
                    "imported_at": datetime.now().isoformat(),
                    "original_format": "json",
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                }

                # 偵測時期和關鍵詞
                full_text = " ".join(
                    str(v) for v in artwork.values() if isinstance(v, (str, int, float))
                )
                if not artwork.get("period"):
                    artwork["period"] = self.detect_period(full_text, artwork.get("date", ""))
                if not artwork.get("keywords"):
                    artwork["keywords"] = self.extract_keywords(full_text)

                standardized = self.standardize_data(artwork)
                if self.validate_data(standardized):
                    standardized_artworks.append(standardized)

            logger.info(f"✅ 從JSON提取了 {len(standardized_artworks)} 件有效藝術品資料")
            return standardized_artworks

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 處理JSON失敗: {e}")
            return []

    def _process_json(self, file_path: Path) -> list[dict[str, Any]]:
        """處理標準JSON檔案"""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # 判斷JSON格式
        if isinstance(data, list):
            # 格式1: 直接是陣列 [{"title": "..."}, ...]
            return data

        elif isinstance(data, dict):
            # 檢查常見的包裝欄位
            wrapper_fields = ["artworks", "data", "items", "results", "objects", "works"]

            for field in wrapper_fields:
                if field in data and isinstance(data[field], list):
                    # 格式2: 包裝格式 {"artworks": [...]}
                    return data[field]

            # 格式3: 單一物件 {"title": "...", "artist": "..."}
            # 檢查是否包含藝術品欄位
            if any(key in data for key in ["title", "artist", "artwork", "name"]):
                return [data]

            # 嘗試尋找第一層的陣列值
            for value in data.values():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict):
                        return value

        logger.warning("⚠️  無法識別JSON格式，將整個物件視為單一作品")
        return [data] if isinstance(data, dict) else []

    def _process_jsonl(self, file_path: Path) -> list[dict[str, Any]]:
        """處理JSONL檔案 (每行一個JSON)"""
        artworks = []
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        artworks.append(obj)
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️  跳過無效JSON (行 {line_num}): {e}")
                    continue

        return artworks

    def create_template(self, output_path: Path, num_examples: int = 3) -> None:
        """
        建立JSON範例模板

        Args:
            output_path: 輸出路徑
            num_examples: 範例數量
        """
        template = {
            "artworks": [
                {
                    "title": "蒙娜麗莎",
                    "artist": "Leonardo da Vinci",
                    "date": "1503-1519",
                    "period": "文藝復興",
                    "style": "Italian Renaissance",
                    "medium": "Oil on poplar panel",
                    "dimensions": "77 cm × 53 cm",
                    "location": "Louvre Museum, Paris",
                    "description": "《蒙娜麗莎》是文藝復興時期最著名的肖像畫之一...",
                    "keywords": ["portrait", "renaissance", "masterpiece"],
                    "image_url": "https://example.com/mona-lisa.jpg",
                },
                {
                    "title": "夜巡",
                    "artist": "Rembrandt van Rijn",
                    "date": "1642",
                    "period": "巴洛克",
                    "style": "Dutch Golden Age",
                    "medium": "Oil on canvas",
                    "dimensions": "363 cm × 437 cm",
                    "location": "Rijksmuseum, Amsterdam",
                    "description": "《夜巡》是荷蘭黃金時代最著名的群像畫...",
                    "keywords": ["baroque", "group portrait", "dutch"],
                },
            ][:num_examples],
            "_format_guide": {
                "說明": "這是藝術史資料JSON格式範例",
                "必填欄位": ["title"],
                "選填欄位": [
                    "artist",
                    "date",
                    "period",
                    "style",
                    "medium",
                    "dimensions",
                    "location",
                    "description",
                    "keywords",
                    "image_url",
                ],
                "支援格式": [
                    "直接陣列: [{artwork1}, {artwork2}]",
                    '包裝格式: {"artworks": [...]}',
                    '單一物件: {title: "...", artist: "..."}',
                ],
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON範例模板已建立: {output_path}")
