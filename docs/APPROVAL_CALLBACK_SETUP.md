# Approval-Callback aktivieren (Stufe 2 — sicher, von überall)

Der Code ist fertig und getestet. Es fehlt nur die **einmalige Einrichtung eines
zweiten Telegram-Bots** — den muss ein Mensch via @BotFather anlegen (Account-Aktion).
Solange `APPROVAL_TELEGRAM_BOT_TOKEN` nicht gesetzt ist, läuft alles wie bisher
weiter (URL-Buttons + fail-open) — **nichts bricht.** Sobald der Token da ist und
OpenFang neu startet, schaltet das System automatisch um auf:
**callback_data-Buttons (kein Inbound/Firewall, funktioniert mobil) + fail-safe
(unbeantwortet = NICHT schreiben).**

## Was bereits erledigt ist (Code, getestet)

- `clarify_notify.py`: `_telegram_notify(bot_token_env_var=...)` + `handoff_approval_request`
  schickt callback_data-Buttons über den Approval-Bot, **wenn** `APPROVAL_TELEGRAM_BOT_TOKEN`
  gesetzt ist (sonst URL-Button-Fallback).
- `mcp_server_document.py`: `default_on_timeout` = `declined` (fail-safe) **wenn** Approval-Bot
  da, sonst `approved` (fail-open). Timeout 180s mit Bot, 90s ohne.
- `scripts/approval_callback_poll.py`: long-pollt `callback_query`, schreibt
  `record_clarify_answer(id, {"_choice": ...})` in dieselbe clarify.db, beantwortet den Callback.

## Deine 4 Schritte

### 1. Zweiten Bot bei @BotFather anlegen
- Telegram öffnen → Chat mit **@BotFather**
- `/newbot` senden
- Name vergeben (z.B. „VibeMind Approval"), dann Username (muss auf `bot` enden, z.B. `vibemind_approval_bot`)
- BotFather gibt einen **Token** zurück (Form `12345:AA...`)
- **Wichtig:** Schreibe diesem neuen Bot einmal `/start` (vom selben Telegram-Account,
  the chat_id from TELEGRAM_CHAT_ID), sonst kann er dir keine Nachrichten schicken.

### 2. Token in `.env` eintragen
In `C:\Users\User\Desktop\Vibemind_V1\.env` eine Zeile ergänzen:
```
APPROVAL_TELEGRAM_BOT_TOKEN=<der-token-von-botfather>
```

### 3. Poller als Dauerprozess starten
Einmal-Test zuerst (sollte „gestartet … Lausche" zeigen, dann mit Ctrl+C beenden):
```powershell
cd C:\Users\User\Desktop\Vibemind_V1
.\.venv\Scripts\python.exe scripts\approval_callback_poll.py
```
Für Dauerbetrieb: als Scheduled Task registrieren ODER in `scripts/vibemind-start.ps1`
aufnehmen (gleiches Muster wie der SoM-Poller). Sag Claude Bescheid — das kann es übernehmen.

### 4. OpenFang neu starten (damit document-mcp den Token sieht)
```powershell
# (Claude macht das normalerweise — .env in Process-Env laden, dann Restart)
```
Danach: document-mcp liest `APPROVAL_TELEGRAM_BOT_TOKEN` → schaltet auf callback_data +
fail-safe um.

## Verifikation (nach Setup)
1. Desktop-Schreibtask an skill-coordinator (Ziel außerhalb `skills/`).
2. Approval-Anfrage kommt vom **neuen** Bot mit ✅/❌ Inline-Buttons.
3. Auf dem Handy (egal welches Netz) Approve tippen → Toast „✅ Freigegeben".
4. Datei wird geschrieben. Bei Decline / keiner Antwort (180s) → **nichts** geschrieben.

## Rückbau / Übergang
- `APPROVAL_TELEGRAM_BOT_TOKEN` aus `.env` entfernen + OpenFang-Restart → zurück zu
  URL-Buttons + fail-open (LAN-Setup). Kein Code-Rollback nötig.
- Die LAN-Firewall-Regel (TCP 8007) wird mit dem Callback-Pfad überflüssig und kann
  entfernt werden: `Remove-NetFirewallRule -DisplayName 'VibeMind Approval 8007'` (Admin).
