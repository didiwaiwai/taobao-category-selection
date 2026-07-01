# taobao-category-selection

基于五维评分模型的淘宝/天猫品类选品分析工具——对齐 Sorftime MCP Skills 方法论，针对淘宝平台本地化适配。

**一行命令采集数据，两行命令生成完整报告（Markdown + Excel 12 Sheets + HTML 仪表板 + Claude 深度分析）。**

## 快速开始

### 1. 安装依赖

```bash
# 安装 bb-browser（浏览器自动化）
npm install -g bb-browser --registry=https://registry.npmmirror.com

# 安装 Python 依赖
pip install xlsxwriter -i https://mirrors.aliyun.com/pypi/simple/
```

### 2. 部署适配器

```bash
# 复制适配器到 bb-browser 目录
mkdir -p ~/.bb-browser/sites/taobao
cp sites/taobao/*.js ~/.bb-browser/sites/taobao/

# 启动 daemon（需 Chrome 已安装）
bb-browser daemon start

# 打开淘宝并扫码登录
bb-browser open https://www.taobao.com
```

### 3. 一键分析品类

```bash
# 采集数据 + 五维评分（3页并发，最多144产品）
bb-browser site taobao/category-score 男士素颜霜 --json > data.json

# 生成完整报告
python scripts/generate_taobao_report.py data.json

# 输出: taobao-reports/男士素颜霜_YYYYMMDD/
#   ├── report.md          # Markdown 完整报告
#   ├── report.xlsx        # Excel 12 Sheets
#   ├── dashboard.html     # Chart.js 可视化仪表板
#   ├── data.json          # 原始评分数据
#   └── data_brief.md      # LLM 上下文简报
```

## 五维评分模型

