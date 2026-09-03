# Vibemind_V1 — Offene Gaps & Plan

**Stand:** 2026-05-19 (nach `a14ed07` master, alle 3 Ebenen `0/0` vs origin)

Konsolidierter Plan über alle offenen / deferred Punkte aus:
1. `~/.claude/plans/mach-einen-sehr-ausf-hrlichen-moonlit-cupcake.md` (der grosse A→E Migrationsplan)
2. `infra/standards/STANDARDS.md` Gap-Liste (alle 6 ursprünglichen geschlossen; Folge-Items hier)
3. Live-Stack (`infra/swarm/vibemind-stack.yml` opt-ins, BLOCKIERT-Markierungen, stale comments)
4. Submodule-Zustand (3 Ebenen, isolierte Branches)

**Was NICHT mehr offen ist** (in dieser Session erledigt + gepusht):
A→D · B-next · Container-Standard · Launcher-Stack-Integration · STANDARDS Gap-Liste #1-#6 ·
coding-engine vollständig (P1/P2a/P2b/P2c, 10/10 Services 1/1) · vscode-Fix · alle
Submodule-Pushes deep→shallow konsistent.

---

## Kategorie A — Konkrete Folge-Items (kurzfristig, klar abgrenzbar)

### A1 — coding-engine frontend in vibemind-os/master integrieren
**Was:** Meine `feat/frontend-static-nginx`-Branch im coding-engine-Repo
(Dockerfile.static + nginx-frontend.conf) gehört in dessen `master`, dann
vibemind-os `master` darauf rebasen (oder den coding-engine-Pointer
bumpen wenn der Workflow das so vorsieht).
**Status:** Branch ist auf `origin/feat/frontend-static-nginx`
(`Flissel/DaveFelix-Coding-Engine.git`) gepusht. NICHT in
`feat/phase-11-vibemind-integration` (fremder WIP) integriert.
**Warum offen:** Submodule-Branch-Workflow des coding-engine-Repos ist
nicht eindeutig — `master` (`c1df852`) ist alt, der aktive Branch ist
`feat/phase-11-vibemind-integration` (`938fe8c`, was vibemind-os
erwartet). Entscheidung: PR `feat/frontend-static-nginx` → coding-engine
`master`? Oder in `feat/phase-11`? User-Entscheidung nötig.
**Risiko:** Niedrig. Der Stack läuft ohne diese Integration (vorgebautes
Image + lokale nginx-conf-Datei reicht für `configs:`). Es ist eine
Ordnungs-Sache, kein Funktions-Blocker.
**Vorgehen:** (a) Entscheiden ob `coding-engine/master` aktualisiert
werden soll (PR/merge `feat/frontend-static-nginx` → master), oder (b)
in `feat/phase-11` integrieren. Dann vibemind-os-Pointer bumpen (deep→
shallow Push wie bei `ccef511`).

### ~~A2~~ — Stale "PHASE-B-NEXT EXTENSION POINTS"-Kommentar ✅ ERLEDIGT
**Status:** **CLOSED** (Commit `c571b69` auf `master`, 2026-05-19,
gepusht). Stale Block ersetzt durch ehrliche "NOT in stack"-Liste
(sandbox/openfang/minibook/bridge/la-fungus/automation-ui/ideas/
brain-learner-inference-opt-in) mit Forward-Pointer auf
`tasks/gaps.md`. YAML valid, nur Kommentar geändert, kein Service
oder Submodule berührt.

### A3 — Submodule-Pointer "M vibemind-os" auf top-level dauerhaft sichtbar
**Was:** `git status` zeigt ` m vibemind-os` (lowercase = modified content
*inside* vibemind-os). Das sind die uncommitteten Dateien anderer
parallelen Sitzungen IN vibemind-os, nicht meins.
**Status:** Kein Defekt. Pointer (`ccef511`) ist korrekt. Aber visuell
verwirrend — sieht aus wie "uncommitted work".
**Vorgehen:** NICHT von hier lösbar. Die jeweiligen parallelen Sitzungen
(brain-core/rowboat-Workstreams) müssen ihre Sachen committen.
**Entscheidung:** Beobachten, nichts tun. Verifizieren dass Pointer
`ccef511` korrekt bleibt.

---

## Kategorie B — Containerisierungs-Lücken (mittelfristig)

