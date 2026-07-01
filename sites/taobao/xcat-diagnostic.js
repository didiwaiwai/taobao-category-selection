/* @meta
{
  "name": "taobao/xcat-diagnostic",
  "description": "跨类目诊断：对比不同品类的字段可用性，寻找通用的新品信号",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "返回数量 (默认 15)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/xcat-diagnostic 收纳盒 --count 15"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var count = Math.min(parseInt(args.count) || 15, 20);

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
          q: query, sort: '_coefp', page: '1', n: String(count),
          m: 'pc', tab: 'all', ttid: '600000@taobao_pc_10.7.0'
        })
      },
      dataType: 'jsonp', ecode: 0
    }).then(function(r) {
      if (done) return;
      done = true;
      clearTimeout(timer);

      try {
        var items = r.data.itemsArray || [];

        // === 1. structuredUSPInfo 属性名汇总 ===
        var uspPropNames = {};
        var uspSamples = {};  // 每个属性名的样例值
        var uspProductCount = 0;

        for (var i = 0; i < items.length; i++) {
          var usp = items[i].structuredUSPInfo;
          if (!usp || !Array.isArray(usp)) continue;
          uspProductCount++;
          for (var j = 0; j < usp.length; j++) {
            var pn = usp[j].propertyName;
            if (!uspPropNames[pn]) { uspPropNames[pn] = 0; uspSamples[pn] = []; }
            uspPropNames[pn]++;
            if (uspSamples[pn].length < 3) {
              uspSamples[pn].push(usp[j].propertyValueName);
            }
          }
        }

        // === 2. priceDesc 模式统计 ===
        var priceDescStats = {};
        for (var k = 0; k < items.length; k++) {
          if (!items[k].item_id || items[k].customCardType) continue;
          var desc = (items[k].priceShow && items[k].priceShow.priceDesc) || '(空)';
          if (!priceDescStats[desc]) priceDescStats[desc] = 0;
          priceDescStats[desc]++;
        }

        // === 3. 标题中的新品关键词 ===
        var titlePatterns = {};
        var newTitleSamples = [];
        var newKeywords = ['新品', '新款', '首发', '上市', '上新', '2026新', 'NEW', 'New'];
        for (var m = 0; m < items.length; m++) {
          if (!items[m].item_id || items[m].customCardType) continue;
          var title = (items[m].title || '').replace(/<[^>]+>/g, '');
          var matched = [];
          for (var n = 0; n < newKeywords.length; n++) {
            if (title.indexOf(newKeywords[n]) >= 0) matched.push(newKeywords[n]);
          }
          if (matched.length > 0) {
            var key = matched.join('+');
            if (!titlePatterns[key]) titlePatterns[key] = 0;
            titlePatterns[key]++;
            if (newTitleSamples.length < 5) {
              newTitleSamples.push(title.substring(0, 80));
            }
          }
        }

        // === 4. umpPriceLog 中的价格阶段信号 ===
        var umpStageStats = {};
        for (var p = 0; p < items.length; p++) {
          if (!items[p].item_id || items[p].customCardType) continue;
          var ump = items[p].umpPriceLog;
          if (!ump) continue;
          var stage = ump.price_stage || '(空)';
          if (!umpStageStats[stage]) umpStageStats[stage] = 0;
          umpStageStats[stage]++;
        }

        // === 5. icons 中的 alias 汇总 ===
        var iconAliasStats = {};
        for (var q = 0; q < items.length; q++) {
          if (!items[q].item_id || items[q].customCardType) continue;
          var icons = items[q].icons;
          if (!icons || !Array.isArray(icons)) continue;
          for (var r = 0; r < icons.length; r++) {
            var alias = icons[r].alias;
            if (!iconAliasStats[alias]) iconAliasStats[alias] = {count: 0, texts: []};
            iconAliasStats[alias].count++;
            if (icons[r].text && iconAliasStats[alias].texts.length < 3) {
              iconAliasStats[alias].texts.push(icons[r].text);
            }
          }
        }

        // === 6. 前几个产品的重要字段一览 ===
        var productPreview = [];
        for (var s = 0; s < Math.min(5, items.length); s++) {
          var it = items[s];
          if (!it.item_id || it.customCardType) continue;
          var uspKeys = [];
          if (it.structuredUSPInfo && Array.isArray(it.structuredUSPInfo)) {
            for (var t = 0; t < it.structuredUSPInfo.length; t++) {
              uspKeys.push(it.structuredUSPInfo[t].propertyName);
            }
          }
          productPreview.push({
            title: (it.title || '').replace(/<[^>]+>/g, '').trim().substring(0, 50),
            priceDesc: (it.priceShow && it.priceShow.priceDesc) || '',
            uspPropertyNames: uspKeys,
            has上市时间: uspKeys.indexOf('上市时间') >= 0,
            iconAliases: (it.icons || []).map(function(ic){return ic.alias;})
          });
        }

        resolve({
          query: query,
          totalItems: items.length,
          uspCoverage: uspProductCount + '/' + items.length,
          uspPropertyNames: Object.keys(uspPropNames).sort(),
          uspPropertyStats: uspPropNames,
          uspPropertySamples: uspSamples,
          priceDescDistribution: priceDescStats,
          titleNewKeywordPatterns: titlePatterns,
          titleNewSamples: newTitleSamples,
          umpPriceStageStats: umpStageStats,
          iconAliasSummary: iconAliasStats,
          productPreview: productPreview
        });

      } catch(e) {
        resolve({error: 'Diagnostic error: ' + e.message, stack: e.stack});
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
