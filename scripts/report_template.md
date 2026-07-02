# {{CATEGORY_NAME}} 淘宝品类选品分析报告

**站点**: 淘宝/天猫 | **分析日期**: {{DATE}} | **模型版本**: {{MODEL_VERSION}}

---

## 一、执行摘要

| 评估维度 | 得分 | 满分 | 等级 |
|---------|------|------|------|
| **市场规模** | {{SCORE_市场规模}}/{{MAX_市场规模}} | {{MAX_市场规模}} | {{LEVEL_市场规模}} |
| **增长潜力** | {{SCORE_增长潜力}}/{{MAX_增长潜力}} | {{MAX_增长潜力}} | {{LEVEL_增长潜力}} |
| **竞争烈度** | {{SCORE_竞争烈度}}/{{MAX_竞争烈度}} | {{MAX_竞争烈度}} | {{LEVEL_竞争烈度}} |
| **进入壁垒** | {{SCORE_进入壁垒}}/{{MAX_进入壁垒}} | {{MAX_进入壁垒}} | {{LEVEL_进入壁垒}} |
| **利润空间** | {{SCORE_利润空间}}/{{MAX_利润空间}} | {{MAX_利润空间}} | {{LEVEL_利润空间}} |
| **总分** | **{{SCORE_总分}}/{{MAX_总分}}** | {{MAX_总分}} | **{{RATING}}** |

**选品建议**: {{RECOMMENDATION}}

---

## 二、市场概况

### 2.1 关键指标

| 指标 | 数值 |
|------|------|
| 搜索关键词 | {{QUERY}} |
| 分析产品数量 | {{PRODUCT_COUNT}} |
| 预估总销量 | {{TOTAL_SALES}} 件 |
| 预估月销额 | {{TOTAL_REVENUE}} |
| 平均价格 | {{AVG_PRICE}} |
| 中位数价格 | {{MEDIAN_PRICE}} |
| 价格区间 | {{PRICE_RANGE}} |
| 天猫店占比 | {{TMALL_RATIO}} |
| 旗舰店占比 | {{FLAGSHIP_RATIO}} |
| 直通车广告占比 | {{AD_RATIO}} |
| 百亿补贴折价指数 | {{SUBSIDY_INDEX}} |

### 2.2 数据质量

| 指标 | 数值 |
|------|------|
| 上市时间数据覆盖率 | {{LISTING_COVERAGE}} |
| 增长潜力数据层级 | {{GROWTH_TIER}} |
| HHI数据来源 | {{HHI_SOURCE}} |
| 品牌数据覆盖率 | {{BRAND_COVERAGE}} |

### 2.3 市场集中度

| 指标 | 数值 |
|------|------|
| 店铺 CR3 (前三集中度) | {{CR3_STORE}} |
| 品牌 CR3 (前三集中度) | {{CR3_BRAND}} |
| HHI 指数 | {{HHI}} |
| 平均同类商品数 | {{AVG_SAME_COUNT}} |

---

## 三、五维评分详情

### 3.1 市场规模 (得分: {{SCORE_市场规模}}/{{MAX_市场规模}})

| 指标 | 数值 |
|------|------|
| 预估月总销量 | {{TOTAL_SALES}} 件 |

### 3.2 增长潜力 (得分: {{SCORE_增长潜力}}/{{MAX_增长潜力}})

| 指标 | 数值 |
|------|------|
| 新品销量占比 | {{NEWNESS_RATIO}} |
| 近6月上架产品数 | {{LISTING_6M_COUNT}} |
| 首单价产品数 | {{FIRST_PRICE_COUNT}} |
| 标题含新品词产品数 | {{NEW_TITLE_COUNT}} |
| 热销爆款标签产品数 | {{HOT_BOMB_COUNT}} |
| 在榜产品数 | {{HOT_LIST_COUNT}} |
| C店销量占比(参考) | {{CSTORE_RATIO}} |

### 3.3 竞争烈度 (得分: {{SCORE_竞争烈度}}/{{MAX_竞争烈度}})

| 指标 | 数值 |
|------|------|
| 店铺 CR3 | {{CR3_STORE}} |
| 品牌 CR3 | {{CR3_BRAND}} |
| HHI 指数 | {{HHI}} |
| 平均同类商品数 | {{AVG_SAME_COUNT}} |

### 3.4 进入壁垒 (得分: {{SCORE_进入壁垒}}/{{MAX_进入壁垒}})

| 指标 | 数值 |
|------|------|
| 壁垒类型 | {{BARRIER_TYPE}} |
| 天猫店占比 | {{TMALL_RATIO}} |
| 旗舰店占比 | {{FLAGSHIP_RATIO}} |
| 百亿补贴折价指数 | {{SUBSIDY_INDEX}} |

### 3.5 利润空间 (得分: {{SCORE_利润空间}}/{{MAX_利润空间}})

| 指标 | 数值 |
|------|------|
| 平均价格 | {{AVG_PRICE}} |
| 中位数价格 | {{MEDIAN_PRICE}} |
| 价格区间 | {{PRICE_RANGE}} |

### 3.6 价格带分布

{{PRICE_BANDS_TABLE}}

---

## 四、品牌分析

{{BRANDS_TABLE}}

---

## 五、Top 店铺

{{TOP_SHOPS_TABLE}}

{{SHOP_TYPE_DIST}}

### 5.1 1688采购成本对标

{{1688_INSIGHT}}

### 5.2 发货地集中度

{{LOCATION_DIST}}

---

## 六、Top 10 产品详情

| 排名 | 产品 | 价格 | 月销量 | 店铺 | 品牌 | 类型 | 新品 |
|------|------|------|--------|------|------|------|:--:|
{{PRODUCTS_TABLE}}

---

## 七、深度分析报告

> 以下内容由 Claude 基于上述数据撰写，非规则引擎生成。

{{LLM_ANALYSIS}}

---

*本报告由 Taobao Category Score v4 自动生成 | 数据来源: 淘宝/天猫实时搜索数据 (via bb-browser)*
*深度分析: Claude (LLM) | 报告时间: {{DATE}}*
