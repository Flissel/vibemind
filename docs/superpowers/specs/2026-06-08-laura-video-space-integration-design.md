# Laura ↔ VibeMind — Video-Space-Integration (Design / Spec v2)

**Datum:** 2026-06-08
**Status:** Design — wartet auf Spec-Review, dann writing-plans
**Branch:** feat/som-resume-loop (Arbeitskontext)

> Dieses Dokument hat **zwei Adressaten**:
> 1. **Dich** (VibeMind-Owner) — als Integrations-Spec.
> 2. **Den Laura-Coder** — Teil **§2** beantwortet seine 10 Integrationsfragen verbindlich, damit er die restlichen Stufen bauen lassen kann.
>
> Die Antworten beruhen auf **verifizierter** Code-Recherche in *beiden* Repos (Vibemind_V1 + `C:\Users\User\Desktop\Laura`), nicht auf Annahmen. Wo die ursprünglichen Fragen eine falsche Architektur unterstellten, steht die Korrektur dabei.

---

## §0 — TL;DR (für Eilige)

- **Laura ist echt** und professionell: lokales, frame-genaues KI-Film-Editing (Electron + React/Vite Frontend, **FastAPI :8765**, FFmpeg, OpenTimelineIO als Wahrheitsquelle, SQLite). Remote `github.com/Vibemind-LAB/Lauras_star.git`.
- **Integrationsentscheidungen (vom Owner bestätigt):**
  1. UI: Lauras Renderer als **BrowserView-Space** in VibeMinds bestehender Electron-Shell (wie rowboat/mirofish) — **nicht** Tauri, **nicht** zweite Electron-Runtime.
  2. Backend: als **native venv-Phase** in `scripts/vibemind-start.ps1` (Phase 3, Muster `Start-VenvPython`).
  3. Repo: **Git-Submodul** unter `spaces/video/laura`.
  4. Steuerung: über **MCP-Tools**, exponiert via **zentralem OpenFang-MCP-Hub** (:4200/mcp). **Kein** neuer Event-Handler-Agent, **keine** Intent-Classifier-Änderung in dieser Iteration.
