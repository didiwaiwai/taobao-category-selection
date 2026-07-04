#!/usr/bin/env python3
"""
淘宝关键词建议采集 — 调用 suggest.taobao.com
用法: python scripts/collect_keywords.py <关键词>
输出: data_<关键词>_keywords.json
"""

import subprocess, json, sys, shutil, os

BB = shutil.which('bb-browser') or shutil.which('bb-browser.cmd')
if not BB:
    npm_global = os.path.expandvars(r'%APPDATA%\npm')
    for name in ['bb-browser', 'bb-browser.cmd', 'bb-browser.ps1']:
        p = os.path.join(npm_global, name)
        if os.path.exists(p): BB = p; break

def main():
    if len(sys.argv) < 2:
        print("Usage: python collect_keywords.py <keyword>")
        sys.exit(1)

    keyword = sys.argv[1]
    print(f"[1/1] Keyword suggest: {keyword}")
    result = subprocess.run(
        [BB, 'site', 'taobao/keyword-suggest', keyword, '--json'],
        capture_output=True, timeout=60
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
            print(f"  Error: {data['error']}")
            sys.exit(1)

        keywords = data.get('main_keywords', [])
        extended = data.get('extended_keywords', [])
        print(f"  Main: {len(keywords)} keywords, Extended: {len(extended)}")

        # Format for output
        output = {
            'keyword': keyword,
            'main': [{'kw': k['keyword'], 'pop': k['popularity']} for k in keywords],
            'extended': [{'kw': k['keyword'], 'pop': k['popularity']} for k in extended],
            'total': len(keywords) + len(extended),
            'source': 'suggest.taobao.com (free)',
            'note': 'pop值越大=搜索热度越高, 可比较相对热度但非绝对搜索量'
        }

        path = f'data_{keyword}_keywords.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {path}")

    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
