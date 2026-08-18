#!/usr/bin/env python3
"""
通用資料匯入器
統一處理PDF、JSON、TXT等多種格式的本地資料
"""

import logging
import sys
from pathlib import Path
from typing import Any

# 添加路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .json_processor import JSONProcessor
from .pdf_processor import PDFProcessor
from .text_processor import TextProcessor

logger = logging.getLogger(__name__)

try:
    import chromadb
    import requests
    from neo4j import GraphDatabase

    HAS_DATABASE_LIBS = True
except ImportError:
    HAS_DATABASE_LIBS = False
    logger.warning("資料庫套件未安裝，僅支援檔案處理")


class UniversalDataImporter:
    """通用資料匯入器"""

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "CHANGE_ME_NEO4J_PASSWORD",
        chromadb_host: str = "localhost",
        chromadb_port: int = 8001,
        ollama_url: str = "http://localhost:11434",
    ):

        # 註冊處理器
        self.processors = [PDFProcessor(), JSONProcessor(), TextProcessor()]

        # 資料庫配置
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.chromadb_host = chromadb_host
        self.chromadb_port = chromadb_port
        self.ollama_url = ollama_url

        # 統計
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_artworks": 0,
            "imported_to_neo4j": 0,
            "imported_to_chromadb": 0,
        }

    def import_file(
        self, file_path: Path, save_to_neo4j: bool = True, save_to_chromadb: bool = True
    ) -> list[dict[str, Any]]:
        """
        匯入單一檔案

        Args:
            file_path: 檔案路徑
            save_to_neo4j: 是否儲存到Neo4j
            save_to_chromadb: 是否儲存到ChromaDB

        Returns:
            List[Dict]: 提取的藝術品資料
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"❌ 檔案不存在: {file_path}")
            return []

        logger.info(f"\n{'=' * 60}")
        logger.info(f"📂 開始處理: {file_path.name}")
        logger.info(f"{'=' * 60}")

        # 選擇處理器
        processor = self._select_processor(file_path)
        if not processor:
            logger.error(f"❌ 不支援的檔案格式: {file_path.suffix}")
            self.stats["failed_files"] += 1
            return []

        # 處理檔案
        try:
            artworks = processor.process(file_path)
            self.stats["total_artworks"] += len(artworks)

            if not artworks:
                logger.warning("⚠️  未能從檔案提取任何資料")
                self.stats["failed_files"] += 1
                return []

            # 儲存到資料庫
            if save_to_neo4j or save_to_chromadb:
                if not HAS_DATABASE_LIBS:
                    logger.error("❌ 資料庫套件未安裝，無法儲存到資料庫")
                    logger.info("請安裝: pip install neo4j chromadb requests")
                else:
                    saved_count = self._save_to_databases(
                        artworks, save_to_neo4j=save_to_neo4j, save_to_chromadb=save_to_chromadb
                    )
                    logger.info(f"💾 成功儲存 {saved_count} 件作品到資料庫")

            self.stats["processed_files"] += 1
            return artworks

        except Exception as e:
            logger.error(f"❌ 處理失敗: {e}", exc_info=True)
            self.stats["failed_files"] += 1
            return []

    def import_directory(
        self,
        directory: Path,
        recursive: bool = True,
        save_to_neo4j: bool = True,
        save_to_chromadb: bool = True,
    ) -> list[dict[str, Any]]:
        """
        匯入整個目錄

        Args:
            directory: 目錄路徑
            recursive: 是否遞迴處理子目錄
            save_to_neo4j: 是否儲存到Neo4j
            save_to_chromadb: 是否儲存到ChromaDB

        Returns:
            List[Dict]: 所有提取的藝術品資料
        """
        directory = Path(directory)

        if not directory.exists() or not directory.is_dir():
            logger.error(f"❌ 目錄不存在: {directory}")
            return []

        logger.info(f"\n{'=' * 60}")
        logger.info(f"📁 掃描目錄: {directory}")
        logger.info(f"{'=' * 60}")

        # 收集所有支援的檔案
        all_files = []
        pattern = "**/*" if recursive else "*"

        for processor in self.processors:
            for ext in processor.supported_extensions:
                files = list(directory.glob(f"{pattern}{ext}"))
                all_files.extend(files)

        if not all_files:
            logger.warning("⚠️  目錄中沒有找到支援的檔案")
            return []

        logger.info(f"🔍 找到 {len(all_files)} 個支援的檔案")
        self.stats["total_files"] = len(all_files)

        # 處理所有檔案
        all_artworks = []
        for file_path in all_files:
            artworks = self.import_file(
                file_path, save_to_neo4j=save_to_neo4j, save_to_chromadb=save_to_chromadb
            )
            all_artworks.extend(artworks)

        return all_artworks

    def _select_processor(self, file_path: Path):
        """選擇適合的處理器"""
        for processor in self.processors:
            if processor.can_process(file_path):
                return processor
        return None

    def _save_to_databases(
        self,
        artworks: list[dict[str, Any]],
        save_to_neo4j: bool = True,
        save_to_chromadb: bool = True,
    ) -> int:
        """儲存到資料庫"""
        saved_count = 0

        # 連接Neo4j
        neo4j_driver = None
        if save_to_neo4j:
            neo4j_driver = self._connect_neo4j()

        # 連接ChromaDB
        chroma_collection = None
        if save_to_chromadb:
            _, chroma_collection = self._connect_chromadb()

        # 儲存每件作品
        for artwork in artworks:
            try:
                if save_to_neo4j and neo4j_driver:
                    self._save_to_neo4j(neo4j_driver, artwork)
                    self.stats["imported_to_neo4j"] += 1

                if save_to_chromadb and chroma_collection:
                    self._save_to_chromadb(chroma_collection, artwork)
                    self.stats["imported_to_chromadb"] += 1

                saved_count += 1

            except Exception as e:
                logger.error(f"❌ 儲存失敗: {artwork.get('title', 'unknown')}: {e}")

        # 關閉連接
        if neo4j_driver:
            neo4j_driver.close()

        return saved_count

    def _connect_neo4j(self):
        """連接Neo4j"""
        try:
            driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
            logger.info("✅ 成功連接 Neo4j")
            return driver
        except Exception as e:
            logger.error(f"❌ Neo4j連接失敗: {e}")
            return None

    def _connect_chromadb(self):
        """連接ChromaDB"""
        try:
            client = chromadb.HttpClient(host=self.chromadb_host, port=self.chromadb_port)
            collection = client.get_or_create_collection(name="art_history_collection")
            logger.info("✅ 成功連接 ChromaDB")
            return client, collection
        except Exception as e:
            logger.error(f"❌ ChromaDB連接失敗: {e}")
            return None, None

    def _save_to_neo4j(self, driver, artwork: dict[str, Any]):
        """儲存到Neo4j"""
        query = """
        MERGE (a:Artwork {id: $id})
        SET a.title = $title,
            a.artist = $artist,
            a.date = $date,
            a.period = $period,
            a.style = $style,
            a.medium = $medium,
            a.dimensions = $dimensions,
            a.location = $location,
            a.description = $description,
            a.source = $source,
            a.imported_at = $imported_at
        """

        # 生成唯一ID
        artwork_id = f"local_{hash(artwork.get('title', '') + artwork.get('artist', ''))}"

        with driver.session() as session:
            session.run(
                query,
                {
                    "id": artwork_id,
                    "title": artwork.get("title", ""),
                    "artist": artwork.get("artist", ""),
                    "date": artwork.get("date", ""),
                    "period": artwork.get("period", ""),
                    "style": artwork.get("style", ""),
                    "medium": artwork.get("medium", ""),
                    "dimensions": artwork.get("dimensions", ""),
                    "location": artwork.get("location", ""),
                    "description": artwork.get("description", ""),
                    "source": artwork.get("source", "local_import"),
                    "imported_at": artwork.get("metadata", {}).get("imported_at", ""),
                },
            )

    def _save_to_chromadb(self, collection, artwork: dict[str, Any]):
        """儲存到ChromaDB"""
        # 生成文檔文本
        doc_text = self._generate_document_text(artwork)

        # 生成嵌入向量
        embedding = self._generate_embedding(doc_text)

        if not embedding:
            logger.warning(f"⚠️  無法生成嵌入向量: {artwork.get('title')}")
            return

        # 生成唯一ID
        artwork_id = f"local_{hash(artwork.get('title', '') + artwork.get('artist', ''))}"

        # 儲存
        collection.add(
            ids=[str(artwork_id)],
            documents=[doc_text],
            embeddings=[embedding],
            metadatas=[
                {
                    "title": artwork.get("title", ""),
                    "artist": artwork.get("artist", ""),
                    "period": artwork.get("period", ""),
                    "source": artwork.get("source", "local_import"),
                }
            ],
        )

    def _generate_document_text(self, artwork: dict[str, Any]) -> str:
        """生成文檔文本"""
        parts = []

        if artwork.get("title"):
            parts.append(f"標題: {artwork['title']}")
        if artwork.get("artist"):
            parts.append(f"藝術家: {artwork['artist']}")
        if artwork.get("date"):
            parts.append(f"年代: {artwork['date']}")
        if artwork.get("period"):
            parts.append(f"時期: {artwork['period']}")
        if artwork.get("description"):
            parts.append(f"描述: {artwork['description']}")

        return "\n".join(parts)

    def _generate_embedding(self, text: str) -> list[float] | None:
        """使用Ollama生成嵌入向量"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=30,
            )

            if response.status_code == 200:
                return response.json().get("embedding")
            else:
                logger.warning(f"⚠️  Ollama API錯誤: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"⚠️  生成嵌入失敗: {e}")
            return None

    def print_stats(self):
        """顯示統計資訊"""
        print("\n" + "=" * 60)
        print("📊 匯入統計")
        print("=" * 60)
        print(f"總檔案數:        {self.stats['total_files']}")
        print(f"成功處理:        {self.stats['processed_files']}")
        print(f"處理失敗:        {self.stats['failed_files']}")
        print(f"提取作品數:      {self.stats['total_artworks']}")
        print(f"儲存到Neo4j:     {self.stats['imported_to_neo4j']}")
        print(f"儲存到ChromaDB:  {self.stats['imported_to_chromadb']}")
        print("=" * 60)
