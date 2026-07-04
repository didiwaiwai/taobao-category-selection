#!/usr/bin/env python3
"""
1688采购成本采集工具 — 纯后台 mtop API (与淘宝完全相同)
使用方法:
  python scripts/collect_1688.py <关键词>

流程:
  1. 调用 bb-browser site 1688/offer-score (adapter自行处理导航+API)
  2. 保存 data_<关键词>_1688.json
"""

import subprocess, json, sys, os, shutil

BB = shutil.which('bb-browser') or shutil.which('bb-browser.cmd')
if not BB:
    npm_global = os.path.expandvars(r'%APPDATA%\npm')
    for name in ['bb-browser', 'bb-browser.cmd', 'bb-browser.ps1']:
        p = os.path.join(npm_global, name)
        if os.path.exists(p): BB = p; break
if not BB:
    print("Error: bb-browser not found")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python collect_1688.py <keyword> [--pages N]")
        sys.exit(1)

    keyword = sys.argv[1]
    auto_mode = '--auto' in sys.argv

    print(f"[1/1] 1688 mtop API: {keyword}")
    result = subprocess.run(
        [BB, 'site', '1688/offer-score', keyword, '--json'],
        capture_output=True, timeout=300
    )

    try:
        stdout = result.stdout.decode('utf-8', errors='replace')
        json_line = ''
        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('{'):
                json_line = line
                break
        if not json_line:
            json_line = stdout.strip()

        raw = json.loads(json_line)
        data = raw.get('result', raw)

        if data.get('error'):
            detail = data.get('detail','') or data.get('hint','') or ''
            print(f"  Error: {data['error']} — {detail}")
            sys.exit(1)

        prices = data.get('prices', [])
        valid = sorted(set([p for p in prices if 0.05 < p < 50000]))
        stats = data.get('stats', {})
        seg = data.get('priceSegments', {})

        print(f"  Products: {data.get('totalProducts',0)} ({data.get('dedupedProducts',0)} unique)")
        print(f"  Pages: {data.get('pagesCrawled',0)} x {data.get('perPage',60)}")
        print(f"  Prices: {len(valid)} | Range: {min(valid):.2f}~{max(valid):.2f} | Median: {stats.get('median',0):.2f}")
        print(f"  Match: {data.get('keywordMatch',0):.0%} | Method: {data.get('method','?')}")

        plist = []
        for p in data.get('products', [])[:25]:
            plist.append({
                'title': p.get('title', '')[:60],
                'price': p.get('price', 0),
                'sales': p.get('sales', 0),
                'shop': str(p.get('shop', ''))[:25],
                'repurchase': p.get('repurchase', 0)
            })

        output = {
            'prices': valid,
            'total_products_scraped': data.get('totalProducts', 0),
            'deduped_products': data.get('dedupedProducts', 0),
            'pages_scraped': data.get('pagesCrawled', 0),
            'stats': stats,
            'price_segments': {
                'budget_0_50': seg.get('budget', 0),
                'mid_50_150': seg.get('mid', 0),
                'premium_150_500': seg.get('premium', 0),
                'high_500_plus': seg.get('high', 0),
            },
            'keyword': keyword,
            'keyword_match': data.get('keywordMatch', 0),
            'source': '1688 mtop API',
            'products': plist
        }

        output_path = '/tmp/taobao_data_1688.json' if auto_mode else f'data_{keyword}_1688.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {output_path}")

    except json.JSONDecodeError:
        print(f"  JSON parse error")
        sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
