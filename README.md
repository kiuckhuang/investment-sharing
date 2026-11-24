# investment-sharing

用 Stage Analysis（Stan Weinstein 四階段）同價量框架驗證市場觀點，並長期記錄「事前判斷 vs 事後結果」的廣東話網站。

- 網站：<https://kiuckhuang.github.io/investment-sharing/>
- 首頁：報告列表 + 免責聲明
- `/method.html`：固定判讀門檻、覆盤結構、歷史政策

## 內容

| 檔案 | 用途 |
|---|---|
| `stan-weinstein-stage-analysis-2026-11.md` | 原始驗證報告（凍結，不再改） |
| `stan-weinstein-review-log.md` | 覆盤記錄（**只增不改**，新一節放最上面） |
| `method.md` | 方法與流程（公開） |
| `docs/PLAYBOOK.md` | 內部作業手冊（唔上站） |

## 覆盤流程（一鍵）

```bash
./tools/setup.sh                 # 一次性：建 .venv + matplotlib
.venv/bin/python tools/review.py # 抓數 → 計指標 → 存快照 → 畫圖 → 出草稿
```

輸出：

- `data/YYYY-MM-DD.json` — 當日完整指標快照（永久保留，用嚟同上次 diff）
- `assets/img/YYYY-MM-DD/{indices,breadth,sectors}.svg` — 三張圖（gzip 後 ~20KB）
- `drafts/YYYY-MM-DD.md` — 填好數字的草稿，人手只補「判讀」同「結論」

冇裝 matplotlib 都可以跑：`python3 tools/review.py --no-charts`。

## 結構

```
tools/
  marketdata.py   # 抓 Nasdaq 日線 + CNBC 報價（有 cache）
  metrics.py      # 所有指標、Stage 分類、廣度、派貨日、FTD
  charts.py       # matplotlib → SVG（字體保持 <text>，檔案細）
  review.py       # CLI：串起上面三步 + 出草稿
data/             # 每日快照（JSON，永久保留）
docs/PLAYBOOK.md  # 規則同流程
```

## 自動化

`.github/workflows/snapshot.yml` 每個交易日 22:10 UTC（美股收市後）自動跑一次，把 `data/` 同圖 commit 返 repo，所以就算本地冇開機，歷史都唔會斷。

人手只需每週寫一次覆盤：跑 script、補判讀、push。

## 要求

- Python 3.12+（用到 f-string 內嵌引號）
- 可選：matplotlib（畫圖）

## 注意

- 唔會上載訪問逐字稿（版權）。
- 冇任何個人資料：冇 email、電話、本機路徑。
- 所有內容**唔構成投資建議**。