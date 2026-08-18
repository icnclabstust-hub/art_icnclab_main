#!/usr/bin/env python3
"""
重建增強型藝術史知識圖譜
整合所有擴展數據源
"""

import json
import logging
from pathlib import Path

from data_mapper import ArtHistoryDataMapper
from enhanced_graph_builder import EnhancedArtHistoryGraphBuilder

logger = logging.getLogger(__name__)


class GraphRebuilder:
    """知識圖譜重建器"""

    def __init__(self):
        self.builder = EnhancedArtHistoryGraphBuilder()
        self.mapper = ArtHistoryDataMapper()

    def load_expanded_harvard_data(self) -> dict[str, list]:
        """加載擴展的Harvard數據"""
        logger.info("📚 加載擴展的Harvard數據...")

        data = {"objects": [], "people": [], "exhibitions": []}

        base_path = Path("expanded_harvard_data")

        # 加載作品數據
        objects_file = base_path / "expanded_harvard_objects.json"
        if objects_file.exists():
            with open(objects_file, encoding="utf-8") as f:
                data["objects"] = json.load(f)
            logger.info(f"✅ 加載了 {len(data['objects'])} 個作品")

        # 加載人物數據
        people_file = base_path / "expanded_harvard_people.json"
        if people_file.exists():
            with open(people_file, encoding="utf-8") as f:
                data["people"] = json.load(f)
            logger.info(f"✅ 加載了 {len(data['people'])} 個人物")

        # 加載展覽數據
        exhibitions_file = base_path / "expanded_harvard_exhibitions.json"
        if exhibitions_file.exists():
            with open(exhibitions_file, encoding="utf-8") as f:
                data["exhibitions"] = json.load(f)
            logger.info(f"✅ 加載了 {len(data['exhibitions'])} 個展覽")

        return data

    def process_harvard_objects(self, objects: list[dict]) -> None:
        """處理Harvard作品數據"""
        logger.info(f"🎨 處理 {len(objects)} 個Harvard作品...")

        for obj in objects:
            # 基本作品信息
            artwork_data = {
                "title": obj.get("title", ""),
                "id": obj.get("id"),
                "classification": obj.get("classification"),
                "medium": obj.get("medium", ""),
                "technique": obj.get("technique", ""),
                "period": obj.get("period"),
                "culture": obj.get("culture"),
                "dated": obj.get("dated", ""),
                "description": obj.get("description", ""),
                "provenance": obj.get("provenance", ""),
                "url": obj.get("url", ""),
                "images": obj.get("images", []),
            }

            # 添加作品
            self.builder.add_artwork(**artwork_data)

            # 處理關聯的人物（藝術家）
            people = obj.get("people", [])
            for person in people:
                if person.get("role") in ["Artist", "Creator", "Maker"]:
                    artist_name = person.get("name", "")
                    if artist_name:
                        self.builder.add_artist(
                            name=artist_name,
                            biography=person.get("biography", ""),
                            birth_year=person.get("birthyear"),
                            death_year=person.get("deathyear"),
                        )
                        # 建立創作關係
                        self.builder.add_relationship(
                            artist_name, artwork_data["title"], "CREATED", source="Harvard_Objects"
                        )

            # 處理展覽關係
            exhibitions = obj.get("exhibitions", [])
            for exhibition in exhibitions:
                exhibition_title = exhibition.get("title", "")
                if exhibition_title:
                    self.builder.add_exhibition(
                        title=exhibition_title,
                        start_date=exhibition.get("begindate"),
                        end_date=exhibition.get("enddate"),
                    )
                    self.builder.add_relationship(
                        artwork_data["title"],
                        exhibition_title,
                        "EXHIBITED_IN",
                        source="Harvard_Objects",
                    )

    def process_harvard_people(self, people: list[dict]) -> None:
        """處理Harvard人物數據"""
        logger.info(f"👥 處理 {len(people)} 個Harvard人物...")

        for person in people:
            self.builder.add_artist(
                name=person.get("displayname", ""),
                full_name=person.get("name", ""),
                biography=person.get("biography", ""),
                birth_year=person.get("birthyear"),
                death_year=person.get("deathyear"),
                nationality=person.get("nationality", ""),
                url=person.get("url", ""),
            )

    def process_harvard_exhibitions(self, exhibitions: list[dict]) -> None:
        """處理Harvard展覽數據"""
        logger.info(f"🖼️ 處理 {len(exhibitions)} 個Harvard展覽...")

        for exhibition in exhibitions:
            self.builder.add_exhibition(
                title=exhibition.get("title", ""),
                description=exhibition.get("description", ""),
                start_date=exhibition.get("begindate"),
                end_date=exhibition.get("enddate"),
                venue=exhibition.get("venue", ""),
                url=exhibition.get("url", ""),
            )

    def rebuild_complete_graph(self) -> None:
        """重建完整的知識圖譜"""
        logger.info("🏗️ 開始重建完整的藝術史知識圖譜...")

        # 1. 加載擴展的Harvard數據
        harvard_data = self.load_expanded_harvard_data()

        # 2. 處理Harvard數據
        if harvard_data["objects"]:
            self.process_harvard_objects(harvard_data["objects"])

        if harvard_data["people"]:
            self.process_harvard_people(harvard_data["people"])

        if harvard_data["exhibitions"]:
            self.process_harvard_exhibitions(harvard_data["exhibitions"])

        # 3. 添加原有的增強數據
        logger.info("🔄 添加增強數據...")
        self.builder.add_comprehensive_enhanced_data()

        # 4. 建立增強關係
        logger.info("🔗 建立增強關係...")
        self.builder.build_enhanced_relationships()

        # 5. 保存完整圖譜
        logger.info("💾 保存重建的知識圖譜...")
        self.builder.save_enhanced_data("rebuilt_enhanced_graph")

        # 6. 生成Neo4j腳本
        logger.info("📝 生成Neo4j導入腳本...")
        cypher_script = self.builder.generate_neo4j_script()

        with open("rebuilt_enhanced_neo4j_import.cypher", "w", encoding="utf-8") as f:
            f.write(cypher_script)

        logger.info("✅ 重建完成！")

        # 統計信息
        stats = self.builder.get_statistics()
        logger.info("📊 圖譜統計:")
        logger.info(f"   🎨 作品: {stats.get('artworks', 0)}")
        logger.info(f"   👥 藝術家: {stats.get('artists', 0)}")
        logger.info(f"   🖼️ 展覽: {stats.get('exhibitions', 0)}")
        logger.info(f"   🏛️ 博物館: {stats.get('museums', 0)}")
        logger.info(f"   🔗 關係: {stats.get('relationships', 0)}")


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🚀 重建增強型藝術史知識圖譜")
    print("=" * 60)

    rebuilder = GraphRebuilder()

    try:
        rebuilder.rebuild_complete_graph()

        print("\n" + "=" * 60)
        print("🎉 知識圖譜重建完成！")
        print("📁 生成的文件:")
        print("   - rebuilt_enhanced_graph_*.json")
        print("   - rebuilt_enhanced_neo4j_import.cypher")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ 重建失敗: {e}")
        raise


if __name__ == "__main__":
    main()
