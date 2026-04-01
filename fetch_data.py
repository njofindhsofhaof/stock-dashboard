#!/usr/bin/env python3
"""
Stock Dashboard – Data Fetcher
Chạy bởi GitHub Actions mỗi 15 phút trong giờ giao dịch.
Fetch giá + tính chỉ báo kỹ thuật → lưu stock_data.json
"""

import requests, json, time, math
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0',
    'Accept': 'application/json, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://finance.yahoo.com/',
}

# ── Danh sách tickers ───────────────────────────────
VIX   = ['^VIX', '^VXMT', 'VIXY']
T12   = ['SPY','QQQ','^DJI','^HSI','TQQQ','GLD','SLV','PALL','USO','COPX','EWJ','EWY','IEFA']
ETFS  = ['XLE','XLI','XLB','XLK','XLF','XLV','XLY','XLP','XLC','XLU','XLRE']
STOCKS = [
    # Energy
    'CVX','XOM','COP','OXY','PBR','SLB','CEG','GEV','ENPH',
    # Industrial
    'CAT','UNP','GE','RTX','LMT','BA','HON','MMM','DE','VRT','UBER','AAL','RKLB','LUNR','ASTS','ACHR',
    # Materials
    'LIN','FCX','MP','NEM','SHW','STX','WDC',
    # Technology
    'NVDA','AMD','MU','INTC','QCOM','AVGO','MRVL','AMAT','LRCX','KLAC','ASML','TXN','ADI','ARM','TSM','SMCI','COHR',
    'MSFT','GOOGL','META','AAPL','ORCL','ADBE','CRM','NOW','PANW','CRWD','INTU','SNOW','PLTR','SHOP','SPOT','RDDT','EQIX','NBIS','CRWV','OKLO','SOUN','BBAI',
    # Finance
    'JPM','BAC','C','GS','AXP','MA','V','PYPL','COF','BLK','SPGI','SOFI','HOOD','COIN','MSTR','RIOT','MARA','IREN','FUTU',
    # Healthcare
    'UNH','JNJ','LLY','MRK','ABBV','NVO','ISRG','HIMS',
    # Consumer Discretionary
    'AMZN','TSLA','HD','MCD','NKE','SBUX','CVNA','RIVN','ABNB','CPNG','MELI','NFLX',
    # Consumer Staples
    'WMT','COST','KO','PG','PM','MO',
    # Communication
    'DIS','VZ','T',
    # Utilities
    'NEE','DUK',
    # Real Estate
    'AVB',
]

def get_all_tickers():
    seen, result = set(), []
    for t in VIX + T12 + ETFS + STOCKS + ['USO','EQIX']:
        if t not in seen:
            seen.add(t); result.append(t)
    return result

# ── Yahoo Finance API ────────────────────────────────
def fetch_quotes(tickers):
    results = {}
    B = 50
    for i in range(0, len(tickers), B):
        batch = ','.join(tickers[i:i+B])
        url = (f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={batch}"
               f"&fields=shortName,regularMarketPrice,regularMarketChange,"
               f"regularMarketChangePercent,regularMarketVolume,"
               f"averageDailyVolume3Month,fiftyTwoWeekHigh,fiftyTwoWeekLow,marketCap")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            for q in r.json().get('quoteResponse', {}).get('result', []):
                results[q['symbol']] = q
        except Exception as e:
            print(f"  ⚠ Quote batch error: {e}")
        if i + B < len(tickers):
            time.sleep(0.3)
    return results

def fetch_history(sym):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1y"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        result = r.json().get('chart', {}).get('result', [None])[0]
        if not result:
            return []
        q = result.get('indicators', {}).get('quote', [{}])[0]
        cl = q.get('close', [])
        hi = q.get('high', [])
        lo = q.get('low', [])
        vo = q.get('volume', [])
        bars = []
        for i, c in enumerate(cl):
            if c is not None and not math.isnan(c):
                bars.append({'c': c,
                             'h': hi[i] if i < len(hi) else None,
                             'l': lo[i] if i < len(lo) else None,
                             'v': int(vo[i]) if i < len(vo) and vo[i] else 0})
        return bars if len(bars) >= 30 else []
    except Exception as e:
        print(f"  ⚠ History error {sym}: {e}")
        return []

