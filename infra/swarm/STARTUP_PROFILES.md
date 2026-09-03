# VibeMind Startup-Profile — isoliertes Testen zusammengehöriger Apps

_Erzeugt 2026-06-23 aus einem fungus-Crawl (4 parallele Subagenten über `infra/swarm/vibemind-stack.yml`
+ Launcher). Zweck: Mit `start debug` nur die **zusammengehörigen** Container eines App-Bündels starten,
statt aller ~36 Services — für isoliertes Testen._

> **Hochlevel-Synthese aller Schichten:** [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) —
> Brain ↔ OpenFang ↔ Electron, Port-Map, Launcher-Phasen, Command-Surface, End-to-End Wiring-Pfade.

Dependency-Graph: [`vibemind-deps.png`](./vibemind-deps.png) · [`.svg`](./vibemind-deps.svg) · Quelle [`.dot`](./vibemind-deps.dot)
(neu rendern: `dot -Tpng infra/swarm/vibemind-deps.dot -o infra/swarm/vibemind-deps.png`)

### Detail-Docs pro Bereich (fungus-Deep-Crawl, je: Overview · Services · Deps up/down · Verwendungen · MCPs/Agents · isolierter Start · Key-Files · Gotchas)
- [`profiles/rowboat.md`](./profiles/rowboat.md) — Rowboat (core/immer): 5-Service-Stack, CDP :9223, Knowledge-Vault, 33 Tools
- [`profiles/bubbles-supabase.md`](./profiles/bubbles-supabase.md) — Bubbles/Ideas = Supabase-REST (public.ideas/canvas_nodes), Bidi-Sync
- [`profiles/brain.md`](./profiles/brain.md) — Brain: Cap-Router, multihop_execute, /api/cortex/route, autotrain, phase-d
- [`profiles/coding-swe.md`](./profiles/coding-swe.md) — Coding/SWE: coding-engine, gitea, OpenClaude, OpenClaw
- [`profiles/mirofish-video.md`](./profiles/mirofish-video.md) — MiroFish (Idea-Scoring-KG, neo4j) + Video/Media-Publishing
- [`profiles/marketing-mailcow.md`](./profiles/marketing-mailcow.md) — Marketing-Ops, n8n, Mailcow (extern), Kanäle/messenger
- [`profiles/openfang-agents.md`](./profiles/openfang-agents.md) — OpenFang :4200 Hub + Agents (brain-gateway, openclaude-coder, …)
- [`profiles/openclaw.md`](./profiles/openclaw.md) — OpenClaw: Personal-AI-Gateway + sichtbare Browser-Steuerung (Docker :18789 headless, Native :18793 visible)
- [`profiles/mcp-native-layer.md`](./profiles/mcp-native-layer.md) — MCP-Server (7) + Native (bridge, la-fungus, automation-ui, ollama)
- [`profiles/flowzen.md`](./profiles/flowzen.md) — Flowzen/Blaue Rose: passive circadiane Intelligenz, rose.recommend
- [`profiles/tribe.md`](./profiles/tribe.md) — TriBE fMRI-Encoder: neuronale Signatur neben Embedding (bio-Personalisierung)
- [`profiles/desktop-automation.md`](./profiles/desktop-automation.md) — Automation_ui :8007, perception (19 Tools), handoff, eyeTerm
- [`profiles/schedule.md`](./profiles/schedule.md) — Scheduling-Schicht: spaces/schedule, brain-scheduler, coding-Scheduler
- [`profiles/voice.md`](./profiles/voice.md) — Voice-Host-Backend (electron_backend, glue über alle Spaces)
- [`profiles/navigator-shuttles.md`](./profiles/navigator-shuttles.md) — _navigator (Space-Resolver-MCP, 14 Spaces) + shuttles (SWE-Design)
- [`profiles/coding-internals.md`](./profiles/coding-internals.md) — req-gen/regen/Architect-Agents + MiroFish→Bubble-Evaluate-Kopplung
- [`profiles/slash-commands.md`](./profiles/slash-commands.md) — VibeMind-eigene /commands: mcp-restart-*, /scan, /memory-review, /vibemind-notify, /graphify
- [`profiles/global-commands.md`](./profiles/global-commands.md) — globale Harness-/Plugin-Commands: /loop, /schedule, /code-review, + 12 Plugins (superpowers, feature-dev, …)

