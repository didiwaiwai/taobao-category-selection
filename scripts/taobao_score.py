#!/usr/bin/env python3
"""
淘宝品类五维评分模型 — 深度分析引擎
============================================
基于 Sorftime 方法论适配，针对淘宝平台数据特征优化。
Python 端负责格式化输出和多品类对比，评分逻辑由 bb-browser adapter 完成。

用法:
    # 单品类分析
    bb-browser site taobao/category-score 蓝牙耳机 --json > data.json
    python taobao_score.py data.json

    # 管道串联
    bb-browser site taobao/category-score 蓝牙耳机 --json 2>&1 | Out-File -Encoding utf8 data.json
    python taobao_score.py data.json

    # 多品类对比
    python taobao_score.py --compare 蓝牙耳机.json 收纳盒.json 机械键盘.json
"""

import json
import sys
import os
from typing import Dict, List, Tuple


# ============================================================
# 适配器输出 → Python 内部格式的桥接
# ============================================================

DIM_NAME_MAP = {
    'marketSize':       '市场规模',
    'growthPotential':  '增长潜力',
    'competition':      '竞争烈度',
    'entryBarrier':     '进入壁垒',
    'profitMargin':     '利润空间',
}

DIM_ORDER = ['市场规模', '增长潜力', '竞争烈度', '进入壁垒', '利润空间']
DIM_MAX =  {'市场规模': 20, '增长潜力': 25, '竞争烈度': 20, '进入壁垒': 20, '利润空间': 15}

SHOP_TYPE_NAMES = {
    'flagship':         '品牌旗舰店',
    'tmall_auth':       '天猫授权店',
    'tmall':            '天猫店',
    'special_channel':  '百亿补贴/精选',
    'c_store':          '淘宝C店',
    'enterprise':       '企业店',
}


def normalize(data: dict) -> dict:
    """将 adapter 输出的 camelCase 格式标准化为 Python 内部格式"""
    if 'result' in data:
        data = data['result']

    scoring_raw = data.get('scoring', {})
    dims_raw = scoring_raw.get('dimensions', {})

    # 标准化维度列表
    dimensions = []
    for key in ['marketSize', 'growthPotential', 'competition', 'entryBarrier', 'profitMargin']:
        if key in dims_raw:
            d = dims_raw[key]
            name = DIM_NAME_MAP.get(key, key)
            dimensions.append({
                'name':  name,
                'score': d.get('score', 0),
                'max':   d.get('maxScore', DIM_MAX.get(name, 20)),
                'label': d.get('label', ''),
            })

    # 标准化市场概况
    mo = data.get('marketOverview', {})
    market_overview = {
        'products_analyzed':  mo.get('totalProducts', len(data.get('products', []))),
        'total_sales':        mo.get('totalSales', 0),
        'avg_price_str':      mo.get('avgPrice', '¥0'),
        'tmall_ratio_str':    mo.get('tmallRatio', '0%'),
        'ad_ratio_str':       mo.get('adRatio', '0%'),
        'shop_type_dist':     mo.get('shopTypeDistribution', {}),
        'top_shops':          mo.get('topShops', []),
    }

    return {
        'query': data.get('query', ''),
        'scoring': {
            'total':          scoring_raw.get('total', 0),
            'maxTotal':       scoring_raw.get('maxTotal', 100),
            'rating':         scoring_raw.get('rating', '未知'),
            'emoji':          scoring_raw.get('ratingEmoji', '⚪'),
            'recommendation': scoring_raw.get('recommendation', ''),
            'dimensions':     dimensions,
        },
        'market_overview': market_overview,
        'products': data.get('products', []),
    }


# ============================================================
# 格式化输出
# ============================================================

