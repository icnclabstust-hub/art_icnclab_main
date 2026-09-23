/**
 * 藝術作品資料驗證器
 * 使用Joi進行資料驗證
 */

const Joi = require('joi');

// 基礎藝術作品結構驗證
const artworkSchema = Joi.object({
    title: Joi.string()
        .min(1)
        .max(500)
        .required()
        .messages({
            'string.empty': '作品標題不能為空',
            'string.max': '作品標題不能超過500個字符',
            'any.required': '作品標題為必填項'
        }),

    title_variants: Joi.array()
        .items(Joi.string().max(500))
        .optional(),

    artist_id: Joi.string()
        .uuid()
        .optional()
        .messages({
            'string.guid': '藝術家ID必須是有效的UUID格式'
        }),

    creation_year: Joi.number()
        .integer()
        .min(-3000)
        .max(new Date().getFullYear() + 10)
        .optional()
        .messages({
            'number.min': '創作年份不能早於公元前3000年',
            'number.max': '創作年份不能超過當前年份'
        }),

    medium: Joi.string()
        .max(200)
        .optional()
        .messages({
            'string.max': '媒材描述不能超過200個字符'
        }),

    dimensions: Joi.string()
        .max(200)
        .optional()
        .messages({
            'string.max': '尺寸描述不能超過200個字符'
        }),

    description: Joi.string()
        .max(5000)
        .optional()
        .messages({
            'string.max': '作品描述不能超過5000個字符'
        }),

    style: Joi.string()
        .max(100)
        .optional()
        .messages({
            'string.max': '風格描述不能超過100個字符'
        }),

    subject_matter: Joi.string()
        .max(200)
        .optional()
        .messages({
            'string.max': '主題內容不能超過200個字符'
        }),

    location: Joi.string()
        .max(300)
        .optional()
        .messages({
            'string.max': '創作地點不能超過300個字符'
        }),

    current_location: Joi.string()
        .max(300)
        .optional()
        .messages({
            'string.max': '現在位置不能超過300個字符'
        }),

    provenance: Joi.string()
        .max(2000)
        .optional()
        .messages({
            'string.max': '來源信息不能超過2000個字符'
        }),

    significance: Joi.string()
        .max(2000)
        .optional()
        .messages({
            'string.max': '藝術史意義不能超過2000個字符'
        }),

    source_urls: Joi.array()
        .items(Joi.string().uri().max(1000))
        .max(10)
        .optional()
        .messages({
            'array.max': '來源URL不能超過10個',
            'string.uri': '必須是有效的URL格式'
        }),

    image_urls: Joi.array()
        .items(Joi.string().uri().max(1000))
        .max(20)
        .optional()
        .messages({
            'array.max': '圖像URL不能超過20個',
            'string.uri': '必須是有效的URL格式'
        }),

    tag_ids: Joi.array()
        .items(Joi.string().uuid())
        .max(50)
        .optional()
        .messages({
            'array.max': '標籤不能超過50個',
            'string.guid': '標籤ID必須是有效的UUID格式'
        }),

    metadata: Joi.object()
        .optional()
        .messages({
            'object.base': '元數據必須是對象格式'
        })
});

// 更新時的驗證（所有字段都是可選的）
const artworkUpdateSchema = artworkSchema.fork(
    ['title'],
    (schema) => schema.optional()
);

// 搜索參數驗證
const searchSchema = Joi.object({
    q: Joi.string()
        .min(1)
        .max(200)
        .required()
        .messages({
            'string.empty': '搜索關鍵字不能為空',
            'string.max': '搜索關鍵字不能超過200個字符',
            'any.required': '搜索關鍵字為必填項'
        }),

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

// 時期搜索參數驗證
const periodSearchSchema = Joi.object({
    start_year: Joi.number()
        .integer()
        .min(-3000)
        .required()
        .messages({
            'number.min': '開始年份不能早於公元前3000年',
            'any.required': '開始年份為必填項'
        }),

    end_year: Joi.number()
        .integer()
        .min(Joi.ref('start_year'))
        .max(new Date().getFullYear() + 10)
        .required()
        .messages({
            'number.min': '結束年份不能早於開始年份',
            'number.max': '結束年份不能超過當前年份',
            'any.required': '結束年份為必填項'
        }),

    limit: Joi.number()
        .integer()
        .min(1)
        .max(200)
        .default(100)
        .optional()
});

// 標籤添加驗證
const addTagsSchema = Joi.object({
    tag_ids: Joi.array()
        .items(Joi.string().uuid())
        .min(1)
        .max(50)
        .required()
        .messages({
            'array.min': '至少需要一個標籤ID',
            'array.max': '標籤不能超過50個',
            'string.guid': '標籤ID必須是有效的UUID格式',
            'any.required': '標籤ID數組為必填項'
        }),

    assigned_by: Joi.string()
        .max(50)
        .default('api')
        .optional()
        .messages({
            'string.max': '分配者標識不能超過50個字符'
        })
});

// 批量操作驗證
const bulkCreateSchema = Joi.object({
    artworks: Joi.array()
        .items(artworkSchema)
        .min(1)
        .max(100)
        .required()
        .messages({
            'array.min': '至少需要一個作品數據',
            'array.max': '批量創建不能超過100個作品',
            'any.required': '作品數組為必填項'
        })
});

// 驗證函數
const validateArtwork = (data, isUpdate = false) => {
    const schema = isUpdate ? artworkUpdateSchema : artworkSchema;
    return schema.validate(data, {
        abortEarly: false,
        allowUnknown: false,
        stripUnknown: true
    });
};

const validateSearch = (data) => {
    return searchSchema.validate(data, {
        abortEarly: false,
        allowUnknown: true,
        stripUnknown: true
    });
};

const validatePeriodSearch = (data) => {
    return periodSearchSchema.validate(data, {
        abortEarly: false,
        allowUnknown: true,
        stripUnknown: true
    });
};

const validateAddTags = (data) => {
    return addTagsSchema.validate(data, {
        abortEarly: false,
        allowUnknown: false,
        stripUnknown: true
    });
};

const validateBulkCreate = (data) => {
    return bulkCreateSchema.validate(data, {
        abortEarly: false,
        allowUnknown: false,
        stripUnknown: true
    });
};

// 自定義驗證中間件
const validateArtworkMiddleware = (isUpdate = false) => {
    return (req, res, next) => {
        const { error, value } = validateArtwork(req.body, isUpdate);

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

const validateSearchMiddleware = () => {
    return (req, res, next) => {
        const { error, value } = validateSearch(req.query);

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
    artworkSchema,
    artworkUpdateSchema,
    searchSchema,
    periodSearchSchema,
    addTagsSchema,
    bulkCreateSchema,
    validateArtwork,
    validateSearch,
    validatePeriodSearch,
    validateAddTags,
    validateBulkCreate,
    validateArtworkMiddleware,
    validateSearchMiddleware
};