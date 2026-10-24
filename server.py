import os, json, math, traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, request, send_from_directory
import pandas as pd

app=Flask(__name__,static_folder='.')
KST=ZoneInfo('Asia/Seoul')

def finite(x):
 try:
  v=float(x)
  return round(v,3) if math.isfinite(v) else None
 except: return None

def load_ticker(q):
 from pykrx import stock
 q=q.strip()
 if q.isdigit() and len(q)==6: return q,stock.get_market_ticker_name(q) or q
 today=datetime.now(KST).strftime('%Y%m%d')
 for market in ['KOSPI','KOSDAQ']:
  for ticker in stock.get_market_ticker_list(today,market=market):
   name=stock.get_market_ticker_name(ticker)
   if name==q: return ticker,name
 raise ValueError('종목명을 정확하게 입력하거나 6자리 종목코드를 입력하세요. 최신 상장목록 조회가 실패했을 수도 있습니다.')

def market_data(ticker):
 from pykrx import stock
 now=datetime.now(KST)
 start=(now-timedelta(days=460)).strftime('%Y%m%d')
 end=now.strftime('%Y%m%d')
 prices=stock.get_market_ohlcv_by_date(start,end,ticker,adjusted=True)
 if prices is None or prices.empty: raise RuntimeError('KRX 주가 데이터 조회 실패: 데이터 제공처의 일시적 차단 또는 종목코드를 확인하세요.')
 prices=prices.sort_index()
 prices=prices[(prices['종가']>0) & (prices['거래량']>0)]
 if len(prices)<65: raise RuntimeError('최근 65거래일 이상 유효한 주가가 없어 기술적 분석을 진행할 수 없습니다.')
 # Historical OHLCV may be delayed or adjusted. The latest actually available date is shown.
 close=prices['종가'].astype(float); volume=prices['거래량'].astype(float)
 last=float(close.iloc[-1]); date=prices.index[-1].strftime('%Y-%m-%d')
 ma={str(n):finite(close.tail(n).mean()) if len(close)>=n else None for n in [20,60,120]}
 delta=close.diff(); gains=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); losses=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
 rsi=finite(100-100/(1+gains.iloc[-1]/losses.iloc[-1])) if losses.iloc[-1]>0 else 100.
 low20=float(prices['저가'].tail(20).min()); low60=float(prices['저가'].tail(60).min())
 high20=float(prices['고가'].tail(20).max()); high60=float(prices['고가'].tail(60).max())
 # heuristic levels, not independently verified order-book resistance
 support=min(low20,ma['20'] or low20) if last>low20 else low60
 resistance=max(high20,last*1.01)
 target1=high60 if high60>last else last*1.12
 target2=max(target1*1.10,last*1.22)
 stop=min(support*0.985,last*0.97)
 rr=(target1-last)/(last-stop) if last>stop else None
 daily=[{'date':d.strftime('%m/%d'),'close':finite(c),'volume':int(v)} for d,c,v in zip(prices.index[-90:],close.iloc[-90:],volume.iloc[-90:])]
 changes={str(n):finite((last/float(close.iloc[-n-1])-1)*100) if len(close)>n else None for n in [5,20,60]}
 return {'date':date,'price':last,'ma':ma,'rsi':rsi,'support':finite(support),'resistance':finite(resistance),'target1':finite(target1),'target2':finite(target2),'stop':finite(stop),'rr':finite(rr),'daily':daily,'changes':changes,'rows':len(prices),'close_series':close,'volume_series':volume}

