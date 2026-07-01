/* @meta
{
  "name": "taobao/sales-rank",
  "description": "淘宝品类销量排行 - 按关键词搜索，按销量排序 (title, price, sales, shop, item_id, location)",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "返回数量 (默认 20, 最大 48)"},
    "sort": {"required": false, "description": "排序：sale-desc(销量,默认) total-desc(综合) price-asc(升) price-desc(降)"},
    "page": {"required": false, "description": "页码 (默认 1)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/sales-rank 蓝牙耳机 --count 10"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query', hint: 'bb-browser site taobao/sales-rank 蓝牙耳机'};

  var count = Math.min(parseInt(args.count) || 20, 48);
  var sort = args.sort || 'sale-desc';
  var page = parseInt(args.page) || 1;

  var sortMap = {'sale-desc': '_coefp', 'total-desc': 'default', 'price-asc': 'price-asc', 'price-desc': 'price-desc'};
  var apiSort = sortMap[sort] || sort;

  if (typeof window.lib === 'undefined' || !window.lib.mtop) {
    return {error: 'mtop library not loaded', hint: 'Open s.taobao.com in Chrome first to load the mtop library'};
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
          sort: apiSort,
          page: String(page),
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
        var list = r.data.itemsArray || [];
        var products = list.reduce(function(acc, item) {
          if (acc.length >= count) return acc;
          var title = (item.title || '').replace(/<[^>]+>/g, '').trim();
          if (!title) return acc;
          var shop = (item.shopInfo && item.shopInfo.title) || item.nick || '';
          // priceShow.price is the real display price; item.price may be "9999" placeholder for subsidized items
          var displayPrice = ((item.priceShow && item.priceShow.price) || item.price || '');
          var priceDesc = (item.priceShow && item.priceShow.priceDesc) || '';
          var priceText = '¥' + displayPrice;
          if (priceDesc) priceText += ' (' + priceDesc + ')';
          acc.push({
            title: title,
            price: priceText,
            sales: item.realSales || '',
            shop: shop,
            item_id: item.item_id || '',
            location: item.procity || ''
          });
          return acc;
        }, []);

        resolve({
          query: query,
          sort: sort,
          page: page,
          count: products.length,
          products: products
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
