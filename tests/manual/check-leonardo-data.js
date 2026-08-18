const fs = require('fs');
const rawData = JSON.parse(fs.readFileSync('data/raw/renaissance_baroque_2025-10-15T11-42-24-847Z.json', 'utf8'));

// 資料可能是 {artworks: []} 或直接是 []
const data = Array.isArray(rawData) ? rawData : (rawData.artworks || []);

console.log('總作品數量:', data.length);

// 查找Leonardo da Vinci的作品
const leonardo = data.filter(a => a.artist && a.artist.includes('Leonardo da Vinci'));

console.log('\n=== Leonardo da Vinci 創作的作品:', leonardo.length, '件 ===\n');

leonardo.forEach((work, i) => {
    console.log((i+1) + '. ' + work.title);
    console.log('   Artist: ' + work.artist);
    console.log('   Date: ' + (work.date || 'N/A'));
    console.log('   Medium: ' + (work.medium ? work.medium.substring(0, 60) : 'N/A'));
    console.log('   Period: ' + (work.period || 'N/A'));
    console.log();
});

// 檢查資料品質
console.log('\n=== 資料品質檢查 ===');
console.log('有artist欄位的作品:', data.filter(a => a.artist).length);
console.log('有title欄位的作品:', data.filter(a => a.title).length);
console.log('有period欄位的作品:', data.filter(a => a.period).length);
console.log('Renaissance作品:', data.filter(a => a.period && a.period.toLowerCase().includes('renaissance')).length);
console.log('Baroque作品:', data.filter(a => a.period && a.period.toLowerCase().includes('baroque')).length);
