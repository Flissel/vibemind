---
name: "source-command-vibemind-notify"
description: "Send a status note to VibeMind chat at end of a Codex run. Summarizes what was accomplished and sends it as a notification via the Game Console to the VibeMind Electron app (CDP injection, no AI response needed)."
---

# source-command-vibemind-notify

Use this skill when the user asks to run the migrated source command `vibemind-notify`.

## Command Template

Generate a concise status summary of what was accomplished in this session, then send it to VibeMind as a notification.

Steps:
1. Summarize the key changes/results from this session in 2-4 bullet points (no more)
2. Format the summary as plain text (no emojis — Windows console encoding): "Session done: <bullet 1>. <bullet 2>. ..."
3. Run the notifier with the Bash tool:

```bash
cd "c:\Users\User\Desktop\Vibemind_V1\Automation_ui\backend\moire_agents" && python -X utf8 skills/vibemind_notify.py --notify-only "<your summary here>"
```

Replace `<your summary here>` with the plain-text summary (single line, no newlines, no special chars).

If VibeMind is not running (CDP fails), print the summary to the terminal with a note that VibeMind was unavailable.

Keep summaries factual and brief: what files changed, what was fixed, what was built.