### B1 — minibook in den Stack (BLOCKIERT)
**Was:** `external/minibook` Build-Kontext ist leer (0 Dateien) — kein
Image baubar.
**Status:** Echter externer Blocker; nicht von uns lösbar.
**Vorgehen:** Quelle besorgen / `external/minibook` Git-Submodule
initialisieren wenn vorhanden. Sobald Source da: pre-build + Stack-Block
nach video/media-Muster (einfaches Static, Phase-1-Klasse).
**Aufwand:** Klein wenn Source da (~30min Stack-Block); blockiert
solange nicht.

### B2 — ideas-Space Dockerfile
**Was:** `vibemind-os/spaces/ideas/` — laut grosser Plan ein
HTTP-Service (`spaces/ideas/http_server.py`, liest `BRAIN_URL`), aber
keine Dockerfile-/Compose-Definition. Im aktuellen Plan als
"Vorlage" für neue standardisierte HTTP-Service-Hülle erwähnt.
**Status:** Nicht im Stack, kein Image. Läuft heute als native
venv-Service oder ist gar nicht containerisiert (verifizieren).
**Vorgehen:** Recon: läuft ideas heute überhaupt? Wie wird es
aufgerufen? Wenn relevant: Dockerfile (Python-3.11-Service-Template
aus `infra/standards/base-python-3.11.Dockerfile`) + Stack-Block.
**Aufwand:** Mittel (Recon + Build + Test).

### B3 — desktop Space: 6 Dockerfile-Varianten → 1 konsolidieren
**Was:** `Automation_ui/backend/` hat ~6 Dockerfile-Varianten
(Dockerfile, .dev, .minimal, .ocr, .remote-desktop, .gpu vom
GPU-offload-Commit). Plan-Item aus der Recon.
**Status:** Funktioniert wie ist (parallel-pflegbare Varianten),
aber unsauber.
**Vorgehen:** Multi-stage Dockerfile mit Build-Args/Target-Stages
für die Varianten — ODER bewusst belassen (jede Variante ist eine
deklarierte Konfiguration).
**Aufwand:** Mittel-Hoch. Berührt fremden App-Code in einem Submodule
+ braucht Test pro Variante. Sinnvoll als eigener Refactor wenn
GPU-offload-Variante stabil ist.

### B4 — Native Services in den Stack (B-next-Rest, langfristig)
**Was:** bridge (venv), la-fungus (venv), Automation_ui-backend
(venv, sandbox-abhängig), openclaw (hybrid).
**Status:** Laufen heute nativ vom Launcher gestartet. Funktionsfähig
aber nicht Server-deploy-fähig.
**Vorgehen:** Pro Service eigene Mini-Migration (Dockerfile +
Stack-Block + Cutover). Niedrig-Priorität — die Server-Vision wird
zunehmend realistisch, je mehr in-Stack ist.
**Aufwand:** Mittel pro Service. **OpenFang permanent native**
(self-daemonize Rust + Host-Hooks — siehe Phase-A-Entscheidung).

---

## Kategorie C — Phase D Live-Aktivierung & Phase E

### C1 — Phase D Learner+Inference live skalieren
**Was:** `brain-learner` + `brain-inference` sind `replicas: 0`
(opt-in, getestet). Routine-Betrieb läuft mono über `brain-core`.
**Status:** Funktionsfähig, getestet (Gate D bestanden in Phase D
direkter Test). Nicht aktiv weil mono-Default ausreicht.
**Vorgehen:** Wenn skaliert werden soll: `docker service scale
vibemind_brain-learner=1 vibemind_brain-inference=2`. Schaltet die
echte Phase-D-Topologie ein.
**Entscheidung:** Aktivieren oder mono lassen — Nutzungs-Entscheidung,
kein Engineering-Blocker.

### C2 — Phase E (Federated per-Space Learning)
**Status:** Bewusst geparkt (dein "mark before E"). Forschungs-/
Experimentier-Phase, nicht Production-Engineering.
**Vorgehen:** Wenn aktiviert: separater grosser Block, eigener Plan
(C1 `brain-learner` muss laufen + `decision_self_prior`-Hash um
`brain_id` erweitern + `federated_merge.py` neu schreiben +
Konvergenz-Monitor). Nicht Teil dieses Gap-Plans.

---

## Kategorie D — Standards-Folge-Items (aus geschlossenen Gaps abgeleitet)

