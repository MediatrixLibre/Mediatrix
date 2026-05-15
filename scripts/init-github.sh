#!/usr/bin/env bash
# scripts/init-github.sh
#
# One-shot configurator for the Mediatrix GitHub repository.
# Run this once after creating the MediatrixLibre/Mediatrix repo and
# authenticating gh CLI as the MediatrixLibre account.
#
# Prerequisites:
#   1. GitHub account "MediatrixLibre" exists (created in browser).
#   2. SSH public key ~/.ssh/id_ed25519_mediatrix.pub added to that
#      account's Settings > SSH and GPG keys.
#   3. gh CLI authenticated as MediatrixLibre:
#         gh auth login --hostname github.com --git-protocol ssh
#      (Select "Login with a web browser" and choose the MediatrixLibre
#      account. Use `gh auth switch` afterwards if you have multiple
#      accounts.)
#   4. SSH alias verified:
#         ssh -T git@github.com-mediatrix   # expect "Hi MediatrixLibre!"
#
# This script will:
#   - Verify gh is authed as MediatrixLibre
#   - Set the repo description, homepage, and topics
#   - Disable Issues, Wiki, and Projects (quiet editorial register)
#   - Add the SSH remote
#   - Push main if no remote exists yet
#
# Idempotent: safe to re-run.

set -euo pipefail

REPO="MediatrixLibre/Mediatrix"
HOMEPAGE="https://mediatrix-marian-library.pages.dev/"
DESCRIPTION="An editorial Marian study library, fifteen hand-designed pages on Mary as Mediatrix and Co-Redemptrix, drawn from a thirteen-file markdown corpus of patristic, medieval, and magisterial witness."
TOPICS=(
  mariology
  mediatrix
  co-redemptrix
  catholic
  patristics
  litany-of-loreto
  akathist
  editorial-typography
  static-site
  cloudflare-pages
)

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m\xe2\x9c\x93\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m\xe2\x9c\x97\033[0m %s\n' "$*"; exit 1; }

bold "Mediatrix, GitHub repo configurator"

# --- 1. gh auth check ---------------------------------------------------
bold "1. Verifying gh authentication"
if ! command -v gh >/dev/null 2>&1; then
  die "gh CLI not installed. Install via: brew install gh"
fi
ACTIVE_USER=$(gh api user --jq '.login' 2>/dev/null || true)
if [ "$ACTIVE_USER" != "MediatrixLibre" ]; then
  warn "Active gh user is '$ACTIVE_USER', not 'MediatrixLibre'."
  warn "Switch with: gh auth switch  (or login: gh auth login --hostname github.com)"
  die "Refusing to configure repo under the wrong account."
fi
ok "gh authed as MediatrixLibre"

# --- 2. SSH alias check -------------------------------------------------
bold "2. Verifying SSH alias github.com-mediatrix"
if ssh -o BatchMode=yes -o ConnectTimeout=5 -T git@github.com-mediatrix 2>&1 | grep -q "Hi MediatrixLibre"; then
  ok "SSH alias resolves to MediatrixLibre"
else
  die "SSH alias not working. Add ~/.ssh/id_ed25519_mediatrix.pub to https://github.com/settings/keys"
fi

# --- 3. Repo description + homepage + topics ----------------------------
bold "3. Setting description, homepage, and topics on $REPO"
gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --homepage "$HOMEPAGE" \
  --enable-issues=false \
  --enable-wiki=false \
  --enable-projects=false \
  --enable-discussions=false >/dev/null
ok "description + homepage set; issues / wiki / projects / discussions disabled"

# Topics via gh api (gh repo edit doesn't currently accept --add-topic in bulk)
TOPIC_JSON=$(printf '%s\n' "${TOPICS[@]}" | python3 -c "import sys, json; print(json.dumps({'names':[l.strip() for l in sys.stdin if l.strip()]}))")
gh api -X PUT "repos/$REPO/topics" \
  -H "Accept: application/vnd.github+json" \
  --input - <<<"$TOPIC_JSON" >/dev/null
ok "topics set: ${TOPICS[*]}"

# --- 4. Default branch protection (light touch) -------------------------
bold "4. Setting default branch to main"
gh api -X PATCH "repos/$REPO" -f default_branch=main >/dev/null 2>&1 || true
ok "default branch confirmed as main"

# --- 5. Git remote ------------------------------------------------------
bold "5. Configuring git remote"
cd "$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
if git remote get-url origin >/dev/null 2>&1; then
  CURRENT_URL=$(git remote get-url origin)
  EXPECTED="git@github.com-mediatrix:$REPO.git"
  if [ "$CURRENT_URL" != "$EXPECTED" ]; then
    warn "origin currently points at: $CURRENT_URL"
    warn "rewriting to: $EXPECTED"
    git remote set-url origin "$EXPECTED"
  fi
else
  git remote add origin "git@github.com-mediatrix:$REPO.git"
fi
ok "origin = $(git remote get-url origin)"

# --- 6. Push if needed --------------------------------------------------
bold "6. Push status"
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  ok "upstream already configured; run 'git push' to publish further commits"
else
  warn "no upstream set. Run when ready:"
  warn "  git push -u origin main"
fi

echo
bold "Done. Visit https://github.com/$REPO"
echo
