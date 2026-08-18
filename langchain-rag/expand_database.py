#!/usr/bin/env python3
"""
藝術史資料庫擴展腳本
利用爬蟲系統大規模擴展資料庫
"""

import json
import logging
from datetime import datetime
from typing import Any

from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig
from unified_crawler_manager import CrawlerConfig, UnifiedCrawlerManager

logger = logging.getLogger(__name__)


class DatabaseExpander:
    """資料庫擴展器"""

    def __init__(self):
        self.expansion_log = {
            "start_time": datetime.now().isoformat(),
            "phases": [],
            "total_data_collected": 0,
            "api_calls_used": 0,
            "errors": [],
        }

    def phase1_harvard_complete_crawl(self) -> dict[str, Any]:
        """階段1: Harvard Art Museums完整數據爬取"""
        logger.info("🎨 階段1: 開始Harvard Art Museums完整數據爬取...")

        config = HarvardCrawlerConfig(
            api_key="CHANGE_ME_HARVARD_API_KEY",
            output_dir="expanded_harvard_data",
            max_per_page=100,  # 最大化每頁數據
            delay_seconds=0.3,  # 稍微加快速度
        )

        crawler = HarvardArtMuseumsCrawler(config)

        phase_results = {
            "phase": "Harvard Complete Crawl",
            "start_time": datetime.now().isoformat(),
            "data_types": {},
        }

        try:
            # 1. 爬取更多作品數據
            logger.info("📸 爬取作品數據...")
            objects = crawler.crawl_all_objects(max_pages=15)  # 增加到15頁
            if objects:
                phase_results["data_types"]["objects"] = len(objects)
                crawler.save_data(objects, "expanded_harvard_objects.json")
                logger.info(f"✅ 獲取 {len(objects)} 個作品")

            # 2. 爬取更多人物數據
            logger.info("👤 爬取人物數據...")
            people = crawler.crawl_all_people(max_pages=10)  # 增加到10頁
            if people:
                phase_results["data_types"]["people"] = len(people)
                crawler.save_data(people, "expanded_harvard_people.json")
                logger.info(f"✅ 獲取 {len(people)} 個人物")

            # 3. 爬取展覽數據
            logger.info("🖼️ 爬取展覽數據...")
            exhibitions = crawler.crawl_all_exhibitions(max_pages=8)  # 增加到8頁
            if exhibitions:
                phase_results["data_types"]["exhibitions"] = len(exhibitions)
                crawler.save_data(exhibitions, "expanded_harvard_exhibitions.json")
                logger.info(f"✅ 獲取 {len(exhibitions)} 個展覽")

            # 4. 爬取畫廊數據
            logger.info("🏛️ 爬取畫廊數據...")
            galleries = crawler.crawl_all_galleries(max_pages=5)
            if galleries:
                phase_results["data_types"]["galleries"] = len(galleries)
                crawler.save_data(galleries, "expanded_harvard_galleries.json")
                logger.info(f"✅ 獲取 {len(galleries)} 個畫廊")

            # 5. 爬取出版物數據
            logger.info("📚 爬取出版物數據...")
            publications = crawler.crawl_all_publications(max_pages=5)
            if publications:
                phase_results["data_types"]["publications"] = len(publications)
                crawler.save_data(publications, "expanded_harvard_publications.json")
                logger.info(f"✅ 獲取 {len(publications)} 個出版物")

            # 6. 爬取完整元數據
            logger.info("📋 爬取完整元數據...")
            metadata = crawler.crawl_metadata()
            if metadata:
                phase_results["data_types"]["metadata"] = sum(
                    len(v) for v in metadata.values() if isinstance(v, list)
                )
                crawler.save_data(metadata, "expanded_harvard_metadata.json")
                logger.info("✅ 獲取元數據")

            phase_results["api_calls_used"] = crawler.api_calls_count
            phase_results["status"] = "success"
            phase_results["end_time"] = datetime.now().isoformat()

            total_items = sum(phase_results["data_types"].values())
            api_calls = crawler.api_calls_count
            logger.info(f"🎉 階段1完成！總計獲取 {total_items} 項數據，使用 {api_calls} 次API調用")

        except Exception as e:
            logger.error(f"❌ 階段1錯誤: {e}")
            phase_results["status"] = "error"
            phase_results["error"] = str(e)

        return phase_results

    def crawl_all_galleries(self, max_pages: int = None) -> list[dict]:
        """爬取所有畫廊數據（為HarvardArtMuseumsCrawler添加方法）"""
        logger.info("🚀 開始爬取Harvard Art Museums畫廊數據...")
        all_galleries = []
        page = 1

        # 創建臨時爬蟲實例
        config = HarvardCrawlerConfig(api_key="CHANGE_ME_HARVARD_API_KEY")
        crawler = HarvardArtMuseumsCrawler(config)

        while True:
            if max_pages and page > max_pages:
                break

            if crawler.api_calls_count >= crawler.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁畫廊數據...")
            response = crawler.get_galleries(page=page)

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

        # 創建臨時爬蟲實例
        config = HarvardCrawlerConfig(api_key="CHANGE_ME_HARVARD_API_KEY")
        crawler = HarvardArtMuseumsCrawler(config)

        while True:
            if max_pages and page > max_pages:
                break

            if crawler.api_calls_count >= crawler.config.daily_limit:
                logger.warning("⚠️ 達到每日API限制，停止爬取")
                break

            logger.info(f"📄 正在獲取第 {page} 頁出版物數據...")
            response = crawler.get_publications(page=page)

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

    def phase2_unified_integration(self) -> dict[str, Any]:
        """階段2: 統一整合所有數據源"""
        logger.info("🔄 階段2: 開始統一整合所有數據源...")

        config = CrawlerConfig(
            harvard_api_key="CHANGE_ME_HARVARD_API_KEY",
            harvard_enabled=True,
            harvard_max_pages=20,  # 大幅增加頁數
            europeana_enabled=True,
            europeana_max_results=2000,  # 增加到2000條
            output_dir="expanded_unified_data",
            save_raw_data=True,
            save_mapped_data=True,
            generate_neo4j_script=True,
        )

        manager = UnifiedCrawlerManager(config)

        phase_results = {
            "phase": "Unified Integration",
            "start_time": datetime.now().isoformat(),
        }

        try:
            results = manager.comprehensive_crawl()
            phase_results.update(results)
            phase_results["status"] = "success"

            n_entities = results["total_entities"]
            n_relationships = results["total_relationships"]
            logger.info(f"🎉 階段2完成！整合了 {n_entities} 個實體和 {n_relationships} 個關係")

        except Exception as e:
            logger.error(f"❌ 階段2錯誤: {e}")
            phase_results["status"] = "error"
            phase_results["error"] = str(e)

        return phase_results

    def phase3_advanced_crawling(self) -> dict[str, Any]:
        """階段3: 高級爬取策略"""
        logger.info("🚀 階段3: 執行高級爬取策略...")

        phase_results = {
            "phase": "Advanced Crawling",
            "start_time": datetime.now().isoformat(),
            "strategies": [],
        }

        try:
            # 策略1: 針對特定藝術運動的深度爬取
            movements_filter = {"classification": "Paintings", "period": "Renaissance", "size": 100}

            config = HarvardCrawlerConfig(api_key="CHANGE_ME_HARVARD_API_KEY")
            crawler = HarvardArtMuseumsCrawler(config)

            logger.info("🎨 針對Renaissance繪畫進行深度爬取...")
            renaissance_objects = crawler.crawl_all_objects(max_pages=10, filters=movements_filter)
            if renaissance_objects:
                crawler.save_data(renaissance_objects, "renaissance_paintings.json")
                phase_results["strategies"].append(
                    {"name": "Renaissance Paintings", "count": len(renaissance_objects)}
                )

            # 策略2: 針對現代藝術的爬取
            modern_filter = {"classification": "Paintings", "datebegin": 1900, "size": 100}

            logger.info("🎭 針對現代藝術進行爬取...")
            modern_objects = crawler.crawl_all_objects(max_pages=8, filters=modern_filter)
            if modern_objects:
                crawler.save_data(modern_objects, "modern_art.json")
                phase_results["strategies"].append(
                    {"name": "Modern Art", "count": len(modern_objects)}
                )

            phase_results["status"] = "success"
            phase_results["end_time"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"❌ 階段3錯誤: {e}")
            phase_results["status"] = "error"
            phase_results["error"] = str(e)

        return phase_results

    def generate_expansion_report(self, results: list[dict]) -> None:
        """生成擴展報告"""
        logger.info("📊 生成資料庫擴展報告...")

        self.expansion_log["phases"] = results
        self.expansion_log["end_time"] = datetime.now().isoformat()

        # 計算總計
        total_entities = 0
        total_api_calls = 0

        for phase in results:
            if phase["status"] == "success":
                if "data_types" in phase:
                    total_entities += sum(phase["data_types"].values())
                if "api_calls_used" in phase:
                    total_api_calls += phase["api_calls_used"]

        self.expansion_log["total_data_collected"] = total_entities
        self.expansion_log["api_calls_used"] = total_api_calls

        # 保存報告
        with open("database_expansion_report.json", "w", encoding="utf-8") as f:
            json.dump(self.expansion_log, f, ensure_ascii=False, indent=2)

        # 打印摘要
        print("\n" + "=" * 60)
        print("📊 資料庫擴展完成報告")
        print("=" * 60)
        print(f"⏰ 擴展時間: {self.expansion_log['start_time']} - {self.expansion_log['end_time']}")
        print(f"📚 總數據量: {self.expansion_log['total_data_collected']} 項")
        print(f"🔧 API調用次數: {self.expansion_log['api_calls_used']}")
        print(f"✅ 成功階段: {sum(1 for p in results if p['status'] == 'success')}/{len(results)}")

        print("\n📋 各階段詳情:")
        for phase in results:
            status_icon = "✅" if phase["status"] == "success" else "❌"
            print(f"   {status_icon} {phase['phase']}")
            if "data_types" in phase:
                for data_type, count in phase["data_types"].items():
                    print(f"     - {data_type}: {count}")

        if any(p["status"] == "error" for p in results):
            print("\n⚠️ 錯誤詳情:")
            for phase in results:
                if phase["status"] == "error":
                    print(f"   - {phase['phase']}: {phase.get('error', 'Unknown error')}")

        print("\n📁 輸出目錄:")
        print("   - expanded_harvard_data/ (Harvard完整數據)")
        print("   - expanded_unified_data/ (統一整合數據)")
        print("   - database_expansion_report.json (擴展報告)")
        print("=" * 60)


def main():
    """主擴展流程"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🚀 藝術史資料庫大規模擴展系統")
    print("=" * 60)
    print("📋 擴展計劃:")
    print("   階段1: Harvard Art Museums完整數據爬取")
    print("   階段2: 統一整合所有數據源")
    print("   階段3: 高級爬取策略")
    print("=" * 60)

    expander = DatabaseExpander()
    results = []

    try:
        # 階段1: Harvard完整爬取
        phase1_result = expander.phase1_harvard_complete_crawl()
        results.append(phase1_result)

        # 階段2: 統一整合
        phase2_result = expander.phase2_unified_integration()
        results.append(phase2_result)

        # 階段3: 高級爬取
        phase3_result = expander.phase3_advanced_crawling()
        results.append(phase3_result)

    except KeyboardInterrupt:
        logger.info("⏹️ 用戶中斷擴展流程")
    except Exception as e:
        logger.error(f"❌ 擴展流程出現嚴重錯誤: {e}")
    finally:
        # 生成報告
        expander.generate_expansion_report(results)


if __name__ == "__main__":
    main()
