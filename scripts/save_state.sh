#!/usr/bin/env bash
# Pushes SQLite state to the "state" branch and generated outputs to main. Retries on conflicts.
set -u
git config user.name agents; git config user.email agents@users.noreply.github.com
if [ -d state ]; then
  cd state
  [ -d .git ] || { git init -q; git checkout -q -b state; git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"; }
  git config user.name agents; git config user.email agents@users.noreply.github.com
  git add -A; git diff --cached --quiet || git commit -qm "state $(date -u +%FT%TZ)"
  for i in 1 2 3; do git push -q origin HEAD:state && break; git pull -q --rebase origin state || git rebase --abort 2>/dev/null; sleep 3; done
  cd ..
fi
for p in dashboard data previews packages docs; do [ -e "$p" ] && git add -A -- "$p"; done
[ -f PAUSE ] && git add PAUSE
git diff --cached --quiet || { git commit -qm "agents output $(date -u +%F)"; for i in 1 2 3; do git push -q && break; git pull -q --rebase; sleep 3; done; }
gh api -X POST "repos/${GITHUB_REPOSITORY}/pages/builds" >/dev/null 2>&1 || true
