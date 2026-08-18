require('dotenv').config();
const axios = require('axios');
const fs = require('fs');

const GOOGLE_BOOKS_API_KEY = process.env.GOOGLE_BOOKS_API_KEY;
if (!GOOGLE_BOOKS_API_KEY) {
    console.error('❌ 缺少 GOOGLE_BOOKS_API_KEY 環境變數。請在 .env 設定後再執行。');
    console.error('   申請網址: https://developers.google.com/books/docs/v1/using#APIKey');
    process.exit(1);
}

// 沒有 API Key 時，Google Books API 會把請求歸類到依 IP 共用的匿名額度桶子（額度極低，
// 且跟其他人共用），非常容易撞到 429；帶上 key 後改用自己專案的配額（免費額度預設每日 1000 次）。
// 撞到 429 時依 Retry-After（若有提供）或指數退避重試，而不是直接放棄該筆查詢。
async function fetchWithRetry(url, maxRetries = 3) {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await axios.get(url);
        } catch (error) {
            const status = error.response?.status;
            if (status === 429 && attempt < maxRetries) {
                const retryAfterHeader = error.response?.headers?.['retry-after'];
                const waitMs = retryAfterHeader
                    ? parseInt(retryAfterHeader, 10) * 1000
                    : 2000 * Math.pow(2, attempt); // 2s, 4s, 8s...
                console.warn(`   ⏳ 429 頻率限制，等待 ${(waitMs / 1000).toFixed(0)} 秒後重試（第 ${attempt + 1}/${maxRetries} 次）...`);
                await new Promise(resolve => setTimeout(resolve, waitMs));
                continue;
            }
            throw error;
        }
    }
}

async function fetchGoogleBooksArt() {
    try {
        console.log('📚 開始爬取Google Books藝術史資料...');

        const queries = [
            '藝術史',
            'art history',
            'renaissance art',
            'impressionism',
            '巴洛克藝術',
            'modern art'
        ];

        const allBooks = [];

        for (const query of queries) {
            try {
                console.log(`🔍 搜索: ${query}`);

                const url = `https://www.googleapis.com/books/v1/volumes?q=${encodeURIComponent(query)}&maxResults=5&langRestrict=zh-TW,en&key=${GOOGLE_BOOKS_API_KEY}`;
                const response = await fetchWithRetry(url);

                if (response.data.items) {
                    for (const item of response.data.items) {
                        const book = {
                            id: item.id,
                            title: item.volumeInfo.title,
                            authors: item.volumeInfo.authors || [],
                            publisher: item.volumeInfo.publisher,
                            publishedDate: item.volumeInfo.publishedDate,
                            description: item.volumeInfo.description,
                            categories: item.volumeInfo.categories || [],
                            pageCount: item.volumeInfo.pageCount,
                            language: item.volumeInfo.language,
                            previewLink: item.volumeInfo.previewLink,
                            infoLink: item.volumeInfo.infoLink,
                            thumbnail: item.volumeInfo.imageLinks?.thumbnail,
                            source: 'Google Books',
                            searchQuery: query
                        };

                        allBooks.push(book);
                        console.log(`📖 ${book.title} - ${book.authors.join(', ')}`);
                    }
                }

                // 查詢間隔拉長，降低瞬間請求密度
                await new Promise(resolve => setTimeout(resolve, 1500));

            } catch (error) {
                console.warn(`⚠️ 查詢 '${query}' 失敗: ${error.message}`);
            }
        }

        // 去重（基於標題和作者）
        const uniqueBooks = [];
        const seen = new Set();

        for (const book of allBooks) {
            const key = `${book.title}_${book.authors.join(',')}`;
            if (!seen.has(key)) {
                seen.add(key);
                uniqueBooks.push(book);
            }
        }

        // 保存資料
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `data/raw/google_books/google_books_art_${timestamp}.json`;

        fs.writeFileSync(filename, JSON.stringify(uniqueBooks, null, 2));

        console.log(`✅ Google Books爬取完成！共收集 ${uniqueBooks.length} 本藝術史書籍`);
        console.log(`📁 資料保存至: ${filename}`);

        return uniqueBooks;

    } catch (error) {
        console.error('❌ Google Books爬取失敗:', error.message);
    }
}

fetchGoogleBooksArt();