# =============================================================================
#  Makefile — 覆盤流程：抓數、計指標、畫圖、出草稿、發佈
#
#  Quick start:
#    make setup     # 一次性：建立 .venv + matplotlib
#    make review    # 抓數 → 計指標 → 存快照 → 畫圖 → 出草稿
#    make show      # 睇最新草稿，補「判讀」同「結論」
#    make publish MSG="review 2026-11-25"
#
#  唔想記指令？`make` 會列出所有 target。
# =============================================================================

VENV := .venv
PY := $(shell if [ -x $(VENV)/bin/python ]; then echo $(VENV)/bin/python; else echo python3; fi)
DATE_ARG := $(if $(DATE),--date $(DATE),)
DRAFT := $(shell ls -1t drafts/*.md 2>/dev/null | head -1)

.PHONY: all help setup review snapshot offline charts show status check test data publish serve clean clean-all

all: help

help:
	@echo "用法：make <target>"
	@echo ""
	@echo "日常："
	@echo "  review      — 抓數 → 計指標 → 存快照 → 畫圖 → 出草稿（DATE=2026-11-25 可指定）"
	@echo "  show        — 印最新草稿（補判讀前先睇）"
	@echo "  status      — 印最新快照摘要（指數、廣度、派貨日、FTD）"
	@echo "  publish     — git add + commit + push（MSG=\"...\" 必填）"
	@echo ""
	@echo "維護："
	@echo "  setup       — 建立 .venv 並安裝 matplotlib（畫圖用）"
	@echo "  snapshot    — 只存快照，唔畫圖（CI 用）"
	@echo "  offline     — 唔上網，用本地 cache 重算一次"
	@echo "  charts      — 用最新快照重畫三張 SVG"
	@echo "  check       — 檢查快照、圖檔、頁面連結、個人資料"
	@echo "  test        — check + 離線跑一次完整流程"
	@echo "  data        — 列出所有快照"
	@echo "  serve       — 本地預覽網站（需要 Jekyll）"
	@echo "  clean       — 清 cache、_site、草稿"
	@echo "  clean-all   — 連 .venv 一齊清"
	@echo ""
	@echo "目前 Python：$(PY)"

setup:
	@./tools/setup.sh

# 完整流程：抓數 + 計指標 + 存快照 + 畫圖 + 出草稿
review:
	@$(PY) tools/review.py $(DATE_ARG)

snapshot:
	@$(PY) tools/review.py --no-charts --quiet $(DATE_ARG)

offline:
	@$(PY) tools/review.py --offline $(DATE_ARG)

charts:
	@$(PY) tools/review.py --offline --quiet $(DATE_ARG)

status:
	@$(PY) tools/review.py --status

show:
	@if [ -z "$(DRAFT)" ]; then echo "未有草稿，先跑 make review"; exit 1; fi; \
	echo "== $(DRAFT) =="; sed -n '1,200p' "$(DRAFT)"

check:
	@$(PY) tools/check.py

test: check
	@$(PY) tools/review.py --offline --no-charts --quiet >/tmp/review-test.log 2>&1 \
		&& grep -q "資料截止" /tmp/review-test.log \
		&& echo "✓ 離線覆盤跑得通"

data:
	@ls -lh data/*.json 2>/dev/null || echo "data/ 冇快照"

publish:
	@test -n "$(MSG)" || { echo "用法：make publish MSG=\"review 2026-11-25\""; exit 1; }
	@git add -A; \
	if git diff --cached --quiet; then echo "冇改動，唔需要 commit"; exit 0; fi; \
	git commit -q -m "$(MSG)" && git push && echo "✓ 已發佈：$(MSG)"

serve:
	@if command -v jekyll >/dev/null 2>&1; then jekyll serve --livereload; \
	elif bundle exec jekyll --version >/dev/null 2>&1; then bundle exec jekyll serve --livereload; \
	else echo "未安裝 Jekyll。可以：gem install jekyll jekyll-theme-primer"; \
	     echo "或者直接睇 GitHub Pages：https://kiuckhuang.github.io/investment-sharing/"; fi

clean:
	@rm -rf tools/.cache _site .jekyll-cache drafts
	@echo "✓ 已清 cache、_site、草稿（data/ 同圖保留）"

clean-all: clean
	@rm -rf $(VENV)
	@echo "✓ 已移除 .venv"