def flows_data(ticker, price):
 from pykrx import stock
 end=datetime.now(KST).strftime('%Y%m%d'); start=(datetime.now(KST)-timedelta(days=240)).strftime('%Y%m%d')
 # Investor net trading value by date (KRW), NOT estimated cost basis.
 df=stock.get_market_trading_value_by_date(start,end,ticker)
 if df is None or df.empty: raise RuntimeError('투자자별 수급 데이터가 제공되지 않았습니다.')
 df=df.sort_index()
 foreign=next((c for c in df.columns if '외국인합계' in str(c)),None)
 if foreign is None: foreign=next((c for c in df.columns if '외국인' in str(c)),None)
 institution=next((c for c in df.columns if '기관합계' in str(c)),None)
 if foreign is None or institution is None: raise RuntimeError('외국인·기관합계 컬럼을 확인할 수 없습니다.')
 vals={}
 for n in [5,20,60]:
  if len(df)<n: vals[str(n)]=None;continue
  d=df.tail(n)
  vals[str(n)]={'foreign':int(d[foreign].sum()),'institution':int(d[institution].sum()),'joint_days':int(((d[foreign]>0)&(d[institution]>0)).sum()),'foreign_positive_days':int((d[foreign]>0).sum()),'institution_positive_days':int((d[institution]>0).sum())}
 daily=[{'date':d.strftime('%m/%d'),'foreign':int(row[foreign]),'institution':int(row[institution])} for d,row in df.tail(40).iterrows()]
 return {'periods':vals,'daily':daily,'date':df.index[-1].strftime('%Y-%m-%d'),'rows':len(df)}

def fundamental_data(ticker,date):
 from pykrx import stock
 # KRX fundamentals are snapshots; often missing for loss-making firms.
 try:
  f=stock.get_market_fundamental_by_date((datetime.now(KST)-timedelta(days=20)).strftime('%Y%m%d'),datetime.now(KST).strftime('%Y%m%d'),ticker)
  if f is None or f.empty:return None
  row=f.iloc[-1]
  return {'date':f.index[-1].strftime('%Y-%m-%d'),'per':finite(row.get('PER')),'pbr':finite(row.get('PBR')),'eps':finite(row.get('EPS')),'bps':finite(row.get('BPS')),'div':finite(row.get('DIV'))}
 except:return None

def score_result(m,f):
 close=m['price']; ma=m['ma']; rsi=m['rsi']
 tech=0
 tech+=7 if ma['20'] and close>ma['20'] else 0
 tech+=7 if ma['60'] and close>ma['60'] else 0
 tech+=3 if ma['120'] and close>ma['120'] else 0
 tech+=3 if rsi is not None and 40<=rsi<=68 else 0
 flow_score=None; details=[]
 if f and all(f['periods'].get(str(n)) for n in [5,20,60]):
  p=f['periods']; flow_score=0
  for actor in ['foreign','institution']:
   s=0
   for n,w in [(5,2),(20,4),(60,4)]:
    if p[str(n)][actor]>0:s+=w
   flow_score+=s;details.append({'name':actor,'score':s,'max':10})
  joint=p['20']['joint_days'];flow_score+=round(5*joint/20)
  flow_score+=5 if (p['20']['foreign']+p['20']['institution']>0 and m['changes']['20'] is not None and m['changes']['20']>0) else 0
  flow_score+=5 if p['5']['foreign']+p['5']['institution']>0 and p['20']['foreign']+p['20']['institution']<=0 else (3 if p['5']['foreign']+p['5']['institution']>0 else 0)
  flow_score=min(35,flow_score)
 # No invented points for missing financial/industry/news data. Display only verified subscore.
 known=20+(35 if flow_score is not None else 0)
 earned=tech+(flow_score or 0)
 return {'technical':tech,'flow':flow_score,'known_points':known,'earned_points':earned,'score_out_of_known':round(100*earned/known,1) if known else None,'total_score':None,'missing':['실적·밸류에이션 20점','시장·업종 15점','뉴스·이벤트 10점']+(['외국인·기관 수급 35점'] if flow_score is None else []),'flow_details':details}

