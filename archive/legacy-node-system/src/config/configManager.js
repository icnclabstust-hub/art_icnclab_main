#!/usr/bin/env node
/**
 * 統一配置管理系統
 * 提供集中化、環境特定、類型安全的配置管理
 */

const fs = require('fs');
const path = require('path');
const EventEmitter = require('events');

class ConfigManager extends EventEmitter {
    constructor(options = {}) {
        super();
        this.options = {
            envFile: options.envFile || '.env',
            configDir: options.configDir || './config',
            environment: options.environment || process.env.NODE_ENV || 'development',
            enableWatch: options.enableWatch !== false,
            enableValidation: options.enableValidation !== false,
            enableCache: options.enableCache !== false
        };

        this.config = {};
        this.schema = {};
        this.watchers = new Map();
        this.cache = new Map();
        this.validators = new Map();

        // 初始化驗證器
        this.initializeValidators();

        // 載入配置
        this.loadConfiguration();

        // 設置文件監視
        if (this.options.enableWatch) {
            this.setupFileWatchers();
        }
    }

    /**
     * 初始化內建驗證器
     */
    initializeValidators() {
        // 數字驗證器
        this.validators.set('number', (value, schema) => {
            const num = Number(value);
            if (isNaN(num)) {
                throw new Error(`Expected number, got ${typeof value}: ${value}`);
            }
            if (schema.min !== undefined && num < schema.min) {
                throw new Error(`Value ${num} is less than minimum ${schema.min}`);
            }
            if (schema.max !== undefined && num > schema.max) {
                throw new Error(`Value ${num} is greater than maximum ${schema.max}`);
            }
            return num;
        });

        // 字符串驗證器
        this.validators.set('string', (value, schema) => {
            const str = String(value);
            if (schema.minLength && str.length < schema.minLength) {
                throw new Error(`String length ${str.length} is less than minimum ${schema.minLength}`);
            }
            if (schema.maxLength && str.length > schema.maxLength) {
                throw new Error(`String length ${str.length} is greater than maximum ${schema.maxLength}`);
            }
            if (schema.pattern && !new RegExp(schema.pattern).test(str)) {
                throw new Error(`String "${str}" does not match pattern ${schema.pattern}`);
            }
            return str;
        });

        // 布林值驗證器
        this.validators.set('boolean', (value, schema) => {
            if (typeof value === 'boolean') return value;
            const str = String(value).toLowerCase();
            if (str === 'true' || str === '1' || str === 'yes') return true;
            if (str === 'false' || str === '0' || str === 'no') return false;
            throw new Error(`Expected boolean, got: ${value}`);
        });

        // 枚舉驗證器
        this.validators.set('enum', (value, schema) => {
            if (!schema.values || !Array.isArray(schema.values)) {
                throw new Error('Enum schema must have values array');
            }
            if (!schema.values.includes(value)) {
                throw new Error(`Value "${value}" is not in allowed values: ${schema.values.join(', ')}`);
            }
            return value;
        });

        // URL驗證器
        this.validators.set('url', (value, schema) => {
            try {
                const url = new URL(value);
                if (schema.protocols && !schema.protocols.includes(url.protocol.slice(0, -1))) {
                    throw new Error(`Protocol "${url.protocol}" is not in allowed protocols: ${schema.protocols.join(', ')}`);
                }
                return value;
            } catch (error) {
                throw new Error(`Invalid URL: ${value}`);
            }
        });

        // 路徑驗證器
        this.validators.set('path', (value, schema) => {
            const resolvedPath = path.resolve(value);
            if (schema.mustExist && !fs.existsSync(resolvedPath)) {
                throw new Error(`Path does not exist: ${resolvedPath}`);
            }
            // 子型別鍵為 pathType：dispatch 已用 type==='path' 選到本 validator，
            // 原本這裡誤寫 schema.type（重複鍵讓 type 變 'directory'，導致查無
            // validator、8 個路徑設定的驗證被靜默跳過）
            if (schema.pathType === 'directory' && fs.existsSync(resolvedPath)) {
                const stat = fs.statSync(resolvedPath);
                if (!stat.isDirectory()) {
                    throw new Error(`Path is not a directory: ${resolvedPath}`);
                }
            }
            if (schema.pathType === 'file' && fs.existsSync(resolvedPath)) {
                const stat = fs.statSync(resolvedPath);
                if (!stat.isFile()) {
                    throw new Error(`Path is not a file: ${resolvedPath}`);
                }
            }
            return resolvedPath;
        });
    }

