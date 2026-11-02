#!/usr/bin/env python3
"""Daily official TWSE/TPEx snapshots, including ETF symbol formats; do not fabricate missing rankings."""
import json, re, urllib.request
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DATA.mkdir(exist_ok=True)
SOURCES={
 'TWSE':'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL',
 'TPEx':'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
}
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'AIStockOS/0.3','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
def num(x):
 try:return float(str(x).strip().replace(',',''))
 except (ValueError,TypeError):return None
def date(x):
 s=re.sub(r'\D','',str(x or ''))
 if len(s)==7:return f'{int(s[:3])+1911:04d}-{s[3:5]}-{s[5:]}'
 if len(s)==8:return f'{s[:4]}-{s[4:6]}-{s[6:]}'
 return None
def parse(market,raw):
 result=[]
 for r in raw:
  if market=='TWSE':
   code=str(r.get('Code','')).strip();name=str(r.get('Name','')).strip()
   close=num(r.get('ClosingPrice'));volume=num(r.get('TradeVolume'))
   day=date(r.get('Date'));change=num(r.get('Change'))
  else:
   code=str(r.get('SecuritiesCompanyCode',r.get('SecuritiesCode',''))).strip()
   name=str(r.get('CompanyName',r.get('SecuritiesCompanyName',r.get('SecuritiesName','')))).strip()
   close=num(r.get('Close'));volume=num(r.get('TradingShares'))
   day=date(r.get('Date'));change=num(r.get('Change',r.get('PriceChange')))
  if re.fullmatch(r'[0-9]{4,6}[A-Za-z]?',code,re.I) and day and close and close>0:
   result.append({'symbol':code,'name':name or code,'asset_type':'ETF' if (code.startswith(('00','01')) and len(code)>=4) else 'STOCK','market':market,'date':day,'close':close,'volume':volume,'change':change})
 return result
