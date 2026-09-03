#!/usr/bin/env bash
# Push all Vibemind repos once Vibemind-LAB has write access to Flissel/*.
#
# PREREQUISITE (run as the Flissel account, or have Flissel do it):
#   for r in Vibemind_V1 vibemind-os vibemind-shared la_fungus_search \
#            openclaude openclaw DaveFelix-Coding-Engine VibeMind-VoiceDialog \
#            openfang swe_desgine vibevideo-deepfake tribev2; do
#     gh api -X PUT repos/Flissel/$r/collaborators/Vibemind-LAB -f permission=push
#   done
# Then accept invites as Vibemind-LAB:
#   gh api user/repository_invitations --jq '.[].id' \
#     | xargs -I{} gh api -X PATCH user/repository_invitations/{}
#
# Run from repo root:  bash scripts/push_all_repos.sh

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# repo-path (relative)  — order: leaves -> vibemind-os -> root
REPOS=(
  "vibemind-os/shared"
  "vibemind-os/la-fungus-search"
  "vibemind-os/openclaude"
  "vibemind-os/openclaw"
  "vibemind-os/coding-engine"
  "vibemind-os/voice"
  "vibemind-os/openfang"
  "vibemind-os/spaces/shuttles/swe_desgine"
  "vibemind-os/spaces/video/vibevideo_deepfake"
  "vibemind-os/spaces/desktop/Automation_ui/moire_tracker"
  "vibemind-os"
  "."
)

ok=0; fail=0
for p in "${REPOS[@]}"; do
  br="$(git -C "$p" branch --show-current 2>/dev/null)"
  [ -z "$br" ] && { echo "SKIP $p (detached/no branch)"; continue; }
  up="$(git -C "$p" rev-parse --abbrev-ref '@{u}' 2>/dev/null || true)"
  if [ -z "$up" ]; then
    echo ">> $p : push -u origin $br (new remote branch)"
    git -C "$p" push -u origin "$br" && ok=$((ok+1)) || { echo "   FAILED"; fail=$((fail+1)); }
  else
    echo ">> $p : push ($br -> $up)"
    git -C "$p" push && ok=$((ok+1)) || { echo "   FAILED"; fail=$((fail+1)); }
  fi
done

echo
echo "=== pushed OK: $ok | failed: $fail ==="
[ "$fail" -eq 0 ] && echo "All pushed." || echo "Some failed — check access for the FAILED repos above."