    /**
     * 載入配置
     */
    loadConfiguration() {
        try {
            // 1. 載入環境文件
            this.loadEnvironmentFile();

            // 2. 載入基礎配置
            this.loadBaseConfiguration();

            // 3. 載入環境特定配置
            this.loadEnvironmentConfiguration();

            // 4. 載入配置模式
            this.loadConfigurationSchema();

            // 5. 驗證配置
            if (this.options.enableValidation) {
                this.validateConfiguration();
            }

            // 6. 處理配置繼承和覆蓋
            this.processConfigurationOverrides();

            console.log(`✅ 配置管理器初始化完成 (環境: ${this.options.environment})`);
            this.emit('configLoaded', this.config);

        } catch (error) {
            console.error(`❌ 配置載入失敗: ${error.message}`);
            throw error;
        }
    }

    /**
     * 載入環境文件
     */
    loadEnvironmentFile() {
        const envFiles = [
            `.env.${this.options.environment}.local`,
            `.env.local`,
            `.env.${this.options.environment}`,
            this.options.envFile
        ];

        for (const envFile of envFiles) {
            const envPath = path.resolve(envFile);
            if (fs.existsSync(envPath)) {
                try {
                    const envContent = fs.readFileSync(envPath, 'utf8');
                    const envVars = this.parseEnvironmentFile(envContent);

                    Object.entries(envVars).forEach(([key, value]) => {
                        if (!Object.prototype.hasOwnProperty.call(process.env, key)) {
                            process.env[key] = value;
                        }
                    });

                    console.log(`📄 載入環境文件: ${envFile}`);
                } catch (error) {
                    console.warn(`⚠️ 無法載入環境文件 ${envFile}: ${error.message}`);
                }
                break;
            }
        }
    }

    /**
     * 解析環境文件
     */
    parseEnvironmentFile(content) {
        const envVars = {};
        const lines = content.split('\n');

        for (let line of lines) {
            line = line.trim();

            // 跳過註釋和空行
            if (!line || line.startsWith('#')) continue;

            const match = line.match(/^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/i);
            if (match) {
                let [, key, value] = match;

                // 移除引號
                if ((value.startsWith('"') && value.endsWith('"')) ||
                    (value.startsWith("'") && value.endsWith("'"))) {
                    value = value.slice(1, -1);
                }

                // 處理變數替換
                value = this.expandVariables(value, envVars);

                envVars[key] = value;
            }
        }

        return envVars;
    }

    /**
     * 變數替換
     */
    expandVariables(value, envVars) {
        return value.replace(/\$\{([A-Z_][A-Z0-9_]*)\}/gi, (match, varName) => {
            return envVars[varName] || process.env[varName] || match;
        });
    }

    /**
     * 載入基礎配置
     */
    loadBaseConfiguration() {
        const baseConfigPath = path.resolve(process.cwd(), 'config', 'default.js');
        if (fs.existsSync(baseConfigPath)) {
            try {
                // 清除 require cache
                if (require.cache[baseConfigPath]) {
                    delete require.cache[baseConfigPath];
                }
                const baseConfig = require(baseConfigPath);
                this.config = this.deepMerge(this.config, baseConfig);
                console.log(`📋 載入基礎配置: ${baseConfigPath}`);
            } catch (error) {
                console.warn(`⚠️ 無法載入基礎配置: ${error.message}`);
            }
        } else {
            console.warn(`⚠️ 基礎配置文件不存在: ${baseConfigPath}`);
        }
    }

    /**
     * 載入環境特定配置
     */
    loadEnvironmentConfiguration() {
        const envConfigPath = path.resolve(process.cwd(), 'config', `${this.options.environment}.js`);
        if (fs.existsSync(envConfigPath)) {
            try {
                // 清除 require cache
                if (require.cache[envConfigPath]) {
                    delete require.cache[envConfigPath];
                }
                const envConfig = require(envConfigPath);
                this.config = this.deepMerge(this.config, envConfig);
                console.log(`🌍 載入環境配置: ${envConfigPath}`);
            } catch (error) {
                console.warn(`⚠️ 無法載入環境配置: ${error.message}`);
            }
        } else {
            console.warn(`⚠️ 環境配置文件不存在: ${envConfigPath}`);
        }
    }