def optional_ai(payload):
 key=os.getenv('OPENAI_API_KEY','').strip()
 if not key:return {'enabled':False,'message':'OPENAI_API_KEY 미설정: AI 해석을 수행하지 않았습니다.'}
 try:
  from openai import OpenAI
  client=OpenAI(api_key=key,timeout=40)
  safe={k:v for k,v in payload.items() if k not in ('daily','close_series','volume_series')}
  safe['market'].pop('close_series',None);safe['market'].pop('volume_series',None)
  resp=client.responses.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),instructions='너는 국내주식 분석 보조자다. 입력 JSON에 확인된 데이터만 사용한다. 없는 실적, 뉴스, 밸류에이션, 기관 평단가를 만들지 않는다. 단기 목표가와 손절가는 기술적 휴리스틱이며 확정 전망이 아님을 설명한다. 투자 의견은 검증 범위에 맞춰 보수적으로 제시한다. 텐베거 모드에서는 실적·시장규모·미래 발행주식 수가 없으면 10배 가능성 판정 보류를 명시한다. 한국어로 450자 이내, 근거·한계·리스크를 구분한다.',input=json.dumps(safe,ensure_ascii=False,default=str))
  return {'enabled':True,'text':resp.output_text}
 except Exception as e:return {'enabled':False,'message':'AI 요청 실패: '+str(e)[:180]}

@app.get('/')
def index():return send_from_directory(app.static_folder,'index.html')

@app.get('/manifest.webmanifest')
def manifest():return send_from_directory(app.static_folder,'manifest.webmanifest',mimetype='application/manifest+json')

@app.get('/sw.js')
def service_worker():
 response=send_from_directory(app.static_folder,'sw.js',mimetype='application/javascript')
 response.headers['Service-Worker-Allowed']='/'
 return response

@app.get('/health')
def health():return jsonify(status='ok',time=datetime.now(KST).isoformat())

@app.post('/api/analyze')
def analyze():
 try:
  data=request.get_json(silent=True) or {}; q=str(data.get('ticker','')).strip(); mode=str(data.get('mode','trade'))
  if not q or len(q)>35:return jsonify(error='유효한 종목명을 입력하세요.'),400
  if mode not in ('trade','tenbagger'):return jsonify(error='잘못된 분석 모드'),400
  ticker,name=load_ticker(q); market=market_data(ticker)
  warnings=[]
  try:flows=flows_data(ticker,market['price'])
  except Exception as e:flows=None;warnings.append('외국인·기관 수급 조회 실패: '+str(e)[:160])
  fundamentals=fundamental_data(ticker,market['date'])
  if fundamentals is None:warnings.append('PER/PBR 최신 스냅샷 조회 불가')
  score=score_result(market,flows)
  market.pop('close_series',None);market.pop('volume_series',None)
  out={'ticker':ticker,'name':name,'mode':mode,'generated_at':datetime.now(KST).strftime('%Y-%m-%d %H:%M KST'),'market':market,'flows':flows,'fundamentals':fundamentals,'score':score,'warnings':warnings,'tenbagger':{'status':'검증 보류','reason':'장기 매출·순이익 전망, 시장규모, 미래 발행주식 수, 희석률을 신뢰할 수 있는 공시·리서치로 확보하지 못했습니다. 주가만으로 10배 성장성을 판단하지 않습니다.'} if mode=='tenbagger' else None,'sources':[{'name':'KRX 정보데이터시스템','url':'https://data.krx.co.kr/'},{'name':'DART 전자공시','url':'https://dart.fss.or.kr/'}]}
  if data.get('ai'):out['ai']=optional_ai(out)
  return jsonify(out)
 except ValueError as e:return jsonify(error=str(e)),400
 except Exception as e:return jsonify(error='데이터 조회 실패: '+str(e)[:220]),502

if __name__=='__main__':
 print('접속 주소: http://127.0.0.1:8765')
 app.run(host=os.getenv('HOST','0.0.0.0'),port=int(os.getenv('PORT','8765')),debug=False)
