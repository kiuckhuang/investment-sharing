#!/usr/bin/env python3
"""覆盤一鍵流程：抓數 → 計指標 → 存快照 → 畫圖 → 出草稿。

用法：
    python3 tools/review.py                  # 用最新收市數據
    python3 tools/review.py --date 2026-11-24
    python3 tools/review.py --no-charts      # 冇裝 matplotlib 時
    python3 tools/review.py --offline        # 只用本地 cache

輸出一律係「資料 + 數字」，唔會幫你寫結論——結論由人補，
所以每次覆盤嘅格式、計法、門檻都一模一樣。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import charts  # noqa: E402
import marketdata  # noqa: E402
import metrics  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
DRAFT_DIR = os.path.join(ROOT, "drafts")
IMG_DIR = os.path.join(ROOT, "assets", "img")

INDEX_KEYS = ["SPY", "QQQ", "IWM", "SOXX", "SMH", "IBB", "RSP"]
RISK_KEYS = ["UUP", "HYG", "LQD", "TLT", "GLD", "SLV", "GDX"]
SECTOR_KEYS = ["XLP", "XLU", "XLE", "XRT", "XLV", "IBB", "XLF", "XLY",
               "XLI", "XLB", "XLRE", "XLC", "IGV"]


def fmt(v, digits=2, sign=False, suffix=""):
    if v is None:
        return "—"
    pat = f"{{:+.{digits}f}}" if sign else f"{{:.{digits}f}}"
    return pat.format(v) + suffix


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join([":--:"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def same_core(path, snap):
    """同舊快照比較（忽略 generated 同即時報價），一樣就唔重寫，免得每日多一個 commit。"""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:  # noqa: BLE001
        return False
    skip = {"generated", "quotes"}
    a = {k: v for k, v in old.items() if k not in skip}
    b = {k: v for k, v in snap.items() if k not in skip}
    return a == b


def load_previous(asof):
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    prev = None
    for path in files:
        if os.path.basename(path) < f"{asof}.json":
            prev = path
    if not prev:
        return None
    try:
        with open(prev, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def section_indices(snap):
    s = snap["symbols"]
    rows = []
    for k in INDEX_KEYS:
        if k not in s:
            continue
        v = s[k]
        rows.append([k, fmt(v["close"]), fmt(v["d1"], sign=True, suffix="%"),
                     fmt(v["vs20"], sign=True, suffix="%"), fmt(v["vs50"], sign=True, suffix="%"),
                     fmt(v["vs200"], sign=True, suffix="%"), fmt(v["rsi"], 0),
                     fmt(v["slope200"], sign=True), v["stage"]])
    body = table(["代號", "收市", "日變", "對 20 日線", "對 50 日線", "對 200 日線", "RSI", "200 日線斜率", "Stage"], rows)
    return "### 1. 指數與 Stage 判定\n\n" + body + "\n\n"


def section_breadth(snap):
    b = snap.get("breadth") or []
    if not b:
        return "### 2. 市場廣度\n\n（無數據）\n\n"
    cur = b[-1]
    prev = b[-2] if len(b) > 1 else None
    low = min(b, key=lambda x: x["pct_above20"])
    prev_txt = f"（上一交易日 {prev["pct_above20"]:.0f}%）" if prev else ""
    lines = ["### 2. 市場廣度（股票樣本）\n",
             f"- 高於 20 日線：**{cur["pct_above20"]:.0f}%**{prev_txt}",
             f"- 創 20 日新低：**{cur["new20_lows"]} 隻**／樣本 {cur["sample"]} 隻",
             f"- 創 20 日新高：**{cur["new20_highs"]} 隻**",
             f"- 近 60 個交易日最低廣度：{low["date"]} 嘅 {low["pct_above20"]:.0f}%",
             f"- 距離牛市推力門檻（60%）：**差 {60 - cur["pct_above20"]:.0f} 個百分點**", ""]
    return "\n".join(lines) + "\n"


def section_days(snap):
    d = snap.get("distribution") or {}
    rows = [[k, f"{v["count"]}/25", "、".join(x[5:] for x in v["dates"][-5:]) or "—"] for k, v in d.items()]
    body = table(["指數", "派貨日", "最近幾日"], rows)
    ftd = snap.get("ftd") or {}
    if ftd:
        verdict = "已出現合格 FTD" if ftd["qualifies"] else "未有合格 FTD"
        vol_txt = "放大" if ftd["volume_up"] else "萎縮"
        pos_txt = "收喺上半部" if ftd["closed_upper_half"] else "收喺下半部"
        ftd_txt = ("- 本輪低位：**{}**（{:.2f}），至今第 **{}** 個交易日；最早可確認日 = 第 {} 日\n"
                   "- 今日升幅 {:+.2f}%、成交{}、{} → **{}**"
                   ).format(ftd["low_date"], ftd["low_price"], ftd["days_since_low"],
                            ftd["first_possible_day"], ftd["today_gain_pct"], vol_txt, pos_txt, verdict)
    else:
        ftd_txt = "- 無 FTD 數據"
    return ("### 3. 派貨日與 Follow-Through Day\n\n" + body + "\n\n" + ftd_txt + "\n\n")


def section_sectors(snap):
    s = snap["symbols"]
    rows = []
    for k in SECTOR_KEYS:
        if k not in s:
            continue
        v = s[k]
        rows.append([marketdata.SECTOR_NAME.get(k, k), fmt(v["d1"], sign=True, suffix="%"),
                     fmt(v["d5"], sign=True, suffix="%"), fmt(v["d20"], sign=True, suffix="%"),
                     fmt(v["vs200"], sign=True, suffix="%"), v["stage"]])
    body = table(["板塊", "單日", "5 日", "20 日", "對 200 日線", "Stage"], rows)
    ranked = sorted(((marketdata.SECTOR_NAME.get(k, k), s[k]["d20"]) for k in SECTOR_KEYS if k in s),
                    key=lambda x: x[1])
    lead = "、".join(f"{n} {v:+.1f}%" for n, v in ranked[-3:][::-1])
    lag = "、".join(f"{n} {v:+.1f}%" for n, v in ranked[:3])
    return ("### 4. 板塊輪動\n\n" + body + "\n\n"
            f"- 20 日領先：{lead}\n- 20 日落後：{lag}\n\n")


def section_risk(snap):
    s = snap["symbols"]
    rows = []
    for k in RISK_KEYS:
        if k not in s:
            continue
        v = s[k]
        rows.append([k, fmt(v["close"]), fmt(v["d5"], sign=True, suffix="%"),
                     fmt(v["vs200"], sign=True, suffix="%"), fmt(v["rsi"], 0),
                     fmt(v["from_hi"], sign=True, suffix="%"), v["stage"]])
    body = table(["代號", "收市", "5 日", "對 200 日線", "RSI", "距 52 週高", "Stage"], rows)
    q = snap.get("quotes") or {}
    bits = []
    vix = q.get(".VIX") or {}
    if vix.get("last"):
        bits.append("- VIX **{:.2f}**（{:+.1f}%）".format(vix["last"], vix.get("change_pct", 0)))
    tnx = q.get("US10Y") or {}
    if tnx.get("last"):
        bits.append("- 10 年美債息 **{:.3f}%**".format(tnx["last"]))
    extra = ("\n".join(bits) + "\n") if bits else ""
    return "### 5. 風險資產（美元／信貸／商品）\n\n" + body + "\n\n" + extra + "\n"


def section_stocks(snap):
    s = snap["symbols"]
    stocks = snap["universe"]["stocks"]
    s2 = sorted(k for k in stocks if k in s and s[k]["stage"] == "2")
    s4 = sorted(k for k in stocks if k in s and s[k]["stage"] == "4")
    rows = []
    for k in stocks:
        if k not in s:
            continue
        v = s[k]
        rows.append([k, fmt(v["close"]), fmt(v["d1"], sign=True, suffix="%"),
                     fmt(v["vs50"], sign=True, suffix="%"), fmt(v["vs200"], sign=True, suffix="%"),
                     fmt(v["rsi"], 0), fmt(v["from_hi"], sign=True, suffix="%"), v["stage"]])
    body = table(["代號", "收市", "日變", "對 50 日線", "對 200 日線", "RSI", "距 52 週高", "Stage"], rows)
    sep = "、"
    list2 = sep.join(s2) if s2 else "無"
    list4 = sep.join(s4) if s4 else "無"
    head = (f"- Stage 2（上升趨勢）：**{len(s2)} 隻** — {list2}\n"
            f"- Stage 4（下跌趨勢）：**{len(s4)} 隻** — {list4}\n")
    return ("### 6. 個股樣本\n\n" + head + "\n" + body + "\n\n")


def section_gaps(snap):
    g = snap.get("gaps") or {}
    rows = []
    for k, v in g.items():
        if not v:
            continue
        rows.append([k, fmt(v["open"]), fmt(v["prev_high"]), fmt(v["gap"], sign=True),
                     fmt(v["gap_pct"], sign=True, suffix="%"), "已補" if v["filled"] else "**未補**"])
    if not rows:
        return ""
    return "### 7. 缺口檢查（當日開市 vs 上日高位）\n\n" + table(["代號", "開市", "上日高位", "缺口", "缺口 %", "狀態"], rows) + "\n\n"


def section_diff(snap, prev):
    if not prev:
        return "### 8. 與上次快照比較\n\n（首次快照，無從比較）\n\n"
    rows = []
    for k in ["SPY", "QQQ", "IWM", "SOXX", "SMH", "HYG", "UUP"]:
        a = prev["symbols"].get(k)
        b = snap["symbols"].get(k)
        if not a or not b:
            continue
        rows.append([k, fmt(a["close"]), fmt(b["close"]),
                     fmt((b["close"] / a["close"] - 1) * 100, sign=True, suffix="%"),
                     fmt(a["vs200"], sign=True, suffix="%"), fmt(b["vs200"], sign=True, suffix="%"),
                     fmt(b["rsi"] - a["rsi"], sign=True)])
    ba = (prev.get("breadth") or [{}])[-1]
    bb = (snap.get("breadth") or [{}])[-1]
    body = table(["代號", "上次收市", "今次收市", "期間變幅",
                  "上次對 200 日線", "今次對 200 日線", "RSI 變化"], rows)
    note = (f"- 廣度：{ba.get("pct_above20", 0):.0f}% → {bb.get("pct_above20", 0):.0f}%\n"
            f"- 創 20 日新低：{ba.get("new20_lows", 0)} → {bb.get("new20_lows", 0)} 隻\n")
    return ("### 8. 與上次快照比較\n\n" + body + "\n\n" + note + "\n")


def build_draft(snap, prev):
    parts = [
        f"# 覆盤 {snap["asof"]}（草稿）",
        "",
        f"> 由 `tools/review.py` 生成：{snap["generated"]}。數字全部由程式計，",
        "> 人手只補「判讀」同「結論」，唔好改上面嘅數。",
        "",
        "## 0. 一頁摘要",
        "",
        "（待填：3–5 條 bullet，每條要有一條數據支持）",
        "",
        section_indices(snap),
        section_breadth(snap),
        section_days(snap),
        section_sectors(snap),
        section_risk(snap),
        section_gaps(snap),
        section_diff(snap, prev),
        "### 9. 覆核清單",
        "",
        "- [ ] 經濟數據（PCE／CPI／非農）日期同市場預期",
        "- [ ] 聯儲局定價（CME FedWatch / Fisclear）有冇變",
        "- [ ] 大型業績、指數成分股調整",
        "- [ ] 上一版判斷今日仍然成立？唔成立就寫「修訂」",
        "",
    ]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="資料截止日（YYYY-MM-DD），預設最新收市")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--offline", action="store_true", help="只用 cache，唔上網")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--status", action="store_true", help="只印最新快照摘要")
    args = ap.parse_args()

    if args.status:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
        if not files:
            print("data/ 未有快照，先跑 make review")
            return
        with open(files[-1], encoding="utf-8") as fh:
            print(metrics.summarise(json.load(fh)))
        print("\n快照：" + os.path.relpath(files[-1], ROOT))
        return

    print("① 抓取數據…")
    if args.offline:
        data = {}
        for sym in marketdata.ETF + marketdata.STOCKS:
            data[sym] = marketdata._read_cache(sym, "0000-00-00") or []  # noqa: SLF001
        quotes = {}
    else:
        data, quotes = marketdata.load_all(not_before=args.date, verbose=not args.quiet)

    print("② 計算指標…")
    snap = metrics.build(data, quotes, asof=args.date)
    os.makedirs(DATA_DIR, exist_ok=True)
    snap_name = snap["asof"]
    snap_path = os.path.join(DATA_DIR, snap_name + ".json")
    if not same_core(snap_path, snap):
        with open(snap_path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=1)
        print("   快照 → " + os.path.relpath(snap_path, ROOT))
    else:
        print("   快照無變化，沿用 " + os.path.relpath(snap_path, ROOT))

    prev = load_previous(snap_name)

    if not args.no_charts:
        print("③ 畫圖…")
        outdir = os.path.join(IMG_DIR, snap_name)
        paths = charts.render_all(data, snap, outdir, names=marketdata.SECTOR_NAME)
        for key, path in paths.items():
            print("   %-8s %s  %s B" % (key, os.path.relpath(path, ROOT), format(os.path.getsize(path), ",")))

    os.makedirs(DRAFT_DIR, exist_ok=True)
    draft_path = os.path.join(DRAFT_DIR, snap_name + ".md")
    with open(draft_path, "w", encoding="utf-8") as fh:
        fh.write(build_draft(snap, prev))

    print()
    print(metrics.summarise(snap))
    print()
    print("草稿 → " + os.path.relpath(draft_path, ROOT))
    print("圖片 → assets/img/%s/" % snap_name)
    print()
    print("下一步：")
    print("  1) 睇 drafts/%s.md，補「判讀」同「結論」" % snap_name)
    print("  2) 貼入 stan-weinstein-review-log.md（新增一節，唔改舊節）")
    print("  3) make publish MSG=\"review %s\"" % snap_name)


if __name__ == "__main__":
    main()