    /**
     * 載入配置模式
     */
    loadConfigurationSchema() {
        const schemaPath = path.resolve(process.cwd(), 'config', 'schema.js');
        if (fs.existsSync(schemaPath)) {
            try {
                // 清除 require cache
                if (require.cache[schemaPath]) {
                    delete require.cache[schemaPath];
                }
                this.schema = require(schemaPath);
                console.log(`📐 載入配置模式: ${schemaPath}`);
            } catch (error) {
                console.warn(`⚠️ 無法載入配置模式: ${error.message}`);
            }
        } else {
            console.warn(`⚠️ 配置模式文件不存在: ${schemaPath}`);
        }
    }

    /**
     * 驗證配置
     */
    validateConfiguration() {
        this.validateConfigurationRecursive(this.config, this.schema);
    }

    /**
     * 遞歸驗證配置
     */
    validateConfigurationRecursive(config, schema, path = '') {
        if (!schema || typeof schema !== 'object') return;

        for (const [key, schemaValue] of Object.entries(schema)) {
            const fullPath = path ? `${path}.${key}` : key;
            const configValue = config[key];

            if (schemaValue.required && (configValue === undefined || configValue === null)) {
                throw new Error(`Required configuration missing: ${fullPath}`);
            }

            if (configValue !== undefined && schemaValue.type) {
                try {
                    const validator = this.validators.get(schemaValue.type);
                    if (validator) {
                        config[key] = validator(configValue, schemaValue);
                    }
                } catch (error) {
                    throw new Error(`Configuration validation failed for ${fullPath}: ${error.message}`);
                }
            }

            // 遞歸驗證嵌套對象
            if (schemaValue.properties && typeof configValue === 'object') {
                this.validateConfigurationRecursive(configValue, schemaValue.properties, fullPath);
            }
        }
    }

    /**
     * 處理配置覆蓋
     */
    processConfigurationOverrides() {
        // 環境變數覆蓋
        this.processEnvironmentOverrides(this.config, this.schema);
    }

    /**
     * 處理環境變數覆蓋
     */
    processEnvironmentOverrides(config, schema, prefix = '') {
        if (!schema || typeof schema !== 'object') return;

        for (const [key, schemaValue] of Object.entries(schema)) {
            const envKey = this.getEnvironmentKey(prefix, key);
            const envValue = process.env[envKey];

            if (envValue !== undefined) {
                try {
                    if (schemaValue.type) {
                        const validator = this.validators.get(schemaValue.type);
                        if (validator) {
                            config[key] = validator(envValue, schemaValue);
                            console.log(`🔧 環境變數覆蓋: ${envKey} -> ${key}`);
                        }
                    } else {
                        config[key] = envValue;
                    }
                } catch (error) {
                    console.warn(`⚠️ 環境變數覆蓋失敗 ${envKey}: ${error.message}`);
                }
            }

            // 遞歸處理嵌套對象
            if (schemaValue.properties && typeof config[key] === 'object') {
                this.processEnvironmentOverrides(config[key], schemaValue.properties, envKey);
            }
        }
    }

    /**
     * 生成環境變數鍵名
     */
    getEnvironmentKey(prefix, key) {
        const envKey = key.replace(/([A-Z])/g, '_$1').toUpperCase();
        return prefix ? `${prefix}_${envKey}` : envKey;
    }

    /**
     * 設置文件監視
     */
    setupFileWatchers() {
        const filesToWatch = [
            path.join(this.options.configDir, 'default.js'),
            path.join(this.options.configDir, `${this.options.environment}.js`),
            path.join(this.options.configDir, 'schema.js'),
            this.options.envFile,
            `.env.${this.options.environment}`
        ];

        filesToWatch.forEach(filePath => {
            if (fs.existsSync(filePath)) {
                const watcher = fs.watchFile(filePath, { interval: 1000 }, () => {
                    console.log(`📁 配置文件變更: ${filePath}`);
                    this.reloadConfiguration();
                });
                this.watchers.set(filePath, watcher);
            }
        });
    }

