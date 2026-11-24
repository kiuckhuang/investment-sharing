#!/usr/bin/env python3
"""`make check` 嘅實作：確認快照、圖檔、頁面連結同個人資料都冇問題。"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

errors = []
warnings = []


def ok(msg):
    print("  ✓ " + msg)


def fail(msg):
    errors.append(msg)
    print("  ✗ " + msg)


def warn(msg):
    warnings.append(msg)
    print("  ! " + msg)


def check_python():
    print("[1/5] Python 語法")
    for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        try:
            with open(path, encoding="utf-8") as fh:
                compile(fh.read(), path, "exec")
        except SyntaxError as exc:
            fail(f"{os.path.basename(path)} 語法錯誤：{exc}")
    ok("tools/*.py 全部 compile 得到")


def check_snapshots():
    print("[2/5] 快照")
    files = sorted(glob.glob(os.path.join(ROOT, "data", "*.json")))
    if not files:
        fail("data/ 冇任何快照")
        return []
    good = []
    for path in files:
        name = os.path.basename(path)[:-5]
        try:
            with open(path, encoding="utf-8") as fh:
                snap = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            fail(f"{name}.json 讀唔到：{exc}")
            continue
        if snap.get("asof") != name:
            fail(f"{name}.json 嘅 asof（{snap.get("asof")}）同檔名唔一致")
            continue
        if not snap.get("symbols"):
            fail(f"{name}.json 冇 symbols")
            continue
        breadth = snap.get("breadth") or []
        if not breadth:
            fail(f"{name}.json 冇 breadth")
            continue
        if breadth[-1]["date"] != name:
            fail(f"{name}.json 嘅廣度最後一日係 {breadth[-1]["date"]}")
            continue
        good.append(snap)
    ok(f"{len(good)}/{len(files)} 個快照結構正常")
    return good


def check_images(snapshots):
    print("[3/5] 圖檔")
    for snap in snapshots:
        asof = snap["asof"]
        for key in ("indices", "breadth", "sectors"):
            path = os.path.join(ROOT, "assets", "img", asof, key + ".svg")
            if not os.path.exists(path):
                warn(f"{asof} 缺少 {key}.svg")
            elif os.path.getsize(path) < 500:
                fail(f"{asof}/{key}.svg 檔案太細，可能壞咗")
    ok("圖檔齊全（缺少只會 warning）")


def check_links():
    print("[4/5] 頁面連結")
    root_md = [p for p in glob.glob(os.path.join(ROOT, "*.md"))]
    missing = 0
    for path in root_md:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for ref in re.findall(r"assets/[\w./-]+", text):
            if "YYYY" in ref or "*" in ref:  # 文件裡面嘅佔位符
                continue
            if not os.path.exists(os.path.join(ROOT, ref)):
                fail(f"{os.path.basename(path)} 引用咗唔存在嘅 {ref}")
                missing += 1
    # 首頁指向嘅頁面要存在
    index = os.path.join(ROOT, "index.md")
    if os.path.exists(index):
        with open(index, encoding="utf-8") as fh:
            text = fh.read()
        for page in re.findall(r"/[\w-]+\.html", text):
            target = os.path.join(ROOT, page.lstrip("/")[:-5] + ".md")
            if not os.path.exists(target):
                fail(f"index.md 連結 {page} 但冇對應嘅 markdown")
    if not missing:
        ok("首頁同報告引用嘅檔案都存在")


PRIVATE = [
    (r"/Users/[a-z]", "本機路徑"),
    (r"[\w.+-]+@(gmail|yahoo|hotmail|icloud)\.com", "私人 email"),
    (r"\+852[\s-]?\d{4}", "電話號碼"),
]


def check_privacy():
    print("[5/5] 個人資料")
    bad = 0
    skip_dirs = {".git", ".venv", "_site", "tools", "drafts"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith((".md", ".yml", ".json", ".py", ".html", ".scss")):
                continue
            path = os.path.join(dirpath, filename)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except Exception:  # noqa: BLE001
                continue
            for pattern, label in PRIVATE:
                if re.search(pattern, text):
                    fail(f"{os.path.relpath(path, ROOT)} 有{label}")
                    bad += 1
    if not bad:
        ok("冇本機路徑、私人 email、電話號碼")


def main():
    print("檢查 investment-sharing\n")
    check_python()
    snaps = check_snapshots()
    check_images(snaps)
    check_links()
    check_privacy()
    print()
    if errors:
        print(f"✗ {len(errors)} 個問題要修")
        return 1
    print("✓ 全部通過" + (f"（{len(warnings)} 個 warning）" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())