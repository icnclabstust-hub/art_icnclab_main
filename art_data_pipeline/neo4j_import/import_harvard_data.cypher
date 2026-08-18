// Harvard Art Museums數據導入腳本
// 生成時間: 2025-10-31T16:03:54.385828
// 數據統計: 0件作品, 0位人物, 0個展覽

// 創建約束和索引
CREATE CONSTRAINT IF NOT EXISTS FOR (a:Artwork) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Artist) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Exhibition) REQUIRE e.id IS UNIQUE;

// 導入人物數據

// 導入作品數據

// 導入展覽數據

// 導入完成
// 共導入: 0位人物, 0件作品, 0個展覽