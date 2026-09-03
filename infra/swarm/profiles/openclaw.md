# OpenClaw (Personal-AI-Gateway · Browser-Automation · sichtbare Chrome-Steuerung)

_Erzeugt 2026-06-24 manuell (Crawl-Lücke aus dem Original-Set vom 2026-06-23 nachgezogen).
Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

OpenClaw ist VibeMinds **personal-AI-Gateway** und der Pfad zur **sichtbaren Browser-Steuerung**
auf dem Host-PC. Es ist eine native Node.js/TypeScript-Anwendung (Upstream:
[openclaw/openclaw](https://github.com/openclaw/openclaw), Submodule unter `vibemind-os/openclaw/`),
die als Submodule eingebunden ist und parallel zu OpenFang läuft.

In VibeMind existiert OpenClaw in **zwei getrennten Ausprägungen** mit unterschiedlichen Aufgaben:

| Instanz | Gateway-Port | Verwendung | Browser-Modus |
|---|---|---|---|
| **vibemind-openclaw** (Docker, im Repo) | `:18789` | coding-engine browser-Tasks (HEADLESS Chromium im Container) | unsichtbar im Container |
| **native openclaw** (npm-global, ausserhalb Repo) | `:18793` | Brain → `browser_automation` capability → VISIBLE Chrome auf dem Host | sichtbar (Benutzer sieht zu) |

Beide werden vom Launcher (`Vibemind.debug.ps1` / `vibemind-start.ps1`) **Phase 1.5** als native
Prozesse hochgefahren — OpenClaw läuft **nicht im Swarm-Stack**, weil es Host-Networking + Browser
Control Service braucht (loopback :18795).

Daneben gibt es OpenClaw-Self-Heal-Scripts (QR-PNG-Patch, WhatsApp-Login persistent halten,
Update nur bei Login-Fehler) und einen `openclaw_brain_dispatcher`-Pfad, mit dem openclaw-main
komplexe Tasks asynchron an Brain → OpenFang-Spezialagents delegieren kann.

## Services / Components

### Docker Compose (im Repo: `vibemind-os/openclaw/docker-compose.yml`)

- **openclaw-gateway** (`openclaw:local` image)
  - Image: `${OPENCLAW_IMAGE:-openclaw:local}` (lokal gebaut)
  - Ports: `${OPENCLAW_GATEWAY_PORT:-18789}:18789` (Gateway HTTP/WS), `${OPENCLAW_BRIDGE_PORT:-18790}:18790`
    (Bridge — Internal-Plugin-Protokoll)
  - Volumes: `${OPENCLAW_CONFIG_DIR}:/home/node/.openclaw`,
    `${OPENCLAW_WORKSPACE_DIR}:/home/node/.openclaw/workspace`
  - Env: `OPENCLAW_GATEWAY_TOKEN`, `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS`,
    `CLAUDE_AI_SESSION_KEY`, `CLAUDE_WEB_SESSION_KEY`, `CLAUDE_WEB_COOKIE`
  - extra_hosts: `host.docker.internal:host-gateway` (reicht zum Host-Brain/OpenFang)
  - Command: `node dist/index.js gateway --bind lan --port 18789`
  - Sandbox-Isolation per default AUS (docker.sock-Mount + Docker-CLI optional via
    `--build-arg OPENCLAW_INSTALL_DOCKER_CLI=1` + `OPENCLAW_SANDBOX=1`)
- **Dockerfile.sandbox / Dockerfile.sandbox-browser / Dockerfile.sandbox-common / Dockerfile.hotel** —
  optionale Sandbox-Layer (für Multi-Tenant- bzw. Hotel-Mode)

### Native Process (Phase 1.5 — kein Docker, kein Repo-File)

- **openclaw Gateway** (npm-global Installation auf Windows)
  - Binary: globales `openclaw` (npm-global, `C:\Users\User\.openclaw\openclaw.json` als Config)
  - Port: **:18793** (kein Konflikt mit Docker-Instance auf :18789)
  - Lifecycle: persistiert via Scheduled Task „OpenClaw Gateway" — kein Launcher-Spawn,
    der Launcher prüft nur Liveness (`/healthz`)
  - Browser Control Service: zusätzlicher loopback-Port :18795 — **das** ist der eigentliche
    Service, der `--local` Mode des Containers fehlt; ohne ihn keine sichtbare Browser-Steuerung
  - Config-Anforderungen (load-bearing, gesetzt einmalig):
    - `gateway.port = 18793` (nicht 18789 — agent-internal browser-tool resolve nimmt den
      Config-Wert, nicht den Flag-Override)
    - `gateway.remote.{url,token}` aligned mit `gateway.auth.token`
    - `browser.defaultProfile = "openclaw"` (sonst Profil `chrome`, das eine
      Chrome-Extension verlangt → fehlt → fail)
    - `agents.defaults.model.primary = openai/gpt-4o-mini` + `env.OPENAI_API_KEY`
      (Anthropic-OAuth-Profil ist out-of-usage seit 2026-05)

### Wrapper-Scripts (`scripts/`)

- **`openfang_openclaw_visible_wrapper.py` + `.cmd`** — OpenFang→native openclaw Brücke.
  Liest Prompt von stdin, setzt `OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18793` +
  `OPENCLAW_GATEWAY_TOKEN` aus `~/.openclaw/openclaw.json`, ruft
  `openclaw agent --agent main --message <prompt> --json --timeout 220`, brace-scanned das
  `{"payloads":[…]}` JSON-Object heraus und gibt nur `payloads[0].text` aus (was OpenFangs
  `claude_code`-Driver erwartet). Timeout 220s (Headroom unter OpenFang 300s heartbeat).
- **`openclaw_apply_patches.ps1`** — QR-Code-Patch (PNG statt ASCII), damit der
  WhatsApp-Login-QR sichtbar im Terminal angezeigt wird statt nur als unscanbarer ASCII-Müll
- **`openclaw_update.ps1`** — Update-Helper; mit `-Login` Re-Pairing-Modus für
  WhatsApp/Telegram-Login (Captcha löst der User selbst). Update wird **nur bei Login-Fehler**
  gemacht (sonst bleibt die Session erhalten)

### Skill-Library (`vibemind-os/skills/openclaw-official/` + `openclaw-management/`)

15+ Skills, die der openclaw-main-Agent (im Gateway) selbst hosten kann:
- `openclaw-debugging`, `openclaw-docs`, `openclaw-pr-maintainer`, `openclaw-qa-testing`,
  `openclaw-release-maintainer`, `openclaw-secret-scanning-maintainer`, `openclaw-testing`,
  `openclaw-test-heap-leaks`, `openclaw-test-performance`,
  `openclaw-ghsa-maintainer`, `openclaw-parallels-smoke`, `openclaw-pre-release-plugin-testing`,
  `openclaw-small-bugfix-sweep` (`skills/openclaw-official/`)
- `clawsweeper`, `crabbox`, `discord-clawd`, `gitcrawl` (`skills/`)
- `mcp-bridge/openclaw-management` — Management-Skill für MCP-Bridges
- `relay-skill/openclaw-bridge` — Relay-Skill zwischen openclaw + restlichem VibeMind

### Apps (`vibemind-os/openclaw/apps/`)

Native Client-Apps (für die mobilen + Desktop-Surface-Channels):
- `android/`, `ios/`, `macos/`, `shared/` (kein Windows-App — Windows wird über die globale
  npm-Installation + WSL2 bedient, per [`apps/openclaw/README.md`](../../vibemind-os/openclaw/README.md))

## Dependencies

### UPSTREAM (was OpenClaw braucht)

**Beide Instanzen:**
- **Node.js 18+** (für Docker-Image: in der Stage gebaut; nativ: globale Installation)
- **Chromium** (Docker: `/usr/local/bin/chromium` per Config; nativ: System-Chrome mit Profil
  `openclaw`)
- **OPENAI_API_KEY** (gpt-4o-mini als default, Anthropic-OAuth out-of-usage)
- **API-Keys optional:** `CLAUDE_AI_SESSION_KEY`, `CLAUDE_WEB_COOKIE` (für claude.ai-Sessions
  über openclaw — letzteres beendet)

**Docker-Instance (`:18789`) zusätzlich:**
- **OPENCLAW_CONFIG_DIR** + **OPENCLAW_WORKSPACE_DIR** host-bind-mounts (sonst keine Persistenz)
- **OPENCLAW_GATEWAY_TOKEN** env (sonst kein Auth)
- **Optional:** `/var/run/docker.sock`-Mount + `DOCKER_GID` env wenn sandbox isolation an

**Native-Instance (`:18793`) zusätzlich:**
- **Globales `openclaw` Binary** via npm/bun (Pairing per `openclaw_update.ps1 -Login`)
- **`~/.openclaw/openclaw.json`** mit gateway.port=18793 + browser.defaultProfile=openclaw
- **Scheduled Task „OpenClaw Gateway"** (für Auto-Start nach Reboot/Crash)
- **Chrome-Profil `openclaw`** angelegt + sichtbar

### DOWNSTREAM (was OpenClaw aufruft)

- **`coding-api` (`:8000`)** — env `OPENCLAW_URL=http://host.docker.internal:18789` für
  browser-Tasks der Coding-Engine (HEADLESS Container-Pfad)
- **Brain capability `browser_automation`** → `execution_target: "openfang:openclaw-visible"` →
  OpenFang dispatched an `openclaw-visible` Agent → `openfang_openclaw_visible_wrapper.py` →
  Native Gateway :18793 → sichtbares Chrome (siehe [`brain.md`](./brain.md) capability registry +
  Auszug aus `vibemind-os/brain/the_brain/data/capabilities.yaml:1131-1185`)
- **Telegram-Bot / Discord-Bot** — können über die brain-gateway-Route ebenfalls
  `browser_automation` triggern → derselbe openclaw-visible-Pfad
- **`scripts/status_probe_server.py`** — Health-Probe (sieht beide Ports)

## Possible usages

### Sichtbare Browser-Automation (via Brain → OpenFang → native :18793)

Voice-Trigger (regex aus `capabilities.yaml:browser_automation`):
- DE: "öffne gmail" / "gehe auf github" / "schau mal in mein linkedin" /
  "screenshot von github.com" / "navigiere zur webseite X" / "fülle das formular auf Y"
- EN: "navigate to X" / "open Y" / "scrape product prices from Z" /
  "login to X" / "extract data from this page"

Was passiert:
1. Brain matcht regex → `execution_target: openfang:openclaw-visible`
2. OpenFang spawnt agent `openclaw-visible` (Agent-TOML wohnt in `~/.openfang/agents/` —
   **NICHT im Repo**, Phase 1-Limitation)
3. Agent ruft `openfang_openclaw_visible_wrapper.cmd` (claude_code driver per stdin/stdout)
4. Wrapper liest Token aus `~/.openclaw/openclaw.json` → ruft `openclaw agent --agent main
   --message <prompt> --json --timeout 220`
5. `openclaw agent` (Gateway-Mode, NICHT `--local`) bekommt das `browser`-Tool und steuert das
   sichtbare Chrome-Window
6. JSON-Object `{"payloads":[{"text":...}]}` zurück → Wrapper extrahiert
   `payloads[0].text` → OpenFang → Brain → Voice/UI

### Container-Browser-Tasks (via coding-api → :18789)

`coding-api` ruft direkt `OPENCLAW_URL=http://host.docker.internal:18789` für Code-Gen-Tasks,
die einen Browser brauchen (Doc-Lookup, Screenshot, etc.) — HEADLESS, kein User sieht zu.
Siehe [`coding-swe.md`](./coding-swe.md) für die Coupling-Details.

### Personal-AI Channels (Upstream-Feature, in VibeMind NICHT primär)

OpenClaw selbst kann auf WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Matrix etc.
antworten — in VibeMind wird der **Brain-Gateway-Pfad** über OpenFang+Bridge bevorzugt
(siehe [`openfang-agents.md`](./openfang-agents.md)), nicht openclaws eigene Channel-Engine.

### Self-Heal (User initiiert)

- **`openclaw_apply_patches.ps1`** — patcht QR-Display so dass WhatsApp-Login QR als PNG
  rauskommt (sonst nicht scanbar)
- **`openclaw_update.ps1`** — `-Login` triggert Re-Pairing; ohne Flag wird nur bei
  Login-Fehler upgegraded (Session bleibt)
- **`vibemind-start.ps1`** orchestriert beides als Self-Heal-Sequenz wenn der Liveness-Probe
  von `:18789/healthz` oder `:18793/healthz` länger als 20s nicht reagiert

## MCPs & OpenFang agents involved

### OpenFang Agents (in `~/.openfang/agents/`, **nicht im Repo**)

- **`openclaw-visible`** — primary für `browser_automation` capability;
  base_url = `scripts/openfang_openclaw_visible_wrapper.cmd`; turn-payload via stdin,
  Antwort über stdout; Timeout 220s
- **`openclaw-coder`** — historischer HEADLESS-Container-Pfad (via
  `docker exec openclaw-gateway openclaw agent --local`); überholt für sichtbare Tasks,
  steht aber noch zur Verfügung für Headless-Use-Cases (siehe Memory
  `project_openclaw_coder_openfang.md`)
- **`openclaw-main`** — innerhalb des openclaw Gateways selbst; kann Brain-Dispatcher
  `brain_dispatch` MCP nutzen, um komplexe Tasks an Brain → OpenFang-Spezialagent zu
  delegieren (Memory `project_openclaw_brain_dispatcher.md`)

> **Repo-Gap:** Diese drei Agents leben in `~/.openfang/agents/` (User-Home), nicht im Repo —
> ein agent-creator-Run müsste sie nachziehen. Beim Wechsel auf neuen Rechner: manuell
> kopieren oder via openfang-export/import.

### MCP Servers (von openclaw-main konsumiert)

- **`brain_dispatch`** (custom MCP, in `~/.openclaw/plugins/`) — async detached Worker,
  überlebt MCP-Teardown; ruft Brain `/api/multihop/execute`. Bekannte Bug-Kette aus dem Bau:
  ENOENT(abs python), -32001(detached), OLLAMA_BASE_URL, Groq-429+OpenRouter-402 →
  `PLANNER_MODEL=gpt-4o-mini`, OpenFang-401 (.env-Restart). Siehe Memory
  `project_openclaw_brain_dispatcher.md` für Details.
- **`acpx`** — Agent Control Protocol Extension (im openclaw-Config aktiviert,
  defaultAgent=claude, allowedAgents=claude,codex,kilo)
- **`openfang`** — über acpx-mcpServers an openclaw-main exponiert (loopback zu OpenFang)

## Isolated startup

### Minimum für sichtbare Browser-Automation (Native :18793)

```powershell
# 1. Globales openclaw installieren (einmalig)
npm install -g openclaw   # oder: bun add -g openclaw

# 2. Config vorbereiten (~/.openclaw/openclaw.json)
#    Wichtig: gateway.port=18793, browser.defaultProfile="openclaw"
#    (siehe Wrapper-Doc oben für volle Liste)

# 3. Pairing (einmalig, mit sichtbarem Chrome)
& "$env:USERPROFILE\.openclaw\bin\openclaw.cmd" gateway --port 18793

# 4. Scheduled Task „OpenClaw Gateway" anlegen (für Persistenz)
#    schtasks /Create /TN "OpenClaw Gateway" /TR "openclaw gateway --port 18793" /SC ONLOGON

# 5. OPENAI_API_KEY setzen (gpt-4o-mini)
$env:OPENAI_API_KEY = "sk-..."

# 6. Smoke-Test
curl http://127.0.0.1:18793/healthz
```

Damit der `openclaw-visible`-Pfad nutzbar ist, müssen zusätzlich laufen:
- **OpenFang** (`:4200`) — Phase 1.5 vom Launcher
- **Brain** (Stack: `brain-core:5000`) — für die capability-Routing-Entscheidung
- **OpenFang-Agent `openclaw-visible`** registriert in `~/.openfang/agents/`

### Minimum für coding-engine browser-tasks (Docker :18789)

```bash
cd vibemind-os/openclaw
export OPENCLAW_CONFIG_DIR=$HOME/.openclaw
export OPENCLAW_WORKSPACE_DIR=$HOME/.openclaw/workspace
export OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
export OPENCLAW_IMAGE=openclaw:local   # oder: docker build -t openclaw:local .

docker compose up -d openclaw-gateway

curl http://127.0.0.1:18789/healthz
```

Dann kann `coding-api` darüber browsen (via env
`OPENCLAW_URL=http://host.docker.internal:18789`).

### Lücken / nicht-isolierbar

- **Sichtbare Browser-Automation braucht zwingend Native + OpenFang + Brain** — ohne diese
  Kette gibt es keinen E2E-Pfad. Headless-Container-Pfad geht ohne Brain (direkt von
  coding-api), bietet aber keine sichtbare Steuerung.
- **`~/.openfang/agents/openclaw-visible/agent.toml` fehlt im Repo** — beim Wechsel auf
  einen neuen Rechner muss diese Datei manuell erstellt oder vom alten System kopiert
  werden. Vorlage: `base_url = scripts/openfang_openclaw_visible_wrapper.cmd`,
  `driver = claude_code`, `timeout = 220`.
- **`brain_dispatch` MCP Plugin in `~/.openclaw/plugins/`** ebenfalls nicht im Repo.
- **Pairing-Status verloren** — wenn der `openclaw`-Account ausgeloggt wird oder die
  Cookies expiren, hilft nur `openclaw_update.ps1 -Login` + Captcha lösen.

## Key files

- **`vibemind-os/openclaw/`** — Submodule (Upstream-Repo), enthält:
  - `README.md`, `AGENTS.md`, `CLAUDE.md`, `VISION.md` — Upstream-Doku
  - `docker-compose.yml` — Compose-File für die Docker-Instance :18789
  - `Dockerfile`, `Dockerfile.sandbox*`, `Dockerfile.hotel` — Build-Stages
  - `apps/{android,ios,macos,shared}` — native Client-Apps
  - `config/openclaw.json` — Default-Config-Template (gateway.port=18789 hier!)
- **`scripts/openfang_openclaw_visible_wrapper.py` (+`.cmd`)** — OpenFang↔native Brücke,
  load-bearing für `browser_automation` capability
- **`scripts/openclaw_update.ps1`** + **`scripts/openclaw_apply_patches.ps1`** — Self-Heal
- **`Vibemind.debug.ps1:1453`** — Liveness-Probe-Eintrag
  (`@{Name="OpenClaw"; Module="openclaw"; Port=18789; Url=…/healthz}`)
- **`Vibemind.debug.ps1:584-595`** — Stale-Container-Cleanup
  (alter `coding-engine-openclaw` Container wird gekillt — wurde 2026-05 abgelöst)
- **`vibemind-os/brain/the_brain/data/capabilities.yaml:1131-1185`** — `browser_automation`
  capability mit regex + `execution_target: openfang:openclaw-visible`
- **`vibemind.config.json:27-30`** — Module-Registrierung (`enabled: true`, `path:
  vibemind-os/openclaw`); **`vibemind.config.json:72`** — Port-Definition
  (`openclaw_gateway: 18789`)
- **`~/.openclaw/openclaw.json`** (außerhalb Repo) — load-bearing Native-Config
- **`~/.openfang/agents/openclaw-visible/agent.toml`** (außerhalb Repo) — load-bearing
  Agent-Definition

## Gotchas

1. **Zwei Instanzen, zwei Ports — nicht verwechseln.** Docker :18789 ist HEADLESS,
   Native :18793 ist sichtbar. Der Wrapper hardcoded :18793 — ein
   `OPENCLAW_GW_URL`-Override geht aber.

2. **`gateway.port` MUSS in der Config stehen, Flag reicht nicht.** Das agent-interne
   browser-tool resolved seinen Target-Port aus `config.gateway.port`, nicht aus dem
   CLI-Flag. Setzt man nur `--port 18793` aber `config.gateway.port = 18789` hat,
   landet die Browser-Anweisung im Container-Gateway und schlägt mit `token mismatch`
   fehl.

3. **`browser.defaultProfile = "openclaw"` ist load-bearing.** Default `"chrome"`
   verlangt eine Chrome-Extension installiert + attached → ohne sie failed der
   `browser`-tool-Call silently.

4. **Anthropic-OAuth out-of-usage.** Native-Config muss
   `agents.defaults.model.primary = openai/gpt-4o-mini` haben + `env.OPENAI_API_KEY`
   gesetzt. Sonst fragt openclaw nach Anthropic-Login, der nie kommt.

5. **`--local` Mode des Containers kann KEINE sichtbare Browser-Steuerung.** Der
   container `openclaw agent --local`-Pfad nutzt den eingebetteten Headless-Chromium,
   nicht die Gateway-Brücke zu einem externen Browser. Nur der Gateway-Mode (ohne
   `--local`, mit `OPENCLAW_GATEWAY_URL`) bekommt das `browser`-Tool.

6. **JSON-Antwort hat Diagnose-Lines davor + danach.** `openclaw agent --json` druckt
   erst Logs, dann das `{"payloads":[…]}` Object, dann mehr Logs. Der Wrapper
   brace-scanned und extrahiert nur das Object, weil OpenFangs claude_code-Driver
   den Endtext erwartet. Wer ohne Wrapper direkt parsed kriegt Müll.

7. **`coding-engine-openclaw`-Container wurde 2026-05 abgelöst.** Der Launcher killt
   ihn proaktiv (`Vibemind.debug.ps1:584-595`) wenn er noch rumliegt. Jetzt bedient
   `vibemind-openclaw` (`:18789`) sowohl Voice als auch Coding-Engine.

8. **Captcha löst der User selbst.** WhatsApp-Login + Telegram-Pairing kommen
   gelegentlich mit Captcha — keine Automatisierung dafür (zu fragil), das macht der
   User.

9. **`brain_dispatch` MCP hatte eine 7-Bug-Kette beim Bau** — die Lessons sind in
   Memory `project_openclaw_brain_dispatcher.md` festgehalten. Wer das Plugin neu
   installiert: ENOENT(abs python), -32001(detached worker), OLLAMA_BASE_URL,
   Groq-429+OpenRouter-402, OpenFang-401 — alles bekannte Stolpersteine.

10. **Scheduled Task „OpenClaw Gateway" startet die NATIVE Instance, nicht die
    Docker-Instance.** Bei Reboot kommt :18793 von alleine zurück; :18789 muss
    `docker compose up` selbst — der Launcher Phase 1.5 ist dafür zuständig.

11. **Heartbeat-Timeout vs. Wrapper-Timeout vs. claude_code-Driver-Ceiling.**
    OpenFang-Heartbeat ist 360s (siehe [`openfang-agents.md`](./openfang-agents.md)),
    Wrapper-Default 220s, claude_code-Driver hat 300s Ceiling. Wrapper-Timeout
    bleibt absichtlich unter Driver-Ceiling, sonst kommt OpenFang nicht mehr an die
    Antwort heran.

12. **Self-Heal triggert nur bei Login-Fehler, NICHT bei jedem Liveness-Fail.**
    `openclaw_update.ps1` ohne `-Login` macht Update nur wenn der Test einen
    Login-Error-Status zurückgibt — sonst wird die laufende Session geschont, damit
    WhatsApp etc. nicht abgemeldet werden.

---

**Zusammenfassung:** OpenClaw ist VibeMinds einziger Pfad zu sichtbarer Browser-Steuerung,
geliefert durch zwei nebeneinander laufende Instanzen (Docker HEADLESS :18789 für
coding-engine, Native VISIBLE :18793 für Brain-Routing). Die kritische Brücke ist
`scripts/openfang_openclaw_visible_wrapper.py`, der Brain.capabilities `browser_automation` →
OpenFang `openclaw-visible` agent → Native Gateway koppelt. Lücken im Repo: die OpenFang-Agent-
Definitionen + das `brain_dispatch` MCP-Plugin leben außerhalb des Repos (`~/.openfang/`,
`~/.openclaw/`) — beim Rechnerwechsel manuell mitziehen.
