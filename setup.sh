#!/bin/bash
# taobao-category-selection 一键安装脚本
# 使用方法: bash setup.sh

echo "========================================="
echo "  淘宝品类选品分析工具 - 一键安装"
echo "========================================="
echo ""

# 1. 检查 Node.js
echo "[1/4] 检查 Node.js..."
if ! command -v node &> /dev/null; then
    echo "  ❌ 未检测到 Node.js，请先安装 https://nodejs.org (需 18+)"
    exit 1
fi
echo "  ✅ Node.js $(node --version)"

# 2. 安装 bb-browser
echo "[2/4] 安装 bb-browser..."
if ! command -v bb-browser &> /dev/null; then
    npm install -g bb-browser --registry=https://registry.npmmirror.com
    echo "  ✅ bb-browser 已安装"
else
    echo "  ✅ bb-browser 已存在"
fi

# 3. 部署适配器
echo "[3/4] 部署淘宝适配器..."
mkdir -p ~/.bb-browser/sites/taobao
cp sites/taobao/*.js ~/.bb-browser/sites/taobao/
echo "  ✅ 适配器已部署到 ~/.bb-browser/sites/taobao/"

# 4. 安装 Python 依赖
echo "[4/4] 安装 Python 依赖..."
pip install xlsxwriter -i https://mirrors.aliyun.com/pypi/simple/ --quiet
echo "  ✅ xlsxwriter 已安装"

echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""
echo "使用方式："
echo "  1. 启动 daemon:  bb-browser daemon start"
echo "  2. 打开淘宝登录: bb-browser open https://www.taobao.com"
echo "  3. 进入本目录:   cd taobao-category-selection"
echo "  4. 分析品类:     在 Claude Code 中说'分析淘宝男士素颜霜'"
echo ""
echo "Claude Code 会自动：采集数据 → 五维评分 → 生成报告 → 撰写深度分析"
echo "输出: taobao-reports/{品类}_{日期}/"
