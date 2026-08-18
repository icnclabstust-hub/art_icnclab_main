#!/usr/bin/env node
/**
 * Agent功能測試腳本
 * 驗證4個Agent的基本功能和Agent Hub的協調能力
 */

const path = require('path');
const fs = require('fs/promises');

// 導入Agent Hub
const AgentHub = require('../../src/agent-hub');

async function testAgents() {
    console.log('🧪 開始Agent功能測試...\n');

    const hub = new AgentHub();
    let testResults = [];

    try {
        // 1. 測試Agent Hub初始化
        console.log('📋 1. 測試Agent Hub初始化');
        await hub.initialize();
        const status = hub.getStatus();
        console.log('✅ Agent Hub初始化成功');
        console.log(`   狀態: ${status.status}`);
        console.log(`   可用Agent數量: ${Object.keys(status.agents).length}`);
        console.log('');

        testResults.push({
            test: 'Agent Hub初始化',
            status: 'pass',
            details: `${Object.keys(status.agents).length} Agents initialized`
        });

        // 2. 測試單個Agent狀態
        console.log('📋 2. 測試各Agent狀態');
        for (const [name, agent] of Object.entries(status.agents)) {
            if (agent && agent.status) {
                console.log(`   ${name}: ${agent.status}`);
                testResults.push({
                    test: `${name} 狀態檢查`,
                    status: agent.status === 'ready' || agent.status === 'initializing' ? 'pass' : 'fail',
                    details: `狀態: ${agent.status}`
                });
            }
        }
        console.log('');

        // 3. 測試創建測試數據
        console.log('📋 3. 創建測試數據');
        await createTestData();
        console.log('✅ 測試數據創建完成');
        console.log('');

        testResults.push({
            test: '測試數據創建',
            status: 'pass',
            details: '模擬藝術品數據已創建'
        });

        // 4. 測試Agent工作流程（簡化版）
        console.log('📋 4. 測試Agent工作流程');

        // 測試processExisting工作流程
        console.log('   執行 processExisting 工作流程...');
        const workflowResult = await hub.executeWorkflow('processExisting', {
            metadataExtractor: {
                inputSources: ['museums'],
                includeValidation: true
            },
            classification: {
                classificationTypes: ['period', 'style'],
                generateReports: true
            },
            summarizationTranslation: {
                targetLanguages: ['zh-TW'],
                generateSummaries: true,
                generateTranslations: false // 關閉翻譯避免API調用
            }
        });

        if (workflowResult && workflowResult.success) {
            console.log('✅ 工作流程執行成功');
            console.log(`   完成步驟: ${workflowResult.statistics.completedTasks}/${workflowResult.statistics.totalTasks}`);
            testResults.push({
                test: 'processExisting工作流程',
                status: 'pass',
                details: `${workflowResult.statistics.completedTasks}/${workflowResult.statistics.totalTasks} 步驟成功`
            });
        } else {
            console.log('❌ 工作流程執行失敗');
            testResults.push({
                test: 'processExisting工作流程',
                status: 'fail',
                details: '工作流程執行失敗'
            });
        }
        console.log('');

        // 5. 測試自定義工作流程
        console.log('📋 5. 測試自定義工作流程');
        try {
            const customWorkflow = hub.createCustomWorkflow(
                'test_custom',
                ['metadataExtractor', 'classification'],
                '測試用自定義工作流程'
            );
            console.log('✅ 自定義工作流程創建成功');
            console.log(`   名稱: ${customWorkflow.name}`);
            console.log(`   步驟: ${customWorkflow.steps.join(' → ')}`);
            testResults.push({
                test: '自定義工作流程創建',
                status: 'pass',
                details: customWorkflow.name
            });
        } catch (error) {
            console.log('❌ 自定義工作流程創建失敗:', error.message);
            testResults.push({
                test: '自定義工作流程創建',
                status: 'fail',
                details: error.message
            });
        }
        console.log('');

    } catch (error) {
        console.error('❌ 測試過程中發生錯誤:', error.message);
        testResults.push({
            test: '整體測試',
            status: 'fail',
            details: error.message
        });
    } finally {
        // 清理
        console.log('📋 6. 清理測試環境');
        await hub.stop();
        console.log('✅ Agent Hub已停止');
        console.log('');
    }

    // 生成測試報告
    console.log('📊 測試報告');
    console.log('=' * 50);

    const passedTests = testResults.filter(t => t.status === 'pass').length;
    const failedTests = testResults.filter(t => t.status === 'fail').length;
    const totalTests = testResults.length;

    console.log(`總測試數: ${totalTests}`);
    console.log(`通過: ${passedTests}`);
    console.log(`失敗: ${failedTests}`);
    console.log(`成功率: ${Math.round((passedTests / totalTests) * 100)}%`);
    console.log('');

    console.log('詳細結果:');
    testResults.forEach((result, index) => {
        const status = result.status === 'pass' ? '✅' : '❌';
        console.log(`${index + 1}. ${status} ${result.test}`);
        console.log(`   ${result.details}`);
    });

    // 保存測試報告
    const report = {
        timestamp: new Date().toISOString(),
        summary: {
            total: totalTests,
            passed: passedTests,
            failed: failedTests,
            successRate: Math.round((passedTests / totalTests) * 100)
        },
        results: testResults
    };

    const reportPath = path.join(__dirname, 'logs', 'agent-test-report.json');
    await fs.mkdir(path.dirname(reportPath), { recursive: true });
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    console.log(`\n📄 測試報告已保存: ${reportPath}`);

    return passedTests === totalTests;
}

async function createTestData() {
    // 創建測試用的藝術品數據
    const testData = [
        {
            source: 'test',
            objectID: 'test_001',
            title: 'The Starry Night',
            artist: 'Vincent van Gogh',
            date: '1889',
            medium: 'Oil on canvas',
            description: 'A famous post-impressionist painting depicting a swirling night sky',
            classification: 'painting',
            culture: 'Dutch',
            period: 'Post-Impressionism',
            crawledAt: new Date().toISOString()
        },
        {
            source: 'test',
            objectID: 'test_002',
            title: 'Mona Lisa',
            artist: 'Leonardo da Vinci',
            date: '1503-1519',
            medium: 'Oil on poplar wood',
            description: 'Renaissance portrait painting known for its enigmatic smile',
            classification: 'painting',
            culture: 'Italian',
            period: 'Renaissance',
            crawledAt: new Date().toISOString()
        }
    ];

    // 確保測試數據目錄存在
    const testDataDir = path.join(__dirname, 'data', 'raw', 'museums');
    await fs.mkdir(testDataDir, { recursive: true });

    // 保存測試數據
    const testDataPath = path.join(testDataDir, 'test_artworks.json');
    await fs.writeFile(testDataPath, JSON.stringify(testData, null, 2));

    console.log(`   測試數據已保存到: ${testDataPath}`);
}

// 執行測試
if (require.main === module) {
    testAgents()
        .then(success => {
            if (success) {
                console.log('\n🎉 所有測試通過！');
                process.exit(0);
            } else {
                console.log('\n❌ 部分測試失敗');
                process.exit(1);
            }
        })
        .catch(error => {
            console.error('\n💥 測試執行失敗:', error);
            process.exit(1);
        });
}

module.exports = { testAgents };