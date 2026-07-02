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

import subprocess, json, sys, os, time, re

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
    from urllib.parse import quote
    url = f'https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}'

    if tab_id:
        result = subprocess.run(['bb-browser', 'goto', url, '--tab', tab_id], capture_output=True, text=True)
    else:
        result = subprocess.run(['bb-browser', 'open', url], capture_output=True, text=True)
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
    snap = subprocess.run(['bb-browser', 'snap', '--tab', tab_id, '-d', '2'], capture_output=True, text=True)
    if '验证码' in snap.stdout or 'punish' in snap.stdout:
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
        document.querySelectorAll('*').forEach(function(el) {
            var t = el.innerText;
            if (t && t.length < 15 && /^[0-9.]+$/.test(t.trim())) {
                var n = parseFloat(t);
                if (n > 0 && n < 500) prices.push(n);
            }
        });
        prices.sort(function(a,b) { return a-b; });
        return JSON.stringify({prices: prices.slice(0, 30)});
    })()"""

    result = subprocess.run(['bb-browser', 'eval', '--tab', tab_id, extract_js], capture_output=True, text=True)

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
