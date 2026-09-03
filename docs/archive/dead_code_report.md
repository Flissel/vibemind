# Dead-Code-Report — Vibemind_V1 / vibemind-os

**Datum:** 2026-05-23 · **Status-Update:** 2026-06-09 (Graph-Cross-Check)
**Scope:** Ganzes `vibemind-os` Submodule (4098 Py, 1421 TS/JS) + Repo-Root `scripts/`
**Methode (Original):** fungus semantic index (54k chunks) + 4 parallele Explore-Agents + vulture statisch + Grep-Cross-Checks
**Methode (Update):** Graphify-Code-Graphen (8 Submodul-Graphen, indeg-Analyse) als unabhängiger Cross-Check + Dateisystem-Verifikation

---

## 0. STATUS-UPDATE 2026-06-09 — was seither erledigt ist

Cross-Check des Original-Reports gegen (a) Dateisystem, (b) 8 frisch gebaute Graphify-Code-Graphen,
(c) git-Historie. Ergebnis: **der Großteil von §1–§4 wurde bereits umgesetzt.**

### ✅ ERLEDIGT (verifiziert weg)

| Fund (Original-Report) | Verifikation | Commit |
|---|---|---|
| `web/legacy/` 6 Flask-Server | FS leer + Graph: 0 Knoten | Stage 1 (`5912878`) |
| `brain/demos/` + `experimental/` | FS: 0 `.py` | Stage 1 |
| `coding-engine/_archive/`, `Data/` (~1.1k files) | FS: nur 12K Rest | Stage 1 / 3c (`42c12a9`) |
| `_v2/_v3.py`-Services (183 Files, 22.584 LOC) | FS: 0 da + **Graph bestätigt: nur 768 lebende Services, kein einziges `_v2`** | (gelöscht) |
| 5× `llm_client.py`-Duplikate (§4) | Jetzt **20-Zeilen-Shims** die `vibemind_shared` re-exportieren (Duplikat-Code weg) | `3140871`, `b3f59bd`, `ca7f190` |
| diverse `.bak`-Files | FS | Stage 1 |

**Graph-Cross-Check-Mehrwert:** Der Graph bestätigt unabhängig, dass die `_v2`-Service-Geister
restlos weg sind — kein `_v2`-Knoten in 61.109 coding-engine-Knoten. Das ist genau die Stärke
des Graphen: **Bestätigung**, nicht Erstfund.

### ⏳ NOCH OFFEN

| Fund | Stand 2026-06-09 | Risiko / Hinweis |
|---|---|---|
| **`spaces/coding/Coding_engine/` (20.913 Dateien)** | NOCH DA. **Keine Code-Referenzen mehr** (die 4 Blocker aus §2 sind weg, grep über ganzes Repo = 0 Code-Treffer). | ⚠️ **Kein verwaister Ordner, sondern registriertes _nested Submodul_** (`.git/modules/voice/modules/python/spaces/coding/Coding_engine`) hinter Junction `voice/python/spaces`→`spaces/`. Entfernen NUR via `git submodule deinit` + `git rm` im **voice**-Submodul, nicht `rm -rf`. Einzige Referenzen: `settings.local.json` (`submodule.update=none`). |
| `legacy_compat.py` einzelne Endpoints | Router lebt (Import in `brain_server.py:1650`), aber einzelne Endpoints (`legacy_forum_history`, `legacy_token_stats`) ungenutzt | niedrig — Endpoint-Ebene, nicht Datei |
| TS/JS Dead Code (§7-Lücke) | Graphen vorhanden (voice 5.5k, openclaude 5k TS/JS-grad-0-Kandidaten), aber **roher grad-0-Scan zu verrauscht** (Exports/JSX/React) — bräuchte export-bewussten Filter (knip/ts-prune) | offen |

### ⚠️ Methodischer Befund zum Graph-Ansatz

Roher **grad-0-Scan ist für diesen Stack KEIN verlässlicher Dead-Code-Detektor**: ~11k „Kandidaten"
allein im Core, davon das Gros falsch-positiv. Beispiel: `OpenFangExecutor`, `McpExecutor`,
`HttpExecutor` erscheinen als „tot", werden aber per **Factory-String-Dispatch** in
`capability_targets.py::build_executor()` erzeugt (statisch keine Kante). Ebenso Decorator-Routen,
MCP-Tool-Lookup-per-Name, importlib. **Der Graph taugt als Cross-Check / Konfidenz-Verstärker,
nicht als Urteilsinstanz.** Für Erstfunde bleibt fungus+vulture+grep (Original-Methode) überlegen.