对齐 [Sorftime MCP Skills](https://github.com/liangdabiao/amazon-sorftime-research-MCP-skill) 的 category-selection 方法论：

| 维度 | 分值 | 淘宝数据指标 | Sorftime 对应 |
|------|:---:|-------------|---------------|
| 市场规模 | 20 | Top产品预估月销量（3页144产品） | Top100月销额 |
| 增长潜力 | 25 | 自适应三层新品占比（上市时间>首单价>标题新品>C店兜底） | 低评论产品占比 |
| 竞争烈度 | 20 | 店铺CR3 + 品牌/店铺HHI + sameCount供给密度 | CR3 + HHI |
| 进入壁垒 | 20 | 天猫占比×新品活跃度 4×3交叉矩阵 + 补贴折价 | Amazon占比×新品占比 |
| 利润空间 | 15 | 平均售价 + 1688成本对标 | 平均价格 |

**评级**: 80+优秀 / 70+良好 / 50+一般 / <50较差

详细评分标准见 [scoring-standard.md](.claude/skills/taobao-category/references/scoring-standard.md)

## 淘宝本地化创新

### 自适应三层数据源
不同品类有不同的可用数据，模型自动选择最优数据源：
- **Tier 1**: `上市时间`（3C数码品类覆盖率高）→ 直接对标 Amazon 低评论逻辑
- **Tier 2**: `首单价`（行为信号，卖家主动降价拉新）+ `标题新品词`
- **Tier 3**: `C店占比` + `热销爆款`（所有品类兜底，上限压制30%）

### 4×3 交叉壁垒矩阵
不是简单的"天猫占比高=壁垒高"，而是天猫占比 × 新品活跃度 的二维交叉：

| 天猫\新品 | 高(>20%) | 中(10-20%) | 低(<10%) |
|----------|:---:|:---:|:---:|
| 低(<30%) | 20 开放繁荣 | 18 门槛低 | 14 静水市场 |
| 中(30-70%) | 14 品牌换皮 | 12 较高壁垒 | 8 品牌锁定 |
| 高(>70%) | 12 品牌迭代 | 8 高壁垒 | 6 封闭市场 |

### 品牌HHI + 店铺HHI 双兜底
品牌数据充足时用品牌HHI，不足时自动降级为店铺HHI——确保任意品类都有集中度指标。

## 项目结构

```
taobao-category-selection/
│
├── .claude/skills/taobao-category/   # Claude Code Skill 定义
│   ├── SKILL.md                      # 角色设定 + 触发条件 + 完整分析流程
│   └── references/
│       └── scoring-standard.md       # 五维评分模型技术规范
│
├── sites/taobao/                     # bb-browser 适配器（浏览器端执行）
│   ├── category-score.js             # ⭐ 核心：数据采集 + 五维评分计算
│   ├── scoring-debug.js              # 调试：查看 API 原始字段
│   ├── scoring-deepdebug.js          # 调试：深度探索未提取字段
│   ├── xcat-diagnostic.js            # 诊断：跨类目字段可用性对比
│   └── sales-rank.js                 # 原始：淘宝销量榜适配器
│
├── scripts/                          # Python 报告生成
│   ├── generate_taobao_report.py     # ⭐ 核心：三格式报告生成器
│   ├── report_template.md            # Markdown 报告模板
│   └── taobao_score.py               # 辅助：评分格式化
│
├── taobao-reports/                   # 报告输出目录
├── .gitignore
├── CLAUDE.md                         # Claude Code 项目指令
└── README.md                         # 本文件
```

## Claude Code 集成

项目包含完整的 Claude Code Skill 定义。安装后可通过自然语言触发：

```
你: "分析淘宝男士素颜霜品类"
Claude: [自动读取 SKILL.md → 执行数据采集 → 生成报告 → 撰写深度分析]
```

Skill 定义在 `.claude/skills/taobao-category/SKILL.md`，Claude Code 会自动识别。

## 分析报告示例

<details>
<summary>男士素颜霜 — 73分 🔵 良好</summary>

- 92产品/3页抓取，月销77万件，¥5209万月销额
- CR3=37%，HHI=830 分散市场
- 天猫70%+补贴折价43% 渠道壁垒
- 机会：¥80-150效率最高，HHI低无品牌垄断
</details>

<details>
<summary>折叠屏手机壳 — 55分 🟡 一般</summary>

- ¥80-150价格带完全空白（结构性机会）
- 52%C店，同类仅4个（蓝海供给）
- 榜首卖点：前框保护+指环支架
- 1688批发¥11-45，零售¥49毛利23%
</details>

<details>
<summary>老年猫主食罐 — 62分 🟡 一般</summary>

- 113万件月销，HHI=918分散市场
- Purrja扑呀唯一专做"中老年猫"
- "老年猫+功能"双维度交叉空白
- 饲料生产许可证硬门槛
</details>

## 技术原理

### 数据采集（非爬虫）
复用淘宝页面内置的 `window.lib.mtop` 库——淘宝自己的前端数据 SDK。请求从你的真实 Chrome 发出，IP/Cookie/指纹完全正常，HMAC 签名由淘宝 JS 自动生成。淘宝感知到的只是一个正常用户在浏览搜索结果。

### 数据分析
浏览器端 JS 直接完成数据解析+五维评分计算，输出结构化 JSON。Python 端负责报告格式化和模板渲染。

## 与 Sorftime MCP Skills 的对比

| | Sorftime | 本项目 |
|---|---|---|
| 数据源 | MCP API (付费) | Chrome CDP (免费) |
| 平台 | Amazon 14站 + 1688 + TikTok | 淘宝/天猫 |
| 趋势数据 | 25个月历史 | 无（需快照积累） |
| 1688成本 | 内置 API | bb-browser 手动采集 |
| 评论分析 | ✅ 差评痛点分析 | ❌ API不返回 |
| 关键词调研 | ✅ 2000+关键词 | ❌ 需生意参谋 |
| 评分模型 | 五维 100分制 | 五维 100分制 + 自适应数据源 |
| 壁垒模型 | Amazon% × 新品% | 天猫% × 新品% 4×3矩阵 |
| 报告输出 | MD + Excel + HTML | MD + Excel + HTML + LLM简报 |
| Claude分析 | SKILL.md 自动触发 | SKILL.md 自动触发 |

## License

MIT
