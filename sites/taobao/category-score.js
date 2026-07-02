/* @meta
{
  "name": "taobao/category-score",
  "description": "淘宝品类五维评分模型v4.2 — 多排序交叉验证+动态地板+品牌HHI+交叉壁垒矩阵",
  "domain": "taobao.com",
  "args": {
    "query": {"required": true, "description": "搜索关键词"},
    "count": {"required": false, "description": "每页数量 (默认48, 最大48)"},
    "pages": {"required": false, "description": "抓取页数 (默认3, 最大5)"},
    "sort": {"required": false, "description": "排序: sale-desc(默认) total-desc"}
  },
  "capabilities": ["network"],
  "readOnly": true,
  "example": "bb-browser site taobao/category-score 蓝牙耳机 --json"
}
*/

async function(args) {
  var query = args.query || (args._ && args._[0]) || '';
  if (!query) return {error: 'Missing query'};

  var perPage = Math.min(parseInt(args.count) || 48, 48);
  var numPages = Math.min(parseInt(args.pages) || 3, 5);
  var sort = args.sort || 'sale-desc';
  var sortMap = {'sale-desc': '_coefp', 'total-desc': 'default'};
  var apiSort = sortMap[sort] || '_coefp';

  if (typeof window.lib === 'undefined' || !window.lib.mtop) {
    return {error: 'mtop library not loaded', hint: 'Open s.taobao.com in Chrome first'};
  }

  return new Promise(function(resolve) {
    var done = false;
    var globalTimer = setTimeout(function() {
      if (!done) { done = true; resolve({error: 'API timeout (multi-page)'}); }
    }, 30000);

    // 单页请求
    function fetchPage(pageNum, overrideSort) {
      var s = overrideSort || apiSort;
      return new Promise(function(ok, fail) {
        var t = setTimeout(function() { fail('timeout'); }, 15000);
        window.lib.mtop.request({
          api: 'mtop.relationrecommend.WirelessRecommend.recommend',
          v: '2.0',
          data: { appId: '34385', params: JSON.stringify({
            q: query, sort: s, page: String(pageNum), n: String(perPage),
            m: 'pc', tab: 'all', ttid: '600000@taobao_pc_10.7.0'
          })},
          dataType: 'jsonp', ecode: 0
        }).then(function(r) { clearTimeout(t); ok(r); }, function(e) { clearTimeout(t); fail(e); });
      });
    }

    // 并发抓取: 主排序3页 + 综合排序1页 + 价格升序1页
    var allPromises = [];
    for (var pg = 1; pg <= numPages; pg++) { allPromises.push(fetchPage(pg)); }
    allPromises.push(fetchPage(1, 'default'));
    allPromises.push(fetchPage(1, 'price-asc'));

    Promise.all(allPromises).then(function(results) {
      if (done) return;
      done = true; clearTimeout(globalTimer);

      try {
        // ================================================================
        // 辅助函数
        // ================================================================
        function parseSales(s) {if(!s)return 0;var m=s.match(/([\d.]+)万\+/);if(m)return Math.round(parseFloat(m[1])*10000);m=s.match(/(\d+)\+/);if(m)return parseInt(m[1]);m=s.match(/(\d+)/);if(m)return parseInt(m[1]);return 0;}
        function detectShopType(iconList, shopTitle) {var s=(iconList||'').toLowerCase(),t=(shopTitle||'').toLowerCase();if(t.indexOf('百亿补贴')>=0||t.indexOf('官方精选')>=0||t.indexOf('品牌优选')>=0)return'special_channel';if(t.indexOf('官方旗舰店')>=0||t.indexOf('旗舰店')>=0)return'flagship';if(t.indexOf('专卖店')>=0||t.indexOf('专营店')>=0)return'tmall_auth';if(s.indexOf('tmall')>=0)return'tmall';if(t.indexOf('企业店')>=0)return'enterprise';return'c_store';}
        function isTmall(st){return st==='flagship'||st==='tmall_auth'||st==='tmall';}
        function extractUSP(arr,prop){if(!arr||!Array.isArray(arr))return null;for(var i=0;i<arr.length;i++){if(arr[i].propertyName===prop)return arr[i].propertyValueName;}return null;}
        function isRecentLaunch(ds,months){if(!ds)return false;var p=ds.split('-');if(p.length<2)return false;var d=new Date(parseInt(p[0]),parseInt(p[1])-1,parseInt(p[2]||'1'));var now=new Date();return d>=new Date(now.getFullYear(),now.getMonth()-months,now.getDate());}
        function hasIconAlias(arr,alias){if(!arr||!Array.isArray(arr))return false;for(var i=0;i<arr.length;i++){if(arr[i].alias===alias)return true;}return false;}
        function hasNewTitle(t){if(!t)return false;var c=t.replace(/<[^>]+>/g,'');return /【新品】|新品|首发|新款|2026新|2025新|上新|NEW/i.test(c);}
        function parseViewCount(tips){if(!tips||!Array.isArray(tips)||!tips.length)return 0;var t=tips[0],m=t.match(/([\d.]+)万\+/);if(m)return Math.round(parseFloat(m[1])*10000);m=t.match(/(\d+)\+/);if(m)return parseInt(m[1]);return 0;}

        // ================================================================
        // 合并多页数据（按item_id去重）
        // ================================================================
        var seen = {};
        var products = [];
        var totalRaw = 0;

        for (var pi = 0; pi < results.length; pi++) {
          var items = (results[pi].data && results[pi].data.itemsArray) || [];
          totalRaw += items.length;
          for (var ii = 0; ii < items.length; ii++) {
            var item = items[ii];
            if (!item.item_id || item.customCardType) continue;
            if (seen[item.item_id]) continue;
            seen[item.item_id] = true;

            var displayPrice = parseFloat((item.priceShow&&item.priceShow.price)||item.price||'0');
            var priceDesc = (item.priceShow&&item.priceShow.priceDesc)||'';
            var salesNum = parseSales(item.realSales||'');
            var shopTitle = (item.shopInfo&&item.shopInfo.title)||'';
            var shopType = detectShopType(item.iconList, shopTitle);
            var listingDate = extractUSP(item.structuredUSPInfo,'上市时间');
            var brand = extractUSP(item.structuredUSPInfo,'品牌');
            var titleClean = (item.title||'').replace(/<[^>]+>/g,'').trim();

            products.push({
              item_id: item.item_id, title: titleClean,
              price: displayPrice, priceDesc: priceDesc,
              sales: salesNum, salesRaw: item.realSales||'',
              shop: shopTitle, nick: item.nick||'',
              shopType: shopType,
              isTmall: isTmall(shopType),
              isAd: item.isP4p==='true',
              location: item.procity||'',
              listingDate: listingDate, brand: brand||'未知',
              isRecent6m: isRecentLaunch(listingDate,6),
              isRecent3m: isRecentLaunch(listingDate,3),
              isFirstPrice: priceDesc==='首单价',
              hasNewTitle: hasNewTitle(item.title||''),
              hasHotBomb: hasIconAlias(item.icons,'richangrexiaobaokuan2'),
              hasHotList: !!(item.hotListInfo&&item.hotListInfo.rank_short_text),
              sameCount: parseInt(item.sameCount)||0,
              viewCount: parseViewCount(item.summaryTips)
            });
          }
        }

        if (!products.length) { resolve({error:'No valid products found'}); return; }

        // ================================================================
        // 基础统计
        // ================================================================
        var totalSales = products.reduce(function(a,p){return a+p.sales;},0);
        var totalSalesSafe = totalSales>0?totalSales:1;

        // 信号计数
        function countSigs(fn){var c=0,s=0;for(var i=0;i<products.length;i++){if(fn(products[i])){c++;s+=products[i].sales;}}return{count:c,sales:s};}
        var sig = {
          listing6m: countSigs(function(p){return p.isRecent6m;}),
          listing3m: countSigs(function(p){return p.isRecent3m;}),
          firstPrice: countSigs(function(p){return p.isFirstPrice;}),
          newTitle: countSigs(function(p){return p.hasNewTitle;}),
          hotBomb: countSigs(function(p){return p.hasHotBomb;}),
          hotList: countSigs(function(p){return p.hasHotList;}),
          hasListing: countSigs(function(p){return !!p.listingDate;}),
        };
        var listingCoverage = sig.hasListing.count/products.length;

        // 预估月销额
        var totalRevenueEst = 0;
        for (var rev=0; rev<products.length; rev++) {
          totalRevenueEst += products[rev].price * products[rev].sales;
        }

        // C店
        var cStoreSales=0,cStoreCount=0;
        for(var j=0;j<products.length;j++){if(!products[j].isTmall&&products[j].shopType!=='special_channel'){cStoreSales+=products[j].sales;cStoreCount++;}}
        var cStoreRatio = totalSalesSafe>0?cStoreSales/totalSalesSafe:0;

        // 店铺CR3 + 发货地分析
        var shopMap={}, locMap={};
        for(var k=0;k<products.length;k++){
          var sh=products[k].shop||products[k].nick; shopMap[sh]=(shopMap[sh]||0)+products[k].sales;
          var loc=products[k].location||'未知'; locMap[loc]=(locMap[loc]||0)+1;
        }
        var shopArr=[]; for(var sn in shopMap)shopArr.push({shop:sn,sales:shopMap[sn]});
        shopArr.sort(function(a,b){return b.sales-a.sales;});
        var top3Sales=0; for(var t=0;t<Math.min(3,shopArr.length);t++)top3Sales+=shopArr[t].sales;
        var cr3Store = totalSalesSafe>0?top3Sales/totalSalesSafe:0;
        // 发货地Top5
        var locArr=[]; for(var ln in locMap)locArr.push({location:ln,count:locMap[ln]});
        locArr.sort(function(a,b){return b.count-a.count;});

        // 品牌 HHI
        var brandMap={};
        for(var b=0;b<products.length;b++){var br=products[b].brand||'未知';brandMap[br]=(brandMap[br]||0)+products[b].sales;}
        var brandArr=[]; for(var bn in brandMap)brandArr.push({brand:bn,sales:brandMap[bn],share:brandMap[bn]/totalSalesSafe});
        brandArr.sort(function(a,b){return b.sales-a.sales;});
        var hhi=0; for(var h=0;h<brandArr.length;h++){hhi+=Math.pow(brandArr[h].share*100,2);}
        var cr3Brand=0; for(var c3=0;c3<Math.min(3,brandArr.length);c3++)cr3Brand+=brandArr[c3].share;
        var hasBrandData=(brandArr.filter(function(x){return x.brand!=='未知';}).length/products.length)>0.3;
        // 店铺HHI兜底
        var storeHHI=0; for(var shh=0;shh<shopArr.length;shh++){storeHHI+=Math.pow(shopArr[shh].sales/totalSalesSafe*100,2);}
        var effectiveHHI=hasBrandData?hhi:storeHHI;
        var hhiSource=hasBrandData?'品牌':'店铺(品牌数据不足)';

        // 自适应新品占比
        var newnessRatio, newnessSource, newnessTier;
        if(listingCoverage>0.30){newnessRatio=sig.listing6m.sales/totalSalesSafe;newnessSource='上市时间(覆盖'+(listingCoverage*100).toFixed(0)+'%)';newnessTier='Tier1';}
        else if(sig.newTitle.count+sig.firstPrice.count>=3){
          var combinedNewSales=0;for(var z=0;z<products.length;z++){if(products[z].hasNewTitle||products[z].isFirstPrice)combinedNewSales+=products[z].sales;}
          newnessRatio=combinedNewSales/totalSalesSafe;newnessSource='标题新品('+sig.newTitle.count+')+首单价('+sig.firstPrice.count+')';newnessTier='Tier2';}
        else{var heatBoost=0;if(sig.hotBomb.count/products.length>0.10)heatBoost+=0.05;if(sig.hotList.count/products.length>0.30)heatBoost+=0.05;newnessRatio=Math.min(0.30,cStoreRatio*0.4+heatBoost);newnessSource='C店占比('+(cStoreRatio*100).toFixed(0)+'%)+热销(Tier3,上限30%)';newnessTier='Tier3';}
        var newTitleCSales=0,newTitleAllSales=0;for(var nt=0;nt<products.length;nt++){if(products[nt].hasNewTitle||products[nt].isFirstPrice){newTitleAllSales+=products[nt].sales;if(!products[nt].isTmall&&products[nt].shopType!=='special_channel')newTitleCSales+=products[nt].sales;}}
        var newSignalCStoreRatio=newTitleAllSales>0?newTitleCSales/newTitleAllSales:0;

        // 天猫/旗舰
        var tmallCount=0,flagshipCount=0;for(var u=0;u<products.length;u++){if(products[u].isTmall)tmallCount++;if(products[u].shopType==='flagship')flagshipCount++;}
        var tmallRatio=tmallCount/products.length,flagshipRatio=flagshipCount/products.length;

        // sameCount
        var sameSum=0,sameCnt=0;for(var v=0;v<products.length;v++){if(products[v].sameCount>0){sameSum+=products[v].sameCount;sameCnt++;}}
        var avgSameCount=sameCnt>0?Math.round(sameSum/sameCnt):0;

        // 价格
        var prices=[];for(var w=0;w<products.length;w++){if(products[w].price>0)prices.push(products[w].price);}
        prices.sort(function(a,b){return a-b;});
        var avgPrice=prices.length>0?prices.reduce(function(a,b){return a+b;},0)/prices.length:0;
        var medPrice=prices.length>0?prices[Math.floor(prices.length/2)]:0;

        // 补贴折价
        var subP=[],nonSubP=[];for(var x=0;x<products.length;x++){if(products[x].shopType==='special_channel'&&products[x].price>0)subP.push(products[x].price);else if(products[x].isTmall&&products[x].shopType==='flagship'&&products[x].price>0)nonSubP.push(products[x].price);}
        var avgSub=subP.length>0?subP.reduce(function(a,b){return a+b;},0)/subP.length:0;
        var avgNonSub=nonSubP.length>0?nonSubP.reduce(function(a,b){return a+b;},0)/nonSubP.length:0;
        var subsidyIndex=avgNonSub>0?avgSub/avgNonSub:0;

        // 价格带分布
        var priceBands=[{label:'¥0-20',min:0,max:20,count:0,sales:0},{label:'¥20-40',min:20,max:40,count:0,sales:0},{label:'¥40-80',min:40,max:80,count:0,sales:0},{label:'¥80-150',min:80,max:150,count:0,sales:0},{label:'¥150-300',min:150,max:300,count:0,sales:0},{label:'¥300-600',min:300,max:600,count:0,sales:0},{label:'¥600+',min:600,max:Infinity,count:0,sales:0}];
        for(var pb=0;pb<products.length;pb++){var pp=products[pb].price;for(var bd=0;bd<priceBands.length;bd++){if(pp>=priceBands[bd].min&&pp<priceBands[bd].max){priceBands[bd].count++;priceBands[bd].sales+=products[pb].sales;break;}}}

        // ========== 多排序交叉验证 ==========
        var totalItems=(results[3]&&results[3].data&&results[3].data.itemsArray)||[];
        var priceItems=(results[4]&&results[4].data&&results[4].data.itemsArray)||[];
        var totalIds={},saleIds={};
        for(var i=0;i<products.length;i++)saleIds[products[i].item_id]=true;
        var totalNewCount=0;
        for(var i=0;i<totalItems.length;i++){if(totalItems[i].item_id&&!totalItems[i].customCardType){totalIds[totalItems[i].item_id]=true;if(hasNewTitle(totalItems[i].title||'')||((totalItems[i].priceShow&&totalItems[i].priceShow.priceDesc)==='首单价'))totalNewCount++;}}
        var intersect=0;for(var id in totalIds){if(saleIds[id])intersect++;}
        var jaccard=intersect/Math.max(1,Object.keys(saleIds).length+Object.keys(totalIds).length-intersect);
        var totalNewRatio=totalItems.length>0?totalNewCount/Math.min(48,totalItems.length):0;
        var saleNewRatio=products.length>0?(sig.newTitle.count+sig.firstPrice.count)/products.length:0;
        var newProductBoost=saleNewRatio>0.001?Math.min(2,totalNewRatio/Math.max(0.001,saleNewRatio)):1;
        var ascPrices=[];for(var i=0;i<priceItems.length;i++){var ap=parseFloat((priceItems[i].priceShow&&priceItems[i].priceShow.price)||priceItems[i].price||'0');if(ap>0)ascPrices.push(ap);}
        ascPrices.sort(function(a,b){return a-b;});
        var priceNorm=ascPrices.length>1?(ascPrices[ascPrices.length-1]-ascPrices[0])/ascPrices[ascPrices.length-1]:0;
        var dynamismIndex=0.4*(1-jaccard)+0.3*Math.min(1,newProductBoost/2)+0.3*Math.min(1,priceNorm);
        var dynamismLabel=dynamismIndex>0.5?'高动态(市场活跃)':(dynamismIndex>0.3?'中等动态':'低动态(市场稳定)');

        // ================================================================
        // 五维评分
        // ================================================================
        var mktScore,mktLabel;
        if(totalSales>500000){mktScore=20;mktLabel='超级大赛道(>'+(totalSales/10000).toFixed(0)+'万件)';}
        else if(totalSales>200000){mktScore=17;mktLabel='大型市场(>'+(totalSales/10000).toFixed(0)+'万件)';}
        else if(totalSales>100000){mktScore=14;mktLabel='中型市场(>'+(totalSales/10000).toFixed(0)+'万件)';}
        else if(totalSales>50000){mktScore=11;mktLabel='中小市场(>'+(totalSales/10000).toFixed(0)+'万件)';}
        else{mktScore=8;mktLabel='小众市场(≤5万件)';}

        var dynFloor=newnessTier==='Tier1'?12:(newnessTier==='Tier2'?14:15);
        var growthBase,growthBaseLabel;
        if(newnessRatio>0.40){growthBase=22;growthBaseLabel='爆发期(新品占'+(newnessRatio*100).toFixed(0)+'%)';}
        else if(newnessRatio>0.20){growthBase=18;growthBaseLabel='成长期(新品占'+(newnessRatio*100).toFixed(0)+'%)';}
        else if(newnessRatio>0.10){growthBase=14;growthBaseLabel='成熟期(新品占'+(newnessRatio*100).toFixed(0)+'%)';}
        else{growthBase=Math.max(dynFloor,12);growthBaseLabel='老化/固化(新品仅'+(newnessRatio*100).toFixed(0)+'%) [地板'+dynFloor+']';}
        var tier2Discount=0;
        if(newnessTier==='Tier2'){if(newSignalCStoreRatio<0.15)tier2Discount=-3;else if(newSignalCStoreRatio<0.30)tier2Discount=-2;else if(newSignalCStoreRatio<0.50)tier2Discount=-1;}
        var heatBonus=0,heatParts=[];
        if(sig.hotBomb.count/products.length>0.15){heatBonus+=1;heatParts.push(sig.hotBomb.count+'热销爆款');}
        if(sig.hotList.count/products.length>0.30){heatBonus+=1;heatParts.push(sig.hotList.count+'在榜');}
        if(sig.newTitle.count>3&&newSignalCStoreRatio>0.30){heatBonus+=1;heatParts.push(sig.newTitle.count+'标题新(C店为主)');}
        var dynamismBonus=0;
        if(dynamismIndex>0.60){dynamismBonus=2;heatParts.push('高动态(DI='+dynamismIndex.toFixed(2)+')');}
        else if(dynamismIndex>0.40){dynamismBonus=1;heatParts.push('中等动态');}
        var growthScore=Math.min(25,Math.max(6,growthBase+heatBonus+tier2Discount+dynamismBonus));
        var growthLabel=growthBaseLabel+' ['+newnessSource+']';
        if(heatParts.length>0)growthLabel+=' +'+heatParts.join(',');
        if(tier2Discount<0)growthLabel+=' ⚠️品牌换皮折扣'+tier2Discount;

        var compScore,compLabel;
        if(cr3Store<0.25){compScore=18;compLabel='极度分散(店铺CR3='+(cr3Store*100).toFixed(0)+'%)';}
        else if(cr3Store<0.45){compScore=14;compLabel='适度集中(店铺CR3='+(cr3Store*100).toFixed(0)+'%)';}
        else{compScore=8;compLabel='寡头格局(店铺CR3='+(cr3Store*100).toFixed(0)+'%)';}
        if(effectiveHHI<1000){compLabel+=' '+hhiSource+'HHI='+effectiveHHI.toFixed(0)+'(分散)';}
        else if(effectiveHHI<2500){compScore=Math.max(6,compScore-1);compLabel+=' '+hhiSource+'HHI='+effectiveHHI.toFixed(0)+'(中等集中)';}
        else{compScore=Math.max(6,compScore-2);compLabel+=' '+hhiSource+'HHI='+effectiveHHI.toFixed(0)+'(高度集中)';}
        if(avgSameCount>500){compScore=Math.max(4,compScore-2);compLabel+=' +高供给密度('+avgSameCount+'同类)';}
        else if(avgSameCount>0&&avgSameCount<50){compScore=Math.min(20,compScore+1);compLabel+=' +蓝海供给('+avgSameCount+'同类)';}

        var barrierScore,barrierLabel;
        var newnessLevel;if(newnessRatio>0.20)newnessLevel='high';else if(newnessRatio>0.10)newnessLevel='mid';else newnessLevel='low';
        var tmallLevel;if(tmallRatio<0.30)tmallLevel='low';else if(tmallRatio<0.50)tmallLevel='mid_low';else if(tmallRatio<0.70)tmallLevel='mid_high';else tmallLevel='high';
        var barrierMatrix={'low':{high:20,mid:18,low:14},'mid_low':{high:16,mid:14,low:10},'mid_high':{high:14,mid:12,low:8},'high':{high:12,mid:8,low:6}};
        var barrierTypeMap={'low_high':'开放繁荣','low_mid':'门槛低','low_low':'静水市场','mid_low_high':'品牌化中','mid_low_mid':'适度壁垒','mid_low_low':'品牌垄断中','mid_high_high':'品牌换皮','mid_high_mid':'较高壁垒','mid_high_low':'品牌锁定','high_high':'品牌迭代','high_mid':'高壁垒','high_low':'封闭市场'};
        barrierScore=barrierMatrix[tmallLevel][newnessLevel];
        var barrierType=barrierTypeMap[tmallLevel+'_'+newnessLevel]||'未分类';
        barrierLabel=barrierType+' (天猫'+(tmallRatio*100).toFixed(0)+'% × 新品'+(newnessRatio*100).toFixed(0)+'%)';
        if(subsidyIndex>0&&subsidyIndex<0.75&&subP.length>0){barrierScore=Math.max(4,barrierScore-2);barrierLabel+=' | 补贴折价'+(subsidyIndex*100).toFixed(0)+'%严重';}
        else if(subsidyIndex>0&&subsidyIndex<0.85&&subP.length>0){barrierScore=Math.max(4,barrierScore-1);barrierLabel+=' | 补贴折价'+(subsidyIndex*100).toFixed(0)+'%';}

        var profitScore,profitLabel;
        if(avgPrice>200){profitScore=12;profitLabel='高利润(均价¥'+avgPrice.toFixed(0)+')';}
        else if(avgPrice>100){profitScore=10;profitLabel='中高利润(均价¥'+avgPrice.toFixed(0)+')';}
        else if(avgPrice>40){profitScore=7;profitLabel='中低利润(均价¥'+avgPrice.toFixed(0)+' — 需走量)';}
        else{profitScore=4;profitLabel='低利润(均价¥'+avgPrice.toFixed(0)+' — 快递费可能吃掉利润)';}

        var totalScore=mktScore+growthScore+compScore+barrierScore+profitScore;
        var rating,emoji,recommendation;
        if(totalScore>=80){rating='优秀';emoji='🟢';recommendation='强烈推荐进入——新品活跃、竞争分散、利润充足';}
        else if(totalScore>=70){rating='良好';emoji='🔵';recommendation='可考虑进入——各项指标均衡，有一定机会';}
        else if(totalScore>=50){rating='一般';emoji='🟡';recommendation='谨慎进入——部分维度存在明显短板，需差异化策略';}
        else{rating='较差';emoji='🔴';recommendation='不建议进入——市场被品牌垄断，新人难突围';}

        // ================================================================
        // 构建结果
        // ================================================================
        var topShops=shopArr.slice(0,5).map(function(s){return{shop:s.shop,sales:s.sales,share:(s.sales/totalSalesSafe*100).toFixed(1)+'%'};});
        var shopTypeDist={};for(var a=0;a<products.length;a++){var st=products[a].shopType;shopTypeDist[st]=(shopTypeDist[st]||0)+1;}

        resolve({
          query:query,sort:sort,
          modelVersion:'v4.2-dynamic',
          analyzedProducts:products.length,
          sampleInfo:{pages:numPages,perPage:perPage,totalRaw:totalRaw,deduped:products.length},
          dynamism:{index:dynamismIndex,label:dynamismLabel,jaccard:jaccard,newProductBoost:newProductBoost,priceDispersion:priceNorm},
          dataQuality:{
            listingDateCoverage:(listingCoverage*100).toFixed(0)+'%',
            brandCoverage:(brandArr.filter(function(x){return x.brand!=='未知';}).length/products.length*100).toFixed(0)+'%',
            growthDataTier:newnessTier,growthDataSource:newnessSource
          },
          scoring:{
            total:totalScore,maxTotal:100,rating:rating,ratingEmoji:emoji,recommendation:recommendation,
            dimensions:{
              marketSize:{score:mktScore,maxScore:20,label:mktLabel,data:{totalSales:totalSales,totalRevenueEst:totalRevenueEst}},
              growthPotential:{score:growthScore,maxScore:25,label:growthLabel,data:{newnessRatio:(newnessRatio*100).toFixed(1)+'%',newnessTier:newnessTier,listing6mCount:sig.listing6m.count,firstPriceCount:sig.firstPrice.count,newTitleCount:sig.newTitle.count,hotBombCount:sig.hotBomb.count,hotListCount:sig.hotList.count,cStoreRatio:(cStoreRatio*100).toFixed(1)+'%',newSignalCStoreRatio:(newSignalCStoreRatio*100).toFixed(0)+'%'}},
              competition:{score:compScore,maxScore:20,label:compLabel,data:{cr3Store:(cr3Store*100).toFixed(1)+'%',cr3Brand:hasBrandData?(cr3Brand*100).toFixed(1)+'%':'N/A',hhi:effectiveHHI.toFixed(0),avgSameCount:avgSameCount,brandCount:brandArr.length}},
              entryBarrier:{score:barrierScore,maxScore:20,label:barrierLabel,data:{tmallRatio:(tmallRatio*100).toFixed(1)+'%',flagshipRatio:(flagshipRatio*100).toFixed(1)+'%',newnessLevel:newnessLevel,tmallLevel:tmallLevel,barrierType:barrierType,subsidyIndex:subsidyIndex>0?(subsidyIndex*100).toFixed(0)+'%':'无补贴'}},
              profitMargin:{score:profitScore,maxScore:15,label:profitLabel,data:{avgPrice:'¥'+avgPrice.toFixed(2),medianPrice:'¥'+medPrice.toFixed(2),priceRange:'¥'+prices[0].toFixed(2)+' ~ ¥'+prices[prices.length-1].toFixed(2)}}
            }
          },
          marketOverview:{
            totalProducts:products.length,totalSales:totalSales,totalRevenueEst:totalRevenueEst,
            avgPrice:'¥'+avgPrice.toFixed(2),medianPrice:'¥'+medPrice.toFixed(2),
            shopTypeDistribution:shopTypeDist,topShops:topShops,
            topBrands:brandArr.slice(0,8).map(function(b){return{brand:b.brand,sales:b.sales,share:(b.share*100).toFixed(1)+'%'};}),
            brandHHI:effectiveHHI.toFixed(0),brandHHI_raw:hhi.toFixed(0),hhiSource:hhiSource,
            topLocations:locArr.slice(0,5),
            tmallRatio:(tmallRatio*100).toFixed(1)+'%',flagshipRatio:(flagshipRatio*100).toFixed(1)+'%',
            adRatio:(products.filter(function(p){return p.isAd;}).length/products.length*100).toFixed(1)+'%',
            subsidyIndex:subsidyIndex>0?(subsidyIndex*100).toFixed(0)+'%':'N/A',
            avgSameCount:avgSameCount,growthDataTier:newnessTier,
            priceBands:priceBands,
            signalSummary:{listing6m:sig.listing6m.count,firstPrice:sig.firstPrice.count,newTitle:sig.newTitle.count,hotBomb:sig.hotBomb.count,hotList:sig.hotList.count,cStoreCount:cStoreCount}
          },
          products:products.map(function(p){return{
            item_id:p.item_id,title:p.title,
            price:'¥'+p.price+(p.priceDesc?' ('+p.priceDesc+')':''),
            sales:p.salesRaw,shop:p.shop,shopType:p.shopType,location:p.location,
            brand:p.brand,listingDate:p.listingDate||'?',
            isRecent6m:p.isRecent6m,isFirstPrice:p.isFirstPrice,
            hasNewTitle:p.hasNewTitle,hasHotBomb:p.hasHotBomb,hasHotList:p.hasHotList,
            sameCount:p.sameCount,viewCount:p.viewCount
          };})
        });

      } catch(e) { resolve({error:'Scoring error: '+e.message, stack:e.stack}); }
    }, function(err) {
      if(!done){done=true;clearTimeout(globalTimer);resolve({error:'Multi-page fetch failed',detail:String(err)});}
    });
  });
}
