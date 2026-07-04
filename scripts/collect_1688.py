#!/usr/bin/env python3
"""
1688采购成本采集工具 — mtop API版 (与淘宝同架构)
使用方法:
  python scripts/collect_1688.py <关键词>

流程:
  1. 复用1688标签页, goto GBK-URL搜索页 (加载mtop库+pageId)
  2. 调用 1688/offer-score adapter (纯mtop API, 不爬DOM)
  3. 保存 data_<关键词>_1688.json
"""

import subprocess, json, sys, os, re, time, shutil

BB_BROWSER = shutil.which('bb-browser') or shutil.which('bb-browser.cmd')
if not BB_BROWSER:
    npm_global = os.path.expandvars(r'%APPDATA%\npm')
    for name in ['bb-browser', 'bb-browser.cmd', 'bb-browser.ps1']:
        p = os.path.join(npm_global, name)
        if os.path.exists(p): BB_BROWSER = p; break
if not BB_BROWSER:
    print("Error: bb-browser not found")
    sys.exit(1)

TAB_CACHE_FILE = os.path.join(os.path.dirname(__file__), '.1688_tab')

def get_or_create_tab():
    if os.path.exists(TAB_CACHE_FILE):
        with open(TAB_CACHE_FILE, 'r') as f:
            saved = f.read().strip()
        r = subprocess.run([BB_BROWSER, 'eval', '--tab', saved, 'document.title'],
                          capture_output=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return saved
    r = subprocess.run([BB_BROWSER, 'open', 'https://www.1688.com/'],
                      capture_output=True, timeout=30)
    m = re.search(rb'tab:\s*(\S+)', r.stdout)
    if m:
        tab = m.group(1).decode()
        with open(TAB_CACHE_FILE, 'w') as f:
            f.write(tab)
        time.sleep(3)
        return tab
    raise RuntimeError("Cannot create 1688 tab")

def main():
    if len(sys.argv) < 2:
        print("Usage: python collect_1688.py <keyword> [--pages N]")
        sys.exit(1)

    keyword = sys.argv[1]
    auto_mode = '--auto' in sys.argv

    # 1. GBK URL + goto
    gbk = ''.join(['%{:02X}'.format(b) for b in keyword.encode('gbk')])
    url = f'https://s.1688.com/selloffer/offer_search.htm?keywords={gbk}'

    tab = get_or_create_tab()
    print(f"[1/2] Open search: {keyword} (tab: {tab})")
    subprocess.run([BB_BROWSER, 'goto', '--tab', tab, url],
                  capture_output=True, timeout=30)
    time.sleep(6)

    # 2. Run adapter (mtop API only, no DOM scraping)
    print(f"[2/2] Query mtop API...")
    result = subprocess.run(
        [BB_BROWSER, 'site', '1688/offer-score', keyword, '--json'],
        capture_output=True, timeout=180
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
            if 'no_page_id' in str(data.get('error','')):
                if os.path.exists(TAB_CACHE_FILE): os.remove(TAB_CACHE_FILE)
            sys.exit(1)

        prices = data.get('prices', [])
        valid = sorted(set([p for p in prices if 0.05 < p < 50000]))
        stats = data.get('stats', {})
        seg = data.get('priceSegments', {})

        print(f"  Products: {data.get('totalProducts',0)} ({data.get('dedupedProducts',0)} unique)")
        print(f"  Pages: {data.get('pagesCrawled',0)} x {60} items")
        print(f"  Prices: {len(valid)} | Range: {min(valid):.2f}~{max(valid):.2f} | Median: {stats.get('median',0):.2f}")
        print(f"  Match: {data.get('keywordMatch',0):.0%} | Method: {data.get('method','?')}")

        # Product list for report
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
        print(f"  JSON parse error: {stdout[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
