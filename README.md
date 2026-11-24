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

## 快速開始

```bash
make            # 列出所有 target
make setup      # 一次性：建立 .venv + matplotlib
make review     # 抓數 → 計指標 → 存快照 → 畫圖 → 出草稿
make show       # 睇最新草稿，補「判讀」同「結論」
make publish MSG="review 2026-11-25"
```

每次覆盤只需三步：`make review` → `make show` → 補完後 `make publish`。

## 常用 target

| Target | 作用 |
|---|---|
| `review` | 完整流程（可用 `DATE=2026-11-25` 指定截止日） |
| `show` | 印最新草稿 |
| `status` | 印最新快照摘要（指數、廣度、派貨日、FTD） |
| `snapshot` | 只存快照、唔畫圖（CI 用） |
| `offline` | 唔上網，用本地 cache 重算 |
| `charts` | 用最新快照重畫三張 SVG |
| `check` | 檢查快照、圖檔、頁面連結、個人資料 |
| `test` | `check` + 離線跑一次完整流程 |
| `data` | 列出所有快照 |
| `serve` | 本地預覽（需要 Jekyll） |
| `clean` / `clean-all` | 清 cache、`_site`、草稿（後者連 `.venv`） |

## 輸出

- `data/YYYY-MM-DD.json` — 當日完整指標快照（永久保留，用嚟同上次 diff）
- `assets/img/YYYY-MM-DD/{indices,breadth,sectors}.svg` — 三張圖（gzip 後 ~20KB）
- `drafts/YYYY-MM-DD.md` — 填好數字的草稿，人手只補「判讀」同「結論」

冇裝 matplotlib 都可以跑（只係冇圖）：`make snapshot`。

## 結構

```
Makefile            # 所有任務入口（make 會列出清單）
tools/
  marketdata.py     # 抓 Nasdaq 日線 + CNBC 報價（有 cache）
  metrics.py        # 所有指標、Stage 分類、廣度、派貨日、FTD
  charts.py         # matplotlib → SVG（字體保持 <text>，檔案細）
  review.py         # CLI：串起上面三步 + 出草稿
  check.py          # make check 嘅實作
data/               # 每日快照（JSON，永久保留）
docs/PLAYBOOK.md    # 規則同流程
```

## 自動化

`.github/workflows/snapshot.yml` 每個交易日 22:10 UTC（美股收市後）自動跑 `make review`，把 `data/` 同圖 commit 返 repo，所以就算本地冇開機，歷史都唔會斷。

人手只需每週寫一次覆盤：`make review`、補判讀、`make publish`。

## 要求

- Python 3.12+（用到 f-string 內嵌引號）
- 可選：matplotlib（畫圖，`make setup` 會裝）

## 注意

- 唔會上載訪問逐字稿（版權）。
- 冇任何個人資料：冇 email、電話、本機路徑（`make check` 會掃）。
- 所有內容**唔構成投資建議**。