#!/usr/bin/env python3
"""Historical backfill for selected TWSE equities and ETFs.
Official monthly STOCK_DAY endpoint. Failures are reported; never synthesize prices.
"""
import json, time, urllib.parse, urllib.request, calendar, os
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
HISTORY=DATA/'history.json'
TICKERS=['00878','009816','00981A','0050','0056','00919','00929','2330','2317','2454','2308','2303','2881','2882','2884','2891','2886','2603','2609','2615','2382','3231','3711','2376','2357','2327','3034','3008','6669','6505','1301','1303','2002','2408','2412','5871','5880']
def months(n=4):
 now=datetime.now(timezone.utc);y,m=now.year,now.month
 for _ in range(n):
  yield f'{y:04d}{m:02d}01'
  m-=1
  if m==0:m=12;y-=1
def number(s):
 try:return float(str(s).replace(',','').strip())
 except (ValueError,TypeError):return None
def roc(s):
 parts=str(s).split('/')
 if len(parts)!=3:return None
 try:return f'{int(parts[0])+1911:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}'
 except ValueError:return None
def run():
 history=json.loads(HISTORY.read_text('utf-8')) if HISTORY.exists() else {}
 report={'attempted':0,'success':0,'failed':[],'symbols':{},'source':'TWSE STOCK_DAY monthly','generated_at':datetime.now(timezone.utc).isoformat()}
 for symbol in TICKERS:
  key='TWSE:'+symbol;existing={r['date']:r for r in history.get(key,[])}
  name=next(iter(existing.values()),{}).get('name',symbol)
  for month in months():
   if len(existing)>=65:break
   report['attempted']+=1
   url='https://www.twse.com.tw/exchangeReport/STOCK_DAY?'+urllib.parse.urlencode({'response':'json','date':month,'stockNo':symbol})
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; AIStockOS/0.3)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as res:payload=json.load(res)
    if payload.get('stat')!='OK' or not isinstance(payload.get('data'),list):raise ValueError('Unexpected response: '+str(payload.get('stat')))
    for row in payload['data']:
     if len(row)<7:continue
     d=roc(row[0]);close=number(row[6]);volume=number(row[1])
     if d and close and close>0:existing[d]={'symbol':symbol,'name':name,'market':'TWSE','asset_type':'ETF' if symbol.startswith('00') else 'STOCK','date':d,'close':close,'volume':volume,'change':None}
    report['success']+=1
   except Exception as e:report['failed'].append({'symbol':symbol,'month':month,'error':str(e)[:180]})
   time.sleep(0.35)
  history[key]=sorted(existing.values(),key=lambda x:x['date'])[-270:]
  report['symbols'][symbol]=len(history[key])
  HISTORY.write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 DATA.mkdir(exist_ok=True)
 HISTORY.write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 (DATA/'backfill-status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'attempted':report['attempted'],'success':report['success'],'failures':len(report['failed']),'symbol_counts':report['symbols']},ensure_ascii=False))
 if report['success']==0:raise RuntimeError('All historical requests failed')
if __name__=='__main__':run()
