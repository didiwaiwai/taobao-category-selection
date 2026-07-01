/* @meta
{
  "name": "taobao/scoring-deepdebug",
  "description": "增强调试：深度dump mtop API中未提取的字段——structuredUSPInfo/icons/umpPriceLog/extraParams/hotListInfo等",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "返回数量 (默认 10)"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/scoring-deepdebug 蓝牙耳机 --count 10"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var count = Math.min(parseInt(args.count) || 10, 20);

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
        var validItems = [];
        for (var i = 0; i < items.length; i++) {
          if (items[i].item_id && !items[i].customCardType) validItems.push(items[i]);
        }

        // === 1. 对每个产品，dump 关键未知字段的完整内容 ===
        var fieldDump = validItems.slice(0, count).map(function(item, idx) {

          // structuredUSPInfo: 每个元素的完整内容
          var uspDetail = null;
          if (item.structuredUSPInfo && Array.isArray(item.structuredUSPInfo)) {
            uspDetail = item.structuredUSPInfo.map(function(u) {
              return JSON.parse(JSON.stringify(u)); // deep copy
            });
          }

          // icons: 完整数组
          var iconsDetail = null;
          if (item.icons && Array.isArray(item.icons)) {
            iconsDetail = item.icons.map(function(ic) {
              return JSON.parse(JSON.stringify(ic));
            });
          }

          // umpPriceLog: 完整对象
          var umpDetail = item.umpPriceLog ? JSON.parse(JSON.stringify(item.umpPriceLog)) : null;

          // extraParams: 完整数组
          var extraDetail = null;
          if (item.extraParams && Array.isArray(item.extraParams)) {
            extraDetail = item.extraParams.map(function(ep) {
              return JSON.parse(JSON.stringify(ep));
            });
          }

          // hotListInfo
          var hotDetail = item.hotListInfo ? JSON.parse(JSON.stringify(item.hotListInfo)) : null;

          // summaryTips
          var tipsDetail = null;
          if (item.summaryTips && Array.isArray(item.summaryTips)) {
            tipsDetail = item.summaryTips.map(function(t) { return JSON.parse(JSON.stringify(t)); });
          }

          // labelOrder
          var labelOrderDetail = null;
          if (item.labelOrder && Array.isArray(item.labelOrder)) {
            labelOrderDetail = item.labelOrder.map(function(l) { return JSON.parse(JSON.stringify(l)); });
          }

          return {
            idx: idx,
            item_id: item.item_id,
            title: (item.title || '').replace(/<[^>]+>/g, '').trim().substring(0, 60),
            priceShow: (item.priceShow || {}),
            realSales: item.realSales,
            shop: (item.shopInfo && item.shopInfo.title) || '',
            nick: item.nick,

            // === 关键深度字段 ===
            structuredUSPInfo: uspDetail,
            icons: iconsDetail,
            umpPriceLog: umpDetail,
            extraParams: extraDetail,
            hotListInfo: hotDetail,
            summaryTips: tipsDetail,
            labelOrder: labelOrderDetail,

            // === 其他可能有用的标量 ===
            sameCount: item.sameCount,
            leafCategory: item.leafCategory,
            relationScore: item.relationScore,
            isP4p: item.isP4p,
            iconList: item.iconList,
            priceColor: item.priceColor,
            localPrice: item.localPrice,
            userId: item.userId,
            uniqpid: item.uniqpid
          };
        });

        // === 2. 全局统计：各字段在所有产品上的出现率 ===
        var fieldOccurrence = {};
        var allKeys = ['structuredUSPInfo','extraParams','icons','umpPriceLog','hotListInfo',
                        'summaryTips','sameCount','leafCategory','labelOrder','userId',
                        'uniqpid','localPrice','secondKillInfo','tradeInfo','video',
                        'relationScore','isP4p','p4pLabel','auctionURL','ifsUrl'];
        for (var k = 0; k < allKeys.length; k++) {
          var key = allKeys[k];
          var present = 0;
          for (var j = 0; j < validItems.length; j++) {
            if (validItems[j][key] !== undefined && validItems[j][key] !== null) present++;
          }
          fieldOccurrence[key] = present + '/' + validItems.length;
        }

        // === 3. 汇总 structuredUSPInfo 中出现的所有"文本"模式 ===
        var uspTexts = {};
        var uspTypes = {};
        for (var u = 0; u < validItems.length; u++) {
          var uspArr = validItems[u].structuredUSPInfo;
          if (!uspArr || !Array.isArray(uspArr)) continue;
          for (var v = 0; v < uspArr.length; v++) {
            var usp = uspArr[v];
            // 收集所有键名
            for (var uspKey in usp) {
              if (!uspTypes[uspKey]) uspTypes[uspKey] = {type: typeof usp[uspKey], samples: []};
              if (uspTypes[uspKey].samples.length < 5) {
                uspTypes[uspKey].samples.push(String(usp[uspKey]).substring(0, 80));
              }
            }
            // 如果有 title/text/desc 类字段，收集文本
            var textFields = ['title','text','desc','label','name','value','tag','content','word'];
            for (var tf = 0; tf < textFields.length; tf++) {
              if (usp[textFields[tf]]) {
                var txt = String(usp[textFields[tf]]);
                if (!uspTexts[textFields[tf]]) uspTexts[textFields[tf]] = {};
                if (!uspTexts[textFields[tf]][txt]) uspTexts[textFields[tf]][txt] = 0;
                uspTexts[textFields[tf]][txt]++;
              }
            }
          }
        }

        // === 4. 汇总 icons 的键值模式 ===
        var iconKeys = {};
        var iconValuePatterns = {};
        for (var ii = 0; ii < validItems.length; ii++) {
          var iconArr = validItems[ii].icons;
          if (!iconArr || !Array.isArray(iconArr)) continue;
          for (var ij = 0; ij < iconArr.length; ij++) {
            var icon = iconArr[ij];
            for (var ik in icon) {
              if (!iconKeys[ik]) iconKeys[ik] = {type: typeof icon[ik], samples: []};
              if (iconKeys[ik].samples.length < 5) {
                iconKeys[ik].samples.push(String(icon[ik]).substring(0, 80));
              }
            }
            // 收集 icon 中出现的 value/key 等可能含标签信息的字段
            if (icon.value) {
              if (!iconValuePatterns[icon.value]) iconValuePatterns[icon.value] = 0;
              iconValuePatterns[icon.value]++;
            }
            if (icon.key) {
              if (!iconValuePatterns['key:' + icon.key]) iconValuePatterns['key:' + icon.key] = 0;
              iconValuePatterns['key:' + icon.key]++;
            }
          }
        }

        // === 5. 汇总 priceDesc 的文本模式 (做新品信号参考) ===
        var priceDescPatterns = {};
        for (var pd = 0; pd < validItems.length; pd++) {
          var desc = (validItems[pd].priceShow && validItems[pd].priceShow.priceDesc) || '(空)';
          if (!priceDescPatterns[desc]) priceDescPatterns[desc] = 0;
          priceDescPatterns[desc]++;
        }

        // === 6. shopInfo 的所有字段 ===
        var shopInfoKeys = {};
        for (var si = 0; si < validItems.length; si++) {
          var siObj = validItems[si].shopInfo;
          if (!siObj) continue;
          for (var sik in siObj) {
            if (!shopInfoKeys[sik]) shopInfoKeys[sik] = {type: typeof siObj[sik], samples: []};
            if (shopInfoKeys[sik].samples.length < 3) {
              shopInfoKeys[sik].samples.push(String(siObj[sik]).substring(0, 80));
            }
          }
        }

        resolve({
          query: query,
          validProductCount: validItems.length,
          productsDump: fieldDump,

          // 汇总洞察
          fieldOccurrence: fieldOccurrence,
          priceDescDistribution: priceDescPatterns,
          structuredUSPInfo_fields: uspTypes,
          structuredUSPInfo_texts: uspTexts,
          icons_fields: iconKeys,
          icons_valuePatterns: iconValuePatterns,
          shopInfo_fields: shopInfoKeys
        });

      } catch(e) {
        resolve({error: 'Deep debug error: ' + e.message, stack: e.stack});
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
