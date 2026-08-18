// ==========================================
// 為 Neo4j 資料庫添加資料來源標記
// ==========================================

// 1. 為 WikiArt 藝術家添加來源
MATCH (a:Artist)
WHERE a.url IS NOT NULL
  AND (a.url CONTAINS 'wikiart' OR a.url CONTAINS 'WikiArt')
  AND a.original_source IS NULL
SET a.original_source = 'WikiArt',
    a.source_type = 'api',
    a.source_url = a.url,
    a.source_database = 'neo4j',
    a.source_collection = 'graph_database'
RETURN count(a) as wikiart_artists;

// 2. 為 Met Museum 藝術家添加來源（透過作品關聯）
MATCH (a:Artist)<-[:CREATED_BY]-(w:Artwork)
WHERE w.objectID IS NOT NULL
  AND a.original_source IS NULL
WITH DISTINCT a
SET a.original_source = 'Met Museum API',
    a.source_type = 'api',
    a.source_database = 'neo4j',
    a.source_collection = 'graph_database'
RETURN count(a) as met_artists;

// 3. 為 Met Museum 作品添加來源
MATCH (w:Artwork)
WHERE w.objectID IS NOT NULL
  AND w.original_source IS NULL
SET w.original_source = 'Met Museum API',
    w.source_type = 'api',
    w.source_url = 'https://www.metmuseum.org/art/collection/search/' + toString(w.objectID),
    w.source_database = 'neo4j',
    w.source_collection = 'graph_database'
RETURN count(w) as met_artworks;

// 4. 為其他來源的作品添加標記
MATCH (w:Artwork)
WHERE w.objectID IS NULL
  AND w.original_source IS NULL
SET w.original_source = 'Internal Knowledge Base',
    w.source_type = 'curated',
    w.source_database = 'neo4j',
    w.source_collection = 'graph_database'
RETURN count(w) as other_artworks;

// 5. 驗證更新 - 統計各來源的數量
MATCH (a:Artist)
WHERE a.original_source = 'WikiArt'
RETURN 'WikiArt Artists' as type, count(a) as count
UNION ALL
MATCH (a:Artist)
WHERE a.original_source = 'Met Museum API'
RETURN 'Met Museum Artists' as type, count(a) as count
UNION ALL
MATCH (w:Artwork)
WHERE w.original_source = 'Met Museum API'
RETURN 'Met Museum Artworks' as type, count(w) as count
UNION ALL
MATCH (w:Artwork)
WHERE w.original_source = 'Internal Knowledge Base'
RETURN 'Internal Artworks' as type, count(w) as count
UNION ALL
MATCH (n)
WHERE (n:Artist OR n:Artwork)
  AND n.original_source IS NULL
RETURN 'Unmarked Nodes' as type, count(n) as count;
