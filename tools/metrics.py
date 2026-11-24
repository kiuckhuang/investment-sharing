#!/usr/bin/env python3
"""由 OHLCV 計出覆盤用嘅所有指標，輸出一個 JSON 快照（data/YYYY-MM-DD.json）。

規則全部寫死喺呢度，所以每次覆盤嘅計法都一樣——呢個就係「一致性」嘅來源。
唔好喺報告人手計數，數一律由呢支 script 出。
"""
from __future__ import annotations

import datetime as dt
import statistics


def sma(values, n):
    out = [None] * len(values)
    run = 0.0
    for i, v in enumerate(values):
        run += v
        if i >= n:
            run -= values[i - n]
        if i >= n - 1:
            out[i] = run / n
    return out


def rsi(values, n=14):
    if len(values) <= n:
        return None
    gain = loss = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gain += max(d, 0.0)
        loss += max(-d, 0.0)
    avg_g, avg_l = gain / n, loss / n
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_g = (avg_g * (n - 1) + max(d, 0.0)) / n
        avg_l = (avg_l * (n - 1) + max(-d, 0.0)) / n
    if avg_l == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def atr(rows, n=14):
    if len(rows) <= n:
        return None
    trs = []
    for i in range(len(rows) - n, len(rows)):
        hi, lo, prev = rows[i]["high"], rows[i]["low"], rows[i - 1]["close"]
        trs.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
    return sum(trs) / n


def stage_label(close, s50, s150, s200, slope200):
    """Stan Weinstein 四階段粗略分類（用嚟保持一致，唔係精確買賣訊號）。"""
    if None in (s50, s150, s200, slope200):
        return ("?", "數據不足")
    above150 = close > s150
    above200 = close > s200
    if (not above150) and (not above200) and slope200 < 0:
        detail = "價 < 150/200 日線、200 日線向下"
        return ("4", detail)
    if above150 and above200 and s50 > s200 and slope200 > 0:
        detail = "價 > 150/200 日線、50 > 200、200 日線向上"
        return ("2", detail)
    if above200 and slope200 <= 0:
        detail = "價 > 200 日線但 200 日線轉平／向下"
        return ("3", detail)
    if (not above200) and abs(slope200) <= 0.3:
        detail = "價喺 200 日線附近、200 日線橫行"
        return ("1", detail)
    if not above200:
        detail = "價 < 200 日線、200 日線未確認向下"
        return ("3", detail)
    detail = "價 > 200 日線、200 日線向上但 50 日線未跟上"
    return ("1", detail)


def symbol_metrics(rows):
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    n = len(closes)
    last = closes[-1]
    s20, s50, s150, s200 = sma(closes, 20), sma(closes, 50), sma(closes, 150), sma(closes, 200)
    i20, i50 = s20[-1], s50[-1]
    s200_prev = sma(closes[:-20], 200)[-1] if n > 220 else None
    s50_prev = sma(closes[:-20], 50)[-1] if n > 70 else None
    slope200 = (s200[-1] / s200_prev - 1) * 100 if (s200[-1] and s200_prev) else None
    slope50 = (i50 / s50_prev - 1) * 100 if (i50 and s50_prev) else None
    hi52 = max(closes[-252:])
    lo52 = min(closes[-252:])
    hi_idx = len(closes) - 252 + closes[-252:].index(hi52) if n >= 252 else closes.index(hi52)
    vol50 = sum(vols[-51:-1]) / 50 if n > 51 else None
    stage, detail = stage_label(last, i50, s150[-1], s200[-1], slope200)
    a = atr(rows)
    return {
        "date": rows[-1]["date"],
        "close": round(last, 4),
        "open": rows[-1]["open"], "high": rows[-1]["high"], "low": rows[-1]["low"],
        "prev_close": closes[-2] if n > 1 else None,
        "prev_high": rows[-2]["high"] if n > 1 else None,
        "d1": (last / closes[-2] - 1) * 100 if n > 1 else None,
        "d5": (last / closes[-6] - 1) * 100 if n > 5 else None,
        "d20": (last / closes[-21] - 1) * 100 if n > 20 else None,
        "s20": i20, "s50": i50, "s150": s150[-1], "s200": s200[-1],
        "vs20": (last / i20 - 1) * 100 if i20 else None,
        "vs50": (last / i50 - 1) * 100 if i50 else None,
        "vs150": (last / s150[-1] - 1) * 100 if s150[-1] else None,
        "vs200": (last / s200[-1] - 1) * 100 if s200[-1] else None,
        "slope50": slope50, "slope200": slope200,
        "rsi": rsi(closes),
        "hi52": hi52, "hi52_date": rows[hi_idx]["date"],
        "from_hi": (last / hi52 - 1) * 100,
        "lo52": lo52, "from_lo": (last / lo52 - 1) * 100,
        "vol": vols[-1], "vol50": vol50,
        "vol_ratio": (vols[-1] / vol50) if vol50 else None,
        "atr": a, "atr_pct": (a / last * 100) if a else None,
        "stage": stage, "stage_detail": detail,
    }


