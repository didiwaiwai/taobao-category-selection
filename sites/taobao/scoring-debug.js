/* @meta
{
  "name": "taobao/scoring-debug",
  "description": "调试工具：查看淘宝搜索API返回的完整字段结构，用于开发评分模型",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "返回数量 (默认 3)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/scoring-debug 蓝牙耳机 --count 3"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var count = Math.min(parseInt(args.count) || 3, 5);

  if (typeof window.lib === 'undefined' || !window.lib.mtop) {
    return {error: 'mtop library not loaded', hint: 'Open s.taobao.com in Chrome first'};
  }

  return new Promise(function(resolve) {
    var done = false;
    var timer = setTimeout(function() {
      if (!done) { done = true; resolve({error: 'API timeout'}); }
    }, 15000);

    window.lib.mtop.request({
      api: 'mtop.relationrecommend.WirelessRecommend.recommend',
      v: '2.0',
      data: {
        appId: '34385',
        params: JSON.stringify({
          q: query,
          sort: '_coefp',
          page: '1',
          n: String(count),
          m: 'pc',
          tab: 'all',
          ttid: '600000@taobao_pc_10.7.0'
        })
      },
      dataType: 'jsonp',
      ecode: 0
    }).then(function(r) {
      if (done) return;
      done = true;
      clearTimeout(timer);

      try {
        var items = r.data.itemsArray || [];
        if (!items.length) {
          resolve({error: 'No results'});
          return;
        }

        // 提取第一个产品的所有字段
        var firstItem = items[0];

        // 展示完整字段树
        var fieldTree = {};
        for (var key in firstItem) {
          var val = firstItem[key];
          if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
            // 嵌套对象：列出子字段名和值的类型
            var subFields = {};
            for (var sk in val) {
              var sv = val[sk];
              var type = sv === null ? 'null' : Array.isArray(sv) ? 'array[' + sv.length + ']' : typeof sv;
              subFields[sk] = type;
            }
            fieldTree[key] = subFields;
          } else if (Array.isArray(val)) {
            fieldTree[key] = 'array[' + val.length + ']';
          } else {
            fieldTree[key] = typeof val === 'string' ? ('"' + String(val).substring(0, 60) + '"') : typeof val;
          }
        }

        // 提取所有产品的核心字段
        var allItems = items.map(function(item, idx) {
          var si = item.shopInfo || {};
          var ps = item.priceShow || {};
          return {
            idx: idx,
            item_id: item.item_id,
            title: (item.title || '').substring(0, 80),
            price: item.price,
            priceShow_price: ps.price,
            priceShow_priceDesc: ps.priceDesc,
            realSales: item.realSales,
            nick: item.nick,
            procity: item.procity,
            shopInfo_title: si.title,
            // 尝试可能的额外字段
            commentCount: item.commentCount,
            sellerType: item.sellerType,
            brandName: item.brandName || item.brand,
            rootCatId: item.rootCatId,
            categoryId: item.categoryId,
            nid: item.nid,
            // 列出 item 的所有一级键名
            _allKeys: Object.keys(item)
          };
        });

        resolve({
          query: query,
          count: items.length,
          firstItem_flatKeys: Object.keys(firstItem),
          firstItem_fieldTree: fieldTree,
          items: allItems
        });
      } catch(e) {
        resolve({error: 'Parse error: ' + e.message});
      }
    }, function(err) {
      if (!done) {
        done = true;
        clearTimeout(timer);
        resolve({error: 'API call failed', detail: (err && (err.msg || err.message)) || String(err)});
      }
    });
  });
}