- **Sequenz:** Lauras Eigenarbeit (UI+Backend, „kommt noch was dazu") ist **Phase 0** und geht **vor** allem hier. Erst danach wird der Submodul-Commit gepinnt.
- **Korrigierte Falschannahmen der alten Fragen:** „:8765 = Lauras Backend" ✅ (stimmt in Laura) — aber in VibeMind ist :8765 die Coding-Engine-WebSocket (kein Konflikt, anderer Server). „VideoAgent muss erst starten" → der existierende `VideoBackendAgent` ist für Laura **irrelevant** (Laura hat eigene REST-API). „Submodul `laura` + Duplikat `voice/python/spaces/video`" → der „Duplikat"-Pfad ist nur ein **Import-Alias**.

---

## §1 — Aktuelle Architektur (verifizierter Ist-Zustand)

### 1.1 VibeMind-Seite

**Start & Lebenszyklus**
- **User-Launcher:** `Vibemind.debug.ps1` (Repo-Root, voll-interaktiv, liest `vibemind.config.json`).
- **Server-Mode-Launcher:** [scripts/vibemind-start.ps1](../../../scripts/vibemind-start.ps1) — phasenbasiert:
  - Phase 0: Preflight (Docker, Swarm)
  - Phase 0.5: Ollama (Host, :11434)
  - Phase 1: Docker-Swarm-Stack (`infra/swarm/vibemind-stack.yml`)
  - Phase 1.5: native Ausnahmen — OpenFang (:4200) + Minibook
  - **Phase 3: venv-Services** via `Start-VenvPython` — `la_fungus :8011`, `bridge :5150`, `automation_backend :8007`. **← Lauras Backend gehört hierher.** (Skip via `-SkipVenv`.)
  - Phase 4: Node — `moire_server :8766`
  - Phase 5: Electron (DevTools :9223) + OpenFang Debug-Agent
  - Phase 6: Health-Gate
- **`Start-VenvPython`-Signatur** (verifiziert [scripts/vibemind-start.ps1:333-386](../../../scripts/vibemind-start.ps1#L333-L386)): nimmt `-Name`, `-VenvPath $SHARED_VENV`, `-WorkDir`, `-ScriptArgs`, `-ExtraEnv @{...}`, `-Port`. PIDs landen in `logs/services.registry.jsonl`.
- **Stop:** [scripts/vibemind-stop.ps1](../../../scripts/vibemind-stop.ps1) killt per Port + CmdLine-Pattern (tree-kill).

**Video-Space (existiert bereits, unabhängig von Laura)**
- `vibemind-os/spaces/video/` mit `VideoBackendAgent` (Stream `events:tasks:video`, [agents/video_agent.py](../../../vibemind-os/spaces/video/agents/video_agent.py)), 10 Events (`video.team_run`, `video.vision`, `video.lipsync`, `video.voice_tts`, `video.publish`, …).
- Submodule: `vibevideo` + `vibevideo_deepfake` ([.gitmodules](../../../vibemind-os/.gitmodules)).
- **Media-Server :8977** ([media_server.py](../../../vibemind-os/spaces/video/media_server.py)) serviert `~/.rowboat/Videos/` (HTTP-Range). Stack hat zusätzlich einen nginx-`media`-Service (:9877, profile `space-media`).
- `voice/python/spaces/video` ist **kein Duplikat**, sondern ein Python-Import-Pfad auf dieselben Submodule.
- **Lücke:** Im [intent_classifier.py](../../../vibemind-os/voice/python/swarm/orchestrator/intent_classifier.py) fehlt der VIDEO-Space → derzeit **keine** deutschen Sprachbefehle für Video. (Für diese Iteration bewusst **nicht** geschlossen — Steuerung läuft über MCP.)

**UI-Muster für Spaces (Electron, nicht Tauri)**
- Spaces werden als **`BrowserView`** in der Electron-Shell gemountet ([renderer/space-navigator.js](../../../vibemind-os/voice/electron-app/renderer/space-navigator.js)).
- Konkretes Vorbild: [rowboat-manager.js](../../../vibemind-os/voice/electron-app/rowboat-manager.js) — `new BrowserView({ webPreferences: { preload, contextIsolation:true, nodeIntegration:false }})`, dev → `loadURL(devUrl)`, prod → `loadFile(dist/index.html)`.
- Es existiert bereits ein `video` → „Video Studio"-Space-Eintrag.
- Die **Tauri**-Apps (`launcher-app`, `openfang-desktop`) sind Bootstrap/Agent-OS — **nicht** die Heimat der Space-UIs. Die alten Fragen 4/5 zielten aufs falsche Programm.

**MCP-Hub**
- Zentraler Aggregator: **OpenFang :4200/mcp**. Konsumenten via [openfang/scripts/mcp_stdio_bridge.py](../../../vibemind-os/openfang/scripts/mcp_stdio_bridge.py). MCP-Server-Code unter [openfang/mcp/](../../../vibemind-os/openfang/mcp/) (z.B. `openfang_agents_server.py`). Kein per-Agent-MCP-Eintrag mehr.

### 1.2 Laura-Seite (`C:\Users\User\Desktop\Laura`)

- **Monorepo (pnpm):** `apps/desktop` (Electron + React 18 + Vite 5 + Tailwind), `services/local-api` (FastAPI, Python ≥3.11, `uv`), `packages/` (leer, Platzhalter), `docs/`, `dist/` (gebündelte `ffmpeg.exe`+`ffprobe.exe` je 223MB, `laura-api.exe` 107MB PyInstaller).
- **Git:** Remote `github.com/Vibemind-LAB/Lauras_star.git`, Branch `feat/pipeline-foundation`. Working Tree **nicht clean** (uv.lock modifiziert; `.claude/`, `build/` untracked).
- **Backend** [services/local-api/src/laura/main.py](file:///C:/Users/User/Desktop/Laura/services/local-api/src/laura/main.py):
  - Bindet `127.0.0.1:8765` (Default, [config.py](file:///C:/Users/User/Desktop/Laura/services/local-api/src/laura/config.py)). Console-Entrypoint `laura-api`.
  - Routen: `/healthz`, `/metrics`, `projects`, `assets` (+ `import`, `import/url`), `jobs`, `analysis` (`shots`/`transcript`), `timelines` (+ Ops `append/insert/delete/split/trim/move/set_speed`, `exports`, `captions.srt|.vtt`), `search`, `admin`.
  - SQLite default (`{workspace}/laura.db`), 13-Tabellen-Schema, eingebauter Job-Runner (claim/lease/heartbeat).
  - **Auth:** `LAURA_TOKEN` (zufällige UUID **pro Start**) — Token-Validierung in [api/security.py](file:///C:/Users/User/Desktop/Laura/services/local-api/src/laura/api/security.py).
- **Frontend** [apps/desktop/src/App.tsx](file:///C:/Users/User/Desktop/Laura/apps/desktop/src/App.tsx): React-Root; Komponenten DropZone/ImportBar/MediaCard/NavRail/Player/SceneInspector/TimelineBar/TranscriptBar/Waveform. Typed Client `LauraClient` ([api.ts](file:///C:/Users/User/Desktop/Laura/apps/desktop/src/api.ts)).
- **Electron-IPC** [apps/desktop/src/main.ts](file:///C:/Users/User/Desktop/Laura/apps/desktop/src/main.ts): `laura:service-info` (→ baseUrl+token), `laura:pick-file`/`pick-files`/`pick-folder`/`save-file`, `laura:list-media-in-folder`. **Custom-Protocol `laura-media://`** für Range-Streaming großer Medien.
- **Capabilities:** Multi-URL/yt-dlp-Import (YouTube/Drive/Vimeo/…), ffprobe-Metadaten, CFR-Proxy, Audio-Extraktion, Waveform, Shot-Detection (PySceneDetect/TransNetV2), ASR (faster-whisper), Alignment (WhisperX), Diarisierung (pyannote), frame-genaues Timeline-Editing, Export **OTIO/EDL/FCP7-XML/FCPXML/SRT/VTT**.
- **Output-Pfade:** Ingest-Artefakte `{workspace}/assets/{id}/`; Exporte `{workspace}/exports/{timeline_id}/timeline.{ext}`.
- **Secrets:** `LAURA_HOST/PORT/TOKEN/WORKSPACE` (Electron setzt sie); optional `LAURA_FFMPEG/FFPROBE`, `HF_TOKEN` (pyannote), Server-Mode `DATABASE_URL/REDIS_URL/QDRANT_URL/S3_*`.
- **Invarianten (aus Lauras CLAUDE.md):** frame-/sample-genau (nie Float-Sekunden), Ranges end-exclusive, OTIO ist Wahrheitsquelle (nie EDL/XML als State), local-first, ML-Extras optional.

---

## §2 — Antworten an den Laura-Coder (die 10 Fragen)

> **Lesehinweis:** ✅ = bestätigt, ❌ = Annahme war falsch (korrigiert), ⚠️ = teils anders. Jede Antwort ist umsetzungsfertig.

### A) Start & Lebenszyklus

**1. Wo liegt das echte Start-Skript?**
✅ Es liegt sehr wohl unter `scripts/`: **`scripts/vibemind-start.ps1`** (Server-Mode) und der interaktive **`Vibemind.debug.ps1`** im Repo-Root (der reale „User-Doppelklick"-Launcher). Beide bringen denselben Stack hoch; `vibemind-start.ps1` ist die phasenstrukturierte Variante, in die Lauras Backend eingehängt wird.

**2. Läuft der VideoAgent mit / ist `events:tasks:video` aktiv?**
✅ Ja, `VideoBackendAgent` läuft mit dem Stack und hört auf `events:tasks:video`. **Aber für Laura irrelevant:** Laura wird **nicht** über diesen Agent gesteuert, sondern über ihre eigene REST-API + MCP (s. Frage 8). Der bestehende Video-Agent (Team-Pipeline/Deepfake/Lipsync) und Laura **koexistieren** unverändert nebeneinander.

**3. Wie soll Lauras Backend (:8765) starten?**
✅ **Als Hintergrund-Service im selben Start-Skript** — exakt dein Vorschlag. Konkret: neue **Phase-3-venv-Zeile** via `Start-VenvPython` (Muster wie `la_fungus`/`bridge`/`automation_backend`). Kein Docker, kein Sidecar.
- `-WorkDir 'vibemind-os\spaces\video\laura\services\local-api'`
- Start über `uv run laura-api` **oder** direkt `python -m uvicorn laura.main:create_app --port 8765` (Implementierungsdetail; `uv` bevorzugt, da Laura es nutzt).
- `-Port 8765`, `-ExtraEnv @{ LAURA_HOST='127.0.0.1'; LAURA_PORT='8765'; LAURA_TOKEN=<siehe Frage 9>; LAURA_WORKSPACE=<siehe Frage 10>; LAURA_FFMPEG=<gebündelt>; LAURA_FFPROBE=<gebündelt> }`
- Gegenstück in `vibemind-stop.ps1`: Stop per Port 8765 + CmdLine-Pattern `laura\.main|local-api`.

### B) UI

**4. Gibt es ein Muster, wie ein Space-UI im Launcher erscheint?**
⚠️ Ja — **aber in Electron, nicht Tauri.** Spaces werden als **`BrowserView`** gemountet (Vorbild: `rowboat-manager.js`). Wir bauen **kein** Tauri-Asset. **Plan:** Lauras Renderer-`dist` wird als neuer BrowserView-Space „Laura" registriert; Lauras eigener Electron-`main.ts` entfällt im integrierten Modus.

**5. OK, dem Launcher `@tauri-apps/plugin-dialog` + `plugin-fs` hinzuzufügen?**
❌ **Nicht nötig** — die Frage zielt auf Tauri, die UI-Heimat ist aber Electron. Lauras File-Dialoge (`laura:pick-file` etc.) müssen auf **VibeMinds Electron-Preload** umgezogen werden (IPC-Bridge), bzw. ein Laura-spezifisches Preload wird im VibeMind-BrowserView registriert. **Action für dich (Laura-Coder):** Lauras Renderer so entkoppeln, dass `window.laura.*` über ein einsetzbares Preload kommt (nicht hart an Lauras `main.ts` gebunden) — siehe §3 Phase 2.

### C) Submodul & Repos

**6. Submodul-Pfad `spaces/video/laura` korrekt? + Duplikat-Pflege?**
✅ Pfad bestätigt: **`spaces/video/laura`** als neues Submodul (relativ zum `vibemind-os`-Submodul: `vibemind-os/spaces/video/laura`). ❌ Das „Duplikat" `voice/python/spaces/video` ist **kein** Duplikat, sondern ein Python-Import-Alias auf dieselben Dateien — **es muss nichts gesynct/symlinkt werden.** Laura taucht an genau **einer** Stelle auf.

**7. Welcher Laura-Stand?**
⚠️ **Noch keiner — Sequenz beachten.** Laura bekommt zuerst weitere UI+Backend-Ergänzungen (Owner: „da kommt noch was dazu, das wird zuerst gemacht"). **Erst danach** wird der Submodul-Commit gepinnt. Vorbedingung vorm Pinnen: Lauras Working Tree clean (offene Änderungen committen/pushen; `.claude/`+`build/` in `.gitignore`). Bis dahin: Branch `feat/pipeline-foundation`.

### D) Events, Secrets, Medien

**8. Welche Editorial-Events zuerst? Voice auf Deutsch?**
⚠️ **Geändert gegenüber der Frage:** Steuerung läuft in dieser Iteration **nicht** über neue Bus-Events oder Voice, sondern über **MCP-Tools** (Owner-Entscheidung). Erste Tools (Wrapper um Lauras REST):
  - `laura_project_create`, `laura_import` (lokal + URL/yt-dlp), `laura_analyze` (shots/asr), `laura_timeline_op` (append/trim/split/…), `laura_export` (otio/edl/fcpxml/srt), `laura_status`.
  - Exponiert über den **OpenFang-MCP-Hub** (s. Frage „MCP-Server"). Damit erreichbar für Claude/Brain/OpenFang-Agents.
  - **Voice/Intent-Classifier bleibt vorerst unangetastet** — kann später als eigene Stufe ergänzt werden (deutsche Aliasse „importiere <link>"/„exportiere als EDL" → die MCP-Tools).

**9. Braucht Lauras Backend ein Token? Wie werden Secrets gereicht?**
✅ Ja: **`LAURA_TOKEN`**, zufällig **pro Start**. Im integrierten Modus erzeugt **nicht** Lauras Electron-`main.ts` das Token, sondern die VibeMind-Startphase:
  - `vibemind-start.ps1` generiert beim Laura-Start ein Token, setzt es als `-ExtraEnv LAURA_TOKEN` **und** schreibt es an einen wohldefinierten Ort, den die Konsumenten lesen (Vorschlag: `logs/laura.token` oder ein Eintrag in `services.registry.jsonl`).
  - Der **MCP-Server** und der **Electron-BrowserView** (via `laura:service-info`) lesen Token+baseUrl von dort.
  - `HF_TOKEN` (für Diarisierung) kommt aus VibeMinds `.env` (wie alle anderen Keys) — **nicht** committen.

**10. Lauras Exporte nach `~/.rowboat/Videos/`?**
⚠️ **Differenziert:** Lauras *kanonische* Workspace-Ausgaben (`exports/{timeline_id}/timeline.{ext}`, OTIO/EDL/XML — das sind Projektdateien, keine Videos) bleiben in Lauras `LAURA_WORKSPACE`. **Aber** die gerenderten **MP4-Endprodukte** sollen nach **`~/.rowboat/Videos/`**, damit VibeMinds Gallery + Media-Server (:8977) sie aufgreifen.
  - **Setze `LAURA_WORKSPACE`** auf einen festen Ort unter VibeMind-Kontrolle (Vorschlag: `~/.rowboat/Laura/` für Projekt-State).
  - Für **gerenderte Videos**: entweder Lauras Render-Output-Pfad auf `~/.rowboat/Videos/` konfigurieren, oder ein dünner Post-Render-Hook kopiert/verlinkt das MP4 dorthin. (Hinweis: Laura exportiert heute primär **Interchange-Formate**, kein direktes MP4-Render — ein „render to mp4"-Schritt ist Teil von Lauras Pipeline-Erweiterung Phase 0, s. Lauras `docs: pipeline export stage plan`.)

---

## §3 — Integrationsstufen (gestufter Bauplan)

> Reihenfolge ist **strikt sequenziell** bei Phase 0→1, danach teils parallelisierbar. Jede Phase hat ein klares Abschlusskriterium.

### Phase 0 — Laura-Eigenarbeit *(Laura-Coder, VOR der Integration)*
**Ziel:** Laura ist integrationsreif.
- Geplante UI- + Backend-Ergänzungen fertigstellen (inkl. Render/Export-Stage → MP4, laut `pipeline export stage plan`).
- Renderer von Lauras `main.ts` entkoppeln: `window.laura.*` über ein **einsetzbares Preload** (damit ein Fremd-Host — VibeMind — es bereitstellen kann).
- Working Tree clean machen: offene Änderungen committen/pushen; `.claude/` + `build/` in `.gitignore`.
- **Abschluss:** Lauras Backend startet headless via `uv run laura-api` (ohne Electron), `/healthz` grün; Renderer-`dist` baut reproduzierbar; ein Commit auf `feat/pipeline-foundation` (oder Merge nach `main`) ist pin-fähig.

### Phase 1 — Submodul + Backend-Lifecycle *(VibeMind)*
**Ziel:** Lauras Backend läuft als nativer VibeMind-Service.
- Submodul hinzufügen: `git submodule add https://github.com/Vibemind-LAB/Lauras_star.git vibemind-os/spaces/video/laura`, Commit aus Phase 0 pinnen, `.gitmodules` ergänzen.
- venv: Lauras Python-Deps in `$SHARED_VENV` installieren (oder dediziertes venv — Implementierungsdetail; `uv`-kompatibel halten). FFmpeg aus Lauras `dist/ffmpeg` referenzieren.
- `vibemind-start.ps1`: neue Phase-3-Zeile `laura_api :8765` (Token-Gen + `-ExtraEnv` + Token-File-Write). `vibemind-stop.ps1`: Stop-by-Port 8765.
- **Abschluss:** `vibemind-start.ps1` bringt Laura mit hoch; `GET http://127.0.0.1:8765/healthz` mit Token grün; Token-File geschrieben; Health-Gate kennt Laura.

### Phase 2 — Electron-BrowserView-Space *(VibeMind)*
**Ziel:** Lauras UI erscheint als „Laura"-Space im Launcher.
- Neuen Space „laura" (oder Unter-Tab im Video-Studio) in `space-navigator.js` registrieren; `laura-manager.js` nach Vorbild `rowboat-manager.js`.
- Lauras Renderer-`dist` als BrowserView laden (prod: `loadFile`; dev: `loadURL` auf Lauras Vite-Dev-Server).
- `laura-preload.js`: bildet `window.laura.*` auf VibeMind-IPC ab (`pick-file` → Electron-Dialog; `service-info` → liest Token-File+baseUrl). `laura-media://`-Protocol im VibeMind-Main registrieren (oder auf :8765-Range-Endpoint umleiten).
- **Abschluss:** Space „Laura" öffnet, lädt Lauras UI, kann importieren/Timeline editieren/exportieren — alles gegen das in Phase 1 gestartete Backend.

### Phase 3 — MCP-Tools via OpenFang-Hub *(VibeMind)*
**Ziel:** Laura ist für Claude/Brain/OpenFang-Agents steuerbar.
- MCP-Server (Python/FastMCP) unter `vibemind-os/openfang/mcp/` (z.B. `laura_server.py`), der Lauras REST :8765 mit dem Token wrappt. Tools: `laura_project_create`, `laura_import`, `laura_analyze`, `laura_timeline_op`, `laura_export`, `laura_status`.
- Im OpenFang-MCP-Hub registrieren; Konsumenten via `mcp_stdio_bridge.py`.
- **Abschluss:** `laura_status` & `laura_import` über den Hub aufrufbar (E2E: Tool-Call → REST → Laura-Job → Ergebnis).

### Phase 4 *(optional, spätere Stufe)* — Voice/Intent
- VIDEO/LAURA-Sektion im `intent_classifier.py` ergänzen; deutsche Aliasse („importiere <link>", „exportiere als EDL") → MCP-Tools bzw. neue `laura.*`-Events auf `events:tasks:video`.
- **Bewusst aus der ersten Iteration ausgeklammert.**

---

## §4 — Risiken & offene Punkte

| Risiko | Auswirkung | Minderung |
|---|---|---|
| **`LAURA_TOKEN` pro Start** | MCP-Server/BrowserView müssen das frische Token finden | Token-File-Kontrakt (`logs/laura.token`), von Startphase geschrieben, von Konsumenten gelesen |
| **Lauras `main.ts` koppelt IPC** | BrowserView-Mount bricht, wenn `window.laura.*` an Lauras Electron hängt | Phase-0-Vorbedingung: einsetzbares Preload |
| **FFmpeg/torch-Größe im venv** | venv wird groß, evtl. CUDA-Wheels | Lauras gebündeltes `dist/ffmpeg` nutzen; ML-Extras optional lassen (local-first) |
| **Render→MP4 fehlt heute** | „Export nach ~/.rowboat/Videos" hat noch kein MP4 | Teil von Lauras Phase 0 (`pipeline export stage plan`); bis dahin Interchange-Formate |
| **Port 8765** | scheinbarer Konflikt mit Coding-Engine | Kein realer Konflikt (CE nutzt 8765 als **WebSocket**, anderer Prozess) — trotzdem im Health-Gate prüfen |
| **Submodul-Working-Tree unclean** | nicht reproduzierbarer Pin | Phase-0-Vorbedingung: clean + `.gitignore` |
| **Zwei Electron-Runtimes** (falls BrowserView scheitert) | doppelter Speicher | Fallback „eigenes Fenster" dokumentiert, nicht bevorzugt |

**Offene Implementierungsentscheidungen (klären beim Bauen):**
- Eigenes venv für Laura vs. `$SHARED_VENV` (Größe/Isolation).
- Token-File-Ort: `logs/laura.token` vs. Feld in `services.registry.jsonl`.
- `laura-media://` im VibeMind-Main neu registrieren vs. direkt :8765-Range nutzen.
- Eigener Space „laura" vs. Unter-Tab im bestehenden „Video Studio".

---

## §5 — Was dieser Plan NICHT macht (YAGNI)

- Kein Voice/Intent-Classifier in Iteration 1 (Phase 4 optional).
- Kein neuer Event-Handler-Agent für Laura (MCP genügt).
- Keine Docker-Containerisierung von Laura (native venv).
- Kein Sync/Symlink für den „Duplikat"-Pfad (existiert nicht real).
- Keine Tauri-Plugins (UI ist Electron).
- Kein Merge von Laura in den bestehenden `VideoBackendAgent` (Koexistenz).