def breadth_series(data, stocks, sessions=60):
    """股票樣本中，高於 20 日線比例 + 創 20 日新低家數（逐日）。"""
    spy = data.get("SPY") or []
    dates = [r["date"] for r in spy][-sessions:]
    index = {sym: {r["date"]: i for i, r in enumerate(rows)} for sym, rows in data.items()}
    out = []
    for day in dates:
        above = total = lows = highs = 0
        for sym in stocks:
            rows = data.get(sym) or []
            i = index[sym].get(day)
            if i is None or i < 20:
                continue
            total += 1
            window = rows[i - 19:i + 1]
            ma20 = sum(r["close"] for r in window) / 20
            if rows[i]["close"] > ma20:
                above += 1
            window20 = [r["close"] for r in rows[i - 20:i + 1]]
            if rows[i]["close"] == min(window20):
                lows += 1
            if rows[i]["close"] == max(window20):
                highs += 1
        if total:
            out.append({"date": day, "pct_above20": round(100 * above / total, 1),
                        "new20_lows": lows, "new20_highs": highs, "sample": total})
    return out


def distribution_days(rows, sessions=25, drop=0.2):
    """跌 > drop% 而成交高過前一日 = 派貨日。IBD 用 25 個交易日窗口，5 個以上要小心。"""
    window = rows[-sessions - 1:]
    hits = []
    for i in range(1, len(window)):
        chg = (window[i]["close"] / window[i - 1]["close"] - 1) * 100
        if chg < -drop and window[i]["volume"] > window[i - 1]["volume"]:
            hits.append(window[i]["date"])
    return {"count": len(hits), "dates": hits[-8:]}


def follow_through_day(rows, lookback=25, min_gain=1.5):
    """IBD 式 FTD：由近 25 日最低位計，第 4 日或之後單日升 >=1.5% 且成交高過前一日。"""
    window = rows[-lookback:]
    if len(window) < 5:
        return None
    low_i = min(range(len(window)), key=lambda i: window[i]["low"])
    day_no = len(window) - low_i
    today = window[-1]
    yday = window[-2]
    gain = (today["close"] / yday["close"] - 1) * 100
    vol_up = today["volume"] > yday["volume"]
    qualified = day_no >= 4 and gain >= min_gain and vol_up
    close_range = today["high"] - today["low"]
    closed_strong = (today["close"] - today["low"]) >= 0.5 * close_range if close_range else False
    return {"low_date": window[low_i]["date"], "low_price": window[low_i]["low"],
            "days_since_low": day_no, "today_gain_pct": round(gain, 2),
            "volume_up": vol_up, "closed_upper_half": closed_strong,
            "qualifies": bool(qualified and closed_strong),
            "first_possible_day": 4}


def gap_info(row, prev_high):
    if not prev_high:
        return None
    gap = row["open"] - prev_high
    return {"open": row["open"], "prev_high": prev_high, "gap": round(gap, 3),
            "gap_pct": round(100 * gap / prev_high, 2) if prev_high else None,
            "filled": bool(row["low"] <= prev_high)}


def build(data, quotes=None, asof=None):
    spy = data.get("SPY") or []
    if not spy:
        raise SystemExit("SPY 無數據，檢查網絡或者 cache")
    asof = asof or spy[-1]["date"]
    stocks = [s for s in data if s not in _ETF_SET]
    symbols = {}
    for sym, rows in data.items():
        if len(rows) < 60:
            continue
        symbols[sym] = symbol_metrics(rows)
    breadth = breadth_series(data, stocks)
    dist = {s: distribution_days(data[s]) for s in ("SPY", "QQQ", "IWM") if s in data}
    ftd = follow_through_day(spy)
    snaps = {}
    for sym in ("SPY", "QQQ", "IWM"):
        if sym in symbols:
            snaps[sym] = gap_info({"open": symbols[sym]["open"], "high": symbols[sym]["high"],
                                   "low": symbols[sym]["low"]}, symbols[sym]["prev_high"])
    return {
        "asof": asof,
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "universe": {"etf": [s for s in data if s in _ETF_SET], "stocks": stocks},
        "symbols": symbols,
        "breadth": breadth,
        "distribution": dist,
        "ftd": ftd,
        "gaps": snaps,
        "quotes": quotes or {},
    }


from marketdata import ETF as _ETF_LIST  # noqa: E402

_ETF_SET = set(_ETF_LIST)


def summarise(snap):
    """人眼用嘅快速摘要，review.py 會印出嚟。"""
    sym = snap["symbols"]
    b = snap["breadth"]
    lines = []
    lines.append(f"資料截止 {snap["asof"]}｜樣本 {len(sym)} 隻（股票 {len(snap["universe"]["stocks"])}）")
    for s in ("SPY", "QQQ", "IWM"):
        if s in sym:
            v = sym[s]
            lines.append(f"  {s:4} {v["close"]:9.2f}  日變 {v["d1"]:+5.2f}%  對 200 日線 {v["vs200"]:+6.2f}%"
                         f"  RSI {v["rsi"]:.0f}  Stage {v["stage"]}")
    if b:
        last = b[-1]
        lines.append(f"  廣度：{last["date"]} 高於 20 日線 {last["pct_above20"]:.0f}%"
                     f"（樣本 {last["sample"]}）、創 20 日新低 {last["new20_lows"]} 隻")
    if snap["ftd"]:
        f = snap["ftd"]
        lines.append(f"  FTD：低位 {f["low_date"]} 起第 {f["days_since_low"]} 日，今日 {f["today_gain_pct"]:+.2f}%，合資格={f["qualifies"]}")
    for s, d in snap["distribution"].items():
        lines.append(f"  派貨日 {s}: {d["count"]}/25")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    from marketdata import load_all

    data, quotes = load_all()
    snap = build(data, quotes)
    print(summarise(snap))
    if "--json" in sys.argv:
        print(json.dumps(snap, ensure_ascii=False)[:2000])