# bash, not zsh: the CI runner (ubuntu-latest) has no /bin/zsh, and every
# recipe is POSIX-compatible anyway. bash exists on both macOS and Linux.
SHELL := /bin/bash
PORT := 8000
ROOT := site

# Source .env.local if present (gitignored, per-machine overrides).
# Use it to set MARIOLOGY_CORPUS or PORT without editing the Makefile.
-include .env.local

# Fallback when .env.local is absent or unreadable (sandboxed sessions deny
# reads of .env.* files): the canonical corpus location on this machine.
# .env.local or the environment still wins when it sets the variable.
MARIOLOGY_CORPUS ?= $(HOME)/Inquiry Vault/Domains/Theology/Mariology
export

.DEFAULT_GOAL := help

.PHONY: help serve stop check seo clean build-data ics verify-data clean-data validate-refs validate-quotes verify-data-sync verify-apparatus-sync

help: ## list available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

seo: ## regenerate SEO blocks, sitemap, and RSS feed (run after editing pages)
	@python3 tools/inject-seo.py
	@python3 tools/regen-sitemap.py
	@python3 tools/gen-feed.py

serve: ## start local site at http://localhost:$(PORT)
	@lsof -ti tcp:$(PORT) >/dev/null 2>&1 && echo "Already serving on :$(PORT)" || \
		( cd $(ROOT) && python3 -m http.server $(PORT) >/tmp/mediatrix-serve.log 2>&1 & ) && \
		sleep 0.4 && echo "Mediatrix → http://localhost:$(PORT)"

stop: ## kill the local server
	@lsof -ti tcp:$(PORT) | xargs -r kill 2>/dev/null && echo "stopped" || echo "not running"

check: ## quick health (page count, dead anchors, raw hex outside :root)
	@echo "--- pages ---"
	@ls $(ROOT)/*.html 2>/dev/null | wc -l | awk '{print "  html pages: " $$1}'
	@echo "--- href=# in primary nav (should be empty) ---"
	@grep -l 'href="#"' $(ROOT)/*.html 2>/dev/null || echo "  none"
	@echo "--- bare document.* outside <script> (should be empty) ---"
	@grep -n '^document\.' $(ROOT)/*.html 2>/dev/null || echo "  none"
	@echo "--- raw hex outside :root (should be empty; theme-color is exempt) ---"
	@grep -EHn '#[0-9A-Fa-f]{6}' $(ROOT)/*.html 2>/dev/null | grep -v 'favicon\|svg\|theme-color' || echo "  none"
	@echo "--- font count (expected 27) ---"
	@ls $(ROOT)/fonts/*.woff2 2>/dev/null | wc -l | awk '{print "  woff2: " $$1}'

clean: ## remove tmp/ + pyc + .DS_Store
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".DS_Store" -delete 2>/dev/null || true
	@rm -rf tmp/ 2>/dev/null || true
	@echo "cleaned"

build-data: ## regenerate site/data/*.json from the markdown corpus
	@python3 tools/build-mediatrix.py

ics: ## regenerate the subscribable Marian feast calendar (site/marian-feasts.ics)
	@python3 tools/gen-ics.py

apparatus: ## regenerate derived pages (catena, concordance, scripture index, timeline) + SEO
	@python3 tools/build-apparatus.py
	@python3 tools/build-scripture-index.py
	@python3 tools/build-timeline.py
	@$(MAKE) seo

verify-data: ## verify all site/data/*.json exist with sensible record counts
	@python3 tools/build-mediatrix.py --verify

clean-data: ## remove all generated site/data/*.json
	@rm -f $(ROOT)/data/*.json && echo "  removed $(ROOT)/data/*.json"

validate-refs: ## cross-page validator: orphan saint references vs anthology
	@python3 tools/validate-references.py

validate-quotes: ## quote integrity gate: source + provenance + renderability (strict)
	@python3 tools/validate-quotes.py --strict

verify-data-sync: ## reproducible-build + committed-data-in-sync gate (needs MARIOLOGY_CORPUS)
	@python3 tools/verify-data-sync.py

verify-apparatus-sync: ## derived pages (catena/concordance/scripture/timeline) + card-count sync gate
	@python3 tools/verify-apparatus-sync.py
