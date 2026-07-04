/* @meta
{
  "name": "1688/offer-score",
  "description": "1688采购成本采集v3 — 直接调用mtop搜索API,单页60条,与淘宝同架构",
  "domain": "1688.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "pages": {"required": false, "description": "抓取页数 (默认3, 最大5)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site 1688/offer-score 蓝牙耳机 --json"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var numPages = Math.min(parseInt(args.pages) || 3, 5);
  var perPage = 60;

  if (typeof window.lib === 'undefined' || !window.lib.mtop) {
    return {error: 'mtop not loaded', hint: 'goto 1688 search page first'};
  }

  // Extract pageId
  var pageId = '';
  var scripts = document.querySelectorAll('script');
  for (var i = 0; i < scripts.length; i++) {
    var m = (scripts[i].textContent || '').match(/pageId["'\s:=]+([a-zA-Z0-9]+)/);
    if (m) { pageId = m[1]; break; }
  }
  if (!pageId) return {error: 'no_page_id'};

  // Helper: one page
  function fetchOnePage(pg) {
    return new Promise(function(ok, fail) {
      var t = setTimeout(function() { fail('timeout'); }, 20000);
      window.lib.mtop.request({
        api: 'mtop.relationrecommend.WirelessRecommend.recommend',
        v: '2.0',
        data: { appId: '32517', params: JSON.stringify({
          beginPage: pg, pageSize: perPage,
          method: 'getOfferList', pageId: pageId,
          keywords: query, charset: 'GBK',
          searchScene: 'pcOfferSearch', verticalProductFlag: 'pcmarket'
        })},
        dataType: 'jsonp', ecode: 0
      }).then(function(r) { clearTimeout(t); ok(r); },
               function(e) { clearTimeout(t); fail(e); });
    });
  }

  // Parse a single product
  function parseProduct(d) {
    var price = 0;
    try {
      var pi = typeof d.priceInfo === 'string' ? JSON.parse(d.priceInfo) : (d.priceInfo || {});
      price = parseFloat(pi.price) || 0;
    } catch(e) {
      price = parseFloat(String(d.priceInfo || '').replace(/[^0-9.]/g, '')) || 0;
    }
    var shop = '';
    if (typeof d.shop === 'string') shop = d.shop;
    else if (d.shop && d.shop.text) shop = d.shop.text;

    return {
      item_id: d.offerId,
      title: (d.title || '').replace(/<[^>]+>/g, '').trim(),
      price: price,
      sales: parseInt(d.bookedCount) || 0,
      shop: shop,
      location: (d.province || '') + ' ' + (d.city || ''),
      repurchase: parseFloat(d.offerRepurchaseRate) || 0
    };
  }

  // Serial fetch
  var allProducts = [];
  var allPrices = [];

  for (var pg = 1; pg <= numPages; pg++) {
    try {
      var r = await fetchOnePage(pg);
      var offer = (r.data && r.data.data && r.data.data.OFFER) || {};
      var items = (offer && offer.items) || [];
      for (var j = 0; j < items.length; j++) {
        var d = items[j].data;
        if (d && d.offerId) {
          var p = parseProduct(d);
          allProducts.push(p);
          if (p.price > 0.05) allPrices.push(p.price);
        }
      }
    } catch(e) {
      // Page failed, continue
    }
    // Delay between pages
    if (pg < numPages) {
      await new Promise(function(r) { setTimeout(r, 2000); });
    }
  }

  if (!allProducts.length) {
    return {error: 'no_products', hint: '可能需要手动过验证码'};
  }

  // Deduplicate
  var seen = {};
  var deduped = [];
  for (var k = 0; k < allProducts.length; k++) {
    if (!seen[allProducts[k].item_id]) {
      seen[allProducts[k].item_id] = true;
      deduped.push(allProducts[k]);
    }
  }

  // Stats
  var uniquePrices = [];
  var ps = {};
  for (var pi = 0; pi < allPrices.length; pi++) {
    var key = Math.round(allPrices[pi] * 100) / 100;
    if (!ps[key]) { ps[key] = true; uniquePrices.push(allPrices[pi]); }
  }
  uniquePrices.sort(function(a,b) { return a - b; });

  var mid = uniquePrices.length > 0 ? uniquePrices[Math.floor(uniquePrices.length / 2)] : 0;
  var avg = uniquePrices.length > 0 ? Math.round(uniquePrices.reduce(function(s,p){return s+p;},0) / uniquePrices.length) : 0;

  // Segments
  var seg = {budget: 0, mid: 0, premium: 0, high: 0};
  for (var si = 0; si < uniquePrices.length; si++) {
    var v = uniquePrices[si];
    if (v < 50) seg.budget++;
    else if (v < 150) seg.mid++;
    else if (v < 500) seg.premium++;
    else seg.high++;
  }

  // Keyword match
  var kwChars = query.replace(/[^一-鿿]/g, '').split('');
  var matchCount = 0;
  var samples = deduped.slice(0, 10);
  for (var mi = 0; mi < samples.length; mi++) {
    var t = samples[mi].title;
    var found = 0;
    for (var cj = 0; cj < kwChars.length; cj++) {
      if (t.indexOf(kwChars[cj]) >= 0) found++;
    }
    if (found >= Math.max(1, kwChars.length * 0.3)) matchCount++;
  }

  // Shop stats
  var shopMap = {};
  for (var sk = 0; sk < deduped.length; sk++) {
    var sh = deduped[sk].shop || 'unknown';
    shopMap[sh] = (shopMap[sh] || 0) + 1;
  }
  var topShops = [];
  for (var sn in shopMap) topShops.push({shop: sn, count: shopMap[sn]});
  topShops.sort(function(a,b) { return b.count - a.count; });

  return {
    query: query,
    method: 'mtop getOfferList',
    totalProducts: allProducts.length,
    dedupedProducts: deduped.length,
    uniquePrices: uniquePrices.length,
    prices: uniquePrices,
    pagesCrawled: numPages,
    perPage: perPage,
    stats: {
      min: uniquePrices[0] || 0,
      max: uniquePrices[uniquePrices.length - 1] || 0,
      q1: uniquePrices[Math.floor(uniquePrices.length / 4)] || 0,
      median: mid,
      q3: uniquePrices[Math.floor(3 * uniquePrices.length / 4)] || 0,
      avg: avg
    },
    priceSegments: seg,
    keywordMatch: samples.length > 0 ? matchCount / samples.length : 0,
    products: deduped.slice(0, 60),
    topShops: topShops.slice(0, 10),
    source: '1688.com mtop API v3'
  };
}
