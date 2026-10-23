/**
 * 資料驗證與清理機制測試
 */

const { ArtDataCleaner, TextCleaner, NumberCleaner, DataQualityChecker } = require('../src/utils/dataCleaner');
const { validateArtwork } = require('../src/api/validators/artworkValidator');
const { validateArtist } = require('../src/api/validators/artistValidator');

describe('資料驗證與清理機制測試', () => {

    describe('文本清理測試', () => {
        test('應該正確清理和標準化文本', () => {
            const dirtyText = '  這是一個  測試\n\n文本   \t  ';
            const cleaned = TextCleaner.cleanText(dirtyText);
            expect(cleaned).toBe('這是一個 測試 文本');
        });

        test('應該移除控制字符', () => {
            const dirtyText = '測試\u0000\u0008文本\u007F';
            const cleaned = TextCleaner.cleanText(dirtyText);
            expect(cleaned).toBe('測試文本');
        });

        test('應該限制文本長度', () => {
            const longText = 'a'.repeat(100);
            const cleaned = TextCleaner.cleanText(longText, { maxLength: 50 });
            expect(cleaned.length).toBeLessThanOrEqual(53); // 包含 '...'
        });

        test('應該清理URL', () => {
            const urls = [
                'https://example.com',
                'invalid-url',
                'http://test.com',
                '',
                'ftp://invalid.com'
            ];
            const cleaned = TextCleaner.cleanUrls(urls);
            expect(cleaned).toHaveLength(2);
            expect(cleaned).toContain('https://example.com');
            expect(cleaned).toContain('http://test.com');
        });
    });

    describe('數值清理測試', () => {
        test('應該正確清理年份', () => {
            expect(NumberCleaner.cleanYear(1990)).toBe(1990);
            expect(NumberCleaner.cleanYear('1990')).toBe(1990);
            expect(NumberCleaner.cleanYear('約1990年')).toBe(1990);
            expect(NumberCleaner.cleanYear(-100)).toBe(-100);
            expect(NumberCleaner.cleanYear(-5000)).toBeNull(); // 超出範圍
            expect(NumberCleaner.cleanYear(3000)).toBeNull(); // 超出範圍
        });

        test('應該清理尺寸字符串', () => {
            const dimensions = '100 x 200 cm';
            const cleaned = NumberCleaner.cleanDimensions(dimensions);
            expect(cleaned).toBe('100 × 200 cm');
        });
    });

    describe('藝術作品資料清理測試', () => {
        test('應該正確清理藝術作品資料', () => {
            const dirtyData = {
                title: '  蒙娜麗莎   ',
                title_variants: ['Mona Lisa', '蒙娜麗莎', '', '  La Gioconda  '],
                creation_year: '1506',
                medium: '  油畫  ',
                dimensions: '77 x 53 cm',
                description: '  達文西最著名的作品之一\n\n包含神秘的微笑   ',
                source_urls: ['https://example.com', 'invalid-url', 'https://test.com'],
                metadata: { test: 'value' }
            };

            const cleaned = ArtDataCleaner.cleanArtworkData(dirtyData);

            expect(cleaned.title).toBe('蒙娜麗莎');
            expect(cleaned.title_variants).toHaveLength(2); // 排除重複和空值
            expect(cleaned.creation_year).toBe(1506);
            expect(cleaned.medium).toBe('油畫');
            expect(cleaned.dimensions).toBe('77 × 53 cm');
            expect(cleaned.description).toContain('達文西最著名的作品之一');
            expect(cleaned.source_urls).toHaveLength(2); // 只保留有效URL
        });

        test('應該處理無效的藝術作品資料', () => {
            expect(() => {
                ArtDataCleaner.cleanArtworkData(null);
            }).toThrow('無效的藝術作品資料');

            expect(() => {
                ArtDataCleaner.cleanArtworkData('invalid');
            }).toThrow('無效的藝術作品資料');
        });
    });

    describe('藝術家資料清理測試', () => {
        test('應該正確清理藝術家資料', () => {
            const dirtyData = {
                name: '  李奧納多·達文西  ',
                name_variants: ['Leonardo da Vinci', 'Leonardo', ''],
                birth_year: '1452',
                death_year: '1519',
                nationality: '  義大利  ',
                art_movement: '  文藝復興  ',
                biography: '  義大利文藝復興時期的博學者\n\n被認為是歷史上最偉大的天才之一   '
            };

            const cleaned = ArtDataCleaner.cleanArtistData(dirtyData);

            expect(cleaned.name).toBe('李奧納多·達文西');
            expect(cleaned.name_variants).toHaveLength(2);
            expect(cleaned.birth_year).toBe(1452);
            expect(cleaned.death_year).toBe(1519);
            expect(cleaned.nationality).toBe('義大利');
            expect(cleaned.art_movement).toBe('文藝復興');
            expect(cleaned.biography).toContain('義大利文藝復興時期的博學者');
        });

        test('應該驗證年份邏輯', () => {
            const invalidData = {
                name: '測試藝術家',
                birth_year: '1500',
                death_year: '1400' // 死亡年份早於出生年份
            };

            const cleaned = ArtDataCleaner.cleanArtistData(invalidData);
            expect(cleaned.birth_year).toBe(1500);
            expect(cleaned.death_year).toBeNull(); // 應該被清除
        });
    });

    describe('批量資料清理測試', () => {
        test('應該正確處理批量藝術作品資料', () => {
            const dataArray = [
                { title: '作品1', creation_year: '2000' },
                { title: '作品2', creation_year: 'invalid' },
                { title: '作品3' }
            ];

            const result = ArtDataCleaner.bulkCleanData(dataArray, 'artwork');

            expect(result.success).toHaveLength(3);
            expect(result.errors).toHaveLength(0);
            expect(result.success[0].creation_year).toBe(2000);
            expect(result.success[1].creation_year).toBeNull();
        });

        test('應該處理無效的批量資料', () => {
            expect(() => {
                ArtDataCleaner.bulkCleanData('invalid', 'artwork');
            }).toThrow('資料必須是數組格式');
        });
    });

    describe('資料品質檢查測試', () => {
        test('應該檢查資料完整性', () => {
            const data = {
                title: '測試作品',
                artist_id: 'test-id',
                description: '描述'
            };

            const result = DataQualityChecker.checkCompleteness(
                data,
                ['title', 'artist_id', 'medium']
            );

            expect(result.score).toBeCloseTo(0.67, 2); // 2/3
            expect(result.missing).toContain('medium');
            expect(result.present).toContain('title');
            expect(result.present).toContain('artist_id');
        });

        test('應該檢查資料一致性', () => {
            const invalidData = {
                birth_year: 1500,
                death_year: 1400,
                source_urls: ['https://example.com', 'invalid-url']
            };

            const result = DataQualityChecker.checkConsistency(invalidData);
            expect(result.isConsistent).toBe(false);
            expect(result.issues).toHaveLength(2);
            expect(result.issues[0]).toContain('早於');
            expect(result.issues[1]).toContain('無效');
        });
    });

    describe('驗證器測試', () => {
        test('應該正確驗證藝術作品資料', () => {
            const validData = {
                title: '測試作品',
                creation_year: 2000,
                medium: '油畫',
                description: '這是一個測試作品'
            };

            const result = validateArtwork(validData);
            expect(result.error).toBeNull();
            expect(result.value.title).toBe('測試作品');
        });

        test('應該拒絕無效的藝術作品資料', () => {
            const invalidData = {
                title: '', // 空標題
                creation_year: -5000, // 超出範圍
                source_urls: ['invalid-url'] // 無效URL
            };

            const result = validateArtwork(invalidData);
            expect(result.error).not.toBeNull();
            expect(result.error.details.length).toBeGreaterThan(0);
        });

        test('應該正確驗證藝術家資料', () => {
            const validData = {
                name: '測試藝術家',
                birth_year: 1900,
                death_year: 2000,
                nationality: '台灣'
            };

            const result = validateArtist(validData);
            expect(result.error).toBeNull();
            expect(result.value.name).toBe('測試藝術家');
        });

        test('應該拒絕無效的藝術家資料', () => {
            const invalidData = {
                name: '', // 空名稱
                birth_year: -5000, // 超出範圍
                death_year: 1800 // 早於出生年份
            };

            const result = validateArtist(invalidData);
            expect(result.error).not.toBeNull();
            expect(result.error.details.length).toBeGreaterThan(0);
        });
    });

    describe('整合測試', () => {
        test('應該完整處理從清理到驗證的流程', () => {
            const dirtyData = {
                title: '  測試作品  ',
                creation_year: '2000',
                medium: '  油畫  ',
                description: '  這是一個測試作品\n\n包含多餘的空白   ',
                source_urls: ['https://example.com', 'invalid-url']
            };

            // 先清理
            const cleanedData = ArtDataCleaner.cleanArtworkData(dirtyData);

            // 再驗證
            const validationResult = validateArtwork(cleanedData);

            expect(validationResult.error).toBeNull();
            expect(validationResult.value.title).toBe('測試作品');
            expect(validationResult.value.creation_year).toBe(2000);
            expect(validationResult.value.medium).toBe('油畫');
            expect(validationResult.value.source_urls).toHaveLength(1);

            // 品質檢查
            const qualityCheck = DataQualityChecker.checkConsistency(validationResult.value);
            expect(qualityCheck.isConsistent).toBe(true);
        });
    });
});