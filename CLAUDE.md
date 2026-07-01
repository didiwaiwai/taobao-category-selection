# CLAUDE.md

## 项目概述

淘宝/天猫品类选品分析工具。基于五维评分模型对淘宝品类进行深度市场调研，生成 Markdown + Excel + HTML 完整报告。方法论对齐 Sorftime MCP Skills 的 category-selection，针对淘宝平台数据特征做了本地化适配。

## 核心 Skill

本项目包含一个 Claude Code Skill：`taobao-category`（定义在 `.claude/skills/taobao-category/SKILL.md`）

**触发条件**：用户使用 "分析XX品类"、"XX选品"、"XX市场调研" 等自然语言请求时自动激活。

## 快速执行流程

```bash
# 1. 采集数据 + 五维评分
bb-browser site taobao/category-score <关键词> --json > data.json

# 2. 生成完整报告
python scripts/generate_taobao_report.py data.json

# 输出: taobao-reports/{品类}_{日期}/
```

## 输出文件

- `report.md` — Markdown 完整报告（含 Claude 深度分析）
- `report.xlsx` — Excel 12 Sheets
- `dashboard.html` — Chart.js 可视化仪表板
- `data.json` — 原始评分数据
- `data_brief.md` — LLM 上下文简报
- `llm_analysis.md` — Claude 深度分析（重跑报告不会覆写）

## 数据分析流程

1. 读取 `data_brief.md` 获取品类的结构化数据简报
2. 以"淘宝选品运营专家"身份撰写深度分析（SWOT + 策略建议）
3. 保存为 `llm_analysis.md`（`generate_taobao_report.py` 自动检测并注入）
4. 完整报告存入 `report.md`

## 1688 成本采集（可选）

```bash
# 手动在 Chrome 打开 1688 并过验证码
bb-browser goto https://s.1688.com/selloffer/offer_search.htm?keywords=...

# 用 eval 提取价格
bb-browser eval --tab <id> "(function(){...})()"

# 保存为 data_{品类}_1688.json → 重跑报告自动包含1688章节
```
