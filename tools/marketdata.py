#!/usr/bin/env python3
"""市場數據抓取層：只拿 OHLCV 同即時報價，唔做計算。

一般唔需要直接跑（交畀 tools/review.py 統一處理），只係想測試網絡時：
    python3 tools/marketdata.py --check
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 觀察名單：改呢兩個 list 就等於改覆盤範圍。
ETF = ["SPY", "QQQ", "IWM", "DIA", "SOXX", "SMH", "IBB", "XRT", "XLV", "IGV",
       "XLE", "XLF", "XLY", "XLI", "XLB", "XLRE", "XLC", "XLU", "XLP", "RSP",
       "SPHB", "SPLV", "MTUM", "GLD", "TLT", "HYG", "LQD", "UUP", "SLV", "XBI",
       "KRE", "XME", "GDX"]

STOCKS = ["NVDA", "AMD", "MU", "AVGO", "TSM", "MSFT", "GOOGL", "META", "AMZN",
          "AAPL", "COST", "MCK", "WMT", "JNJ", "PG", "CAT", "BLK", "FIX", "GIL",
          "AMKR", "CAMT", "ACMR", "AS", "PLNT", "ADMA", "CCSI", "BSY", "EPAM",
          "GDYN", "IBTA", "ARDT", "MAZE", "KD", "RWAY", "ANET", "VRT", "SMCI",
          "ORCL", "DELL", "TSLA", "NFLX", "CRM", "ADBE"]

SECTOR_NAME = {
    "XLP": "必需消費", "XLU": "公用事業", "XLE": "能源", "XRT": "零售",
    "XLV": "醫療", "IBB": "生物科技", "XLF": "金融", "XLY": "非必需消費",
    "XLI": "工業", "XLB": "原材料", "XLRE": "房地產", "XLC": "通訊",
    "IGV": "軟件", "RSP": "標普等權", "SPY": "標普 500", "QQQ": "納指 100",
    "IWM": "羅素 2000", "SOXX": "半導體 (SOXX)", "SMH": "半導體 (SMH)",
}

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")


def _get(url, tries=3, timeout=25):
    last = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - 網絡錯誤一律重試
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (i + 1))
    sys.stderr.write(f"[warn] 抓取失敗 {url} ({last})\n")
    return ""


def _num(text):
    if text is None:
        return 0.0
    s = str(text).replace(",", "").replace("$", "").strip()
    if not s or s in {"N/A", "--"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_nasdaq(payload):
    """Nasdaq historical API -> [{date, open, high, low, close, volume}]，舊到新。"""
    doc = json.loads(payload)
    rows = (((doc.get("data") or {}).get("tradesTable") or {}).get("rows")) or []
    out = []
    for r in rows:
        try:
            day = dt.datetime.strptime(r["date"], "%m/%d/%Y").date().isoformat()
        except Exception:  # noqa: BLE001
            continue
        out.append({"date": day, "open": _num(r.get("open")),
                    "high": _num(r.get("high")), "low": _num(r.get("low")),
                    "close": _num(r.get("close")), "volume": _num(r.get("volume"))})
    out.sort(key=lambda x: x["date"])
    return out


def _cache_path(sym):
    return os.path.join(CACHE, f"{sym}.json")


def _read_cache(sym, not_before):
    path = _cache_path(sym)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
    except Exception:  # noqa: BLE001
        return None
    if not rows or rows[-1]["date"] < not_before:
        return None
    return rows


def _write_cache(sym, rows):
    os.makedirs(CACHE, exist_ok=True)
    tmp = _cache_path(sym) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, separators=(",", ":"))
    os.replace(tmp, _cache_path(sym))


def fetch_history(sym, not_before=None, span_days=760, pause=0.9, verbose=True):
    """取 ~2 年日線。cache 已經去到 not_before 或之後就唔重複抓。"""
    if not_before:
        rows = _read_cache(sym, not_before)
        if rows:
            return rows
    end = dt.date.today()
    start = end - dt.timedelta(days=span_days)
    klass = "etf" if sym in ETF else "stocks"
    url = ("https://api.nasdaq.com/api/quote/{}/historical?assetclass={}"
           "&fromdate={}&todate={}&limit=9999").format(
               sym, klass, start.isoformat(), end.isoformat())
    payload = _get(url)
    rows = []
    if payload:
        try:
            rows = parse_nasdaq(payload)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[warn] {sym} 解析失敗 {exc}\n")
    if not rows:
        rows = _read_cache(sym, "0000-00-00") or []
        if verbose:
            print(f"  {sym:<6} FAIL（用舊 cache {len(rows)} 根）", flush=True)
        return rows
    _write_cache(sym, rows)
    if verbose:
        last = rows[-1]["date"]
        print(f"  {sym:<6} OK   {last}  {len(rows)} 根", flush=True)
    time.sleep(pause)
    return rows


def fetch_quotes():
    """CNBC 即時報價（指數、VIX、10 年債息）。抓唔到就回傳空 dict。"""
    syms = ".SPX|.NDX|.RUT|.DJI|.VIX|US10Y"
    url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
           f"?symbols={syms}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1"
           "&output=json&events=1")
    payload = _get(url)
    out = {}
    if not payload:
        return out
    try:
        doc = json.loads(payload)
        items = doc["FormattedQuoteResult"]["FormattedQuote"]
    except Exception:  # noqa: BLE001
        return out
    for item in items:
        last = _num(item.get("last"))
        chg = _num(item.get("change"))
        pct = _num(item.get("change_pct"))
        if not pct and last and chg and (last - chg):
            pct = chg / (last - chg) * 100
        out[item.get("symbol", "")] = {
            "last": last,
            "change": chg,
            "change_pct": round(pct, 2),
            "time": item.get("last_time", ""),
        }
    return out


def load_all(not_before=None, verbose=True):
    """回傳 {sym: rows}，同時附上即時報價。"""
    data = {}
    for sym in ETF + STOCKS:
        data[sym] = fetch_history(sym, not_before=not_before, verbose=verbose)
    return data, fetch_quotes()


if __name__ == "__main__":
    if "--check" in sys.argv:
        rows = fetch_history("SPY", verbose=True)
        print(f"SPY 最新 {rows[-1] if rows else None}")
        print(json.dumps(fetch_quotes(), ensure_ascii=False, indent=2)[:800])
    else:
        print(__doc__)