/**
 * 藝術家資料驗證器
 * 使用Joi進行資料驗證
 */

const Joi = require('joi');

// 藝術家基礎結構驗證
const artistSchema = Joi.object({
    name: Joi.string()
        .min(1)
        .max(200)
        .required()
        .messages({
            'string.empty': '藝術家姓名不能為空',
            'string.max': '藝術家姓名不能超過200個字符',
            'any.required': '藝術家姓名為必填項'
        }),

    name_variants: Joi.array()
        .items(Joi.string().max(200))
        .max(20)
        .optional()
        .messages({
            'array.max': '姓名變體不能超過20個',
            'string.max': '單個姓名變體不能超過200個字符'
        }),

    birth_year: Joi.number()
        .integer()
        .min(-3000)
        .max(new Date().getFullYear())
        .optional()
        .messages({
            'number.min': '出生年份不能早於公元前3000年',
            'number.max': '出生年份不能超過當前年份'
        }),

    death_year: Joi.number()
        .integer()
        .min(Joi.ref('birth_year'))
        .max(new Date().getFullYear())
        .optional()
        .messages({
            'number.min': '死亡年份不能早於出生年份',
            'number.max': '死亡年份不能超過當前年份'
        }),

    nationality: Joi.string()
        .max(100)
        .optional()
        .messages({
            'string.max': '國籍不能超過100個字符'
        }),

    art_movement: Joi.string()
        .max(100)
        .optional()
        .messages({
            'string.max': '藝術運動不能超過100個字符'
        }),

    biography: Joi.string()
        .max(10000)
        .optional()
        .messages({
            'string.max': '傳記不能超過10000個字符'
        }),

    source_urls: Joi.array()
        .items(Joi.string().uri().max(1000))
        .max(20)
        .optional()
        .messages({
            'array.max': '來源URL不能超過20個',
            'string.uri': '必須是有效的URL格式'
        }),

    metadata: Joi.object()
        .optional()
        .messages({
            'object.base': '元數據必須是對象格式'
        })
});

// 更新時的驗證（所有字段都是可選的）
const artistUpdateSchema = artistSchema.fork(
    ['name'],
    (schema) => schema.optional()
);

// 搜索參數驗證
const artistSearchSchema = Joi.object({
    q: Joi.string()
        .min(1)
        .max(200)
        .required()
        .messages({
            'string.empty': '搜索關鍵字不能為空',
            'string.max': '搜索關鍵字不能超過200個字符',
            'any.required': '搜索關鍵字為必填項'
        }),

    nationality: Joi.string()
        .max(100)
        .optional(),

    art_movement: Joi.string()
        .max(100)
        .optional(),

    birth_year_min: Joi.number()
        .integer()
        .min(-3000)
        .optional(),

    birth_year_max: Joi.number()
        .integer()
        .min(Joi.ref('birth_year_min'))
        .max(new Date().getFullYear())
        .optional(),

    limit: Joi.number()
        .integer()
        .min(1)
        .max(100)
        .default(20)
        .optional(),

    page: Joi.number()
        .integer()
        .min(1)
        .default(1)
        .optional()
});

// 批量操作驗證
const bulkCreateArtistsSchema = Joi.object({
    artists: Joi.array()
        .items(artistSchema)
        .min(1)
        .max(50)
        .required()
        .messages({
            'array.min': '至少需要一個藝術家數據',
            'array.max': '批量創建不能超過50個藝術家',
            'any.required': '藝術家數組為必填項'
        })
});

// 驗證函數
const validateArtist = (data, isUpdate = false) => {
    const schema = isUpdate ? artistUpdateSchema : artistSchema;
    return schema.validate(data, {
        abortEarly: false,
        allowUnknown: false,
        stripUnknown: true
    });
};

const validateArtistSearch = (data) => {
    return artistSearchSchema.validate(data, {
        abortEarly: false,
        allowUnknown: true,
        stripUnknown: true
    });
};

const validateBulkCreateArtists = (data) => {
    return bulkCreateArtistsSchema.validate(data, {
        abortEarly: false,
        allowUnknown: false,
        stripUnknown: true
    });
};

// 中間件
const validateArtistMiddleware = (isUpdate = false) => {
    return (req, res, next) => {
        const { error, value } = validateArtist(req.body, isUpdate);

        if (error) {
            return res.status(400).json({
                success: false,
                message: '資料驗證失敗',
                errors: error.details.map(detail => ({
                    field: detail.path.join('.'),
                    message: detail.message,
                    value: detail.context?.value
                }))
            });
        }

        req.body = value;
        next();
    };
};

const validateArtistSearchMiddleware = () => {
    return (req, res, next) => {
        const { error, value } = validateArtistSearch(req.query);

        if (error) {
            return res.status(400).json({
                success: false,
                message: '搜索參數驗證失敗',
                errors: error.details.map(detail => ({
                    field: detail.path.join('.'),
                    message: detail.message,
                    value: detail.context?.value
                }))
            });
        }

        req.query = { ...req.query, ...value };
        next();
    };
};

module.exports = {
    artistSchema,
    artistUpdateSchema,
    artistSearchSchema,
    bulkCreateArtistsSchema,
    validateArtist,
    validateArtistSearch,
    validateBulkCreateArtists,
    validateArtistMiddleware,
    validateArtistSearchMiddleware
};