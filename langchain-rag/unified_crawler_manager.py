#!/usr/bin/env python3
"""
統一爬蟲管理器
集成所有藝術史數據源的爬蟲系統
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from data_mapper import ArtHistoryDataMapper
from enhanced_graph_builder import EnhancedArtHistoryGraphBuilder
from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig

logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """統一爬蟲配置"""

    # Harvard Art Museums配置
    harvard_api_key: str
    harvard_enabled: bool = True
    harvard_max_pages: int = 5

    # Europeana配置
    europeana_enabled: bool = True
    europeana_max_results: int = 1000

    # 輸出配置
    output_dir: str = "unified_crawler_data"
    save_raw_data: bool = True
    save_mapped_data: bool = True
    generate_neo4j_script: bool = True


class UnifiedCrawlerManager:
    """統一爬蟲管理器"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.crawl_results = {}
        self.data_mapper = ArtHistoryDataMapper()
        self.graph_builder = EnhancedArtHistoryGraphBuilder()

        # 創建輸出目錄
        os.makedirs(config.output_dir, exist_ok=True)

    def setup_harvard_crawler(self) -> HarvardArtMuseumsCrawler | None:
        """設置Harvard Art Museums爬蟲"""
        if not self.config.harvard_enabled:
            logger.info("⚠️ Harvard Art Museums爬蟲已禁用")
            return None

        harvard_config = HarvardCrawlerConfig(
            api_key=self.config.harvard_api_key,
            output_dir=os.path.join(self.config.output_dir, "harvard"),
            max_per_page=50,
            delay_seconds=0.5,
        )

        return HarvardArtMuseumsCrawler(harvard_config)

    def crawl_harvard_data(self) -> dict[str, Any]:
        """爬取Harvard Art Museums數據"""
        logger.info("🎨 開始爬取Harvard Art Museums數據...")

        harvard_crawler = self.setup_harvard_crawler()
        if not harvard_crawler:
            return {"status": "disabled", "data": {}}

        try:
            # 獲取樣本數據以節省API調用
            harvard_crawler.get_sample_data()

            # 讀取爬取結果
            harvard_dir = os.path.join(self.config.output_dir, "harvard")
            harvard_data = {}

            # 讀取各類數據文件
            data_files = {
                "objects": "harvard_objects_sample.json",
                "people": "harvard_people_sample.json",
                "exhibitions": "harvard_exhibitions_sample.json",
                "metadata": "harvard_metadata_sample.json",
            }

            for data_type, filename in data_files.items():
                filepath = os.path.join(harvard_dir, filename)
                if os.path.exists(filepath):
                    with open(filepath, encoding="utf-8") as f:
                        harvard_data[data_type] = json.load(f)
                    logger.info(f"✅ 讀取Harvard {data_type}數據")

            logger.info("✅ Harvard Art Museums數據爬取完成")
            return {"status": "success", "data": harvard_data}

        except Exception as e:
            logger.error(f"❌ Harvard爬蟲出錯: {e}")
            return {"status": "error", "error": str(e), "data": {}}

    def crawl_europeana_data(self) -> dict[str, Any]:
        """爬取Europeana數據（模擬，使用現有文件）"""
        logger.info("🏛️ 處理Europeana數據...")

        if not self.config.europeana_enabled:
            logger.info("⚠️ Europeana爬蟲已禁用")
            return {"status": "disabled", "data": {}}

        try:
            # 檢查是否有現有的Europeana數據文件
            europeana_files = ["europeana_art_data.json", "crawled_data.json", "art_data.json"]

            europeana_data = []
            for filename in europeana_files:
                if os.path.exists(filename):
                    with open(filename, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            europeana_data.extend(data)
                        elif isinstance(data, dict) and "items" in data:
                            europeana_data.extend(data["items"])
                    logger.info(f"✅ 讀取Europeana數據文件: {filename}")
                    break

            if not europeana_data:
                logger.warning("⚠️ 未找到Europeana數據文件")
                return {"status": "no_data", "data": []}

            # 限制結果數量
            if len(europeana_data) > self.config.europeana_max_results:
                europeana_data = europeana_data[: self.config.europeana_max_results]

            logger.info(f"✅ Europeana數據處理完成，共 {len(europeana_data)} 條記錄")
            return {"status": "success", "data": europeana_data}

        except Exception as e:
            logger.error(f"❌ Europeana數據處理出錯: {e}")
            return {"status": "error", "error": str(e), "data": []}

    def map_harvard_data(self, harvard_data: dict) -> dict[str, Any]:
        """映射Harvard數據到增強節點體系"""
        logger.info("🔄 映射Harvard數據到增強節點體系...")

        try:
            mapped_entities = []
            mapped_relationships = []

            # 映射作品數據
            if "objects" in harvard_data and harvard_data["objects"].get("records"):
                objects = harvard_data["objects"]["records"]
                for obj in objects:
                    # 轉換Harvard格式到標準格式
                    standardized_obj = self._standardize_harvard_object(obj)
                    entities, relationships = self.data_mapper.map_single_item(
                        standardized_obj, source="harvard"
                    )
                    mapped_entities.extend(entities)
                    mapped_relationships.extend(relationships)

            # 映射人物數據
            if "people" in harvard_data and harvard_data["people"].get("records"):
                people = harvard_data["people"]["records"]
                for person in people:
                    # 轉換Harvard人物格式
                    standardized_person = self._standardize_harvard_person(person)
                    entities, relationships = self.data_mapper.map_single_item(
                        standardized_person, source="harvard"
                    )
                    mapped_entities.extend(entities)
                    mapped_relationships.extend(relationships)

            # 映射展覽數據
            if "exhibitions" in harvard_data and harvard_data["exhibitions"].get("records"):
                exhibitions = harvard_data["exhibitions"]["records"]
                for exhibition in exhibitions:
                    # 轉換Harvard展覽格式
                    standardized_exhibition = self._standardize_harvard_exhibition(exhibition)
                    entities, relationships = self.data_mapper.map_single_item(
                        standardized_exhibition, source="harvard"
                    )
                    mapped_entities.extend(entities)
                    mapped_relationships.extend(relationships)

            # 去重
            unique_entities = self.data_mapper._deduplicate_entities(mapped_entities)

            n_relationships = len(mapped_relationships)
            logger.info(
                f"✅ Harvard數據映射完成: {len(unique_entities)} 個實體, {n_relationships} 個關係"
            )
            return {
                "status": "success",
                "entities": unique_entities,
                "relationships": mapped_relationships,
                "stats": {
                    "total_entities": len(unique_entities),
                    "total_relationships": len(mapped_relationships),
                },
            }

        except Exception as e:
            logger.error(f"❌ Harvard數據映射出錯: {e}")
            return {"status": "error", "error": str(e)}

    def _standardize_harvard_object(self, obj: dict) -> dict:
        """標準化Harvard作品數據格式"""
        return {
            "dcTitle": obj.get("title", ""),
            "dcCreator": obj.get("people", [{}])[0].get("name", "") if obj.get("people") else "",
            "dcDate": obj.get("dated", ""),
            "dcDescription": obj.get("description", ""),
            "dcType": obj.get("classification", ""),
            "dcFormat": obj.get("medium", ""),
            "dcSubject": "; ".join(obj.get("subject", [])) if obj.get("subject") else "",
            "edmDataProvider": "Harvard Art Museums",
            "edmCountry": "United States",
            "edmIsShownAt": obj.get("url", ""),
            "id": str(obj.get("id", "")),
        }

    def _standardize_harvard_person(self, person: dict) -> dict:
        """標準化Harvard人物數據格式"""
        return {
            "dcCreator": person.get("displayname", ""),
            "dcTitle": f"Person: {person.get('displayname', '')}",
            "dcDescription": person.get("alphasort", ""),
            "dcDate": f"{person.get('datebegin', '')}-{person.get('dateend', '')}",
            "edmDataProvider": "Harvard Art Museums",
            "edmCountry": "United States",
            "edmIsShownAt": person.get("url", ""),
            "id": str(person.get("id", "")),
        }

    def _standardize_harvard_exhibition(self, exhibition: dict) -> dict:
        """標準化Harvard展覽數據格式"""
        return {
            "dcTitle": exhibition.get("title", ""),
            "dcDescription": exhibition.get("shortdescription", ""),
            "dcDate": f"{exhibition.get('begindate', '')}-{exhibition.get('enddate', '')}",
            "dcType": "Exhibition",
            "edmDataProvider": "Harvard Art Museums",
            "edmCountry": "United States",
            "edmIsShownAt": exhibition.get("url", ""),
            "id": str(exhibition.get("id", "")),
        }

    def comprehensive_crawl(self) -> dict[str, Any]:
        """執行全面爬取"""
        logger.info("🚀 開始執行統一爬蟲系統...")

        crawl_summary = {
            "start_time": datetime.now().isoformat(),
            "sources_processed": [],
            "total_entities": 0,
            "total_relationships": 0,
            "errors": [],
        }

        all_entities = []
        all_relationships = []

        try:
            # 1. 爬取Harvard Art Museums數據
            if self.config.harvard_enabled:
                logger.info("\n=== 處理Harvard Art Museums數據 ===")
                harvard_result = self.crawl_harvard_data()

                if harvard_result["status"] == "success":
                    # 映射Harvard數據
                    mapped_result = self.map_harvard_data(harvard_result["data"])
                    if mapped_result["status"] == "success":
                        all_entities.extend(mapped_result["entities"])
                        all_relationships.extend(mapped_result["relationships"])
                        crawl_summary["sources_processed"].append("Harvard Art Museums")
                    else:
                        crawl_summary["errors"].append(
                            f"Harvard mapping error: {mapped_result.get('error', 'Unknown')}"
                        )
                else:
                    crawl_summary["errors"].append(
                        f"Harvard crawl error: {harvard_result.get('error', 'Unknown')}"
                    )

            # 2. 處理Europeana數據
            if self.config.europeana_enabled:
                logger.info("\n=== 處理Europeana數據 ===")
                europeana_result = self.crawl_europeana_data()

                if europeana_result["status"] == "success":
                    # 映射Europeana數據
                    entities, relationships = self.data_mapper.map_europeana_data(
                        europeana_result["data"]
                    )
                    all_entities.extend(entities)
                    all_relationships.extend(relationships)
                    crawl_summary["sources_processed"].append("Europeana")
                else:
                    crawl_summary["errors"].append(
                        f"Europeana error: {europeana_result.get('error', 'Unknown')}"
                    )

            # 3. 去重和統計
            unique_entities = self.data_mapper._deduplicate_entities(all_entities)
            crawl_summary["total_entities"] = len(unique_entities)
            crawl_summary["total_relationships"] = len(all_relationships)

            # 4. 保存數據
            if self.config.save_raw_data or self.config.save_mapped_data:
                self._save_crawl_results(unique_entities, all_relationships, crawl_summary)

            # 5. 生成Neo4j腳本
            if self.config.generate_neo4j_script:
                self._generate_neo4j_script(unique_entities, all_relationships)

        except Exception as e:
            logger.error(f"❌ 統一爬蟲執行出錯: {e}")
            crawl_summary["errors"].append(f"System error: {str(e)}")

        finally:
            crawl_summary["end_time"] = datetime.now().isoformat()

            logger.info("\n🎉 統一爬蟲系統執行完成！")
            logger.info(f"📊 處理數據源: {', '.join(crawl_summary['sources_processed'])}")
            logger.info(f"📊 總實體數量: {crawl_summary['total_entities']}")
            logger.info(f"📊 總關係數量: {crawl_summary['total_relationships']}")

            if crawl_summary["errors"]:
                logger.warning(f"⚠️ 遇到 {len(crawl_summary['errors'])} 個錯誤")

        return crawl_summary

    def _save_crawl_results(self, entities: list, relationships: list, summary: dict):
        """保存爬取結果"""
        logger.info("💾 保存爬取結果...")

        # 保存實體數據
        entities_file = os.path.join(self.config.output_dir, "unified_entities.json")
        entities_data = [
            {
                "type": entity.entity_type.value,
                "name": entity.name,
                "properties": entity.properties,
                "source": entity.properties.get("source_data", "unknown"),
            }
            for entity in entities
        ]

        with open(entities_file, "w", encoding="utf-8") as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)

        # 保存關係數據
        relationships_file = os.path.join(self.config.output_dir, "unified_relationships.json")
        with open(relationships_file, "w", encoding="utf-8") as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

        # 保存爬取摘要
        summary_file = os.path.join(self.config.output_dir, "crawl_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 數據已保存到 {self.config.output_dir}")

    def _generate_neo4j_script(self, entities: list, relationships: list):
        """生成Neo4j導入腳本"""
        logger.info("📝 生成Neo4j導入腳本...")

        cypher_statements = []

        # 清理數據庫
        cypher_statements.append("MATCH (n) DETACH DELETE n;")

        # 創建約束
        unique_types = set(entity.entity_type.value for entity in entities)
        for node_type in unique_types:
            cypher_statements.append(
                f"CREATE CONSTRAINT {node_type.lower()}_name_unique IF NOT EXISTS "
                f"FOR (n:{node_type}) REQUIRE n.name IS UNIQUE;"
            )

        # 創建節點
        for entity in entities:
            # 清理屬性
            clean_props = {}
            for k, v in entity.properties.items():
                if isinstance(v, str):
                    clean_props[k] = v.replace("'", "\\'").replace('"', '\\"')[:500]  # 限制長度
                elif isinstance(v, (int, float, bool)):
                    clean_props[k] = v
                elif isinstance(v, list):
                    clean_props[k] = [str(item)[:100] for item in v[:5]]  # 限制列表長度

            props_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in clean_props.items()])
            cypher = f"CREATE (:{entity.entity_type.value} {{{props_str}}});"
            cypher_statements.append(cypher)

        # 創建關係
        for rel in relationships:
            props_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in rel["properties"].items()])
            cypher = f"""
MATCH (a {{name: {json.dumps(rel["from"])}}})
MATCH (b {{name: {json.dumps(rel["to"])}}})
CREATE (a)-[:{rel["type"]} {{{props_str}}}]->(b);
"""
            cypher_statements.append(cypher.strip())

        # 保存腳本
        script_file = os.path.join(self.config.output_dir, "unified_neo4j_import.cypher")
        with open(script_file, "w", encoding="utf-8") as f:
            for statement in cypher_statements:
                f.write(statement + "\n\n")

        logger.info(f"✅ Neo4j腳本已保存到 {script_file}")


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🎨 統一藝術史爬蟲管理系統")
    print("=" * 50)

    # 配置
    config = CrawlerConfig(
        harvard_api_key="CHANGE_ME_HARVARD_API_KEY",
        harvard_enabled=True,
        harvard_max_pages=3,
        europeana_enabled=True,
        europeana_max_results=500,
        output_dir="unified_crawler_data",
        save_raw_data=True,
        save_mapped_data=True,
        generate_neo4j_script=True,
    )

    # 創建爬蟲管理器
    crawler_manager = UnifiedCrawlerManager(config)

    # 執行爬取
    results = crawler_manager.comprehensive_crawl()

    print("\n" + "=" * 50)
    print("📋 爬取結果摘要:")
    print(f"   處理的數據源: {', '.join(results['sources_processed'])}")
    print(f"   總實體數量: {results['total_entities']}")
    print(f"   總關係數量: {results['total_relationships']}")
    print(f"   錯誤數量: {len(results['errors'])}")

    if results["errors"]:
        print("\n❌ 錯誤詳情:")
        for error in results["errors"]:
            print(f"   - {error}")

    print(f"\n📁 輸出目錄: {config.output_dir}")
    print("🎉 統一爬蟲系統執行完成！")


if __name__ == "__main__":
    main()
