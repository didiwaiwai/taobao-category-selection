/* @meta
{
  "name": "taobao/keyword-suggest",
  "description": "淘宝关键词建议 — 调用 suggest.taobao.com 免费API获取相关词+热度指数",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "返回数量 (默认10)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/keyword-suggest 蓝牙耳机 --json"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var count = Math.min(parseInt(args.count) || 10, 10);

  try {
    // Use JSONP callback to bypass CORS
    function suggestFetch(q) {
      return new Promise(function(resolve, reject) {
        var callbackName = 'sug_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
        var script = document.createElement('script');
        var timeout = setTimeout(function() {
          cleanup();
          reject('timeout');
        }, 8000);

        function cleanup() {
          clearTimeout(timeout);
          if (script.parentNode) script.parentNode.removeChild(script);
          delete window[callbackName];
        }

        window[callbackName] = function(data) {
          cleanup();
          resolve(data);
        };

        script.src = 'https://suggest.taobao.com/sug?code=utf-8&q=' + encodeURIComponent(q) + '&callback=' + callbackName;
        script.onerror = function() { cleanup(); reject('network_error'); };
        document.head.appendChild(script);
      });
    }

    var data = await suggestFetch(query);
    var results = (data.result || []).slice(0, count);

    var keywords = results.map(function(r) {
      return { keyword: r[0], popularity: parseFloat(r[1]) || 0 };
    });

    // Extended: try with first char as prefix
    var extended = [];
    var prefix = query.substring(0, 1);
    if (prefix !== query) {
      try {
        var extData = await suggestFetch(prefix);
        var extResults = (extData.result || []).slice(0, 20);
        for (var i = 0; i < extResults.length; i++) {
          var exists = keywords.some(function(k) { return k.keyword === extResults[i][0]; });
          if (!exists) {
            extended.push({ keyword: extResults[i][0], popularity: parseInt(extResults[i][1]) || 0 });
          }
        }
      } catch(e) { /* skip */ }
    }

    return {
      query: query,
      main_keywords: keywords,
      extended_keywords: extended.slice(0, 30),
      total_found: keywords.length + extended.length,
      popularity_scale: 'relative (taobao suggest index, higher = more searches)',
      source: 'suggest.taobao.com'
    };

  } catch(e) {
    return {error: 'fetch_error', detail: String(e)};
  }
}