    /**
     * 重新載入配置
     */
    reloadConfiguration() {
        try {
            this.config = {};
            this.cache.clear();
            this.loadConfiguration();
            this.emit('configReloaded', this.config);
        } catch (error) {
            console.error(`❌ 配置重新載入失敗: ${error.message}`);
            this.emit('configError', error);
        }
    }

    /**
     * 獲取配置值
     */
    get(path, defaultValue = undefined) {
        const cacheKey = `get:${path}`;

        if (this.options.enableCache && this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        const value = this.getNestedValue(this.config, path) ?? defaultValue;

        if (this.options.enableCache) {
            this.cache.set(cacheKey, value);
        }

        return value;
    }

    /**
     * 設置配置值
     */
    set(path, value) {
        this.setNestedValue(this.config, path, value);
        this.cache.clear(); // 清除緩存
        this.emit('configChanged', { path, value });
    }

    /**
     * 檢查配置是否存在
     */
    has(path) {
        return this.getNestedValue(this.config, path) !== undefined;
    }

    /**
     * 獲取嵌套值
     */
    getNestedValue(obj, path) {
        const keys = path.split('.');
        let current = obj;

        for (const key of keys) {
            if (current === null || current === undefined || !Object.prototype.hasOwnProperty.call(current, key)) {
                return undefined;
            }
            current = current[key];
        }

        return current;
    }

    /**
     * 設置嵌套值
     */
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        let current = obj;

        for (const key of keys) {
            if (!current[key] || typeof current[key] !== 'object') {
                current[key] = {};
            }
            current = current[key];
        }

        current[lastKey] = value;
    }

    /**
     * 深度合併對象
     */
    deepMerge(target, source) {
        if (!source || typeof source !== 'object') return target;
        if (!target || typeof target !== 'object') return source;

        const result = { ...target };

        for (const [key, value] of Object.entries(source)) {
            if (value && typeof value === 'object' && !Array.isArray(value)) {
                result[key] = this.deepMerge(result[key], value);
            } else {
                result[key] = value;
            }
        }

        return result;
    }

    /**
     * 獲取所有配置
     */
    getAll() {
        return JSON.parse(JSON.stringify(this.config));
    }

    /**
     * 獲取配置摘要
     */
    getSummary() {
        return {
            environment: this.options.environment,
            configKeys: Object.keys(this.config),
            schemaKeys: Object.keys(this.schema),
            watchers: Array.from(this.watchers.keys()),
            cacheSize: this.cache.size
        };
    }

    /**
     * 導出配置到文件
     */
    async exportConfiguration(filePath, format = 'json') {
        const config = this.getAll();

        let content;
        switch (format.toLowerCase()) {
            case 'json':
                content = JSON.stringify(config, null, 2);
                break;
            case 'yaml':
                // 需要yaml庫
                content = require('yaml').stringify(config);
                break;
            case 'env':
                content = this.configToEnvFormat(config);
                break;
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }

        await fs.promises.writeFile(filePath, content, 'utf8');
        console.log(`📤 配置已導出: ${filePath} (${format.toUpperCase()})`);
    }

    /**
     * 將配置轉換為環境變數格式
     */
    configToEnvFormat(config, prefix = '') {
        let envContent = '';

        for (const [key, value] of Object.entries(config)) {
            const envKey = this.getEnvironmentKey(prefix, key);

            if (value && typeof value === 'object' && !Array.isArray(value)) {
                envContent += this.configToEnvFormat(value, envKey);
            } else {
                envContent += `${envKey}=${value}\n`;
            }
        }

        return envContent;
    }

    /**
     * 清理資源
     */
    destroy() {
        // 停止文件監視
        this.watchers.forEach((watcher, filePath) => {
            fs.unwatchFile(filePath);
        });
        this.watchers.clear();

        // 清除緩存
        this.cache.clear();

        // 移除所有監聽器
        this.removeAllListeners();

        console.log('🧹 配置管理器已清理');
    }
}

module.exports = ConfigManager;