# ── Indicator Calculations ───────────────────────────
def calc_rsi(closes, p=14):
    if len(closes) < p + 1:
        return None
    ag = al = 0.0
    for i in range(1, p + 1):
        d = closes[i] - closes[i-1]
        if d > 0: ag += d
        else: al -= d
    ag /= p; al /= p
    for i in range(p + 1, len(closes)):
        d = closes[i] - closes[i-1]
        ag = (ag * (p - 1) + (d if d > 0 else 0)) / p
        al = (al * (p - 1) + (-d if d < 0 else 0)) / p
    return 100.0 - 100.0 / (1 + ag / al) if al != 0 else 100.0

def calc_adx(hi, lo, cl, P=14):
    n = len(cl)
    if n < P * 2 + 1:
        return None, None, None
    tr_a, pm_a, nm_a = [], [], []
    for i in range(1, n):
        if hi[i] is None or lo[i] is None:
            tr_a.append(0); pm_a.append(0); nm_a.append(0)
            continue
        hl = hi[i] - lo[i]
        hc = abs(hi[i] - cl[i-1])
        lc = abs(lo[i] - cl[i-1])
        tr_a.append(max(hl, hc, lc))
        up = hi[i] - hi[i-1] if hi[i-1] is not None else 0
        dn = lo[i-1] - lo[i] if lo[i-1] is not None else 0
        pm_a.append(up if up > dn and up > 0 else 0)
        nm_a.append(dn if dn > up and dn > 0 else 0)
    if len(tr_a) < P * 2:
        return None, None, None
    atr = sum(tr_a[:P])
    pdm = sum(pm_a[:P])
    ndm = sum(nm_a[:P])
    def sdx(p, n): return abs(p-n)/(p+n)*100 if p+n > 0 else 0
    dx_a = [sdx(pdm/atr*100 if atr > 0 else 0, ndm/atr*100 if atr > 0 else 0)]
    for i in range(P, len(tr_a)):
        atr = atr - atr/P + tr_a[i]
        pdm = pdm - pdm/P + pm_a[i]
        ndm = ndm - ndm/P + nm_a[i]
        dx_a.append(sdx(pdm/atr*100 if atr > 0 else 0, ndm/atr*100 if atr > 0 else 0))
    adx_v = sum(dx_a[:P]) / P
    for i in range(P, len(dx_a)):
        adx_v = (adx_v * (P-1) + dx_a[i]) / P
    di_p = pdm/atr*100 if atr > 0 else 0
    di_n = ndm/atr*100 if atr > 0 else 0
    return adx_v, di_p, di_n

def calc_indicators(bars):
    if len(bars) < 30:
        return {}
    cl = [b['c'] for b in bars]
    hi = [b['h'] for b in bars]
    lo = [b['l'] for b in bars]
    vo = [b['v'] for b in bars]
    n  = len(cl)

    k12,k26,k9,k50,k200 = 2/13, 2/27, 2/10, 2/51, 2/201
    e12=e26=e50=e200=cl[0]
    ml, sl, e50a, e200a = [], [], [], []
    se = cl[0]
    for c in cl:
        e12 = c*k12 + e12*(1-k12)
        e26 = c*k26 + e26*(1-k26)
        e50 = c*k50 + e50*(1-k50)
        e200= c*k200+ e200*(1-k200)
        m = e12-e26; ml.append(m)
        se = m*k9 + se*(1-k9); sl.append(se)
        e50a.append(e50); e200a.append(e200)

    lm,pm = ml[-1], ml[-2] if n>1 else 0
    ls,ps = sl[-1], sl[-2] if n>1 else 0
    lh,ph = lm-ls, pm-ps

    golden = death = False
    lb = min(20, n-1)
    for i in range(n-lb, n):
        if i > 0:
            if e50a[i-1] <= e200a[i-1] and e50a[i] > e200a[i]: golden = True
            if e50a[i-1] >= e200a[i-1] and e50a[i] < e200a[i]: death  = True

    s20 = sum(cl[-20:])/20 if n>=20 else None
    s50 = sum(cl[-50:])/50 if n>=50 else None
    adx_v, di_p, di_n = calc_adx(hi, lo, cl, 14)

    vol65 = [v for v in vo[-66:-1] if v and v > 0]
    avg65 = sum(vol65)/len(vol65) if vol65 else None
    vol_vs65 = vo[-1]/avg65 if avg65 and avg65 > 0 and vo[-1] else None

    pr = cl[-1]
    rsi = calc_rsi(cl, 14)
    return {
        'rsi':        round(rsi, 1) if rsi is not None else None,
        'macd':       round(lm, 4),
        'macdSig':    round(ls, 4),
        'macdHist':   round(lh, 4),
        'macdUp':     bool(lh > 0 and ph <= 0),
        'macdDn':     bool(lh < 0 and ph >= 0),
        'sma20':      round(s20, 2) if s20 else None,
        'sma50':      round(s50, 2) if s50 else None,
        'ema50':      round(e50a[-1], 2),
        'ema200':     round(e200a[-1], 2),
        'goldenCross':golden,
        'deathCross': death,
        'adx':        round(adx_v, 1) if adx_v is not None else None,
        'diP':        round(di_p, 1) if di_p is not None else None,
        'diN':        round(di_n, 1) if di_n is not None else None,
        'volVs65':    round(vol_vs65, 2) if vol_vs65 is not None else None,
        'c1W':        round((pr-cl[-6])/cl[-6]*100, 2) if n>=6 else None,
        'c1M':        round((pr-cl[-22])/cl[-22]*100, 2) if n>=22 else None,
    }