def format_report(result: dict) -> str:
    """生成可读的五维评分报告"""
    s = result['scoring']
    m = result['market_overview']
    q = result['query']
    dims = s['dimensions']

    # 计算视觉条宽度
    lines = []
    lines.append('=' * 64)
    lines.append(f'  淘宝品类五维评分报告: {q}')
    lines.append('=' * 64)
    lines.append('')
    lines.append(f'  {s["emoji"]} 综合评分: {s["total"]}/{s["maxTotal"]} — {s["rating"]}')
    lines.append(f'  💡 {s["recommendation"]}')
    lines.append('')

    # 维度卡片
    lines.append('  ┌────────────┬──────────────────────────────────┬──────┐')
    lines.append('  │   维度     │  得分                              │ 满分 │')
    lines.append('  ├────────────┼──────────────────────────────────┼──────┤')

    for d in dims:
        filled  = '█' * d['score']
        empty   = '░' * (d['max'] - d['score'])
        bar     = filled + empty
        lines.append(f'  │ {d["name"]:10s} │ {d["score"]:2d} {bar} │ {d["max"]:3d} │')
        if d['label']:
            lines.append(f'  │ {"":10s} │ {d["label"]:<32s} │ {"":3s} │')

    lines.append('  └────────────┴──────────────────────────────────┴──────┘')
    lines.append('')

    # 市场概况
    lines.append('  📊 市场概况:')
    lines.append(f'     分析产品数:     {m["products_analyzed"]}')
    lines.append(f'     总销量(估):     {m["total_sales"]:,} 件')
    lines.append(f'     均价:           {m["avg_price_str"]}')
    lines.append(f'     天猫店占比:     {m["tmall_ratio_str"]}')
    lines.append(f'     广告占比:       {m["ad_ratio_str"]}')
    lines.append('')

    # 店铺类型分布
    if m['shop_type_dist']:
        lines.append('  🏪 店铺类型分布:')
        total = m['products_analyzed']
        for t, c in sorted(m['shop_type_dist'].items(), key=lambda x: x[1], reverse=True):
            name = SHOP_TYPE_NAMES.get(t, t)
            lines.append(f'     {name}: {c}家 ({c/total*100:.1f}%)')
        lines.append('')

    # Top5 店铺
    if m['top_shops']:
        lines.append('  🏆 Top5 店铺 (按销量):')
        for i, shop in enumerate(m['top_shops'], 1):
            lines.append(f'     {i}. {shop["shop"]} — {shop["sales"]:,}件 ({shop["share"]})')
        lines.append('')

    lines.append('=' * 64)
    return '\n'.join(lines)


def format_compare(results: List[Tuple[str, dict]]) -> str:
    """多品类对比表"""
    lines = []
    lines.append('=' * 80)
    lines.append('  多品类五维评分对比')
    lines.append('=' * 80)
    lines.append('')
    header = f'  {"品类":14s} {"总分":>4s} {"评级":6s}  {"市场(20)":>8s} {"增长(25)":>8s} {"竞争(20)":>8s} {"壁垒(20)":>8s} {"利润(15)":>8s}'
    lines.append(header)
    lines.append('  ' + '-' * 76)

    for name, result in results:
        s = result['scoring']
        dims = {d['name']: d for d in s['dimensions']}

        def score_str(key):
            d = dims.get(key, {})
            return f'{d.get("score", 0):>2d}'

        lines.append(
            f'  {name:14s} {s["total"]:>3d}  {s["rating"]:4s}  '
            f'  {score_str("市场规模"):>6s}    {score_str("增长潜力"):>6s}    '
            f'{score_str("竞争烈度"):>6s}    {score_str("进入壁垒"):>6s}    '
            f'{score_str("利润空间"):>6s}'
        )

    lines.append('')
    lines.append('  💡 高增长+低竞争 = 蓝海机会 | 低增长+高壁垒 = 红海禁区')
    lines.append('=' * 80)
    return '\n'.join(lines)


# ============================================================
# 主入口
# ============================================================

def safe_print(text: str):
    """跨平台安全打印——自动剔除当前终端编码不支持的字符"""
    try:
        # 获取终端编码并强制编码/解码以剔除不兼容字符
        encoding = sys.stdout.encoding or 'utf-8'
        print(text.encode(encoding, errors='replace').decode(encoding))
    except (UnicodeEncodeError, UnicodeDecodeError):
        # 最后兜底：纯 ASCII
        print(text.encode('ascii', errors='replace').decode('ascii'))


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return

    # ---- 对比模式 ----
    if '--compare' in sys.argv:
        idx = sys.argv.index('--compare')
        files = sys.argv[idx + 1:]
        results = []
        for f in files:
            with open(f, 'r', encoding='utf-8-sig') as fh:
                raw = json.load(fh)
            norm = normalize(raw)
            results.append((norm['query'] or os.path.splitext(os.path.basename(f))[0], norm))
        safe_print(format_compare(results))
        return

    # ---- 单品类模式 ----
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
            raw = json.load(f)
    else:
        raw_text = sys.stdin.buffer.read().decode('utf-8-sig').strip()
        raw = json.loads(raw_text)

    norm = normalize(raw)
    safe_print(format_report(norm))


if __name__ == '__main__':
    main()
