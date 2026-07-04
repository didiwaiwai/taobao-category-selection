# CLAUDE.md

## 项目概述

淘宝/天猫品类选品分析工具。基于五维评分模型对淘宝品类进行深度市场调研，生成 Markdown + Excel + HTML 完整报告。同时集成 1688 mtop API 供应链数据采集。

## 快速执行流程

```bash
# 1. 淘宝数据采集 (五维评分, 后台mtop API)
bb-browser site taobao/category-score <关键词> --json > data.json

# 2. 1688 成本采集 (mtop API, 与淘宝同架构, 180条/3页)
python scripts/collect_1688.py <关键词>

# 3. 生成完整报告 (Markdown + Excel + HTML仪表板)
python scripts/generate_taobao_report.py data.json
```

## 数据采集架构

### 淘宝: mtop 推荐接口 (后台API)
- adapter: `.bb-browser/sites/taobao/category-score.js`
- API: `mtop.relationrecommend.WirelessRecommend.recommend` (appId: 34385)
- 排序: `total-desc` (纯销量排序, 非个性化推荐)
- 每页48条, 默认2页, 支持 --pages 参数
- 无需打开浏览器标签页, 完全后台调用

### 1688: mtop 搜索接口 (与淘宝同架构)
- adapter: `bb-sites/1688/offer-score.js` (项目内) + `~/.bb-browser/sites/1688/`
- API: `mtop.relationrecommend.WirelessRecommend.recommend` (appId: 32517)
- 方法: `getOfferList` (pageSize=60, 每页60条)
- 脚本: `scripts/collect_1688.py` (Python端: GBK URL导航 + 标签页复用)
- 默认3页×60=180条, 关键词匹配100%

## 五维评分模型 (100分)

| 维度 | 分值 | 评估指标 |
|------|:---:|------|
| 市场规模 | 20 | 预估总月销量 |
| 增长潜力 | 25 | 新品占比 + DI动态指数 |
| 竞争烈度 | 20 | 店铺CR3 + HHI + 同类商品数 |
| 进入壁垒 | 20 | 天猫占比 × 新品活跃度交叉矩阵 |
| 利润空间 | 15 | 均价 + 1688批发对标 |

## 输出文件

| 文件 | 说明 |
|------|------|
| `report.md` | Markdown 完整报告 (含 Claude 深度分析) |
| `report.xlsx` | Excel 13 Sheets (含1688供应链+产品列表) |
| `dashboard.html` | HTML 仪表板 (图表+14标签页数据+深度分析) |
| `data.json` | 淘宝原始评分数据 |
| `data_brief.md` | LLM 上下文简报 (含1688产品列表) |
| `llm_analysis.md` | Claude 深度分析 (重跑不会覆写) |
| `data_1688.json` | 1688 完整产品数据 (180条) |

## 项目文件结构

```
taobao-category-selection/
├── scripts/
│   ├── taobao_score.py           # 五维评分报告 (控制台)
│   ├── generate_taobao_report.py # 三格式报告生成器
│   ├── collect_1688.py           # 1688 采集工具
│   └── .1688_tab                 # 1688 标签页缓存 (gitignored)
├── bb-sites/
│   └── 1688/
│       └── offer-score.js        # 1688 adapter 副本
├── taobao-reports/               # 报告输出 (gitignored)
│   └── {品类}_{日期}/
└── CLAUDE.md
```

## 依赖

- **bb-browser**: `npm install -g bb-browser` (站点适配器运行时)
- **Python**: xlsxwriter (`pip install xlsxwriter`)
- **Chrome**: bb-browser 复用本地 Chrome 实例
