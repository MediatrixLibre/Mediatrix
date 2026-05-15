SHELL := /bin/zsh
PORT := 8000
ROOT := site

# Source .env.local if present (gitignored, per-machine overrides).
# Use it to set MARIOLOGY_CORPUS or PORT without editing the Makefile.
-include .env.local
export

.DEFAULT_GOAL := help

.PHONY: help serve stop check clean build-data verify-data clean-data validate-refs

help: ## list available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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
	@echo "--- raw hex outside :root (should be empty) ---"
	@grep -EHn '#[0-9A-Fa-f]{6}' $(ROOT)/*.html 2>/dev/null | grep -v 'favicon\|svg' || echo "  none"
	@echo "--- font count (expected 27) ---"
	@ls $(ROOT)/fonts/*.woff2 2>/dev/null | wc -l | awk '{print "  woff2: " $$1}'

clean: ## remove tmp/ + pyc + .DS_Store
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".DS_Store" -delete 2>/dev/null || true
	@rm -rf tmp/ 2>/dev/null || true
	@echo "cleaned"

build-data: ## regenerate site/data/*.json from the markdown corpus
	@python3 tools/build-mediatrix.py

verify-data: ## verify all site/data/*.json exist with sensible record counts
	@python3 tools/build-mediatrix.py --verify

clean-data: ## remove all generated site/data/*.json
	@rm -f $(ROOT)/data/*.json && echo "  removed $(ROOT)/data/*.json"

validate-refs: ## cross-page validator: orphan saint references vs anthology
	@python3 tools/validate-references.py