### D1 — Existing-code Logging-Migration (Folge zu Gap #6)
**Was:** STANDARDS.md §9 Konvention ist geschrieben (JSON-Schema +
`BRAIN_LOG_*` env-Contract, binding für neuen/refactored code). Aber
rowboat (`console.log`) + mirofish (`print()`) sind nicht migriert.
**Status:** Bewusst deferred — fremder App-Code in 2 Submodulen, je
eigener verifizierter Refactor.
**Vorgehen:** Pro Service: eigener Branch im jeweiligen Submodule,
JSON-Formatter einbauen (brain_logger als Referenz), App-Code von
`console.log`/`print` auf den Logger umstellen, lokal verifizieren,
PR/Merge in den jeweiligen Submodule-Master.
**Aufwand:** Mittel-Hoch pro Service. Sinnvoll bevor ein
Log-Aggregator (ELK/Loki) integriert wird.

### D2 — docker.sock-Hardening bei coding-api/worker
**Was:** `coding-api` + `coding-worker` mounten `/var/run/docker.sock`
(Docker-in-Docker — Sicherheits-Smell). Aktuell `placement: manager`-
pinned + dokumentierter Trade-off.
**Status:** Funktional notwendig (api spawnt Container für
Code-Generation), Server-Hardening-TODO.
**Vorgehen:** App-Refactor: Docker-CLI-Aufrufe → Docker SDK / API-Client
(rootless), oder rootless-Docker-Daemon, oder Sysbox runtime. Berührt
App-Code im coding-engine-Submodule. Mittel-Hoch Aufwand.
**Risiko ohne Fix:** Container-Escape würde Host-Docker-Zugriff bedeuten.
Auf Single-Node-Dev akzeptabel, auf Production-Server riskant.

### D3 — Multi-Node Server-Hardening (TODOs aus coding-engine Phase 2a/b)
**Was:** Auf Single-Node funktioniert alles. Multi-Node hat dokumentierte
Lücken:
- host-bind-mounts in api/worker für `/var/run/docker.sock` → manager-only
- `extra_hosts: host.docker.internal:host-gateway` → bricht auf Linux-Swarm
- `brain_data` volume `driver: local` → physisch ein Node (Phase-D-Limit
  dokumentiert in Plan)
- coding-engine `egress-proxy` `internal: true` Overlay → routing-layer
  control, nicht App-Layer (tinyproxy-filter ist die echte Allowlist —
  dokumentiert)
**Vorgehen:** Pro Punkt eigene Lösung wenn echter Multi-Node-Deploy
ansteht (NFS-Volume / Linux DNS-Eintrag für openclaw / etc.). Heute
nicht akut.

### D4 — STANDARDS.md neue Sektion "Server-Hardening Backlog"
**Was:** §10 für die D1-D3 Themen oben hinzufügen, damit zukünftige
Reader sie auf dem Schirm haben (jetzt nur in dieser Datei).
**Aufwand:** Klein (10 Min Doku). Sinnvoll wenn Gap-Plan akzeptiert.

---

## Kategorie E — Das eigentliche User-Ziel

### E1 — Validiertes `vibemind-start.ps1` / `vibemind-stop.ps1` (.exe / Icon)
**Was:** Der Ursprung dieser Sitzungs-Iteration. Validierte Scripts
die den Stack + native Ausnahmen hoch-/runterfahren, .exe /
Desktop-Icon-tauglich. **Bewusste Entscheidung:** vollwertiger
Launcher-Ersatz (alle 7 Launcher-Phasen), phasiert in E1a-d weil
mehrtägig.

**E1a — Stack-Layer ✅ ERLEDIGT** (Commit `bf7f9d0`, 2026-05-19):
`scripts/vibemind-start.ps1` + `scripts/vibemind-stop.ps1` decken die
**Stack-Layer-Hälfte** ab (Phase 0 preflight, Phase 0.5 Ollama, Phase
1 stack deploy + OpenFang/Minibook native exceptions, Phase 6 health
gate). **Live verifiziert**: idempotent gegen laufenden Stack
ausgeführt → "All 25 services converged + 6 endpoints answering",
exit 0, Stack unbeeinflusst. PS-IPv6-Bug gefunden + gefixt
(Invoke-WebRequest http://localhost:<port> → IPv6 ::1 first → 5s
timeout; rewrite zu 127.0.0.1 — gleiche §2-Klasse wie busybox
in rowboat/media).