### Vollständigkeit pro Bereich (aus dem Crawl — was läuft vs. Stub/offen)
| Bereich | Status | Stub / unvollständig |
|---|---|---|
| rowboat | ✅ live | rowboat-agents `replicas:0` (Upstream entfernt); RowboatSyncAgent geplant |
| bubbles/supabase | ✅ live | — (Bidi-Sync scharf) |
| brain | ✅ live | brain-learner/inference opt-in (`replicas:0`, phase-d) |
| coding/swe | ✅ live | inkrementeller diff-basierter **Regen NICHT implementiert**; shuttle-Validierungs-Loop unklar |
| mirofish/video | ✅ live | — (Scoring feeds bubble_evaluate via capabilities.yaml) |
| marketing | ⚠️ teils | mailcow extern; marketing = Tooling, kein Service |
| openfang | ✅ live | — (Hub, immer native) |
| **openclaw** | ✅ live (dual) | Docker `:18789` headless + Native `:18793` visible; OpenFang-Agent-TOMLs (`openclaw-visible`, `openclaw-coder`) + `brain_dispatch` MCP-Plugin liegen in `~/.openfang/`/`~/.openclaw/` (außerhalb Repo) |
| mcp/native | ✅ live | — |
| **flowzen** | ⚠️ Kern da | brain_bridge teil-Stub; 3D-Rose-Visual (Three.js) **nicht implementiert**; rowboat-Kontext offen |
| **tribe** | ⚠️ experimentell | „incomplete integrations" (eigener Abschnitt in der Doc) |
| **desktop-automation** | ⚠️ teils | perception (19 Tools) ✅; **eyeTerm gaze/dwell/calibrate NICHT implementiert** |
| **schedule** | ⚠️ funktioniert | Stub: Docker-Image, Healthchecks, TZ-Auto, Cancel-UI, Crash-Recovery |
| **voice** | ⚠️ glue läuft | **OpenFang nicht verdrahtet** (in-process swarm); Brain-Routing optional; native STT/TTS unvollständig |
| **_navigator** | ✅ live | 3-Schicht-Resolver-MCP fertig |
| **shuttles** | ❌ Stub | 0 Tools, kein Agent — Events laufen über BubblesAgent (ideas) |

---

## TL;DR — „Können wir nur relevante Container starten?" → JA, das geht schon heute

Die Selektions-Maschinerie **existiert bereits** im Launcher (verifiziert im Code):

```
-Spaces "coding,n8n"          (CSV; leer = nur core)
  → ConvertTo-SpaceList       (helpers.ps1:598 — trim/lower/split)
  → Get-ComposeProfiles       (helpers.ps1:614 — immer 'core' + je Space 'space-<name>')
  → ConvertTo-FilteredStack   (helpers.ps1:630 — filtert vibemind-stack.yml nach profile:-Tags)
  → docker stack deploy --prune  (Invoke-FilteredStackDeploy, helpers.ps1:749)
```

Aufruf:
```powershell
.\Vibemind.debug.ps1 -Spaces "coding"          # nur coding-Bündel + core
.\scripts\vibemind-start.ps1 -Spaces "video"   # nur video-Bündel + core
```
`vibemind-spaces.ps1` hält das `KNOWN_SPACES`-Mapping (name → `space-<profile>` → Service-Liste) und kann
Spaces live an/aus-toggeln (`Invoke-ToggleAction`/`Invoke-ApplyAction`).

