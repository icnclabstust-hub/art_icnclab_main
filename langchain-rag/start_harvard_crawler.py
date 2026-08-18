#!/usr/bin/env python3
"""
Harvard Art Museums爬蟲啟動腳本
一鍵啟動Harvard數據爬取和處理
"""

import logging
from datetime import datetime


def main():
    """主啟動函數"""

    print("🎨 Harvard Art Museums 藝術史數據爬蟲系統")
    print("=" * 60)
    print(f"🕐 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔑 API Key: CHANGE_ME_HARVARD_API_KEY")
    print("=" * 60)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        # 導入相關模塊
        from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig
        from unified_crawler_manager import CrawlerConfig, UnifiedCrawlerManager

        print("\n📋 選擇運行模式:")
        print("1. 僅測試Harvard API連接")
        print("2. 獲取Harvard樣本數據")
        print("3. 運行統一爬蟲系統 (推薦)")
        print("4. 生成知識圖譜架構")

        choice = input("\n請選擇 (1-4): ").strip()

        if choice == "1":
            print("\n🧪 測試Harvard API連接...")
            from test_harvard_api import test_harvard_api

            test_harvard_api()

        elif choice == "2":
            print("\n📥 獲取Harvard樣本數據...")
            config = HarvardCrawlerConfig(api_key="CHANGE_ME_HARVARD_API_KEY", max_per_page=10)
            crawler = HarvardArtMuseumsCrawler(config)
            crawler.get_sample_data()
            print("✅ Harvard樣本數據獲取完成！")

        elif choice == "3":
            print("\n🚀 運行統一爬蟲系統...")
            config = CrawlerConfig(
                harvard_api_key="CHANGE_ME_HARVARD_API_KEY",
                harvard_enabled=True,
                harvard_max_pages=3,
                europeana_enabled=True,
                europeana_max_results=100,
                output_dir="unified_crawler_data",
                save_raw_data=True,
                save_mapped_data=True,
                generate_neo4j_script=True,
            )

            manager = UnifiedCrawlerManager(config)
            results = manager.comprehensive_crawl()

            print("\n" + "=" * 60)
            print("📊 爬取統計:")
            print(f"   📚 處理數據源: {', '.join(results['sources_processed'])}")
            print(f"   🏛️ 總實體數量: {results['total_entities']}")
            print(f"   🔗 總關係數量: {results['total_relationships']}")
            print(f"   ⏰ 開始時間: {results['start_time']}")
            print("   📁 輸出目錄: unified_crawler_data/")

            if results["errors"]:
                print(f"   ⚠️ 錯誤數量: {len(results['errors'])}")

            print("\n📁 生成的文件:")
            output_files = [
                "unified_entities.json - 統一實體數據",
                "unified_relationships.json - 統一關係數據",
                "unified_neo4j_import.cypher - Neo4j導入腳本",
                "crawl_summary.json - 爬取摘要",
                "harvard/ - Harvard原始數據",
            ]
            for file_desc in output_files:
                print(f"   📄 {file_desc}")

        elif choice == "4":
            print("\n🏗️ 生成知識圖譜架構...")
            from enhanced_graph_builder import EnhancedArtHistoryGraphBuilder

            builder = EnhancedArtHistoryGraphBuilder()
            builder.add_comprehensive_enhanced_data()
            builder.build_enhanced_relationships()
            builder.save_enhanced_data()
            print("✅ 知識圖譜架構生成完成！")

        else:
            print("❌ 無效選擇")
            return

        print("\n🎉 系統運行完成！")
        print("💡 提示:")
        print("   - 生成的Neo4j腳本可直接導入到Neo4j數據庫")
        print("   - JSON文件包含結構化的藝術史數據")
        print("   - 每日API調用限制為2500次")

    except ImportError as e:
        print(f"❌ 模塊導入錯誤: {e}")
        print("💡 請確保所有依賴文件都在同一目錄下")
    except KeyboardInterrupt:
        print("\n⏹️ 用戶中斷操作")
    except Exception as e:
        print(f"❌ 系統錯誤: {e}")
        logging.error(f"系統錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    main()