---

## (HISTORISCH 2026-05-23 — Original-Report, Methodik-Referenz)

---

## 1. SICHER TOT — sofort löschbar

Verifiziert durch: keinerlei Import/Aufruf-Referenzen außerhalb der Files selbst.

| Pfad (rel. zu `vibemind-os/`) | Typ | Größe | Verifikation |
|---|---|---|---|
| `brain/the_brain/web/legacy/autonomous_swarm_server.py` | Legacy Flask-Server | 1 file | Grep: nur Docstring-Erwähnung in `unified_brain_service.py:26` |
| `brain/the_brain/web/legacy/brain_dashboard_server.py` | Legacy Flask-Server | 1 file | Grep: nur Docstring-Erwähnung in `unified_brain_service.py:24` |
| `brain/the_brain/web/legacy/evolutionary_training_server.py` | Legacy Flask-Server | 1 file | Keine Imports |
| `brain/the_brain/web/legacy/klotski_dashboard_server.py` | Legacy Flask-Server | 1 file | Keine Imports |
| `brain/the_brain/web/legacy/moltbook_dashboard_server.py` | Legacy Flask-Server | 1 file | Keine Imports |
| `brain/the_brain/web/legacy/oscillator_dashboard_server.py` | Legacy Flask-Server | 1 file | Keine Imports |
| `brain/the_brain/demos/` | Demo-Skripte | 30 files | Grep `from brain.demos` / `import brain.demos` → **0 Treffer** |
| `brain/the_brain/demos/experimental/` | Experimental Demos | 19 files | Wie oben — keine Imports |
| `coding-engine/_archive/old_tests/` | Alte Tests | 443 files | Verzeichnis ist explizit `_archive`, keine pytest-Discovery |
| `coding-engine/_archive/old_runners/` | Alte Runner-Skripte | 15 files | Nur in Trainingsdaten-JSONs erwähnt (Output-Artefakte) |
| `coding-engine/Data/all_services/whatsapp-messaging-service_20260211_025459/` | Generierte Service-Outputs | ~680 files | Generierte Artefakte, gehören nicht ins Repo |
| `coding-engine/Data/all_services/whatsapp-messaging-service_20260211_025459.zip` | Archiv-Kopie | 2 MB | Selbe Daten als ZIP |
| `coding-engine/mcp_plugins/servers/playwright/agent_backup.py` | Backup-Datei | 1 file | `_backup`-Suffix |
| `coding-engine/mcp_plugins/servers/time/agent_backup.py` | Backup-Datei | 1 file | `_backup`-Suffix |
| `security/poc_playwright/agent_backup.py` | Backup-Datei | 1 file | `_backup`-Suffix |
| `security/poc_time/agent_backup.py` | Backup-Datei | 1 file | `_backup`-Suffix |
| `brain/the_brain/docker-compose.brain-core.yml.bak.pre-autotrain` | Compose-Backup | 1 file | `.bak`-Suffix |
| `brain/the_brain/docker-compose.brain-core.yml.bak.pre-openfangurl` | Compose-Backup | 1 file | `.bak`-Suffix |
| `openclaw/config/openclaw.json.bak` | Config-Backup | 1 file | `.bak`-Suffix |
| `spaces/autogen/config/openclaw_gateway.json.bak` | Config-Backup | 1 file | `.bak`-Suffix |

**Repo-Root (außerhalb Submodule):**
| Pfad | Typ |
|---|---|
| `Vibemind.debug.ps1.bak.pre-probe-fix` | PS-Backup |
| `backups/` | Backup-Sammlung (untracked) |

**Geschätzter Wegfall:** ~1.200 Dateien, mehrere hundert MB (vor allem `coding-engine/Data/`).

---

## 2. WAHRSCHEINLICH TOT — manuell prüfen, dann löschen

