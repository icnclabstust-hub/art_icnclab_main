/**
 * ESLint flat config（eslint 9+）
 *
 * 設計原則（沿用前身 repo chore/coding-style 分支的拍板，原檔未隨搬遷保留，
 * 依 CODING_STYLE.md 精神重建）：
 * - 只管邏輯不管排版——排版全權交給 Prettier（G-02：格式爭論交給 formatter 終結）
 * - no-console 降為 warn：爬蟲與腳本以 console 輸出進度是本專案既定慣例
 * - no-unused-vars 降為 warn 並允許底線前綴：與 Python 側 ruff F841 的處理一致
 */
const js = require('@eslint/js');
const globals = require('globals');

module.exports = [
  {
    ignores: [
      'node_modules/**',
      'venv/**',
      'coverage/**',
      'db_backups/**',
      'public/**', // 目前僅 HTML；若日後放前端 JS，需另立 browser globals 區塊
    ],
  },
  js.configs.recommended,
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'commonjs',
      globals: {
        ...globals.node,
      },
    },
    rules: {
      // 邏輯類維持 error（來自 recommended），以下為專案調整：
      'no-console': 'warn',
      'no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      'no-return-await': 'warn',
      // 空 catch 常見於「探測性呼叫」，要求至少留註解說明
      'no-empty': ['error', { allowEmptyCatch: false }],
    },
  },
  {
    // OpenWebUI 介面用腳本，跑在瀏覽器不在 Node
    files: ['openwebui-config/**/*.js'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  },
  {
    files: ['tests/**/*.js', 'jest.config.js', '**/*.test.js'],
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.jest,
      },
    },
  },
];