**Was fehlt, damit das sauber greift** (siehe [§ Lücke](#lücke--profil-tags-an-den-services)): die meisten
Services tragen noch **keine `profile:`-Deploy-Labels** — ohne die landet ein Service im immer-deployten
`core`. Heute sind nur `brain-learner`/`brain-inference` opt-in (`replicas: 0`).

---

## Core-Baseline (immer an — „rowboat immer", „bubbles auch immer")

Jedes Profil enthält automatisch diese Basis:

| Gruppe | Services | Warum immer |
|---|---|---|
| **Shared** | `qdrant` | Vektor-DB für rowboat **und** brain |
| **Rowboat** | `rowboat`, `rowboat-mongo`, `rowboat-redis`, `rowboat-jobs-worker` | User: „rowboat immer". rowboat `depends_on`=[mongo, redis, qdrant]; jobs-worker = Pflicht-Queue |
| **Bubbles = Supabase** | `supabase-db`, `-kong`, `-rest`, `-auth`, `-realtime`, `-storage`, `-pg-meta`, `-analytics`, `-studio`, `-inbucket` | User: „bubbles auch immer". Ideas/Bubbles = Supabase-REST-Daten (Phase-11-Supabase-Migration). kong ist das Gateway, alles hängt an `supabase-db` |
| **MiroFish-KG** | `neo4j-mirofish` | Host-gekoppelt an Brain (bolt); im `vibemind-spaces.ps1`-Header als core deklariert |

> Hinweis: `neo4j-mirofish` ist core, der `mirofish`-**Service** aber liegt im Video-Profil (Publishing-Kette).

---

## Die Profile (App-Bündel)

| Profil | Zweck | `-Spaces` | Eigene Services (zusätzlich zur Core-Baseline) | Brain? |
|---|---|---|---|---|
| **coding-stack** | Voller Code-Gen/SWE-Pipeline (deine „coding swe bubble rowboat agentfarm gitea") | `coding` | `coding-postgres`, `coding-redis`, `gitea-postgres`, `coding-gitea`, `coding-vscode`, `coding-egress-proxy`, `coding-api`, `coding-worker`, `coding-openclaude`, `coding-frontend` | **ja** (Routing/Kognition für SWE-Req-Eng) |
| **rowboat-agents** | Schlanke Rowboat-Agent-Workbench (deine „rowboat bubble agentfarm") | `rowboat-agents` | `rowboat-agents`, `rowboat-rag-worker` (heute `replicas:0` → dieses Profil skaliert sie hoch) | nein |
| **video** | Media-Publishing an Rowboat (deine „video rowboat") | `video` | `media` + `mirofish`+`neo4j-mirofish` (Publishing-Kette importiert `mirofish_tools`→`rowboat_knowledge`) | nein |
| **mailcow-marketing** | Marketing-Ops + E-Mail-Relay (deine „mailcow und marketing") | `n8n` | `n8n` (+ Supabase aus core) | nein |
| **core-phase-d** | Opt-in Brain Learning/Inference (die einzigen `replicas:0`-Services) | `core-phase-d` | `brain-learner`, `brain-inference` | — |
| **logging** | Observability-Triade (eigener Space) | `logging` | `loki`, `promtail`, `grafana-vibemind` | nein |

### Wichtige Befunde aus dem Crawl (nicht 1:1 Service-Namen)
- **agentfarm** = **kein** Swarm-Service. Es sind OpenFang-AutoGen-Agenten auf dem **Host** (`:4200`) +
  separates `docker-compose.agentfarm.yml` (agentfarm-server :8080, -ui :3457). Muss separat gestartet werden.
- **swe** = **kein** eigener Service. Spannt coding + autogen → in `coding-stack` gefaltet.
- **mailcow** = **extern** (`~/Documents/mailcow-deployment`, WSL/Host), **nicht** im Swarm. Marketing
  erreicht es als Host-SMTP-Relay über den OpenFang email-assistant-Agent. Das `mailcow-marketing`-Profil
  schaltet nur `n8n` im Swarm; mailcow startet separat.
- **marketing** = Space/Tooling, **kein** Service: nutzt `n8n` (in-stack) + Supabase (core) + mailcow (extern).
- **brain** ist gestaffelt: `brain-core`+`brain-api`+`brain-loops`+`brain-autotrain-drain` (Basis-Kognition)
  vs. `brain-learner`+`brain-inference` (Phase-D, opt-in).

---

## Dependency-Graph (Kurzfassung)

```
ALWAYS:  qdrant ← rowboat(+mongo,redis,jobs-worker)
         supabase-db ← kong ← {auth,rest,realtime,storage,analytics,studio}   (= bubbles)
         neo4j-mirofish (host-coupled to brain)

coding-stack:  coding-api/worker → coding-postgres, coding-redis,
                                    coding-gitea→gitea-postgres,
                                    coding-openclaude→egress-proxy,
                                    coding-frontend→coding-api
               coding-stack → brain-core (Routing/Kognition)
brain:         brain-core → qdrant, brain-api;  brain-inference → brain-learner → qdrant
video:         media → rowboat, media → mirofish → neo4j-mirofish
marketing:     marketing → n8n, → supabase-kong, → mailcow (host, extern)
logging:       promtail → loki,  grafana-vibemind → loki
```
Vollständig + geclustert: siehe das gerenderte PNG/SVG.

---

## Lücke — `profile:`-Tags an den Services

`ConvertTo-FilteredStack` filtert die Stack-YAML **zeilenweise nach `profile:`-Tags** (kein echtes
`docker compose --profile`, weil `docker stack deploy` das `profiles:`-Key ablehnt — verifiziert
2026-05-25). Damit ein Service per `-Spaces` an/abwählbar wird, muss er ein Profil-Label tragen, z.B.:

```yaml
coding-api:
  deploy:
    labels:
      - "vibemind.profile=space-coding"   # ← Filter-Tag (Beispiel; exaktes Schema = ConvertTo-FilteredStack prüfen)
```

**Heutiger Stand:** Nur `brain-learner`/`brain-inference` sind opt-in (`replicas: 0`). Die übrigen Services
haben (noch) keine Profil-Tags → sie sind faktisch alle „core" und werden immer deployed. Um die obigen
Profile scharf zu schalten, müssten die jeweiligen Service-Blöcke ihre `space-<name>`-Tags bekommen.

→ **Nächster Schritt (eigener, größerer Edit — nicht in dieser Analyse enthalten):** Profil-Tags pro
Service-Block setzen, dann `-Spaces "coding"` deployt wirklich nur core+coding. Erst nach Klärung der
offenen Fragen unten.

---

## Offene Fragen (brauchen deine Klärung, bevor die Tags gesetzt werden)

1. **Brain-Bedingung** — dein Satz war abgeschnitten („brain ist dann sinnvoll wenn wir…"). **Default-Annahme:**
   Brain-Basis (core/api/loops/autotrain-drain) **AN** bei `coding-stack` (SWE braucht Routing), **AUS** bei
   reinem `rowboat`/`video`/`marketing`. Stimmt das? Wann genau soll Brain dazu?
2. **agentfarm** — separat (`docker-compose.agentfarm.yml` + OpenFang host). Soll `debug` das mitstarten,
   wenn ein Profil agentfarm braucht (coding-stack, rowboat-agents), oder bleibt es manuell?
3. **mailcow** — extern (WSL/Host). Soll der Launcher es beim `mailcow-marketing`-Profil mit hochfahren oder
   nur prüfen/anstoßen?
4. **rowboat-agents/rowboat-rag-worker** — heute `replicas:0`. In ein Profil (so vorgeschlagen) oder doch in
   die immer-an Core-Baseline („rowboat immer")?
5. **mirofish** — als eigener Space ODER (so vorgeschlagen) Teil des video-Profils? `neo4j-mirofish` bleibt core.

---

## Vollständige Schichten pro Profil (Services + Native-Agents + MCPs)

Ein „isoliertes Profil" ist **kein reines Docker-Set** — es ist ein vertikaler Schnitt über **4 Schichten**.
Antwort auf „alle spaces / mcps / agents dabei?": **Ja — aber auf verschiedenen Ebenen deployt.**

| Schicht | Wie deployt | Beispiele |
|---|---|---|
| **Docker-Swarm** | `-Spaces` / `profile:`-Tags | coding-*, rowboat-*, supabase-*, brain-*, media, n8n, loki |
| **Native-Host** | Launcher Phase 1.5/3/5 (Prozesse) | **OpenFang** :4200, **OpenClaw** :18789, ollama :11434, bridge :5150, la-fungus :8011/8412, automation-ui :8007 |
| **OpenFang-Agents** | logisch IN OpenFang (`~/.openfang`) | brain-gateway, openclaude-coder, openclaw-visible, email-assistant, curator |
| **MCP-Server** | `.mcp.json` (Projekt) + `~/.claude.json` (User) | fungus-search, rowboat-ui, desktop-knowledge, vibemind, perception, messenger, MCP_DOCKER |

### Agents — „openfang openclaude openclaw dabei?"
- **OpenClaude** = der Docker-Service **`coding-openclaude`** (:8091) — steckt **schon im `coding`-Space** ✓.
  coding-api/worker hängen dran (`OPENCLAUDE_URL`). Zusätzlich gibt's den `openclaude-coder` OpenFang-Agent.
- **OpenFang** (:4200) = **Native, läuft in BEIDEN Launcher-Modi immer** (Phase 1.5, „runs in both modes") ✓.
  Der MCP-Aggregator-Hub; Brain (brain-core/api/loops) ruft ihn (`OPENFANG_URL`). Quasi „core-native".
- **OpenClaw** (:18789 Gateway) = **Native, Launcher-Modul `openclaw`** ✓. coding-api braucht ihn
  (`OPENCLAW_URL=host:18789`); auch Brains visible-browser. Nicht im Docker-Stack → native gestartet.

### MCP-Server — „alle mcps dabei?" (7 total)
| MCP | Quelle | gehört zu Profil/Bündel |
|---|---|---|
| **fungus-search** | Projekt `.mcp.json` (HTTP :8412) | global/dev (Code-Suche, codebase-weit) |
| **rowboat-ui** | User (CDP :9223) | **rowboat (core/immer)** — Chat in die Rowboat-Electron |
| **desktop-knowledge** | User (= roarboot/data) | **rowboat + bubbles** (Knowledge-Base read/search/upload) |
| **vibemind** | User | global Control-Plane (launcher/brain/bubbles-Steuerung) |
| **perception** | User | Native/Desktop-Automation (global) |
| **messenger** | User (clawdbot/send_to_channel) | **mailcow-marketing** (Kanäle/Messaging) |
| **MCP_DOCKER** | User | Infra/global (Docker-Verwaltung) |

> MCPs sind eine **eigene Schicht** — sie werden NICHT von `-Spaces` gesteuert, sondern von Claude/OpenFang
> beim Sessionstart verbunden. Ein Profil „braucht" bestimmte MCPs (z.B. rowboat-ui für rowboat), aber sie
> laufen unabhängig vom Docker-Deploy. fungus-search startet jetzt über den Launcher (Phase 3, `:8412`).

### Matrix: was kommt pro Profil hoch (alle Schichten)
| Profil | Docker (zusätzl. zu core) | Native-Agents | MCPs (relevant) |
|---|---|---|---|
| **core (immer)** | qdrant, rowboat(+mongo/redis/jobs), supabase-*, neo4j-mirofish | OpenFang, ollama, bridge, la-fungus, automation-ui | fungus-search, rowboat-ui, desktop-knowledge, vibemind, perception |
| **coding-stack** | coding-* (inkl. **coding-openclaude**), gitea | **+OpenClaw** (:18789), Brain* | (coding nutzt eigene `.claude/skills`) |
| **rowboat-agents** | rowboat-agents, rowboat-rag-worker | — | rowboat-ui, desktop-knowledge |
| **video** | media, mirofish | — | — |
| **mailcow-marketing** | n8n | mailcow (extern WSL) | **messenger** |
| **core-phase-d** | brain-learner, brain-inference | — | — |
| **logging** | loki, promtail, grafana | — | — |

\* Brain (brain-core/api/loops/autotrain-drain): per Default an bei coding-stack — abhängig von deiner offenen Frage #1.

### Lücken (für die spätere Schärfung)
- **rowboat-agents/rowboat-rag-worker** haben **keinen `KNOWN_SPACES`-Eintrag** → heute nicht per `-Spaces`
  ziehbar. Bräuchte einen neuen `space-rowboat-agents`-Eintrag in `vibemind-spaces.ps1:57` + Profil-Tags.
- **video** = Kombination `media`+`mirofish` (zwei bestehende Spaces) → entweder zusammen aufrufen
  (`-Spaces "media,mirofish"`) oder neuen Bündel-Preset anlegen.
- **OpenFang/OpenClaw/mailcow** sind **nicht** über `-Spaces` steuerbar (native/extern) — ein Profil müsste
  zusätzlich die passenden Launcher-Module (`-SkipNative`/Modul-Flags) bzw. mailcow-Start koordinieren.

---

## Verwandte Dateien
- Stack: `infra/swarm/vibemind-stack.yml` (90 Einträge, ~36 echte Services)
- Selektion: `scripts/lib/vibemind-helpers.ps1` (`ConvertTo-SpaceList`:598, `Get-ComposeProfiles`:614,
  `ConvertTo-FilteredStack`:630, `Invoke-FilteredStackDeploy`:749)
- Spaces-Verwaltung: `scripts/vibemind-spaces.ps1` (`KNOWN_SPACES`:57, Toggle/Apply)
- Launcher: `Vibemind.debug.ps1` (Dev), `scripts/vibemind-start.ps1` (Server-Mode); beide `-Spaces`
- Graph: `infra/swarm/vibemind-deps.{dot,svg,png}`
