#!/usr/bin/env python3
"""
1688采购成本采集工具
使用方法:
  python scripts/collect_1688.py <关键词> [--tab <tab_id>]

流程:
  1. 自动打开1688搜索页
  2. 等待用户手动过验证码(如需)
  3. 提取批发价格
  4. 保存为 data_1688.json
"""

import subprocess, json, sys, os, time, re, shutil

# 自动定位 bb-browser
BB_BROWSER = shutil.which('bb-browser') or shutil.which('bb-browser.cmd')
if not BB_BROWSER:
    npm_global = os.path.expandvars(r'%APPDATA%\npm')
    for name in ['bb-browser', 'bb-browser.cmd', 'bb-browser.ps1']:
        p = os.path.join(npm_global, name)
        if os.path.exists(p): BB_BROWSER = p; break
if not BB_BROWSER:
    print("错误: 找不到 bb-browser, 请先安装: npm install -g bb-browser")
    sys.exit(1)

def bb(*args):
    try:
        r = subprocess.run([BB_BROWSER] + list(args), capture_output=True, encoding='utf-8', errors='replace')
        return r
    except Exception as e:
        print(f"  bb-browser error: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("用法: python collect_1688.py <关键词> [--tab <tab_id>]")
        print("示例: python collect_1688.py 折叠屏手机壳")
        sys.exit(1)

    keyword = sys.argv[1]
    tab_id = None
    if '--tab' in sys.argv:
        tab_id = sys.argv[sys.argv.index('--tab') + 1]

    print(f"[1/4] 打开1688搜索: {keyword}")
    # 打开1688搜索
    url = f'https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}'

    if tab_id:
        result = bb('goto', url, '--tab', tab_id)
    else:
        result = bb('open', url)
        # 提取新标签页ID
        match = re.search(r'tab:\s*(\S+)', result.stdout)
        if match:
            tab_id = match.group(1)

    if not tab_id:
        print("错误: 无法获取1688标签页ID")
        sys.exit(1)

    print(f"  标签页: {tab_id}")
    print(f"[2/4] 等待页面加载(5秒)...")
    time.sleep(5)

    auto_mode = '--auto' in sys.argv

    # 检查是否需要验证码
    snap = bb('snap', '--tab', tab_id, '-d', '2')
    snap_text = snap.stdout if snap else ''
    if '验证码' in snap_text or 'punish' in snap_text:
        if auto_mode:
            print("  ⚠️ 1688验证码拦截,自动跳过")
            sys.exit(0)
        print("  ⚠️ 1688需要滑块验证,请手动在Chrome中完成验证...")
        print("  完成后按Enter继续")
        input()
        time.sleep(2)

    print("[3/4] 提取价格数据...")
    # JavaScript提取
    extract_js = """(function() {
        var prices = [];
        var text = document.body.innerText;
        var re = /[\\u00a5]\\s*(\\d+\\.?\\d*)/g;
        var m;
        while ((m = re.exec(text)) !== null) {
            var v = parseFloat(m[1]);
            if (v > 1 && v < 500 && prices.indexOf(v) === -1) prices.push(v);
        }
        if (prices.length < 3) {
            document.querySelectorAll('*').forEach(function(el) {
                var t = el.innerText;
                if (t && t.length < 15 && /^[0-9.]+$/.test(t.trim())) {
                    var n = parseFloat(t);
                    if (n > 1 && n < 500 && prices.length < 40) prices.push(n);
                }
            });
        }
        prices.sort(function(a,b) { return a-b; });
        return JSON.stringify({prices: prices.slice(0, 25)});
    })()"""

    result = bb('eval', '--tab', tab_id, extract_js)

    try:
        data = json.loads(result.stdout.strip())
        prices = data.get('prices', [])
        if not prices:
            print("  未提取到价格数据")
            sys.exit(1)

        # 过滤噪音，保留合理价格区间
        valid_prices = [p for p in prices if 1 < p < 1000]
        if len(valid_prices) > 10:
            # 去重并排序
            valid_prices = sorted(set(valid_prices))

        print(f"  提取到 {len(valid_prices)} 个价格: ¥{min(valid_prices):.0f} ~ ¥{max(valid_prices):.0f}")

        # 保存
        output = {'prices': valid_prices}
        output_path = '/tmp/taobao_data_1688.json' if auto_mode else f'data_{keyword}_1688.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)

        print(f"[4/4] 保存到: {output_path}")
        print(f"\n下一步: python scripts/generate_taobao_report.py data.json")
        print(f"  (确保 data_{keyword}_1688.json 与 data.json 在同一目录)")

    except json.JSONDecodeError:
        print(f"  解析失败,原始输出: {result.stdout[:200]}")
        sys.exit(1)


if __name__ == '__main__':
    main()
