#!/usr/bin/env python3
"""
國立臺灣歷史博物館 (NMTH) 資料爬蟲
透過國家文化記憶庫 OpenAPI (https://tcmb.culture.tw/zh-tw/OpenApi) 取得文物資料

申請 API Key: https://tcmb.culture.tw/zh-tw/OpenApi
  需附上申請單位名稱、申請原因、固定 IP，審核通過後以電子郵件通知 Key。

注意：此開放平台彙整多個文化機構的資料，公開文件並未列出可依「來源機構」
過濾的參數，因此本爬蟲以關鍵字搜尋 + 用戶端過濾候選欄位雙重方式篩選出
NMTH 的紀錄。首次執行建議先用 --dump-sample 存一份原始回應，確認實際欄位
名稱後再視需要調整 INSTITUTION_FIELD_CANDIDATES / INSTITUTION_ALIASES。
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

# NMTH 在不同資料集裡可能出現的名稱寫法
INSTITUTION_ALIASES = ["國立臺灣歷史博物館", "臺灣歷史博物館", "臺史博", "NMTH"]

# 回應項目中可能記錄來源機構的欄位名稱（依實際樣本再調整）
INSTITUTION_FIELD_CANDIDATES = [
    "contributor",
    "publisher",
    "source",
    "unit",
    "organization",
    "provider",
    "dataSource",
    "museum",
    "creator",
]


@dataclass
class NMTHCrawlerConfig:
    """NMTH / TCMB 爬蟲配置"""

    api_key: str
    base_url: str = "https://tcmbdata.culture.tw/opendata/openapi"
    search_keyword: str = "臺灣歷史博物館"
    page_size: int = 50
    max_pages: int | None = 20
    delay_seconds: float = 0.5
    output_dir: str = "data/raw"
    filter_by_institution: bool = True
    institution_aliases: list[str] = field(default_factory=lambda: list(INSTITUTION_ALIASES))


class NMTHTCMBCrawler:
    """國家文化記憶庫 OpenAPI 爬蟲 (用於取得 NMTH 資料)"""

    def __init__(self, config: NMTHCrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": config.api_key,
                "Accept": "application/json",
                "User-Agent": "Art History Database Research Tool v1.0",
            }
        )
        self.api_calls_count = 0
        os.makedirs(config.output_dir, exist_ok=True)

    def _make_request(self, endpoint: str, params: dict) -> dict | None:
        url = f"{self.config.base_url}/{endpoint}"
        try:
            time.sleep(self.config.delay_seconds)
            response = self.session.get(url, params=params, timeout=30)
            self.api_calls_count += 1

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("⚠️ API 速率限制，等待 60 秒")
                time.sleep(60)
                return self._make_request(endpoint, params)
            else:
                logger.error(f"❌ API 請求失敗: {response.status_code} - {response.text[:300]}")
                return None
        except Exception as e:
            logger.error(f"❌ 請求異常: {e}")
            return None

    def _extract_page(self, response: dict) -> (list[dict], bool):
        """相容 Spring Data Page 格式 ({content: [...]})，並保留其他常見鍵作為備援"""
        for key in ("content", "data", "records", "items"):
            if key in response and isinstance(response[key], list):
                items = response[key]
                # Spring Data Page 慣例：'last' 為 True 代表最後一頁
                is_last = response.get("last")
                if is_last is None:
                    total_pages = response.get("totalPages")
                    number = response.get("number")
                    is_last = (
                        total_pages is not None and number is not None and number + 1 >= total_pages
                    ) or len(items) < self.config.page_size
                return items, bool(is_last)
        return [], True

    def _matches_institution(self, item: dict) -> bool:
        if not self.config.filter_by_institution:
            return True

        haystacks = []
        for candidate_key in INSTITUTION_FIELD_CANDIDATES:
            value = item.get(candidate_key)
            if value is None:
                continue
            if isinstance(value, list):
                haystacks.extend(str(v) for v in value)
            else:
                haystacks.append(str(value))

        # 找不到任何候選欄位時，退而對整筆資料做粗略字串比對，並記一次警告
        if not haystacks:
            haystacks = [json.dumps(item, ensure_ascii=False)]

        combined = " ".join(haystacks)
        return any(alias in combined for alias in self.config.institution_aliases)

    def dump_sample(self, size: int = 5) -> dict | None:
        """存一份原始回應，供確認實際欄位名稱使用"""
        logger.info("🧪 取得樣本資料...")
        response = self._make_request(
            "cultureObject",
            {
                "search": self.config.search_keyword,
                "page": 0,
                "size": size,
            },
        )
        if response:
            self.save_data(response, "nmth_sample_raw.json")
            logger.info("💾 已儲存原始樣本到 nmth_sample_raw.json，請檢查欄位名稱")
        else:
            logger.error("❌ 樣本取得失敗，請確認 TCMB_API_KEY 與網路連線")
        return response

    def crawl_culture_objects(self) -> list[dict]:
        """爬取 cultureObject（文物/作品）資料，並依機構關鍵字過濾"""
        logger.info(f"🚀 開始爬取 NMTH 文物資料 (關鍵字: {self.config.search_keyword})...")
        matched: list[dict] = []
        total_seen = 0
        page = 0

        while True:
            if self.config.max_pages is not None and page >= self.config.max_pages:
                logger.info(f"已達最大頁數限制 ({self.config.max_pages})，停止爬取")
                break

            logger.info(f"📄 正在取得第 {page + 1} 頁...")
            response = self._make_request(
                "cultureObject",
                {
                    "search": self.config.search_keyword,
                    "page": page,
                    "size": self.config.page_size,
                },
            )

            if response is None:
                logger.warning(f"⚠️ 第 {page + 1} 頁取得失敗，停止爬取")
                break

            items, is_last = self._extract_page(response)
            if not items:
                logger.info("✅ 沒有更多資料")
                break

            total_seen += len(items)
            for item in items:
                if self._matches_institution(item):
                    matched.append(item)

            logger.info(
                f"✅ 本頁 {len(items)} 筆，累計檢視 {total_seen} 筆，符合機構過濾 {len(matched)} 筆"
            )

            if is_last:
                break
            page += 1

        logger.info(f"🎉 爬取完成，共檢視 {total_seen} 筆，符合 NMTH 過濾條件 {len(matched)} 筆")
        if self.config.filter_by_institution and total_seen > 0 and not matched:
            logger.warning(
                "⚠️ 過濾後沒有任何符合結果，可能是 INSTITUTION_FIELD_CANDIDATES 未命中實際欄位名稱。"
                "請先用 --dump-sample 檢查原始資料結構，或加上 --no-filter 停用過濾。"
            )
        return matched

    def normalize_for_pipeline(self, items: list[dict]) -> list[dict]:
        """轉為與既有 integrate-to-vector-db-fixed.py 相容的扁平欄位，同時保留原始資料"""
        normalized = []
        for item in items:
            title = item.get("title") or item.get("name") or "Untitled"
            if isinstance(title, list):
                title = title[0] if title else "Untitled"

            description = item.get("description") or ""
            if isinstance(description, list):
                description = " ".join(str(d) for d in description)

            creator = item.get("creator") or item.get("contributor") or ""
            if isinstance(creator, list):
                creator = ", ".join(str(c) for c in creator)

            normalized.append(
                {
                    "id": str(
                        item.get("id")
                        or item.get("identifier")
                        or f"nmth_{hash(json.dumps(item, sort_keys=True, ensure_ascii=False))}"
                    ),
                    "title": title,
                    "creator": creator,
                    "date": str(item.get("date") or ""),
                    "description": description,
                    "subject": item.get("subject") or item.get("keywords") or "",
                    "imageLic": item.get("imageLic") or "",
                    "contentLic": item.get("contentLic") or "",
                    "repImage": item.get("repImage") or "",
                    "institution": "國立臺灣歷史博物館",
                    "raw": item,
                }
            )
        return normalized

    def save_data(self, data: Any, filename: str):
        filepath = os.path.join(self.config.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 資料已儲存到 {filepath}")


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="NMTH / 國家文化記憶庫 OpenAPI 爬蟲")
    parser.add_argument("--search", default="臺灣歷史博物館", help="搜尋關鍵字")
    parser.add_argument("--max-pages", type=int, default=20, help="最大頁數 (預設 20)")
    parser.add_argument("--page-size", type=int, default=50, help="每頁筆數 (預設 50)")
    parser.add_argument("--no-filter", action="store_true", help="停用機構過濾，保留所有搜尋結果")
    parser.add_argument(
        "--dump-sample", action="store_true", help="只取得少量樣本資料並存檔，用於確認欄位名稱"
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
        help="輸出目錄 (預設: 專案根目錄 data/raw，與既有匯入腳本一致)",
    )
    args = parser.parse_args()

    api_key = os.getenv("TCMB_API_KEY")
    if not api_key or "你的" in api_key:
        logger.error("❌ 未設定 TCMB_API_KEY，請先於 .env 設定後再執行")
        logger.error("   申請: https://tcmb.culture.tw/zh-tw/OpenApi")
        return

    config = NMTHCrawlerConfig(
        api_key=api_key,
        search_keyword=args.search,
        max_pages=args.max_pages,
        page_size=args.page_size,
        filter_by_institution=not args.no_filter,
        output_dir=args.output_dir,
    )
    crawler = NMTHTCMBCrawler(config)

    if args.dump_sample:
        crawler.dump_sample()
        return

    items = crawler.crawl_culture_objects()
    if items:
        normalized = crawler.normalize_for_pipeline(items)
        crawler.save_data(normalized, "nmth_objects.json")
        logger.info(f"📊 API 呼叫次數: {crawler.api_calls_count}")
        logger.info("下一步: 執行 python integrate-to-vector-db-fixed.py 匯入 ChromaDB / Neo4j")
    else:
        logger.warning("⚠️ 沒有取得任何資料，未寫入檔案")


if __name__ == "__main__":
    main()
