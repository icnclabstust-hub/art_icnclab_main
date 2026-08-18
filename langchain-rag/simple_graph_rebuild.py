#!/usr/bin/env python3
"""
簡化版圖譜重建腳本
使用統一爬蟲數據重建Neo4j知識圖譜
"""

import logging

from unified_crawler_manager import CrawlerConfig, UnifiedCrawlerManager

logger = logging.getLogger(__name__)


def rebuild_with_expanded_data():
    """使用擴展數據重建圖譜"""
    print("🚀 使用擴展數據重建藝術史知識圖譜")
    print("=" * 60)

    # 配置統一爬蟲，使用更大的參數
    config = CrawlerConfig(
        harvard_api_key="CHANGE_ME_HARVARD_API_KEY",
        harvard_enabled=True,
        harvard_max_pages=25,  # 增加頁數
        europeana_enabled=True,
        europeana_max_results=3000,  # 增加結果數
        output_dir="final_expanded_data",
        save_raw_data=True,
        save_mapped_data=True,
        generate_neo4j_script=True,
    )

    manager = UnifiedCrawlerManager(config)

    try:
        logger.info("🔄 開始最終的統一爬取...")
        results = manager.comprehensive_crawl()

        print("\n" + "=" * 60)
        print("📊 最終爬取統計:")
        print(f"   📚 處理數據源: {', '.join(results['sources_processed'])}")
        print(f"   🏛️ 總實體數量: {results['total_entities']}")
        print(f"   🔗 總關係數量: {results['total_relationships']}")
        print(f"   ⏰ 開始時間: {results['start_time']}")
        print("   📁 輸出目錄: final_expanded_data/")

        if results["errors"]:
            print(f"   ⚠️ 錯誤數量: {len(results['errors'])}")

        print("\n📁 生成的文件:")
        output_files = [
            "unified_entities.json - 統一實體數據",
            "unified_relationships.json - 統一關係數據",
            "unified_neo4j_import.cypher - Neo4j導入腳本",
            "crawl_summary.json - 爬取摘要",
        ]
        for file_desc in output_files:
            print(f"   📄 {file_desc}")

        print("\n🎉 圖譜重建完成！")
        print("💡 使用以下命令導入Neo4j:")
        print("   cypher-shell < final_expanded_data/unified_neo4j_import.cypher")
        print("=" * 60)

        return results

    except Exception as e:
        logger.error(f"❌ 重建失敗: {e}")
        raise


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        results = rebuild_with_expanded_data()
        return results
    except Exception as e:
        logger.error(f"❌ 系統錯誤: {e}")
        return None


if __name__ == "__main__":
    main()
