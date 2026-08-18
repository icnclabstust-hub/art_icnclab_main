#!/usr/bin/env python3
"""
Harvard Art Museums API 爬蟲
從哈佛藝術博物館API獲取藝術史數據
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class HarvardCrawlerConfig:
    """Harvard Art Museums爬蟲配置"""

    api_key: str
    base_url: str = "https://api.harvardartmuseums.org"
    max_per_page: int = 100
    daily_limit: int = 2500
    delay_seconds: float = 0.5
    output_dir: str = "harvard_data"


class HarvardArtMuseumsCrawler:
    """Harvard Art Museums API爬蟲"""

    def __init__(self, config: HarvardCrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.api_calls_count = 0
        self.session.headers.update(
            {"User-Agent": "Art History Database Research Tool v1.0", "Accept": "application/json"}
        )

        # 創建輸出目錄
        os.makedirs(config.output_dir, exist_ok=True)

    def _make_request(self, endpoint: str, params: dict = None) -> dict | None:
        """執行API請求"""
        if self.api_calls_count >= self.config.daily_limit:
            logger.warning("⚠️ 已達到每日API調用限制")
            return None

        if params is None:
            params = {}

        params["apikey"] = self.config.api_key
        url = f"{self.config.base_url}/{endpoint}"

        try:
            time.sleep(self.config.delay_seconds)
            response = self.session.get(url, params=params)
            self.api_calls_count += 1

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("⚠️ API速率限制，等待60秒")
                time.sleep(60)
                return self._make_request(endpoint, params)
            else:
                logger.error(f"❌ API請求失敗: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ 請求異常: {e}")
            return None

    def get_objects(self, page: int = 1, size: int = None, filters: dict = None) -> dict | None:
        """獲取藝術作品數據"""
        if size is None:
            size = self.config.max_per_page

        params = {"page": page, "size": size, "sort": "id", "sortorder": "asc"}

        if filters:
            params.update(filters)

        return self._make_request("object", params)

    def get_people(self, page: int = 1, size: int = None) -> dict | None:
        """獲取人物數據（藝術家、策展人等）"""
        if size is None:
            size = self.config.max_per_page

        params = {"page": page, "size": size, "sort": "id", "sortorder": "asc"}

        return self._make_request("person", params)

    def get_exhibitions(self, page: int = 1, size: int = None) -> dict | None:
        """獲取展覽數據"""
        if size is None:
            size = self.config.max_per_page

        params = {"page": page, "size": size, "sort": "id", "sortorder": "asc"}

        return self._make_request("exhibition", params)

    def get_galleries(self, page: int = 1, size: int = None) -> dict | None:
        """獲取畫廊數據"""
        if size is None:
            size = self.config.max_per_page

        params = {"page": page, "size": size, "sort": "id", "sortorder": "asc"}

        return self._make_request("gallery", params)

    def get_publications(self, page: int = 1, size: int = None) -> dict | None:
        """獲取出版物數據"""
        if size is None:
            size = self.config.max_per_page

        params = {"page": page, "size": size, "sort": "id", "sortorder": "asc"}

        return self._make_request("publication", params)

    def get_classifications(self) -> dict | None:
        """獲取分類數據"""
        return self._make_request("classification")

    def get_cultures(self) -> dict | None:
        """獲取文化分類數據"""
        return self._make_request("culture")

    def get_mediums(self) -> dict | None:
        """獲取媒材數據"""
        return self._make_request("medium")

    def get_techniques(self) -> dict | None:
        """獲取技法數據"""
        return self._make_request("technique")

    def crawl_all_objects(self, max_pages: int = None, filters: dict = None) -> list[dict]:
        """爬取所有藝術作品數據"""
        logger.info("🚀 開始爬取Harvard Art Museums作品數據...")
        all_objects = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            if self.api_calls_count >= self.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁作品數據...")
            response = self.get_objects(page=page, filters=filters)

            if not response or "records" not in response:
                logger.warning(f"⚠️ 第 {page} 頁數據獲取失敗")
                break

            objects = response["records"]
            if not objects:
                logger.info("✅ 所有作品數據已獲取完成")
                break

            all_objects.extend(objects)
            logger.info(f"✅ 已獲取 {len(objects)} 個作品，累計 {len(all_objects)} 個")

            # 檢查是否還有更多頁面
            info = response.get("info", {})
            if page >= info.get("pages", 1):
                break

            page += 1

        logger.info(f"🎉 作品數據爬取完成，共獲取 {len(all_objects)} 個作品")
        return all_objects

    def crawl_all_people(self, max_pages: int = None) -> list[dict]:
        """爬取所有人物數據"""
        logger.info("🚀 開始爬取Harvard Art Museums人物數據...")
        all_people = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            if self.api_calls_count >= self.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁人物數據...")
            response = self.get_people(page=page)

            if not response or "records" not in response:
                logger.warning(f"⚠️ 第 {page} 頁數據獲取失敗")
                break

            people = response["records"]
            if not people:
                logger.info("✅ 所有人物數據已獲取完成")
                break

            all_people.extend(people)
            logger.info(f"✅ 已獲取 {len(people)} 個人物，累計 {len(all_people)} 個")

            # 檢查是否還有更多頁面
            info = response.get("info", {})
            if page >= info.get("pages", 1):
                break

            page += 1

        logger.info(f"🎉 人物數據爬取完成，共獲取 {len(all_people)} 個人物")
        return all_people

    def crawl_all_exhibitions(self, max_pages: int = None) -> list[dict]:
        """爬取所有展覽數據"""
        logger.info("🚀 開始爬取Harvard Art Museums展覽數據...")
        all_exhibitions = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            if self.api_calls_count >= self.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁展覽數據...")
            response = self.get_exhibitions(page=page)

            if not response or "records" not in response:
                logger.warning(f"⚠️ 第 {page} 頁數據獲取失敗")
                break

            exhibitions = response["records"]
            if not exhibitions:
                logger.info("✅ 所有展覽數據已獲取完成")
                break

            all_exhibitions.extend(exhibitions)
            logger.info(f"✅ 已獲取 {len(exhibitions)} 個展覽，累計 {len(all_exhibitions)} 個")

            # 檢查是否還有更多頁面
            info = response.get("info", {})
            if page >= info.get("pages", 1):
                break

            page += 1

        logger.info(f"🎉 展覽數據爬取完成，共獲取 {len(all_exhibitions)} 個展覽")
        return all_exhibitions

    def crawl_metadata(self) -> dict[str, Any]:
        """爬取元數據（分類、文化、媒材等）"""
        logger.info("🚀 開始爬取元數據...")
        metadata = {}

        # 獲取分類
        logger.info("📋 獲取分類數據...")
        classifications = self.get_classifications()
        if classifications and "records" in classifications:
            metadata["classifications"] = classifications["records"]
            logger.info(f"✅ 獲取 {len(metadata['classifications'])} 個分類")

        # 獲取文化
        logger.info("🌍 獲取文化數據...")
        cultures = self.get_cultures()
        if cultures and "records" in cultures:
            metadata["cultures"] = cultures["records"]
            logger.info(f"✅ 獲取 {len(metadata['cultures'])} 個文化")

        # 獲取媒材
        logger.info("🎨 獲取媒材數據...")
        mediums = self.get_mediums()
        if mediums and "records" in mediums:
            metadata["mediums"] = mediums["records"]
            logger.info(f"✅ 獲取 {len(metadata['mediums'])} 個媒材")

        # 獲取技法
        logger.info("🔧 獲取技法數據...")
        techniques = self.get_techniques()
        if techniques and "records" in techniques:
            metadata["techniques"] = techniques["records"]
            logger.info(f"✅ 獲取 {len(metadata['techniques'])} 個技法")

        return metadata

    def save_data(self, data: Any, filename: str):
        """保存數據到文件"""
        filepath = os.path.join(self.config.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 數據已保存到 {filepath}")

    def crawl_all_galleries(self, max_pages: int = None) -> list[dict]:
        """爬取所有畫廊數據"""
        logger.info("🚀 開始爬取Harvard Art Museums畫廊數據...")
        all_galleries = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            if self.api_calls_count >= self.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁畫廊數據...")
            response = self.get_galleries(page=page)

            if not response or "records" not in response:
                logger.warning(f"⚠️ 第 {page} 頁數據獲取失敗")
                break

            galleries = response["records"]
            if not galleries:
                logger.info("✅ 所有畫廊數據已獲取完成")
                break

            all_galleries.extend(galleries)
            logger.info(f"✅ 已獲取 {len(galleries)} 個畫廊，累計 {len(all_galleries)} 個")

            # 檢查是否還有更多頁面
            info = response.get("info", {})
            if page >= info.get("pages", 1):
                break

            page += 1

        logger.info(f"🎉 畫廊數據爬取完成，共獲取 {len(all_galleries)} 個畫廊")
        return all_galleries

    def crawl_all_publications(self, max_pages: int = None) -> list[dict]:
        """爬取所有出版物數據"""
        logger.info("🚀 開始爬取Harvard Art Museums出版物數據...")
        all_publications = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            if self.api_calls_count >= self.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁出版物數據...")
            response = self.get_publications(page=page)

            if not response or "records" not in response:
                logger.warning(f"⚠️ 第 {page} 頁數據獲取失敗")
                break

            publications = response["records"]
            if not publications:
                logger.info("✅ 所有出版物數據已獲取完成")
                break

            all_publications.extend(publications)
            logger.info(f"✅ 已獲取 {len(publications)} 個出版物，累計 {len(all_publications)} 個")

            # 檢查是否還有更多頁面
            info = response.get("info", {})
            if page >= info.get("pages", 1):
                break

            page += 1

        logger.info(f"🎉 出版物數據爬取完成，共獲取 {len(all_publications)} 個出版物")
        return all_publications

    def comprehensive_crawl(self, max_pages_per_type: int = 5):
        """全面爬取數據"""
        logger.info("🚀 開始全面爬取Harvard Art Museums數據...")

        crawl_summary = {
            "start_time": datetime.now().isoformat(),
            "api_calls_used": 0,
            "data_collected": {},
        }

        try:
            # 1. 爬取元數據
            logger.info("\n=== 第1步：爬取元數據 ===")
            metadata = self.crawl_metadata()
            if metadata:
                self.save_data(metadata, "harvard_metadata.json")
                crawl_summary["data_collected"]["metadata"] = {
                    "classifications": len(metadata.get("classifications", [])),
                    "cultures": len(metadata.get("cultures", [])),
                    "mediums": len(metadata.get("mediums", [])),
                    "techniques": len(metadata.get("techniques", [])),
                }

            # 2. 爬取作品數據
            logger.info("\n=== 第2步：爬取作品數據 ===")
            objects = self.crawl_all_objects(max_pages=max_pages_per_type)
            if objects:
                self.save_data(objects, "harvard_objects.json")
                crawl_summary["data_collected"]["objects"] = len(objects)

            # 3. 爬取人物數據
            logger.info("\n=== 第3步：爬取人物數據 ===")
            people = self.crawl_all_people(max_pages=max_pages_per_type)
            if people:
                self.save_data(people, "harvard_people.json")
                crawl_summary["data_collected"]["people"] = len(people)

            # 4. 爬取展覽數據
            logger.info("\n=== 第4步：爬取展覽數據 ===")
            exhibitions = self.crawl_all_exhibitions(max_pages=max_pages_per_type)
            if exhibitions:
                self.save_data(exhibitions, "harvard_exhibitions.json")
                crawl_summary["data_collected"]["exhibitions"] = len(exhibitions)

        except Exception as e:
            logger.error(f"❌ 爬取過程中出現錯誤: {e}")

        finally:
            crawl_summary["end_time"] = datetime.now().isoformat()
            crawl_summary["api_calls_used"] = self.api_calls_count
            self.save_data(crawl_summary, "harvard_crawl_summary.json")

            logger.info("\n🎉 Harvard Art Museums數據爬取完成！")
            logger.info(f"📊 總共使用了 {self.api_calls_count} 次API調用")
            logger.info("📁 數據文件已保存到 harvard_data/ 目錄")

    def get_sample_data(self):
        """獲取少量樣本數據用於測試"""
        logger.info("🧪 獲取樣本數據進行測試...")

        # 獲取5個作品樣本
        objects_sample = self.get_objects(page=1, size=5)
        if objects_sample:
            self.save_data(objects_sample, "harvard_objects_sample.json")

        # 獲取5個人物樣本
        people_sample = self.get_people(page=1, size=5)
        if people_sample:
            self.save_data(people_sample, "harvard_people_sample.json")

        # 獲取5個展覽樣本
        exhibitions_sample = self.get_exhibitions(page=1, size=5)
        if exhibitions_sample:
            self.save_data(exhibitions_sample, "harvard_exhibitions_sample.json")

        # 獲取元數據樣本
        metadata_sample = {
            "classifications": self.get_classifications(),
            "cultures": self.get_cultures(),
            "mediums": self.get_mediums(),
            "techniques": self.get_techniques(),
        }
        self.save_data(metadata_sample, "harvard_metadata_sample.json")

        logger.info("✅ 樣本數據獲取完成")


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 配置爬蟲
    config = HarvardCrawlerConfig(
        api_key="CHANGE_ME_HARVARD_API_KEY",
        delay_seconds=0.5,
        max_per_page=50,  # 減少每頁數量以節省API調用
    )

    crawler = HarvardArtMuseumsCrawler(config)

    print("🎨 Harvard Art Museums API 爬蟲")
    print("選擇操作：")
    print("1. 獲取樣本數據（推薦，節省API調用）")
    print("2. 全面爬取數據（大量API調用）")
    print("3. 僅獲取元數據")

    choice = input("請輸入選擇 (1-3): ").strip()

    if choice == "1":
        crawler.get_sample_data()
    elif choice == "2":
        max_pages = int(input("每種數據類型的最大頁數 (建議不超過10): ") or "5")
        crawler.comprehensive_crawl(max_pages_per_type=max_pages)
    elif choice == "3":
        metadata = crawler.crawl_metadata()
        if metadata:
            crawler.save_data(metadata, "harvard_metadata_only.json")
    else:
        print("❌ 無效選擇")


if __name__ == "__main__":
    main()
