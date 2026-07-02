#!/usr/bin/env python3
"""
淘宝品类选品报告生成器 — 对齐 Sorftime MCP Skills 输出标准
============================================================
生成三种格式:
  1. Markdown 报告 (report.md)
  2. Excel 多Sheet报告 (report.xlsx)
  3. HTML 仪表板 (dashboard.html)

用法:
  python generate_taobao_report.py <adapter_output.json> [--output-dir <dir>]
"""

import json, os, sys, re
from datetime import datetime
from pathlib import Path


# ============================================================
# 数据加载与标准化
# ============================================================

def load_data(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        raw = json.load(f)
    # 兼容 bb-browser 输出格式
    if 'result' in raw:
        raw = raw['result']
    return raw


def normalize(data: dict) -> dict:
    """将 adapter JSON 标准化为报告生成器内部格式"""
    s = data.get('scoring', {})
    mo = data.get('marketOverview', {})
    dq = data.get('dataQuality', {})
    dims_raw = s.get('dimensions', {})

    # 维度数据
    def dim(key):
        d = dims_raw.get(key, {})
        return {
            'score': d.get('score', 0),
            'max': d.get('maxScore', 20),
            'label': d.get('label', ''),
            'data': d.get('data', {})
        }

    dims = {
        'marketSize':      dim('marketSize'),
        'growthPotential': dim('growthPotential'),
        'competition':     dim('competition'),
        'entryBarrier':    dim('entryBarrier'),
        'profitMargin':    dim('profitMargin'),
    }

    # 竞争数据
    comp_data = dims['competition']['data']

    return {
        'query': data.get('query', ''),
        'model_version': data.get('modelVersion', 'v4'),
        'analyzed_count': data.get('analyzedProducts', 0),
        'scoring': {
            'total': s.get('total', 0),
            'max': s.get('maxTotal', 100),
            'rating': s.get('rating', ''),
            'emoji': s.get('ratingEmoji', ''),
            'recommendation': s.get('recommendation', ''),
        },
        'dimensions': dims,
        'market': {
            'total_sales': mo.get('totalSales', 0),
            'avg_price': mo.get('avgPrice', ''),
            'median_price': mo.get('medianPrice', ''),
            'tmall_ratio': mo.get('tmallRatio', ''),
            'flagship_ratio': mo.get('flagshipRatio', ''),
            'ad_ratio': mo.get('adRatio', ''),
            'subsidy_index': mo.get('subsidyIndex', 'N/A'),
            'avg_same_count': mo.get('avgSameCount', 0),
        },
        'data_quality': {
            'listing_coverage': dq.get('listingDateCoverage', '0%'),
            'growth_tier': dq.get('growthDataTier', ''),
            'brand_coverage': dq.get('brandCoverage', '0%'),
            'growth_source': dq.get('growthDataSource', ''),
        },
        'competition': {
            'cr3_store': comp_data.get('cr3Store', ''),
            'cr3_brand': comp_data.get('cr3Brand', 'N/A'),
            'hhi': comp_data.get('hhi', '0'),
            'avg_same_count': comp_data.get('avgSameCount', 0),
        },
        'barrier': {
            'tmall_level': dims['entryBarrier']['data'].get('tmallLevel', ''),
            'newness_level': dims['entryBarrier']['data'].get('newnessLevel', ''),
            'barrier_type': dims['entryBarrier']['data'].get('barrierType', ''),
            'subsidy_index': dims['entryBarrier']['data'].get('subsidyIndex', 'N/A'),
        },
        'growth': {
            'source': dq.get('growthDataSource', ''),
            'newness_ratio': dims['growthPotential']['data'].get('newnessRatio', ''),
            'listing_6m': dims['growthPotential']['data'].get('listing6mCount', 0),
            'first_price': dims['growthPotential']['data'].get('firstPriceCount', 0),
            'new_title': dims['growthPotential']['data'].get('newTitleCount', 0),
            'hot_bomb': dims['growthPotential']['data'].get('hotBombCount', 0),
            'hot_list': dims['growthPotential']['data'].get('hotListCount', 0),
            'cstore_ratio': dims['growthPotential']['data'].get('cStoreRatio', ''),
        },
        'profit': {
            'avg_price': dims['profitMargin']['data'].get('avgPrice', ''),
            'median_price': dims['profitMargin']['data'].get('medianPrice', ''),
            'price_range': dims['profitMargin']['data'].get('priceRange', ''),
        },
        'products': data.get('products', []),
        'top_shops': mo.get('topShops', []),
        'shop_types': mo.get('shopTypeDistribution', {}),
        'top_brands': mo.get('topBrands', []),
        'price_bands': mo.get('priceBands', []),
        'signal_summary': mo.get('signalSummary', {}),
        'hhi_source': '店铺(品牌数据不足)' if comp_data.get('cr3Brand', 'N/A') == 'N/A' else '品牌',
        # 🆕 v4.1
        'total_revenue_est': mo.get('totalRevenueEst', 0),
        'top_locations': mo.get('topLocations', []),
        'sample_info': data.get('sampleInfo', {}),
        # 🆕 v4.2
        'dynamism': data.get('dynamism', {}),
    }


# ============================================================
# 分析文本生成 (LLM 替代 — 规则驱动)
# ============================================================

def level_text(score, max_score):
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.80: return '优秀'
    elif pct >= 0.60: return '良好'
    elif pct >= 0.40: return '一般'
    return '较差'


def market_size_analysis(d):
    s, total = d['score'], d['data'].get('totalSales', 0)
    if s >= 20: return f'市场规模巨大，Top产品预估月销量超过{total/10000:.0f}万件，属于高流量超级赛道。'
    elif s >= 17: return f'市场规模较大，Top产品预估月销量约{total/10000:.0f}万件，整体流量可观。'
    elif s >= 14: return f'市场规模中等，预估月销量约{total/10000:.0f}万件，有一定市场空间。'
    elif s >= 11: return f'中小型市场，预估月销量约{total/10000:.0f}万件，适合小而美策略。'
    return f'小众市场，预估月销量不足5万件。'


def growth_analysis(d, norm):
    newness = norm['growth']['newness_ratio']
    src = norm['data_quality']['growth_tier']
    s = d['score']
    if s >= 22: return f'新品活跃度高({newness})，市场处于爆发期，新进入者有较大机会。数据源: {src}。'
    elif s >= 18: return f'新品有一定活跃度({newness})，市场处于成长期。数据源: {src}。'
    elif s >= 14: return f'新品活跃度一般({newness})，市场趋于成熟。数据源: {src}。'
    return f'新品活跃度低({newness})，市场已老化/固化，新品较难突围。数据源: {src}。'


def competition_analysis(d, norm):
    cr3 = norm['competition']['cr3_store']
    hhi = norm['competition']['hhi']
    same = norm['competition']['avg_same_count']
    s = d['score']
    if s >= 18: return f'店铺集中度低({cr3})，竞争分散，草根卖家有机会。HHI={hhi}，同类商品{same}个。'
    elif s >= 14: return f'店铺集中度中等({cr3})，存在一定竞争但仍有空间。HHI={hhi}。'
    elif s >= 8: return f'店铺集中度较高({cr3})，头部店铺已建立优势。HHI={hhi}。'
    return f'店铺高度集中({cr3})，HHI={hhi}，市场被寡头主导，同质化供给{same}个。'


def barrier_analysis(d, norm):
    bt = norm['barrier']['barrier_type']
    tmall = norm['market']['tmall_ratio']
    sub = norm['barrier']['subsidy_index']
    s = d['score']

    type_desc = {
        '开放繁荣': '天猫占比低，新品活跃，市场对任何卖家都开放，是创业者的理想选择。',
        '门槛低': '天猫占比较低，新品有一定空间，进入门槛不高。',
        '静水市场': '天猫占比低，但新品不活跃，是一个平静但可能缺乏增长的市场。',
        '品牌化中': '品牌化进程进行中，仍存在C店和新品机会，适合有品牌意识的卖家。',
        '适度壁垒': '存在适度的品牌准入壁垒，需要一定的资源和能力。',
        '品牌垄断中': '品牌正在建立垄断地位，C店虽多但新品难以突围。',
        '品牌换皮': '品牌主导市场，新品信号多来自品牌翻新SKU而非真正的新进入者。',
        '较高壁垒': '较高的品牌准入壁垒，新品空间有限。',
        '品牌锁定': '品牌已经锁定市场，新品极难获得销量，不建议新卖家进入。',
        '品牌迭代': '品牌壁垒高，但产品迭代活跃——适合有品牌授权或技术壁垒的卖家。',
        '高壁垒': '市场被品牌统治，进入需要强大的资源和品牌力。',
        '封闭市场': '市场完全封闭，品牌+平台补贴双重封锁，不建议进入。',
    }
    analysis = type_desc.get(bt, f'壁垒类型为{bt}，天猫占比{tmall}。')
    if sub != 'N/A' and '折价' in d.get('label', ''):
        analysis += f' 百亿补贴渠道存在({sub})，对非补贴卖家定价形成压制。'
    return analysis


def profit_analysis(d, norm):
    avg = norm['profit']['avg_price']
    s = d['score']
    if s >= 12: return f'高利润品类，均价{avg}，有充足利润空间支撑投流和内容营销。'
    elif s >= 10: return f'中高利润品类，均价{avg}，利润空间较为可观。'
    elif s >= 7: return f'中低利润品类，均价{avg}，需要靠走量维持利润，关注供应链成本。'
    return f'低价品类，均价{avg}，快递包装成本可能吃掉大部分利润，必须有极致成本优势。'


# ============================================================
# 🆕 统一评分矩阵 — 消除结论自相矛盾
# ============================================================

def _score_tier(score, max_score):
    """统一评分等级: '强' / '中' / '弱'"""
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.70: return '强'
    elif pct >= 0.50: return '中'
    return '弱'


def _dim_tier(dims, key):
    d = dims[key]
    return _score_tier(d['score'], d['max'])


def generate_advantages(norm):
    """基于统一评分矩阵的优势分析 — 不与劣势冲突"""
    dims = norm['dimensions']
    tiers = {k: _dim_tier(dims, k) for k in ['marketSize','growthPotential','competition','entryBarrier','profitMargin']}
    items = []
    idx = 0
    n = norm

    # 市场规模
    if tiers['marketSize'] == '强':
        idx += 1; items.append(f"{idx}. **市场规模可观**: {dims['marketSize']['label']}，大盘流量充足")
    elif tiers['marketSize'] == '中':
        idx += 1; items.append(f"{idx}. **市场规模适中**: {dims['marketSize']['label']}，有足够空间做小而美")

    # 增长潜力
    if tiers['growthPotential'] == '强':
        idx += 1; items.append(f"{idx}. **新品活跃**: 新品占比{n['growth']['newness_ratio']}，市场对新品接受度高")
    elif tiers['growthPotential'] == '中':
        idx += 1; items.append(f"{idx}. **新品有机会**: 新品占比{n['growth']['newness_ratio']}，差异化新品仍可拿到量")

    # 竞争
    if tiers['competition'] == '强':
        idx += 1; items.append(f"{idx}. **竞争分散**: 店铺CR3={n['competition']['cr3_store']}，草根卖家有生存空间")
    elif tiers['competition'] == '中':
        idx += 1; items.append(f"{idx}. **竞争适中**: CR3={n['competition']['cr3_store']}，找准定位后有机会")

    # 壁垒
    if tiers['entryBarrier'] == '强':
        idx += 1; items.append(f"{idx}. **门槛较低**: 天猫占比{n['market']['tmall_ratio']}，C店活跃，适合个人/小团队")
    elif tiers['entryBarrier'] == '中':
        idx += 1; items.append(f"{idx}. **壁垒适中**: 天猫{n['market']['tmall_ratio']}，有一定品牌化但未完全封闭")

    # 利润
    if tiers['profitMargin'] == '强':
        idx += 1; items.append(f"{idx}. **利润空间充足**: {n['profit']['avg_price']}，可支撑投流和内容运营")
    elif tiers['profitMargin'] == '中' and tiers['profitMargin'] != '弱':
        idx += 1; items.append(f"{idx}. **利润尚可**: {n['profit']['avg_price']}，控制成本后可盈利")

    return '\n'.join(items) if items else "暂无明显优势"


def generate_disadvantages(norm):
    """基于统一评分矩阵的劣势分析 — 与优势互斥"""
    dims = norm['dimensions']
    tiers = {k: _dim_tier(dims, k) for k in ['marketSize','growthPotential','competition','entryBarrier','profitMargin']}
    items = []
    idx = 0
    n = norm

    if tiers['marketSize'] == '弱':
        idx += 1; items.append(f"{idx}. **市场规模偏小**: {dims['marketSize']['label']}，天花板较低，不适合追求规模")

    if tiers['growthPotential'] == '弱':
        idx += 1; items.append(f"{idx}. **新品活跃度低**: 新品仅占{n['growth']['newness_ratio']}，市场趋于固化")

    if tiers['competition'] == '弱':
        idx += 1; items.append(f"{idx}. **竞争激烈**: 店铺CR3={n['competition']['cr3_store']}，头部已建立壁垒")
        if n['competition']['avg_same_count'] > 200:
            idx += 1; items.append(f"{idx}. **同质化严重**: {n['competition']['avg_same_count']}个同类商品，供给端竞争激烈")

    if tiers['entryBarrier'] == '弱':
        idx += 1; items.append(f"{idx}. **进入壁垒高**: 天猫{n['market']['tmall_ratio']}，{n['barrier']['barrier_type']}，新人进入难度大")

    if tiers['profitMargin'] == '弱':
        idx += 1; items.append(f"{idx}. **利润空间薄**: {n['profit']['avg_price']}，快递和包装成本可能吃掉大部分利润")

    return '\n'.join(items) if items else "暂无明显劣势"


# ============================================================
# 🆕 价格带洞察自动提炼
# ============================================================

def generate_price_band_insight(norm):
    """从价格带分布中自动提炼可落地的选品方向"""
    bands = norm.get('price_bands', [])
    if not bands:
        return '暂无价格带数据'

    total = norm['analyzed_count']
    lines = []

    # 1. 找拥挤带（占比>40%）
    crowded = [b for b in bands if b['count']/total > 0.40 if total > 0]
    if crowded:
        c = crowded[0]
        lines.append(f"- **{c['label']} 极度拥挤**: {c['count']}个产品扎堆(占{c['count']/total*100:.0f}%)，价格战激烈，新进入者应避开此区间")

    # 2. 找空白带（0产品）
    gaps = [b for b in bands if b['count'] == 0 and b['label'] != '¥600+']
    if gaps:
        for g in gaps[:2]:
            lines.append(f"- **{g['label']} 完全空白**: 无人占据，如果产品力足够可做差异化定价")
        if len(gaps) >= 2:
            lines.append(f"- 💡 **定价建议**: {gaps[0]['label']}~{gaps[-1]['label']} 是结构性机会区间，率先进入者有定价权")

    # 3. 找稀疏带（1-2个产品）——可能是先行者信号
    sparse = [b for b in bands if 0 < b['count'] <= 3 and b['label'] != '¥600+']
    if sparse:
        for s in sparse[:2]:
            pct = s['sales']/norm['market']['total_sales']*100 if norm['market']['total_sales'] > 0 else 0
            lines.append(f"- **{s['label']} 稀疏但高销**: {s['count']}个产品拿走了{pct:.1f}%销量，验证了此价格带的需求")

    # 4. 找销量最高的价格带
    if bands:
        top_band = max(bands, key=lambda b: b['sales'])
        lines.append(f"- **主力价格带是 {top_band['label']}**: 贡献了{top_band['sales']:,}件销量，消费者的心理价位锚点在此")

    return '\n'.join(lines) if lines else '价格带分布均匀，无明显空白或拥挤'


# ============================================================
# 🆕 头部产品策略提炼
# ============================================================

def generate_top_product_insights(norm):
    """从Top产品中提取运营可参考的模式和信号"""
    products = norm.get('products', [])
    if not products:
        return '暂无产品数据'

    top5 = products[:5]
    lines = []

    # 1. 头部店铺分析
    top_shops = {}
    for p in products[:10]:
        s = p.get('shop', '')
        if s not in top_shops: top_shops[s] = {'count':0, 'types':set(), 'prices':[]}
        top_shops[s]['count'] += 1
        top_shops[s]['types'].add(p.get('shopType', ''))
        try:
            price_str = p.get('price', '¥0').replace('¥','').split(' ')[0]
            top_shops[s]['prices'].append(float(price_str))
        except: pass

    # 2. 头部价格策略
    top_prices = []
    for p in products[:10]:
        try:
            price_str = p.get('price', '¥0').replace('¥','').split(' ')[0].replace(',','')
            top_prices.append(float(price_str))
        except: pass
    if top_prices:
        avg_top_price = sum(top_prices)/len(top_prices)
        all_prices = []
        for p in products:
            try:
                price_str = p.get('price', '¥0').replace('¥','').split(' ')[0].replace(',','')
                all_prices.append(float(price_str))
            except: pass
        avg_all = sum(all_prices)/len(all_prices) if all_prices else 0
        if avg_top_price > avg_all * 1.3:
            lines.append(f"- **头部溢价显著**: Top10均价¥{avg_top_price:.0f}，远高于全品类均价¥{avg_all:.0f}，消费者愿为头部产品支付溢价")
        elif avg_top_price < avg_all * 0.7:
            lines.append(f"- **头部低价走量**: Top10均价¥{avg_top_price:.0f}，低于全品类均价¥{avg_all:.0f}，头部靠价格优势冲量")
        else:
            lines.append(f"- **价格竞争均衡**: Top10均价¥{avg_top_price:.0f}，与大盘均价¥{avg_all:.0f}接近，价格非核心差异点")

    # 3. 新品在头部的占比
    new_in_top = sum(1 for p in products[:10] if p.get('isRecent6m') or p.get('hasNewTitle') or p.get('isFirstPrice'))
    if new_in_top >= 3:
        lines.append(f"- **新品能冲入头部**: Top10中{new_in_top}个带新品信号，验证了新品在这个品类有突围可能")
    elif new_in_top == 0:
        lines.append(f"- **头部无新品**: Top10中没有任何新品信号，头部已被老品/老店锁定")

    # 4. C店在头部的占比
    c_in_top = sum(1 for p in products[:10] if p.get('shopType') == 'c_store')
    if c_in_top >= 4:
        lines.append(f"- **C店主导头部**: Top10中{c_in_top}个是C店，个人卖家在此品类可以与大店同台竞争")
    elif c_in_top == 0:
        lines.append(f"- **天猫独占头部**: Top10全部是天猫/旗舰店，C店很难拿到头部流量")

    # 5. 榜首产品卖点
    first = products[0]
    title = first.get('title', '')
    # 提取可能的卖点关键词
    keywords = ['支架','保护','磁吸','超薄','透明','防摔','全包','磨砂','液态硅胶','皮质','复古','可爱','ins','高级感','原机质感','指环','链条']
    found_kw = [kw for kw in keywords if kw in title]
    if found_kw:
        lines.append(f"- **榜首卖点**: \"{title[:30]}...\" 关键词: {'/'.join(found_kw[:4])}")

    return '\n'.join(lines) if lines else '数据不足以提炼头部策略'

    if cr3 > 60: items.append("1. **寡头风险**: 头部店铺占据大部分销量，小型卖家生存空间有限")
    elif cr3 > 45: items.append("1. **集中度上升风险**: 头部店铺正在扩大份额")

    if growth_score < 14: items.append("2. **市场停滞风险**: 新品难以进入，市场可能走向固化")

    if barrier_score <= 8: items.append("3. **准入壁垒**: 天猫/品牌壁垒可能进一步抬高")

    sub = market['subsidy_index']
    if sub != 'N/A':
        try:
            sv = float(sub.replace('%', ''))
            if sv < 85: items.append(f"4. **补贴价格压制**: 百亿补贴折价{sub}，非补贴渠道定价受损")
        except: pass

    dims_data = norm['dimensions']
    if dims['profitMargin']['score'] <= 4: items.append("5. **价格战风险**: 超低均价极易引发恶性价格竞争")

    return '\n'.join(items) if items else "暂无明显威胁"


# ============================================================
# 🆕 1688成本对标
# ============================================================

def generate_1688_insight(norm):
    """1688成本对标分析"""
    data_1688 = norm.get('data_1688', {})
    if not data_1688 or not data_1688.get('prices'):
        return ''
    prices = data_1688['prices']
    avg_taobao_str = str(norm['market']['avg_price']).replace('¥','').replace(',','')
    try: avg_taobao_num = float(avg_taobao_str)
    except: return ''
    mid_cost = sorted(prices)[len(prices)//2]
    markup = avg_taobao_num / mid_cost if mid_cost > 0 else 0
    gross_margin = (avg_taobao_num - mid_cost) / avg_taobao_num * 100 if avg_taobao_num > 0 else 0
    platform_fee = avg_taobao_num * 0.05
    net_profit = avg_taobao_num - mid_cost - platform_fee - 3 - 1.5
    net_margin = net_profit / avg_taobao_num * 100
    lines = [f'- **1688批发价区间**: ¥{min(prices):.0f} ~ ¥{max(prices):.0f}']
    lines.append(f'- **中位批发价**: ¥{mid_cost:.0f}，零售价约为批发价的 {markup:.1f}x')
    lines.append(f'- **预估毛利率**: {gross_margin:.0f}% | **预估净利**: ¥{net_profit:.1f}/单 ({net_margin:.0f}%)')
    if gross_margin > 60: lines.append('💡 毛利空间充足，可支撑投流和内容营销，适合品牌化运作')
    elif gross_margin > 40: lines.append('💡 毛利尚可，走量可盈利，注意控制广告ROI')
    else: lines.append('💡 毛利偏低，必须靠供应链优势或走量策略')
    return '\n'.join(lines)


def generate_opportunities(norm):
    """基于统一评分矩阵的机会分析"""
    dims = norm['dimensions']
    tiers = {k: _dim_tier(dims, k) for k in ['marketSize','growthPotential','competition','entryBarrier','profitMargin']}
    items = []
    idx = 0

    # 价格带空位是最有价值的机会信号
    bands = norm.get('price_bands', [])
    gaps = [b for b in bands if b['count'] == 0 and b['label'] != '¥600+']
    if gaps:
        idx += 1
        gap_labels = ', '.join(b['label'] for b in gaps[:3])
        items.append(f"{idx}. **价格带空白机会**: {gap_labels} 完全无人占据，率先进入有定价权")

    # 低门槛+分散竞争=草根入场窗口
    if tiers['entryBarrier'] in ('强','中') and tiers['competition'] in ('强','中'):
        idx += 1; items.append(f"{idx}. **入场窗口**: 门槛适中+竞争分散，当前是较好的进入时机")

    # 高增长+低壁垒=蓝海
    if tiers['growthPotential'] == '强' and tiers['entryBarrier'] == '强':
        idx += 1; items.append(f"{idx}. **蓝海信号**: 新品活跃且门槛低，属于早期红利阶段")

    # 有利润空间的中高端
    if tiers['profitMargin'] == '强':
        idx += 1; items.append(f"{idx}. **中高端机会**: {norm['profit']['avg_price']}，中高端定位有品牌溢价空间")

    # 品类有热度
    if norm['growth']['hot_list'] > 10:
        idx += 1; items.append(f"{idx}. **榜单活跃**: {norm['growth']['hot_list']}个产品在各类榜单，品类有持续热度")

    return '\n'.join(items) if items else "需要深入调研寻找机会"


def generate_threats(norm):
    """基于统一评分矩阵的威胁分析"""
    dims = norm['dimensions']
    tiers = {k: _dim_tier(dims, k) for k in ['marketSize','growthPotential','competition','entryBarrier','profitMargin']}
    items = []
    idx = 0
    n = norm

    if tiers['competition'] == '弱':
        idx += 1; items.append(f"{idx}. **寡头威胁**: 头部店铺CR3={n['competition']['cr3_store']}，新进入者面临强力挤压")

    if tiers['growthPotential'] == '弱':
        idx += 1; items.append(f"{idx}. **市场固化风险**: 新品活跃度仅{n['growth']['newness_ratio']}，市场可能走向僵化")

    if tiers['entryBarrier'] == '弱':
        idx += 1; items.append(f"{idx}. **准入壁垒上升**: {n['barrier']['barrier_type']}，进入成本可能持续走高")

    if tiers['profitMargin'] == '弱':
        idx += 1; items.append(f"{idx}. **价格战风险**: 均价{n['profit']['avg_price']}，极易陷入恶性价格竞争")

    # 补贴压制
    sub = n['barrier'].get('subsidy_index', 'N/A')
    if sub != 'N/A' and sub != '无补贴':
        try:
            sv = float(sub.replace('%',''))
            if sv < 85: idx += 1; items.append(f"{idx}. **补贴渠道压制**: 百亿补贴折价仅{sub}，非补贴卖家定价空间被严重挤压")
        except: pass

    return '\n'.join(items) if items else "暂无明显威胁"


def entry_strategy(norm):
    total = norm['scoring']['total']
    if total >= 70:
        return """**推荐策略**:
- 该品类综合评分较高，值得优先考虑
- 建议从中端价格区间切入，避免与低端价格战和高端品牌正面竞争
- 重视差异化产品设计和视觉呈现
- 前期以少量SKU测试市场反应"""
    elif total >= 50:
        return """**谨慎策略**:
- 该品类存在明显短板，建议评估自身资源是否匹配
- 如果进入，建议选择细分垂直方向做差异化
- 重视供应链成本控制
- 建议先小规模测试，快速迭代"""
    else:
        return """**不推荐进入**:
- 该品类综合评分较低
- 如有特殊资源(品牌授权/工厂直供/独家设计)才可考虑
- 建议转向评分更高或更匹配自身优势的品类"""


def suitable_seller(norm):
    total = norm['scoring']['total']
    barrier = norm['dimensions']['entryBarrier']['score']
    if total >= 70: return '有一定资金实力、有供应链资源、有运营经验的卖家'
    elif total >= 50:
        if barrier >= 14: return '个人创业者、小团队、能做出差异化设计的卖家'
        return '有特定品类经验、能找到差异化定位的卖家'
    return '不推荐新手卖家进入'


def unsuitable_seller(norm):
    total = norm['scoring']['total']
    profit = norm['dimensions']['profitMargin']['score']
    if profit <= 4: return '资金紧张的小卖家(利润太薄)、没有供应链优势的中间商'
    if total < 60: return '新手卖家、无供应链资源的小卖家、资金有限的卖家'
    return '缺乏运营经验的新手、无差异化能力的跟风卖家'


def brand_concentration_analysis(norm):
    # 🆕 数据质量守卫
    coverage = norm.get('data_quality', {}).get('brandCoverage', '0%')
    if not coverage or coverage in ('0%', ''):
        return '品牌数据不足，无法进行品牌集中度分析。建议手动补充品牌信息后重新评估。'
    hhi = float(norm['competition']['hhi'])
    if hhi > 2500: return '品牌高度集中，市场被少数品牌主宰，新品牌进入难度极大。'
    elif hhi > 1000: return '品牌中等集中，头部品牌有一定优势但未完全垄断。'
    return '品牌较为分散，新品牌仍有机会获得市场份额。'


def risk_warning(norm):
    items = []
    dims = norm['dimensions']
    comp = norm['competition']
    market = norm['market']

    if dims['competition']['score'] <= 8:
        items.append('- 头部店铺已建立稳固地位，新产品需要较大营销投入获取初期销量')
    if dims['growthPotential']['score'] < 14:
        items.append('- 新品活跃度低，可能需要较长时间才能获得稳定流量')
    if dims['profitMargin']['score'] <= 4:
        items.append('- 利润空间极薄，任何成本波动都可能导致亏损')
    if comp['avg_same_count'] > 200:
        items.append(f'- 同类商品{comp["avg_same_count"]}个，差异化难度大')
    sub = market['subsidy_index']
    if sub != 'N/A':
        try:
            sv = float(sub.replace('%', ''))
            if sv < 80: items.append(f'- 百亿补贴折价仅{sub}，非补贴卖家面临严重价格挤压')
        except: pass

    return '\n'.join(items) if items else '- 暂无明显风险'


# ============================================================
# Markdown 报告生成
# ============================================================

# ============================================================
# 🆕 LLM 数据简报 — 替代规则引擎，由 Claude 写分析
# ============================================================

def generate_data_brief(norm: dict) -> str:
    """生成结构化数据简报，作为 Claude 写专业分析的上下文"""
    s = norm['scoring']
    m = norm['market']
    c = norm['competition']
    g = norm['growth']
    b = norm['barrier']
    p = norm['profit']
    dims = norm['dimensions']
    dq = norm['data_quality']

    brief = f'''## 品类数据简报: {norm['query']}

### 评分快照
| 维度 | 得分 | 分析 |
|------|:---:|------|
| 市场规模 | {dims['marketSize']['score']}/{dims['marketSize']['max']} | {dims['marketSize']['label']} |
| 增长潜力 | {dims['growthPotential']['score']}/{dims['growthPotential']['max']} | {dims['growthPotential']['label']} |
| 竞争烈度 | {dims['competition']['score']}/{dims['competition']['max']} | {dims['competition']['label']} |
| 进入壁垒 | {dims['entryBarrier']['score']}/{dims['entryBarrier']['max']} | {dims['entryBarrier']['label']} |
| 利润空间 | {dims['profitMargin']['score']}/{dims['profitMargin']['max']} | {dims['profitMargin']['label']} |
| **总分** | **{s['total']}/100** | **{s['rating']}** |

### 关键数据
- 分析产品数: {norm['analyzed_count']} | 预估总销量: {m['total_sales']:,}件
- 均价: {m['avg_price']} | 中位数: {m['median_price']} | 价格区间: {p['price_range']}
- 天猫占比: {m['tmall_ratio']} | 旗舰店占比: {m.get('flagship_ratio','N/A')}
- 店铺CR3: {c['cr3_store']} | HHI: {c['hhi']} | 同类商品数: {c['avg_same_count']}
- 壁垒类型: {b['barrier_type']} (天猫{b.get('tmall_level','?')} × 新品{b.get('newness_level','?')})
- 百亿补贴: {b.get('subsidy_index','无')} | 直通车广告占比: {m['ad_ratio']}
- 数据层级: {dq['growth_tier']} | 上市时间覆盖: {dq['listing_coverage']} | 品牌覆盖: {dq.get('brandCoverage','0%')}

### 增长信号
- 新品销量占比: {g['newness_ratio']} | 近6月上架: {g['listing_6m']}个
- 首单价产品: {g['first_price']}个 | 标题含新品词: {g['new_title']}个
- 热销爆款标签: {g['hot_bomb']}个 | 在榜产品: {g['hot_list']}个
- C店销量占比(参考): {g.get('cstore_ratio','N/A')}

### 价格带分布
'''
    bands = norm.get('price_bands', [])
    if bands:
        total_p = norm['analyzed_count']
        for pb in bands:
            pct = f"{pb['count']/total_p*100:.1f}%" if total_p > 0 else '0%'
            marker = ' ← 完全空白!' if pb['count'] == 0 else (' ← 极度拥挤' if pb['count']/total_p > 0.4 else '')
            brief += f"- {pb['label']}: {pb['count']}个产品({pct}), 销量{pb['sales']:,}{marker}\n"

    # Top店铺
    brief += '\n### Top 5 店铺\n'
    shops = norm.get('top_shops', [])[:5]
    for i, sh in enumerate(shops, 1):
        brief += f"- {i}. {sh['shop']}: {sh['sales']:,}件 ({sh['share']})\n"

    # 店铺类型
    brief += '\n### 店铺类型分布\n'
    stypes = norm.get('shop_types', {})
    type_names = {'flagship':'品牌旗舰店','tmall_auth':'天猫授权店','tmall':'天猫店','special_channel':'百亿补贴/精选','c_store':'淘宝C店','enterprise':'企业店'}
    total_st = sum(stypes.values())
    for t, c in sorted(stypes.items(), key=lambda x: x[1], reverse=True):
        brief += f"- {type_names.get(t,t)}: {c}家 ({c/total_st*100:.0f}%)\n"

    # Top 10 产品
    brief += '\n### Top 10 产品\n'
    products = norm.get('products', [])
    for i, pr in enumerate(products[:10], 1):
        title = pr.get('title','')[:40]
        price = pr.get('price','')
        sales = pr.get('sales','')
        shop = pr.get('shop','')[:15]
        shtype = pr.get('shopType','')
        is_new = '新品' if pr.get('isRecent6m') or pr.get('hasNewTitle') or pr.get('isFirstPrice') else ''
        is_hot = '热销' if pr.get('hasHotBomb') or pr.get('hasHotList') else ''
        tags = ' '.join(filter(None, [is_new, is_hot]))
        brief += f"- {i}. [{shop}] {title} — {price} | {sales} {tags}\n"

    # 1688数据
    d1688 = norm.get('data_1688', {})
    if d1688 and d1688.get('prices'):
        prices_1688 = d1688['prices']
        brief += f'\n### 1688采购成本\n'
        brief += f"- 批发价区间: ¥{min(prices_1688)} ~ ¥{max(prices_1688)}\n"
        mid_1688 = sorted(prices_1688)[len(prices_1688)//2]
        brief += f"- 中位批发价: ¥{mid_1688}\n"
        try:
            avg_t = float(str(m['avg_price']).replace('¥','').replace(',',''))
            markup = avg_t / mid_1688 if mid_1688 > 0 else 0
            gross = (avg_t - mid_1688) / avg_t * 100
            brief += f"- 零售/批发比: {markup:.1f}x | 预估毛利率: {gross:.0f}%\n"
        except: pass

    brief += f'''
### 你的任务
请以上述数据为基础，以资深电商选品运营专家的身份，写一份完整的分析报告，包含以下部分：

1. **执行摘要** — 3-5句话概括这个品类的核心特征和是否值得进入
2. **优势分析** — 基于数据，这个品类对新进入者有利的因素
3. **劣势/短板** — 客观指出的不足和风险点
4. **市场机会** — 从价格带空白、头部产品策略等维度发现可落地的选品方向
5. **威胁与风险** — 外部竞争和平台政策等风险
6. **进入策略建议** — 具体的定价建议、差异化方向、运营重点
7. **适合/不适合的卖家画像** — 什么样的人应该做/不应该做这个品类

要求：每个结论都要引用具体数据支撑，不要泛泛而谈。报告直接输出Markdown格式。'''
    return brief


def generate_markdown(norm: dict, template_path: str = None) -> str:
    """生成 Markdown 报告"""
    dims = norm['dimensions']
    s = norm['scoring']
    m = norm['market']
    c = norm['competition']
    g = norm['growth']
    b = norm['barrier']
    p = norm['profit']
    dq = norm['data_quality']

    # 读取模板
    if template_path and os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            md = f.read()
    else:
        md = "# {{CATEGORY_NAME}} 淘宝品类选品分析报告\n\n..."

    # 维度简写
    dim = lambda k: dims[k]

    # 替换变量
    vars_map = {
        '{{CATEGORY_NAME}}': norm['query'],
        '{{DATE}}': datetime.now().strftime('%Y-%m-%d'),
        '{{MODEL_VERSION}}': norm['model_version'],
        '{{QUERY}}': norm['query'],
        '{{PRODUCT_COUNT}}': str(norm['analyzed_count']),
        '{{TOTAL_SALES}}': f'{m["total_sales"]:,}',
        '{{TOTAL_REVENUE}}': f'¥{norm.get("total_revenue_est",0)/10000:,.0f}万' if norm.get('total_revenue_est',0)>0 else '未估算',
        '{{AVG_PRICE}}': m['avg_price'],
        '{{MEDIAN_PRICE}}': m['median_price'],
        '{{PRICE_RANGE}}': p['price_range'],
        '{{TMALL_RATIO}}': m['tmall_ratio'],
        '{{FLAGSHIP_RATIO}}': m.get('flagship_ratio', ''),
        '{{AD_RATIO}}': m['ad_ratio'],
        '{{SUBSIDY_INDEX}}': b['subsidy_index'],
        '{{LISTING_COVERAGE}}': dq['listing_coverage'],
        '{{GROWTH_TIER}}': dq['growth_tier'],
        '{{GROWTH_SOURCE}}': dq['growth_source'],
        '{{BRAND_COVERAGE}}': dq.get('brandCoverage', ''),
        '{{HHI_SOURCE}}': norm['hhi_source'],
        '{{CR3_STORE}}': c['cr3_store'],
        '{{CR3_BRAND}}': c['cr3_brand'],
        '{{HHI}}': c['hhi'],
        '{{AVG_SAME_COUNT}}': str(c['avg_same_count']),
        '{{NEWNESS_RATIO}}': g['newness_ratio'],
        '{{LISTING_6M_COUNT}}': str(g['listing_6m']),
        '{{FIRST_PRICE_COUNT}}': str(g['first_price']),
        '{{NEW_TITLE_COUNT}}': str(g['new_title']),
        '{{HOT_BOMB_COUNT}}': str(g['hot_bomb']),
        '{{HOT_LIST_COUNT}}': str(g['hot_list']),
        '{{CSTORE_RATIO}}': g.get('cstore_ratio', ''),
        '{{BARRIER_TYPE}}': b['barrier_type'],
        '{{NEWNESS_LEVEL}}': b['newness_level'],
        # 评分
        '{{SCORE_总分}}': str(s['total']),
        '{{MAX_总分}}': str(s['max']),
        '{{RATING}}': s['rating'],
        '{{RECOMMENDATION}}': s['recommendation'],
        '{{SCORE_市场规模}}': str(dim('marketSize')['score']),
        '{{MAX_市场规模}}': str(dim('marketSize')['max']),
        '{{LEVEL_市场规模}}': level_text(dim('marketSize')['score'], dim('marketSize')['max']),
        '{{SCORE_增长潜力}}': str(dim('growthPotential')['score']),
        '{{MAX_增长潜力}}': str(dim('growthPotential')['max']),
        '{{LEVEL_增长潜力}}': level_text(dim('growthPotential')['score'], dim('growthPotential')['max']),
        '{{SCORE_竞争烈度}}': str(dim('competition')['score']),
        '{{MAX_竞争烈度}}': str(dim('competition')['max']),
        '{{LEVEL_竞争烈度}}': level_text(dim('competition')['score'], dim('competition')['max']),
        '{{SCORE_进入壁垒}}': str(dim('entryBarrier')['score']),
        '{{MAX_进入壁垒}}': str(dim('entryBarrier')['max']),
        '{{LEVEL_进入壁垒}}': level_text(dim('entryBarrier')['score'], dim('entryBarrier')['max']),
        '{{SCORE_利润空间}}': str(dim('profitMargin')['score']),
        '{{MAX_利润空间}}': str(dim('profitMargin')['max']),
        '{{LEVEL_利润空间}}': level_text(dim('profitMargin')['score'], dim('profitMargin')['max']),
        # 分析文本 — 单维度简析保留，完整深度分析用 LLM
        '{{ANALYSIS_市场规模}}': market_size_analysis(dim('marketSize')),
        '{{ANALYSIS_增长潜力}}': growth_analysis(dim('growthPotential'), norm),
        '{{ANALYSIS_竞争烈度}}': competition_analysis(dim('competition'), norm),
        '{{ANALYSIS_进入壁垒}}': barrier_analysis(dim('entryBarrier'), norm),
        '{{ANALYSIS_利润空间}}': profit_analysis(dim('profitMargin'), norm),
        # LLM深度分析占位
        '{{LLM_ANALYSIS}}': norm.get('llm_analysis', '> ⚠️ Claude 深度分析待生成。请将本报告数据交由 Claude 完成 SWOT + 策略分析。\n\n> 数据简报已保存为 data_brief.md，可直接作为 Claude 的上下文输入。'),
        '{{RISK_WARNING}}': risk_warning(norm),
        '{{SUITABLE_SELLER}}': suitable_seller(norm),
        '{{UNSUITABLE_SELLER}}': unsuitable_seller(norm),
    }

    # 价格带分布表
    price_bands = norm.get('price_bands', [])
    if price_bands:
        pb_rows = ['| 价格带 | 产品数 | 占比 | 销量 |', '|--------|--------|------|------|']
        total_p = norm['analyzed_count']
        for pb in price_bands:
            pct = f"{pb['count']/total_p*100:.1f}%" if total_p > 0 else '0%'
            pb_rows.append(f'| {pb["label"]} | {pb["count"]} | {pct} | {pb["sales"]:,} |')
        vars_map['{{PRICE_BANDS_TABLE}}'] = '\n'.join(pb_rows)
        vars_map['{{PRICE_BAND_INSIGHT}}'] = generate_price_band_insight(norm)
        vars_map['{{TOP_PRODUCT_INSIGHTS}}'] = generate_top_product_insights(norm)
        vars_map['{{1688_INSIGHT}}'] = generate_1688_insight(norm)
    else:
        vars_map['{{PRICE_BANDS_TABLE}}'] = '暂无价格带数据'

    # 品牌表
    brands = norm.get('top_brands', [])
    if brands:
        br_rows = ['| 排名 | 品牌 | 产品数 |', '|------|------|--------|']
        for i, br in enumerate(brands[:10], 1):
            br_rows.append(f'| {i} | {br.get("brand","")} | {br.get("count","")} |')
        vars_map['{{BRANDS_TABLE}}'] = '\n'.join(br_rows)
    else:
        vars_map['{{BRANDS_TABLE}}'] = '暂无品牌数据'

    # Top店铺表
    shops = norm.get('top_shops', [])
    if shops:
        sh_rows = ['| 排名 | 店铺 | 预估销量 | 份额 |', '|------|------|----------|------|']
        for i, sh in enumerate(shops[:10], 1):
            sh_rows.append(f'| {i} | {sh.get("shop","")} | {sh.get("sales",0):,} | {sh.get("share","")} |')
        vars_map['{{TOP_SHOPS_TABLE}}'] = '\n'.join(sh_rows)
    else:
        vars_map['{{TOP_SHOPS_TABLE}}'] = '暂无店铺数据'

    # 产品表 (Top10 + 品牌列 + 链接)
    products = norm.get('products', [])
    if products:
        pr_rows = []
        for i, pr in enumerate(products[:10], 1):
            title = pr.get('title', '')[:28]
            price = pr.get('price', '')
            sales = pr.get('sales', '')
            shop = pr.get('shop', '')[:10]
            brand = (pr.get('brand', '?'))[:6]
            shtype = pr.get('shopType', '')
            is_new = '✓' if pr.get('isRecent6m') or pr.get('hasNewTitle') or pr.get('isFirstPrice') else ''
            item_id = pr.get('item_id', '')
            title_display = title[:30]
            if item_id:
                link = f'[{title_display}](https://item.taobao.com/item.htm?id={item_id})'
            else:
                link = title_display
            pr_rows.append(f'| {i} | {link} | {price} | {sales} | {shop} | {brand} | {shtype} | {is_new} |')
        vars_map['{{PRODUCTS_TABLE}}'] = '\n'.join(pr_rows)
    else:
        vars_map['{{PRODUCTS_TABLE}}'] = '暂无产品数据'

    # 🆕 发货地分布
    locs = norm.get('top_locations', [])
    if locs:
        loc_rows = ['| 发货地 | 产品数 | 占比 |', '|--------|--------|------|']
        total_l = norm['analyzed_count']
        for loc in locs[:5]:
            loc_rows.append(f'| {loc["location"]} | {loc["count"]} | {loc["count"]/total_l*100:.0f}% |')
        vars_map['{{LOCATION_DIST}}'] = '\n'.join(loc_rows)
    else:
        vars_map['{{LOCATION_DIST}}'] = '暂无发货地数据'

    # 店铺类型分布
    stypes = norm.get('shop_types', {})
    type_names = {
        'flagship': '品牌旗舰店', 'tmall_auth': '天猫授权店', 'tmall': '天猫店',
        'special_channel': '百亿补贴/精选', 'c_store': '淘宝C店', 'enterprise': '企业店'
    }
    if stypes:
        st_rows = ['| 店铺类型 | 数量 | 占比 |', '|----------|------|------|']
        total_st = sum(stypes.values())
        for t, c in sorted(stypes.items(), key=lambda x: x[1], reverse=True):
            st_rows.append(f'| {type_names.get(t, t)} | {c} | {c/total_st*100:.1f}% |')
        vars_map['{{SHOP_TYPE_DIST}}'] = '\n'.join(st_rows)
    else:
        vars_map['{{SHOP_TYPE_DIST}}'] = ''

    # 执行替换
    for key, val in vars_map.items():
        md = md.replace(key, str(val))

    return md


# ============================================================
# Excel 报告生成
# ============================================================

def generate_excel(norm: dict, output_path: str):
    """生成 Excel 多Sheet报告 (对齐 Sorftime 的 12 sheets)"""
    import xlsxwriter

    wb = xlsxwriter.Workbook(output_path)

    # 通用格式
    hdr_fmt = wb.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1})
    cell_fmt = wb.add_format({'border': 1})
    num_fmt = wb.add_format({'border': 1, 'num_format': '#,##0'})
    pct_fmt = wb.add_format({'border': 1, 'num_format': '0.0%'})
    score_good = wb.add_format({'bold': True, 'bg_color': '#C6EFCE', 'border': 1})
    score_mid = wb.add_format({'bold': True, 'bg_color': '#FFEB9C', 'border': 1})
    score_bad = wb.add_format({'bold': True, 'bg_color': '#FFC7CE', 'border': 1})

    dims = norm['dimensions']
    s = norm['scoring']
    m = norm['market']

    def score_fmt(val, max_val):
        pct = val / max_val if max_val > 0 else 0
        return score_good if pct >= 0.7 else score_mid if pct >= 0.4 else score_bad

    def write_dim_row(ws, row, name, data):
        ws.write(row, 0, name, cell_fmt)
        ws.write(row, 1, data['score'], score_fmt(data['score'], data['max']))
        ws.write(row, 2, data['max'], cell_fmt)
        ws.write(row, 3, data['label'], cell_fmt)

    # ========== Sheet 1: 评分总览 ==========
    ws1 = wb.add_worksheet('评分总览')
    ws1.set_column(0, 0, 14); ws1.set_column(1, 1, 8); ws1.set_column(2, 2, 8); ws1.set_column(3, 3, 60)
    ws1.write(0, 0, f"淘宝品类五维评分: {norm['query']}", hdr_fmt)
    ws1.merge_range(0, 0, 0, 3, f"淘宝品类五维评分: {norm['query']}", hdr_fmt)
    ws1.write(1, 0, '维度', hdr_fmt); ws1.write(1, 1, '得分', hdr_fmt)
    ws1.write(1, 2, '满分', hdr_fmt); ws1.write(1, 3, '分析', hdr_fmt)
    write_dim_row(ws1, 2, '市场规模', dims['marketSize'])
    write_dim_row(ws1, 3, '增长潜力', dims['growthPotential'])
    write_dim_row(ws1, 4, '竞争烈度', dims['competition'])
    write_dim_row(ws1, 5, '进入壁垒', dims['entryBarrier'])
    write_dim_row(ws1, 6, '利润空间', dims['profitMargin'])
    ws1.write(7, 0, '总分', hdr_fmt)
    ws1.write(7, 1, s['total'], score_fmt(s['total'], 100))
    ws1.write(7, 2, 100, cell_fmt)
    ws1.write(7, 3, f"{s['rating']} — {s['recommendation']}", cell_fmt)
    # 评分柱状图
    chart_score = wb.add_chart({'type': 'column'})
    chart_score.add_series({'name': '得分','categories':'=评分总览!$A$3:$A$7','values':'=评分总览!$B$3:$B$7'})
    chart_score.set_title({'name': '五维评分'})
    ws1.insert_chart('F1', chart_score)

    # ========== Sheet 2: 市场规模 ==========
    ws2 = wb.add_worksheet('市场规模')
    ws2.write(0, 0, '指标', hdr_fmt); ws2.write(0, 1, '数值', hdr_fmt)
    ws2.write(1, 0, '预估总销量(件)', cell_fmt); ws2.write(1, 1, m['total_sales'], num_fmt)
    ws2.write(2, 0, '分析产品数', cell_fmt); ws2.write(2, 1, norm['analyzed_count'], num_fmt)
    ws2.write(3, 0, '平均价格', cell_fmt); ws2.write(3, 1, m['avg_price'], cell_fmt)
    ws2.write(4, 0, '中位数价格', cell_fmt); ws2.write(4, 1, m['median_price'], cell_fmt)

    # ========== Sheet 3: 增长潜力 ==========
    ws3 = wb.add_worksheet('增长潜力')
    ws3.write(0, 0, '指标', hdr_fmt); ws3.write(0, 1, '数值', hdr_fmt)
    g = norm['growth']
    ws3.write(1, 0, '新品销量占比', cell_fmt); ws3.write(1, 1, g['newness_ratio'], cell_fmt)
    ws3.write(2, 0, '近6月上架产品', cell_fmt); ws3.write(2, 1, g['listing_6m'], num_fmt)
    ws3.write(3, 0, '首单价产品', cell_fmt); ws3.write(3, 1, g['first_price'], num_fmt)
    ws3.write(4, 0, '标题新品词产品', cell_fmt); ws3.write(4, 1, g['new_title'], num_fmt)
    ws3.write(5, 0, '热销爆款产品', cell_fmt); ws3.write(5, 1, g['hot_bomb'], num_fmt)
    ws3.write(6, 0, '在榜产品', cell_fmt); ws3.write(6, 1, g['hot_list'], num_fmt)
    ws3.write(7, 0, 'C店销量占比(参考)', cell_fmt); ws3.write(7, 1, g.get('cstore_ratio',''), cell_fmt)
    ws3.write(8, 0, '数据层级', cell_fmt); ws3.write(8, 1, norm['data_quality']['growth_tier'], cell_fmt)
    # 增长信号柱状图
    if norm['growth']['hot_bomb']+norm['growth']['hot_list']+norm['growth']['first_price']+norm['growth']['new_title']>0:
        chart_growth = wb.add_chart({'type': 'column'})
        ws3.write(10,0,'信号类型',hdr_fmt);ws3.write(10,1,'数量',hdr_fmt)
        ws3.write(11,0,'热销爆款',cell_fmt);ws3.write(11,1,norm['growth']['hot_bomb'],num_fmt)
        ws3.write(12,0,'在榜产品',cell_fmt);ws3.write(12,1,norm['growth']['hot_list'],num_fmt)
        ws3.write(13,0,'首单价',cell_fmt);ws3.write(13,1,norm['growth']['first_price'],num_fmt)
        ws3.write(14,0,'标题新品',cell_fmt);ws3.write(14,1,norm['growth']['new_title'],num_fmt)
        chart_growth.add_series({'name':'信号数','categories':'=增长潜力!$A$11:$A$14','values':'=增长潜力!$B$11:$B$14'})
        chart_growth.set_title({'name': '增长信号分布'})
        ws3.insert_chart('D1', chart_growth)

    # ========== Sheet 4: 竞争格局 ==========
    ws4 = wb.add_worksheet('竞争格局')
    ws4.write(0, 0, '指标', hdr_fmt); ws4.write(0, 1, '数值', hdr_fmt)
    c = norm['competition']
    ws4.write(1, 0, '店铺CR3', cell_fmt); ws4.write(1, 1, c['cr3_store'], cell_fmt)
    ws4.write(2, 0, '品牌CR3', cell_fmt); ws4.write(2, 1, c['cr3_brand'], cell_fmt)
    ws4.write(3, 0, 'HHI指数', cell_fmt); ws4.write(3, 1, int(float(c['hhi'])), num_fmt)
    ws4.write(4, 0, '平均同类商品数', cell_fmt); ws4.write(4, 1, c['avg_same_count'], num_fmt)
    ws4.write(5, 0, 'HHI数据来源', cell_fmt); ws4.write(5, 1, norm['hhi_source'], cell_fmt)

    # ========== Sheet 5: 进入壁垒 ==========
    ws5 = wb.add_worksheet('进入壁垒')
    ws5.write(0, 0, '指标', hdr_fmt); ws5.write(0, 1, '数值', hdr_fmt)
    ws5.write(1, 0, '壁垒类型', cell_fmt); ws5.write(1, 1, norm['barrier']['barrier_type'], cell_fmt)
    ws5.write(2, 0, '天猫占比', cell_fmt); ws5.write(2, 1, m['tmall_ratio'], cell_fmt)
    ws5.write(3, 0, '旗舰店占比', cell_fmt); ws5.write(3, 1, m.get('flagship_ratio',''), cell_fmt)
    ws5.write(4, 0, '新品活跃度', cell_fmt); ws5.write(4, 1, norm['barrier']['newness_level'], cell_fmt)
    ws5.write(5, 0, '补贴折价指数', cell_fmt); ws5.write(5, 1, norm['barrier']['subsidy_index'], cell_fmt)

    # ========== Sheet 6: 利润空间 ==========
    ws6 = wb.add_worksheet('利润空间')
    ws6.write(0, 0, '指标', hdr_fmt); ws6.write(0, 1, '数值', hdr_fmt)
    p = norm['profit']
    ws6.write(1, 0, '平均价格', cell_fmt); ws6.write(1, 1, p['avg_price'], cell_fmt)
    ws6.write(2, 0, '中位数价格', cell_fmt); ws6.write(2, 1, p['median_price'], cell_fmt)
    ws6.write(3, 0, '价格区间', cell_fmt); ws6.write(3, 1, p['price_range'], cell_fmt)

    # ========== Sheet 7: 价格带分布 ==========
    ws7 = wb.add_worksheet('价格带分布')
    ws7.write(0, 0, '价格带', hdr_fmt); ws7.write(0, 1, '产品数', hdr_fmt)
    ws7.write(0, 2, '占比', hdr_fmt); ws7.write(0, 3, '销量', hdr_fmt)
    price_bands = norm.get('price_bands', [])
    for i, pb in enumerate(price_bands):
        ws7.write(i+1, 0, pb['label'], cell_fmt)
        ws7.write(i+1, 1, pb['count'], num_fmt)
        pct = pb['count']/norm['analyzed_count'] if norm['analyzed_count'] > 0 else 0
        ws7.write(i+1, 2, pct, pct_fmt)
        ws7.write(i+1, 3, pb['sales'], num_fmt)

    # 价格带柱状图
    if price_bands:
        chart = wb.add_chart({'type': 'column'})
        chart.add_series({'name': '产品数', 'categories': f'=价格带分布!$A$2:$A${len(price_bands)+1}',
                          'values': f'=价格带分布!$B$2:$B${len(price_bands)+1}'})
        chart.set_title({'name': '价格带产品分布'})
        ws7.insert_chart('F1', chart)

    # ========== Sheet 8: 品牌分析 ==========
    ws8 = wb.add_worksheet('品牌分析')
    ws8.write(0, 0, '排名', hdr_fmt); ws8.write(0, 1, '品牌', hdr_fmt); ws8.write(0, 2, '产品数', hdr_fmt)
    brands = norm.get('top_brands', [])
    for i, br in enumerate(brands[:20], 1):
        ws8.write(i, 0, i, cell_fmt); ws8.write(i, 1, br.get('brand',''), cell_fmt)
        ws8.write(i, 2, br.get('count',0), num_fmt)

    # ========== Sheet 9: 店铺分析 ==========
    ws9 = wb.add_worksheet('店铺分析')
    ws9.write(0, 0, '排名', hdr_fmt); ws9.write(0, 1, '店铺', hdr_fmt)
    ws9.write(0, 2, '预估销量', hdr_fmt); ws9.write(0, 3, '份额', hdr_fmt)
    shops = norm.get('top_shops', [])
    for i, sh in enumerate(shops[:20], 1):
        ws9.write(i, 0, i, cell_fmt); ws9.write(i, 1, sh.get('shop',''), cell_fmt)
        ws9.write(i, 2, sh.get('sales',0), num_fmt)
        ws9.write(i, 3, sh.get('share',''), cell_fmt)

    # ========== Sheet 10: 产品清单 ==========
    ws10 = wb.add_worksheet('产品清单')
    ws10.write(0, 0, '排名', hdr_fmt); ws10.write(0, 1, '产品标题', hdr_fmt)
    ws10.write(0, 2, '价格', hdr_fmt); ws10.write(0, 3, '销量', hdr_fmt)
    ws10.write(0, 4, '月销额(估)', hdr_fmt); ws10.write(0, 5, '店铺', hdr_fmt)
    ws10.write(0, 6, '店铺类型', hdr_fmt); ws10.write(0, 7, '发货地', hdr_fmt)
    ws10.write(0, 8, '品牌', hdr_fmt); ws10.write(0, 9, '上架日期', hdr_fmt)
    ws10.write(0, 10, '近6月新品', hdr_fmt); ws10.write(0, 11, '热销', hdr_fmt)
    ws10.write(0, 12, '同类数', hdr_fmt); ws10.write(0, 13, '商品链接', hdr_fmt)
    ws10.set_column(1, 1, 45); ws10.set_column(13, 13, 45)
    products = norm.get('products', [])
    for i, pr in enumerate(products, 1):
        ws10.write(i, 0, i, cell_fmt); ws10.write(i, 1, pr.get('title',''), cell_fmt)
        ws10.write(i, 2, pr.get('price',''), cell_fmt); ws10.write(i, 3, pr.get('sales',''), cell_fmt)
        # 估算月销额
        try:
            price_str = str(pr.get('price','¥0')).replace('¥','').split(' ')[0].replace(',','')
            price_num = float(price_str)
            sales_str = pr.get('sales','0').replace('万+人付款','0000').replace('+人付款','').replace(',','')
            sales_num = float(sales_str) if sales_str else 0
            revenue_est = price_num * sales_num
            ws10.write(i, 4, f'¥{revenue_est:,.0f}' if revenue_est > 0 else '', cell_fmt)
        except:
            ws10.write(i, 4, '', cell_fmt)
        ws10.write(i, 5, pr.get('shop',''), cell_fmt); ws10.write(i, 6, pr.get('shopType',''), cell_fmt)
        ws10.write(i, 7, pr.get('location',''), cell_fmt); ws10.write(i, 8, pr.get('brand',''), cell_fmt)
        ws10.write(i, 9, pr.get('listingDate',''), cell_fmt)
        ws10.write(i, 10, '是' if pr.get('isRecent6m') else '', cell_fmt)
        hot = ('热销' if pr.get('hasHotBomb') else '') + ('在榜' if pr.get('hasHotList') else '')
        ws10.write(i, 11, hot, cell_fmt)
        ws10.write(i, 12, pr.get('sameCount',0), num_fmt)
        item_id = pr.get('item_id','')
        ws10.write(i, 13, f'https://item.taobao.com/item.htm?id={item_id}' if item_id else '', cell_fmt)

    # ========== Sheet 11: 策略建议 ==========
    ws11 = wb.add_worksheet('策略建议')
    ws11.write(0, 0, '类别', hdr_fmt); ws11.write(0, 1, '内容', hdr_fmt)
    ws11.set_column(1, 1, 80)
    ws11.write(1, 0, '优势', cell_fmt); ws11.write(1, 1, generate_advantages(norm), cell_fmt)
    ws11.write(2, 0, '劣势', cell_fmt); ws11.write(2, 1, generate_disadvantages(norm), cell_fmt)
    ws11.write(3, 0, '机会', cell_fmt); ws11.write(3, 1, generate_opportunities(norm), cell_fmt)
    ws11.write(4, 0, '威胁', cell_fmt); ws11.write(4, 1, generate_threats(norm), cell_fmt)
    ws11.write(5, 0, '进入策略', cell_fmt); ws11.write(5, 1, entry_strategy(norm), cell_fmt)
    ws11.write(6, 0, '风险提示', cell_fmt); ws11.write(6, 1, risk_warning(norm), cell_fmt)
    ws11.write(7, 0, '适合卖家', cell_fmt); ws11.write(7, 1, suitable_seller(norm), cell_fmt)
    ws11.write(8, 0, '不适合卖家', cell_fmt); ws11.write(8, 1, unsuitable_seller(norm), cell_fmt)

    # ========== Sheet 12: 数据质量 ==========
    ws12 = wb.add_worksheet('数据质量')
    ws12.write(0, 0, '指标', hdr_fmt); ws12.write(0, 1, '数值', hdr_fmt)
    dq = norm['data_quality']
    ws12.write(1, 0, '上市时间覆盖率', cell_fmt); ws12.write(1, 1, dq['listing_coverage'], cell_fmt)
    ws12.write(2, 0, '增长数据层级', cell_fmt); ws12.write(2, 1, dq['growth_tier'], cell_fmt)
    ws12.write(3, 0, '增长数据源', cell_fmt); ws12.write(3, 1, dq['growth_source'], cell_fmt)
    ws12.write(4, 0, '品牌数据覆盖率', cell_fmt); ws12.write(4, 1, dq.get('brandCoverage',''), cell_fmt)
    ws12.write(5, 0, 'HHI数据源', cell_fmt); ws12.write(5, 1, norm['hhi_source'], cell_fmt)
    ws12.write(6, 0, '模型版本', cell_fmt); ws12.write(6, 1, norm['model_version'], cell_fmt)
    ws12.write(7, 0, '生成时间', cell_fmt); ws12.write(7, 1, datetime.now().isoformat(), cell_fmt)

    wb.close()
    return output_path


# ============================================================
# HTML 仪表板生成
# ============================================================

def generate_html(norm: dict, output_path: str):
    """生成 HTML 仪表板 (Chart.js)"""
    dims = norm['dimensions']
    s = norm['scoring']

    dim_names = ['市场规模', '增长潜力', '竞争烈度', '进入壁垒', '利润空间']
    dim_keys = ['marketSize', 'growthPotential', 'competition', 'entryBarrier', 'profitMargin']
    dim_scores = [dims[k]['score'] for k in dim_keys]
    dim_maxs = [dims[k]['max'] for k in dim_keys]

    price_bands = norm.get('price_bands', [])
    pb_labels = [p['label'] for p in price_bands]
    pb_counts = [p['count'] for p in price_bands]

    shops = norm.get('top_shops', [])[:5]
    shop_labels = [s['shop'][:8] for s in shops]
    shop_sales = [s['sales'] for s in shops]

    # Build JS scripts separately (avoid f-string brace escaping issues)
    js_scripts = f'''
<script>
new Chart(document.getElementById('radarChart'), {{
    type: 'radar',
    data: {{
        labels: {json.dumps(dim_names, ensure_ascii=False)},
        datasets: [{{
            label: '得分',
            data: {json.dumps(dim_scores)},
            borderColor: '#4472C4',
            backgroundColor: 'rgba(68,114,196,0.2)'
        }}]
    }},
    options: {{
        scales: {{
            r: {{ suggestedMin: 0, suggestedMax: {max(dim_maxs)} }}
        }}
    }}
}});

new Chart(document.getElementById('priceChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(pb_labels, ensure_ascii=False)},
        datasets: [{{
            label: '产品数',
            data: {json.dumps(pb_counts)},
            backgroundColor: '#4472C4'
        }}]
    }}
}});

new Chart(document.getElementById('shopChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(shop_labels, ensure_ascii=False)},
        datasets: [{{
            label: '预估销量',
            data: {json.dumps(shop_sales)},
            backgroundColor: '#5B9BD5'
        }}]
    }}
}});
</script>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{norm['query']} - 淘宝品类选品分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f7fa;color:#333;padding:20px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{text-align:center;margin-bottom:5px;font-size:24px}}
.subtitle{{text-align:center;color:#888;margin-bottom:20px;font-size:14px}}
.score-big{{text-align:center;margin:15px 0;font-size:48px;font-weight:bold;color:{"#22c55e" if s["total"]>=80 else "#3b82f6" if s["total"]>=70 else "#f59e0b" if s["total"]>=50 else "#ef4444"}}}
.rating-badge{{display:inline-block;padding:4px 16px;border-radius:20px;font-weight:bold;font-size:18px;background:{"#C6EFCE" if s["total"]>=80 else "#BDD7EE" if s["total"]>=70 else "#FFEB9C" if s["total"]>=50 else "#FFC7CE"}}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}}
.card{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.card h3{{margin-bottom:12px;font-size:16px;color:#555}}
.card.full{{grid-column:1/-1}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{background:#4472C4;color:#fff;padding:8px 12px;text-align:left;font-weight:bold}}
td{{padding:8px 12px;border-bottom:1px solid #eee}}
tr:hover td{{background:#f0f4ff}}
</style>
</head>
<body>
<div class="container">
<h1>🔍 {norm['query']} — 淘宝品类选品分析</h1>
<p class="subtitle">模型: {norm['model_version']} | 分析产品: {norm['analyzed_count']} | {datetime.now().strftime('%Y-%m-%d %H:%M')} | 数据源: 淘宝/天猫</p>

<div style="text-align:center">
<span class="rating-badge">{s["rating"]}</span>
<div class="score-big">{s["total"]}<span style="font-size:20px;color:#999">/100</span></div>
<p style="font-size:15px;color:#666;margin-top:5px">{s["recommendation"]}</p>
</div>

<div class="grid">
<div class="card">
<h3>五维评分</h3>
<canvas id="radarChart" height="280"></canvas>
</div>
<div class="card">
<h3>市场概况</h3>
<table>
<tr><td><strong>预估总销量</strong></td><td>{norm["market"]["total_sales"]:,} 件</td></tr>
<tr><td><strong>平均价格</strong></td><td>{norm["market"]["avg_price"]}</td></tr>
<tr><td><strong>天猫占比</strong></td><td>{norm["market"]["tmall_ratio"]}</td></tr>
<tr><td><strong>店铺CR3</strong></td><td>{norm["competition"]["cr3_store"]}</td></tr>
<tr><td><strong>HHI指数</strong></td><td>{norm["competition"]["hhi"]}</td></tr>
<tr><td><strong>壁垒类型</strong></td><td>{norm["barrier"]["barrier_type"]}</td></tr>
</table>
</div>
<div class="card">
<h3>价格带分布</h3>
<canvas id="priceChart" height="220"></canvas>
</div>
<div class="card">
<h3>Top 5 店铺</h3>
<canvas id="shopChart" height="220"></canvas>
</div>
<div class="card full">
<h3>评分详情</h3>
<table>
<tr><th>维度</th><th>得分</th><th>满分</th><th>分析</th></tr>
'''
    for i, key in enumerate(dim_keys):
        d = dims[key]
        html += f'<tr><td>{dim_names[i]}</td><td><strong>{d["score"]}</strong></td><td>{d["max"]}</td><td>{d["label"]}</td></tr>\n'

    html += f'''
</table>
</div>
<div class="card full">
<h3>选品建议</h3>
<table>
<tr><td><strong>优势</strong></td><td>{generate_advantages(norm).replace(chr(10),'<br>')}</td></tr>
<tr><td><strong>劣势</strong></td><td>{generate_disadvantages(norm).replace(chr(10),'<br>')}</td></tr>
<tr><td><strong>机会</strong></td><td>{generate_opportunities(norm).replace(chr(10),'<br>')}</td></tr>
<tr><td><strong>威胁</strong></td><td>{generate_threats(norm).replace(chr(10),'<br>')}</td></tr>
<tr><td><strong>适合卖家</strong></td><td>{suitable_seller(norm)}</td></tr>
</table>
</div>
</div>
'''
    html += js_scripts
    html += f'''
</div>
</div>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


# ============================================================
# 主入口
# ============================================================

def main():
    # 🆕 自动检测并启动 daemon
    import subprocess as _sp
    try:
        r = _sp.run(['bb-browser', 'daemon', 'status'], capture_output=True, text=True, timeout=5)
        if 'Daemon running: no' in (r.stdout or ''):
            print('[AUTO] 启动 bb-browser daemon...')
            _sp.run(['bb-browser', 'daemon', 'start'], capture_output=True, timeout=15)
            import time; time.sleep(3)
            print('[AUTO] daemon 已启动')
    except Exception:
        pass  # daemon 不可用时静默跳过

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    # 加载数据
    raw = load_data(input_file)
    norm = normalize(raw)

    # 🆕 注入1688数据
    _1688_file = os.path.join(os.path.dirname(os.path.abspath(input_file)), os.path.basename(input_file).replace('.json','_1688.json'))
    # Also check /tmp/ fallback
    if not os.path.exists(_1688_file):
        _1688_file = '/tmp/' + os.path.basename(input_file).replace('.json','_1688.json')
    if os.path.exists(_1688_file):
        with open(_1688_file, 'r', encoding='utf-8-sig') as f:
            norm['data_1688'] = json.load(f)
        print('[OK] 1688 loaded: ' + str(norm['data_1688']['prices']))

    # Determine output directory
    query_safe = re.sub(r'[^\w]', '_', norm['query'])
    date_str = datetime.now().strftime('%Y%m%d')
    report_subdir = f'{query_safe}_{date_str}'

    if not output_dir:
        output_dir = f'taobao-reports/{report_subdir}'
    else:
        output_dir = os.path.join(output_dir, report_subdir)

    os.makedirs(output_dir, exist_ok=True)

    # 保存原始数据
    data_path = os.path.join(output_dir, 'data.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f'[OK] data: {data_path}')

    # Generate Markdown
    template = os.path.join(os.path.dirname(__file__), 'report_template.md')
    # 如果已有LLM分析，注入到模板变量中
    llm_file = os.path.join(output_dir, 'llm_analysis.md')
    if os.path.exists(llm_file):
        with open(llm_file, 'r', encoding='utf-8') as f:
            norm['llm_analysis'] = f.read()
    md = generate_markdown(norm, template)
    md_path = os.path.join(output_dir, 'report.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'[OK] markdown: {md_path}')

    # Generate Excel
    xlsx_path = os.path.join(output_dir, 'report.xlsx')
    generate_excel(norm, xlsx_path)
    print(f'[OK] excel: {xlsx_path}')

    # Generate HTML
    html_path = os.path.join(output_dir, 'dashboard.html')
    generate_html(norm, html_path)
    print(f'[OK] html: {html_path}')

    # Generate LLM data brief
    brief = generate_data_brief(norm)
    brief_path = os.path.join(output_dir, 'data_brief.md')
    with open(brief_path, 'w', encoding='utf-8') as f:
        f.write(brief)
    print(f'[OK] data_brief: {brief_path}')

    print(f'\n[DONE] All reports saved to: {os.path.abspath(output_dir)}')


if __name__ == '__main__':
    main()