| Pfad | Typ | Begründung |
|---|---|---|
| `spaces/coding/Coding_engine/_archive/` | 458 files | Inneres Archive in alter Coding-Engine-Kopie |
| `spaces/coding/Coding_engine/external/Automation_ui/` | 750 files | Eingebettete UI-Kopie; aktive Variante lebt in `spaces/desktop/Automation_ui/` |
| `spaces/coding/Coding_engine/mcp_plugins/` | ~150 agents | Stub-Server, keine `spaces.coding.Coding_engine.mcp_plugins`-Imports |
| `spaces/coding/Coding_engine/src/` | ~2900 files | **Achtung:** Migrationspfad — `coding-engine/src/tools/claude_code_tool.py`, `coding-engine/src/mind/orchestrator.py`, `coding-engine/docker-compose.yml`, `spaces/coding/engine/coding_engine_runner.py` enthalten noch Referenzen. Vor Löschung diese 4 Stellen umstellen. |
| `spaces/shuttles/swe_desgine/` | 500+ files | Embedded SWE-Agent Forschungsprojekt; keine aktiven Imports |
| `coding-engine/src/services/*_v2.py` + `*_v3.py` | 183 Module | Versions-Suffix, nur in `emergent_pipeline.py` + paralleler Tests — Architektur-Review erforderlich, ob v1 noch live ist |
| `brain/the_brain/web/routers/legacy_compat.py` | 22 redirect endpoints | Wird zwar importiert in `brain_server.py`, einzelne Endpoints (`legacy_forum_history`, `legacy_token_stats`) ungenutzt |
| `brain/the_brain/web/routers/introspection.py:2904-2909` | `causal_analyze()` | Selbst markiert "not yet wired", returnt 503 |
| `scripts/demo_*.py` (Repo-Root) | 15 files | One-shot Skill-Demos, kein Test/CI nutzt sie |
| `scripts/_openclaude_profile.py`, `scripts/openclaw_browser.py`, `scripts/openfang_*.{py,cmd}` (~12 files) | Legacy-Wrapper | Ersetzt durch vibemind MCP-Server; manueller Check je File |
| `_test_remaining_pocs.py` (vibemind-os root) | POC-Test | Außerhalb tests/, kein pytest-Hook |
| `security/_test_all_pocs.py` + `security/poc_red_blue/_test_*.py` (6 files) | Debug-Skripte | `_test_`-Präfix, ad-hoc Tests |

---

## 3. UNSICHER — Architektur-Review nötig

Diese sehen ungenutzt aus, könnten aber dynamisch geladen werden (importlib, MCP-Decorator-Registrierung, String-Dispatch).

| Pfad | Risiko |
|---|---|
| `ops/poc_*/` und `security/poc_*/` (47x security, 8x system) | POCs könnten via Scheduler/Cron aufgerufen werden — `Vibemind.debug.ps1`, `infra/swarm/vibemind-stack.yml` prüfen |

---

## 3b. SICHER TOT (NEU — fungus + statisch verifiziert) — `coding-engine/src/services/*_v[23].py`

**Vorher als UNSICHER geführt, jetzt mit fungus auf GPU + Grep-Korrelation eindeutig:**

- **183 Service-Files** (178× `_v2.py`, 5× `_v3.py`), zusammen **22.584 LOC**
- In `emergent_pipeline.py` werden alle 183 als `self._xxx_v[23] = None` deklariert
- **0 echte Zuweisungen** mit Wert ≠ `None` für 178 von ihnen
- **Nur 5 Services werden je instanziiert** (in try-except-Blöcken Zeilen 6182-6603):
  - `pipeline_data_sampler_v2`, `agent_execution_tracker_v2`, `agent_task_scheduler_v2`, `pipeline_step_logger_v2`, `pipeline_step_condition_v2`
- **Aber selbst diese 5 werden nie aufgerufen** — `self._<name>.<method>()` Count = **0** für alle fünf
- **Keine** dynamische Discovery (kein importlib, kein getattr, kein Plugin-Loader); fungus_search_multi für "service discovery / importlib dynamic / getattr reflection" liefert nur Treffer für andere Systeme (openclaude TS, openclaw extensions)
- **Tests existieren** (180 `test_*_v2.py`-Files), aber `.github/workflows/ci.yml` ruft `pytest` mit `continue-on-error: true` — Failures werden ignoriert
- pytest.ini bindet keinen Filter, sammelt alles; das ist also kein Hinweis auf "lebendig"

**Konfidenz:** SICHER tot — alle 183 `_v[23].py` Service-Files (22.584 LOC) + zugehörige 180 Test-Files können weg. Anschließend in `emergent_pipeline.py` die 5 try-Blöcke (Zeilen 6182-6603) und die 183 `None`-Init-Lines aufräumen.

---

## 4. REFACTOR-Kandidaten (nicht tot, aber redundant)

