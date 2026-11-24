#!/usr/bin/env python3
"""由快照 JSON 畫三張 SVG 圖（指數走勢、市場廣度、板塊單日表現）。

刻意用 SVG 而唔用 Chart.js：五張圖 gzip 後加埋 ~40KB，細過一個 JS library，
而且放大唔會矇、可以離線睇、唔使執行 JS。
"""
from __future__ import annotations

import datetime as dt
import os

try:  # 冇裝 matplotlib 都要行到（只係冇圖）
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates  # noqa: E402
    import matplotlib.pyplot as plt  # noqa: E402
    from matplotlib import font_manager  # noqa: E402

    HAVE_MPL = True
except Exception:  # noqa: BLE001
    HAVE_MPL = False

CJK_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

GREY, ORANGE, RED, GREEN, BLUE, PURPLE = "#7f8c8d", "#e08a1e", "#c0392b", "#27ae60", "#2c6fbb", "#8e44ad"


def setup_fonts():
    for path in CJK_CANDIDATES:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
                name = font_manager.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = [name]
                break
            except Exception:  # noqa: BLE001
                continue
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"   # 文字保持 <text>，SVG 細 10 倍以上
    plt.rcParams["svg.hashsalt"] = "stage-analysis"  # 固定 id，數據無變就 byte-identical
    plt.rcParams["path.simplify"] = True
    plt.rcParams["path.simplify_threshold"] = 0.4


def _dates_axis(ax, interval=14):
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.grid(alpha=0.25)
    ax.margins(x=0.012)


def chart_indices(history, snap, path, months=3):
    """三大指數：收市價 + 20/50/200 日線，標出近期低位。"""
    figs = ["SPY", "QQQ", "IWM"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 10.2))
    start = None
    for ax, sym in zip(axes, figs):
        rows = history.get(sym) or []
        if not rows:
            ax.set_visible(False)
            continue
        dates = [dt.date.fromisoformat(r["date"]) for r in rows]
        closes = [r["close"] for r in rows]
        if start is None:
            start = dates[-1] - dt.timedelta(days=30 * months)
        idx = [i for i, d in enumerate(dates) if d >= start]
        d = [dates[i] for i in idx]
        c = [closes[i] for i in idx]

        def ma(n):
            out = [None] * len(closes)
            for i in range(n - 1, len(closes)):
                out[i] = sum(closes[i - n + 1:i + 1]) / n
            return out

        ax.plot(d, c, color="#111", lw=1.7, label="收市價")
        ax.plot(d, [ma(20)[i] for i in idx], color=GREY, lw=1.0, ls=":", label="20 日線")
        ax.plot(d, [ma(50)[i] for i in idx], color=ORANGE, lw=1.2, label="50 日線")
        ax.plot(d, [ma(200)[i] for i in idx], color=RED, lw=1.5, label="200 日線")
        v = snap["symbols"].get(sym, {})
        low_i = min(range(len(rows) - 25, len(rows)), key=lambda i: rows[i]["low"])
        ax.plot([dates[low_i]], [rows[low_i]["low"]], marker="o", ms=4.5, color=PURPLE, zorder=5)
        ax.annotate(f"{dates[low_i]:%m/%d} 低位 {rows[low_i]["low"]:.2f}",
                    xy=(dates[low_i], rows[low_i]["low"]),
                    xytext=(-122, 16), textcoords="offset points",
                    fontsize=7.5, color=PURPLE,
                    arrowprops=dict(arrowstyle="->", color=PURPLE, lw=0.7))
        ax.set_title(f"{sym}　收 {v.get("close", 0):.2f}　對 200 日線 {v.get("vs200", 0):+.1f}%"
                     f"　RSI {v.get("rsi", 0):.0f}　Stage {v.get("stage", "?")}",
                     fontsize=11.5, loc="left")
        ax.legend(fontsize=7.5, loc="upper left", ncol=4, framealpha=0.9)
        _dates_axis(ax)
    fig.suptitle(f"{snap["asof"]}　三大指數：反彈之後仲未收復 200 日線", fontsize=13.5)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(path, metadata={"Date": None})
    plt.close(fig)