def calc_score(ind, change_pct):
    if not ind: return None
    sc = 0.0
    e50, e200 = ind.get('ema50'), ind.get('ema200')
    if e50 is not None and e200 is not None:
        sc += 2.0 if e50 > e200 else -2.0
    if ind.get('goldenCross'): sc += 1.5
    if ind.get('deathCross'):  sc -= 1.5
    rsi = ind.get('rsi')
    if rsi is not None:
        if 30 <= rsi <= 70: sc += 1.0
        elif rsi > 70:      sc -= 1.5
    macd, mh = ind.get('macd'), ind.get('macdHist')
    if macd is not None and mh is not None:
        if macd > 0 and mh > 0:   sc += 1.0
        elif macd < 0 and mh < 0: sc -= 1.0
        if ind.get('macdUp'): sc += 0.5
        if ind.get('macdDn'): sc -= 0.5
    adx, dp, dn = ind.get('adx'), ind.get('diP'), ind.get('diN')
    if adx is not None and dp is not None and dn is not None and adx > 25:
        sc += 0.5 if dp > dn else -0.5
    vv = ind.get('volVs65')
    if vv is not None and change_pct is not None:
        if vv > 1.1 and change_pct > 0:   sc += 1.0
        elif vv > 1.1 and change_pct < 0: sc -= 1.0
    return round(sc * 10) / 10

def calc_signal(score):
    if score is None: return 'LOADING'
    if score >= 3.0:  return 'BUY'
    if score <= -3.0: return 'SELL'
    return 'HOLD'

# ── Main ─────────────────────────────────────────────
def main():
    start = time.time()
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n{'='*50}")
    print(f"  Bắt đầu fetch lúc {now_str}")
    print(f"{'='*50}")

    all_tickers = get_all_tickers()
    print(f"  Tổng: {len(all_tickers)} tickers\n")

    print("1/2  Đang lấy giá realtime…")
    quotes = fetch_quotes(all_tickers)
    print(f"     → {len(quotes)} tickers OK\n")

    print("2/2  Đang fetch lịch sử + tính chỉ báo…")
    data = {}
    errors = []
    for i, sym in enumerate(all_tickers, 1):
        q = quotes.get(sym, {})
        chg = q.get('regularMarketChangePercent')
        bars = fetch_history(sym)
        ind  = calc_indicators(bars) if bars else {}
        sc   = calc_score(ind, chg)
        sig  = calc_signal(sc)
        entry = {
            'symbol':        sym,
            'name':          q.get('shortName', sym),
            'price':         q.get('regularMarketPrice'),
            'change':        q.get('regularMarketChange'),
            'changePercent': chg,
            'volume':        q.get('regularMarketVolume'),
            'avgVolume':     q.get('averageDailyVolume3Month'),
            'week52H':       q.get('fiftyTwoWeekHigh'),
            'week52L':       q.get('fiftyTwoWeekLow'),
            'score':         sc,
            'signal':        sig,
        }
        entry.update(ind)
        data[sym] = entry
        if not bars: errors.append(sym)
        if i % 25 == 0:
            print(f"     → {i}/{len(all_tickers)} xong…")
        time.sleep(0.12)

    output = {
        'updated':    datetime.now(timezone.utc).isoformat(),
        'count':      len(data),
        'errors':     errors,
        'tickers':    data,
    }

    with open('stock_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    elapsed = time.time() - start
    print(f"\n✅  Xong! {len(data)} tickers — {elapsed:.0f}s")
    if errors:
        print(f"⚠   Lỗi history: {', '.join(errors[:10])}")
    print(f"    Đã lưu → stock_data.json\n")

if __name__ == '__main__':
    main()