def scaled(v,lo,hi):return max(0,min(100,100*(v-lo)/(hi-lo)))
def main():
 fetched={};errors={}
 for market,url in SOURCES.items():
  try:
   raw=fetch(url)
   if not isinstance(raw,list):raise ValueError('Unexpected JSON structure')
   rows=parse(market,raw)
   if len(rows)<50:raise ValueError(f'Only {len(rows)} valid rows: schema may have changed')
   fetched[market]=rows
  except Exception as exc:errors[market]=str(exc)
 if not fetched:raise RuntimeError('Both official sources failed: '+str(errors))
 path=DATA/'history.json'
 history=json.loads(path.read_text('utf-8')) if path.exists() else {}
 for market,rows in fetched.items():
  for r in rows:
   key=market+':'+r['symbol']
   items=[x for x in history.get(key,[]) if x['date']!=r['date']]
   items.append(r);items.sort(key=lambda x:x['date'])
   history[key]=items[-270:]
 latest=max(r['date'] for rows in fetched.values() for r in rows)
 catalog=[dict(r) for rows in fetched.values() for r in rows if r['date']==latest]
 ranks={'short':[],'swing':[],'long':[]}
 valuation={};valuation_error=None
 try:
  for v in fetch('https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL'):
   code=str(v.get('Code','')).strip()
   pe=num(v.get('PEratio'));pb=num(v.get('PBratio'));dy=num(v.get('DividendYield'))
   if code and ((pe and pe>0) or (pb and pb>0) or (dy is not None and dy>=0)):
    valuation[code]={'pe':pe,'pb':pb,'dividend_yield':dy}
 except Exception as exc:valuation_error=str(exc)
 for all_items in history.values():
  # Monthly history can be newer than the official daily snapshot; score as-of the snapshot date.
  items=[x for x in all_items if x.get('date') and x['date']<=latest and x.get('close') and x['close']>0]
  if not items:continue
  items.sort(key=lambda x:x['date'])
  r=items[-1]
  if (datetime.fromisoformat(latest)-datetime.fromisoformat(r['date'])).days>7:continue
  if r.get('asset_type')=='ETF' or str(r.get('symbol','')).startswith(('00','01')):continue
  closes=[x['close'] for x in items];n=len(closes)
  if n>=21 and len(set(x['date'] for x in items))>=21:
   mom5=closes[-1]/closes[-6]-1;mom20=closes[-1]/closes[-20]-1
   volumes=[x['volume'] for x in items[-20:] if x['volume'] is not None]
   ratio=r['volume']/(sum(volumes)/len(volumes)) if volumes and r['volume'] is not None and sum(volumes)>0 else 1
   s=round(.4*scaled(mom5,-.1,.1)+.25*scaled(mom20,-.2,.2)+.2*scaled(ratio,.5,3)+.15*(100-scaled(abs(mom5),0,.2)))
   ranks['short'].append(dict(r,score=s,observations=n,coverage='價格動能、成交量、波動；尚未納入法人及社群輿情'))
  if n>=60 and len(set(x['date'] for x in items))>=60:
   m20=sum(closes[-20:])/20;m60=sum(closes[-60:])/60
   s=round(.5*scaled(closes[-1]/closes[-60]-1,-.25,.35)+.3*scaled(m20/m60-1,-.1,.1)+.2*scaled(closes[-1]/m20-1,-.1,.1))
   ranks['swing'].append(dict(r,score=s,observations=n,coverage='價格趨勢代理指標；尚未納入基本面及法人'))
  v=valuation.get(r['symbol'])
  if n>=60 and v and (v.get('pe') or v.get('pb')):
   trend=scaled(closes[-1]/closes[-60]-1,-.3,.45)
   parts=[]
   if v.get('pe'):parts.append(100-scaled(v['pe'],5,55))
   if v.get('pb'):parts.append(100-scaled(v['pb'],.5,8))
   if v.get('dividend_yield') is not None:parts.append(scaled(v['dividend_yield'],0,8))
   score=round(.45*trend+.55*sum(parts)/len(parts))
   ranks['long'].append(dict(r,score=score,observations=n,valuation=v,coverage='官方本益比、股價淨值比、殖利率與60日價格趨勢代理評分；尚未納入完整財報及產業差異'))
 for k in ranks:ranks[k]=sorted(ranks[k],key=lambda x:(-x['score'],x['symbol']))[:10]
 market_rows=[r for r in catalog if r.get('asset_type')=='STOCK' and r.get('change') is not None]
 adv=sum(1 for r in market_rows if r['change']>0)
 dec=sum(1 for r in market_rows if r['change']<0)
 flat=sum(1 for r in market_rows if r['change']==0)
 active=[r for r in catalog if r.get('volume') is not None and r['volume']>0]
 active.sort(key=lambda r:r['volume'],reverse=True)
 heat={'session':latest,'scope':'TWSE / TPEx official daily close; share-volume ranking, not turnover value or social sentiment','advancers':adv,'decliners':dec,'unchanged':flat,'measured':len(market_rows),'advance_ratio':round(100*adv/(adv+dec),1) if adv+dec else None,'top_volume':active[:15],'change_coverage':round(100*len(market_rows)/len(catalog),1) if catalog else 0}
 count=sum(1 for items in history.values() if items and items[-1]['date']==latest)
 output={'version':'0.3','generated_at':datetime.now(timezone.utc).isoformat(),'latest_session':latest,
 'market_count':count,'catalog':catalog,'market_heat':heat,'coverage':{'history_symbols':len(history),'short_eligible':sum(len([r for r in x if r.get('date','')<=latest])>=21 for x in history.values()),'swing_eligible':sum(len([r for r in x if r.get('date','')<=latest])>=60 for x in history.values())},'source_status':dict({k:{'ok':k in fetched,'count':len(fetched.get(k,[])),'error':errors.get(k)} for k in SOURCES},VALUATION={'ok':bool(valuation),'count':len(valuation),'error':valuation_error}),
 'rankings':ranks,'status':{'short':'價格技術面試行版' if ranks['short'] else '歷史資料不足，尚未評分',
 'swing':'價格技術面試行版' if ranks['swing'] else '歷史資料不足，尚未評分',
 'long':'官方估值與價格趨勢代理研究（非完整基本面）' if ranks['long'] else '估值或歷史資料不足，尚未評分'},
 'buzz_status':'社群資料尚未授權串接，不發布熱門討論排行榜'}
 path.write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 (DATA/'latest.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'date':latest,'market_count':count,'rank_counts':{k:len(v) for k,v in ranks.items()},'errors':errors},ensure_ascii=False))
if __name__=='__main__':main()