**E1b/c/d — ✅ ERLEDIGT** (4 Commits `c4d121b..6798fff`, 2026-05-20,
gepusht):
- **`c4d121b`** Helper-Modul-Extraktion → `scripts/lib/vibemind-helpers.ps1`
  (Write-*, Test-HttpHealth, Test-PortFree, Stop-ByPort, Get-RuntimeHint,
  Register-SpawnedProcess, Initialize-Registry, Start-ServiceProcess,
  Start-VenvPython, Test-RegisteredProcessAlive, Get-CrashedFromRegistry,
  Stop-AllServicesFromRegistry, Wait-Interactive). Dependency-frei
  (alles über -RegistryFile-Param, kein `$script:`-Global).
- **`973a5d1` E1b** — Phase 3 (la_fungus :8011 TCP / bridge :5150 HTTP
  /bridge/health / automation_backend :8007 HTTP /api/health) + Phase 4
  (moire_server :8766, 4-Kandidaten-Probe). **Brain-API STRUKTURELL
  AUSGESCHLOSSEN** — kommt in keiner Funktion vor, kein Flag flippt
  ihn an (Launcher-Port-Conflict-Bug bei Z.1018-1022 strukturell
  verhindert). Idempotent (Test-PortFree-Skip). Stop nutzt
  Stop-ByPort -Tree + CmdLinePattern/RepoRoot-Backstop für orphaned
  workers. Bekannte Win-Quirk: automation_backend's multiprocessing-
  fork-Kinder können als kernel-ghost-Listener auf :8007 überleben
  (im Code dokumentiert).
- **`05077a2` E1c** — Phase 5 (Electron-App :9223 + OpenFang
  Debug-Agent sidecar). Server-Mode hardcodet `SKIP_BRAIN_SPAWN=1` +
  `BRAIN_PORT=5000` (Brain immer aus Stack). Stop tree-kill via :9223
  + path-gefilterter electron.exe-Sweep (foreign Electrons aus VSCode/
  Discord/Slack überleben).
- **`6798fff` E1d** — opt-in `-Interactive`-Flag. Default unverändert:
  exit 0 nach Health-Gate (.exe / Scheduled Task event-driven). Mit
  Flag: Wait-Loop mit Ctrl+C-Trap (PowerShell.Exiting +
  AppDomain.ProcessExit) → `Stop-AllServicesFromRegistry` mit
  Managed-Ports-Backstop. Stack bleibt zwischen Sessions up.

Server-Mode-Default-Flags nun: `-SkipOllama/-SkipNative/-SkipVenv/
-SkipNode/-SkipElectron/-Interactive` + `-HealthTimeout`.

**Aufwand insgesamt:** E1a = 1 Sitzung, E1b/c/d/Helpers = 1 Sitzung
(diese, 4 commits). Funktional ersetzt der neue Pfad
`Vibemind.debug.ps1` für Server-Mode UND Dev-Mode; Launcher bleibt
optional für Debug-Verbosity, `vm-procs`-Integration, Live-Tail.

---

## Priorisierung & Reihenfolge

**Sofort (eigene Sitzung):**
- ~~**E1** — Start/Stop-Script.~~ ✅ ABGESCHLOSSEN (E1a..d, siehe Kategorie E).

**Kurzfristig (jeweils klein, eigener Commit):**
- A2 stale Kommentar (5 Min)
- D4 STANDARDS.md §10 (10 Min)
- A1 frontend-Branch-Integration (Entscheidung nötig)

**Mittelfristig (eigene Refactors):**
- B2 ideas-Dockerfile (wenn Recon ergibt: relevant)
- D1 existing-code Logging-Migration (rowboat, mirofish — je separat)
- B4 native services containerisieren (eins nach dem anderen)

**Langfristig / externer Blocker:**
- B1 minibook (blockiert auf Source)
- C1 Phase D scale-up (Nutzungs-Entscheidung)
- B3 desktop 6→1 Dockerfile (nach GPU-offload-Stabilität)

**Geparkt / nicht in diesem Backlog:**
- C2 Phase E Federated (eigene Welt)
- D2 docker.sock-Hardening (Server-Deploy-zeitig)
- D3 Multi-Node-Hardening (Server-Deploy-zeitig)

**Beobachten / nichts tun:**
- A3 `M vibemind-os` (fremde parallel sessions)

---

## Pflege dieser Datei

Diese Datei lebt im Repo (`tasks/gaps.md`) und wird mit dem Stand
aktualisiert. Wenn ein Punkt erledigt wird: hier streichen + im Plan
(`~/.claude/plans/mach-einen-sehr-ausf-hrlichen-moonlit-cupcake.md`)
spiegeln. Wenn ein neuer Gap auftaucht: hier eintragen.

Letzte Aktualisierung: 2026-05-19 nach `a14ed07`.