**Nicht in den Lösch-Listen** — werden aktiv genutzt, aber sollten konsolidiert werden:

| Pfad | Problem | Vorschlag |
|---|---|---|
| `business/llm_client.py`, `devops/llm_client.py`, `ops/llm_client.py`, `security/llm_client.py`, `system/llm_client.py` (5 Kopien, je 204 Zeilen) | Identische Kopien von `shared/src/vibemind_shared/llm_client.py` (283 Zeilen). Jeder wird intra-package per `from .llm_client` importiert. | Auf `from vibemind_shared import get_client` umstellen, dann die 5 Kopien löschen (passt zum llm-config-migration Skill). |
| `ops/poc_red_blue/` (24 files) vs `security/poc_red_blue/` (118 files) | security/ ist Superset von ops/. Wahrscheinlich Migration ops→security. | Verifizieren, dann `ops/poc_red_blue/` löschen |
| `ops/poc_git_agents/` vs `devops/poc_git_agents/` | Doppelt | Eine Kopie wegwerfen |
| `ops/poc_docker/` vs `security/poc_docker/` | Doppelt (Pattern) | Eine Kopie wegwerfen |
| `ops/poc_log_analyzer/` vs `security/poc_log_analyzer/` | Doppelt | Eine Kopie wegwerfen |
| `ops/poc_os_shield/` vs `security/poc_os_shield/` | Doppelt | Eine Kopie wegwerfen |
| `ops/poc_security_scanner/` vs `security/poc_security_scanner/` | Doppelt | Eine Kopie wegwerfen |
| `voice/python/spaces` (Junction → `spaces/`) | Windows Junction-Link, dupliziert Funde in statischen Tools | Junction entfernen, Imports auf echte `spaces/`-Pfade umstellen (oder andersrum) |

---

## 5. Vulture-Funde (top-confidence)

**127 ungenutzte Imports + 67 ungenutzte Variablen** (≥90% Konfidenz). Auszug der häufigsten Files:

| File | Findings |
|---|---|
| `shared/tests/test_factory.py` | 8 |
| `voice/python/spaces/shuttles/swe_desgine/requirements_engineer/propagation/file_watcher.py` | 7 (in toter Subtree, s.o.) |
| `spaces/desktop/Automation_ui/backend/app/services/node_service.py` | 4 |
| `security/poc_red_blue/game_controller.py` + `ops/poc_red_blue/game_controller.py` | je 4 (s. Refactor §4) |
| `brain/the_brain/scripts/check_mamba_installation.py` | 3 |

Vollständige Liste in `/tmp/vulture_v2.txt` (200 Zeilen). Empfehlung: hochkonfidente Imports automatisiert per `autoflake --remove-all-unused-imports -i` aufräumen, Variablen manuell.

---

## 6. Empfohlene Lösch-Reihenfolge

1. **Risikofrei (Stufe 1):** Alle `.bak`-Files + `coding-engine/Data/` + `coding-engine/_archive/` → wenige Befehle, ~1.000 Files, kein Code-Risiko.
2. **Stufe 2:** `web/legacy/`-Server (6 files) + `brain/demos/` (49 files) — vorher `production/unified_brain_service.py` Docstring (Zeilen 24,26) aktualisieren.
3. **Stufe 3:** POC-Duplikate konsolidieren (§4), llm_client-Kopien auf `vibemind_shared` umstellen.
4. **Stufe 4:** `spaces/coding/Coding_engine/` — zuerst die 4 Referenzen in `coding-engine/` umstellen, dann ganzen Subtree löschen (~4.250 Files). **Größter Cleanup-Gewinn.**
5. **Stufe 5:** Vulture-Imports per autoflake, dann verbleibende UNSICHER-Kandidaten nach Architektur-Review.

---

## 7. Was nicht im Report ist

- **TS/JS Dead Code:** knip/ts-prune nicht ausgeführt (1421 TS/JS Files). Bei Bedarf separater Lauf.
- **Frontend-Komponenten:** `dashboard-app/`, `frontend/`, `electron-app/` — nicht gescannt.
- **`brain/the_brain/`-Submodule-Interna** (z.B. CTM, theory_of_mind) wurden nur grob geprüft; viel scheint aktive Forschung.
- **fungus-Cross-Checks für UNSICHER-Kandidaten:** fungus-Server fiel mid-session aus, ersatzweise per Grep validiert. Bei Bedarf erneut über fungus_search/multi für semantische Validierung.