def chart_breadth(snap, path):
    b = snap.get("breadth") or []
    if not b:
        return
    dates = [dt.date.fromisoformat(x["date"]) for x in b]
    pct = [x["pct_above20"] for x in b]
    lows = [x["new20_lows"] for x in b]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.8),
                                 gridspec_kw={"height_ratios": [2.2, 1]}, sharex=True)
    a1.plot(dates, pct, color="#111", lw=1.9)
    a1.axhline(60, color=GREEN, ls="--", lw=1.2)
    a1.text(dates[1], 62, "牛市推力門檻 60%", color=GREEN, fontsize=8)
    a1.axhline(20, color=RED, ls=":", lw=1)
    a1.set_ylim(0, 102)
    a1.set_ylabel("高於 20 日線（%）", fontsize=9)
    a1.set_title(f"{snap["asof"]}　市場廣度：{pct[-1]:.0f}%（樣本 {b[-1]["sample"]} 隻股票）",
                 fontsize=12.5, loc="left")
    low_i = min(range(len(pct)), key=lambda i: pct[i])
    a1.plot([dates[low_i]], [pct[low_i]], marker="o", ms=5, color=RED, zorder=5)
    a1.annotate(f"{dates[low_i]:%m/%d} 低位 {pct[low_i]:.0f}%",
                xy=(dates[low_i], pct[low_i]), xytext=(-96, -28), textcoords="offset points",
                fontsize=8, color=RED, arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))
    a1.plot([dates[-1]], [pct[-1]], marker="o", ms=5, color=GREEN, zorder=5)
    a1.annotate(f"{dates[-1]:%m/%d} {pct[-1]:.0f}%", xy=(dates[-1], pct[-1]),
                xytext=(-78, 22), textcoords="offset points", fontsize=8, color=GREEN,
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=0.8))
    a1.grid(alpha=0.25)
    a2.bar(dates, lows, color=RED, alpha=0.75, width=1.0)
    a2.set_ylabel("創 20 日新低（隻）", fontsize=9)
    a2.grid(alpha=0.25)
    a2.set_ylim(0, max(lows + [5]) + 3)
    peak = max(range(len(lows)), key=lambda i: lows[i])
    a2.annotate(f"{dates[peak]:%m/%d}：{lows[peak]} 隻", xy=(dates[peak], lows[peak]),
                xytext=(-70, 8), textcoords="offset points", fontsize=8, color=PURPLE)
    _dates_axis(a2, 7)
    fig.tight_layout()
    fig.savefig(path, metadata={"Date": None})
    plt.close(fig)


def chart_sectors(snap, path, names=None):
    sym = snap["symbols"]
    pairs = [(names.get(k, k), sym[k]["d1"]) for k in (names or {}) if k in sym and sym[k]["d1"] is not None]
    if not pairs:
        return
    pairs.sort(key=lambda x: x[1])
    labels = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    fig, ax = plt.subplots(figsize=(9.5, 0.34 * len(pairs) + 1.6))
    colors = [RED if v < 0 else GREEN for v in vals]
    ax.barh(labels, vals, color=colors, alpha=0.85, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + (0.12 if v >= 0 else -0.12), i, f"{v:+.1f}%",
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333", lw=0.9)
    pad = max(abs(min(vals)), abs(max(vals))) * 0.18 + 0.4
    ax.set_xlim(min(vals) - pad, max(vals) + pad)
    ax.set_title(f"{snap["asof"]}　板塊單日表現（紅跌綠升）", fontsize=12.5, loc="left")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, metadata={"Date": None})
    plt.close(fig)


def render_all(history, snap, outdir, names=None):
    if not HAVE_MPL:
        print("[warn] 未安裝 matplotlib，跳過畫圖（跑 tools/setup.sh 安裝）")
        return {}
    os.makedirs(outdir, exist_ok=True)
    setup_fonts()
    paths = {}
    for key, fn in (("indices", lambda p: chart_indices(history, snap, p)),
                    ("breadth", lambda p: chart_breadth(snap, p)),
                    ("sectors", lambda p: chart_sectors(snap, p, names))):
        path = os.path.join(outdir, f"{key}.svg")
        try:
            fn(path)
            if os.path.exists(path) and os.path.getsize(path) > 500:
                paths[key] = path
        except Exception as exc:  # noqa: BLE001 - 畫唔到圖唔應該阻住出報告
            print(f"[warn] {key} 圖失敗：{type(exc).__name__}: {exc}")
    return paths