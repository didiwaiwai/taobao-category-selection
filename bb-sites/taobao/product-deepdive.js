/* @meta
{
  "name": "taobao/product-deepdive",
  "description": "竞品深挖 — 输入item_id列表, 获取品牌/上市时间/评价/卖点/店铺信息",
  "domain": "taobao.com",
  "args": {
    "ids": {"required": true, "description": "逗号分隔的item_id列表 (如 123,456,789)"},
    "query": {"required": false, "description": "品类关键词(用于流量词)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/product-deepdive --ids 1009927548942,832299494668 --json"
}
*/

async function(args) {
  var idsStr = args.ids || (args._ && args._[0]) || '';
  if (!idsStr) return {error: 'Missing ids'};
  var ids = idsStr.split(',').map(function(s) { return s.trim(); }).filter(Boolean).slice(0, 5);
  var query = args.query || '';

  function sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

  if (typeof window.lib === 'undefined' || !window.lib.mtop) {
    return {error: 'mtop not loaded', hint: 'Open item.taobao.com in Chrome first'};
  }

  var results = [];

  for (var i = 0; i < ids.length; i++) {
    var itemId = ids[i];

    try {
      // Call detail desc API
      var descData = await new Promise(function(ok, fail) {
        var t = setTimeout(function() { fail('timeout'); }, 15000);
        window.lib.mtop.request({
          api: 'mtop.taobao.detail.getdesc',
          v: '6.0',
          data: { id: itemId, type: '1' },
          dataType: 'jsonp', ecode: 0
        }).then(function(r) { clearTimeout(t); ok(r); },
                 function(e) { clearTimeout(t); fail(e); });
      });

      // Extract fields
      var detail = (descData.data || {});
      var product = {
        item_id: itemId,
        brand: '',
        listing_date: '',
        sku_count: 0,
        review_count: 0,
        selling_points: [],
        shop_name: '',
        shop_type: ''
      };

      // Brand from multiple sources
      if (detail.brand) product.brand = detail.brand;
      else if (detail.brandName) product.brand = detail.brandName;
      else if (detail.props && detail.props.brand) product.brand = detail.props.brand;

      // Listing date
      if (detail.listingDate) product.listing_date = detail.listingDate;
      else if (detail.createTime) product.listing_date = detail.createTime;
      else if (detail.props && detail.props.listingDate) product.listing_date = detail.props.listingDate;

      // Review count
      if (detail.commentCount) product.review_count = parseInt(detail.commentCount) || 0;
      else if (detail.totalRate) product.review_count = parseInt(detail.totalRate) || 0;

      // SKU info
      if (detail.skuModel) {
        var skus = detail.skuModel.skuProps || [];
        product.sku_count = skus.length;
      }

      // Shop info
      if (detail.seller) {
        product.shop_name = detail.seller.shopName || detail.seller.nick || '';
        product.shop_type = detail.seller.type || '';
      }

      // Selling points from props
      var props = detail.props || {};
      var sp = [];
      if (props.features) sp = (typeof props.features === 'string' ? props.features.split(',') : props.features) || [];
      if (props.sellingPoint) sp.push(props.sellingPoint);
      product.selling_points = sp.slice(0, 5);

      results.push(product);

    } catch(e) {
      results.push({ item_id: itemId, error: String(e) });
    }

    // Delay between products
    if (i < ids.length - 1) await sleep(2000);
  }

  // Summary
  var brands = {};
  var hasDates = 0;
  var totalReviews = 0;
  for (var j = 0; j < results.length; j++) {
    if (results[j].brand) brands[results[j].brand] = (brands[results[j].brand] || 0) + 1;
    if (results[j].listing_date) hasDates++;
    totalReviews += results[j].review_count || 0;
  }

  return {
    query: query,
    products_analyzed: results.length,
    products: results,
    summary: {
      brands_found: Object.keys(brands).length,
      listing_date_coverage: results.length > 0 ? (hasDates / results.length) : 0,
      total_reviews: totalReviews,
      avg_reviews: results.length > 0 ? Math.round(totalReviews / results.length) : 0
    },
    source: 'taobao detail API (mtop.taobao.detail.getdesc)'
  };
}
