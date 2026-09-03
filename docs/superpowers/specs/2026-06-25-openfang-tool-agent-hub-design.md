# Design-Spec: OpenFang Tool-Agent-Hub mit zentraler MCP-Source-of-Truth

**Datum:** 2026-06-25 · **Status:** Design (freigegeben, Spec-Review offen)
**Scope:** MCP-Tool-Layer von VibeMind — Entdoppelung + prompt-getriebene Tool-Agents über OpenFang, orchestriert von Brain.

---

## 1. Ziel

1. **Eine Source of Truth** für die generischen MCP-Tools (docker, qdrant, redis, postgres, n8n, supabase, playwright, filesystem, fetch, git, time, github, brave-search, memory, tavily, context7, taskmanager, supermemory, windows-core).
2. **Redundanz töten:** derselbe Tool-MCP existiert heute 2–3× parallel (coding-engine `servers.json`, openfang-TOML, `security/poc_*`).
3. **Prompt-getriebene Nutzung:** ein Prompt rein → das richtige Tool wird mit den richtigen Werten ausgeführt.
4. **Security bleibt gesondert** — eigene Registry/Welt, NICHT im generischen Tool-Agent.

**Nicht-Ziel:** coding-engine umbauen (sie konsumiert `servers.json` schon nativ und bleibt dadurch automatisch an der Wahrheit); die security-PoCs vereinheitlichen.

---

## 1a. Design-Korrektur (bei der Implementierung 2026-06-25)

Empirisch beim Bauen gefunden: `servers.json` ist **Container/Linux** (Zeile 1: „Docker/Linux paths"), die openfang-TOML ist **Windows-Host** (`.exe`, `${HOME}`). Gleiche Tools, **unterschiedliche** `command`/`args` pro Umgebung. Die ursprüngliche Annahme „servers.json generiert die openfang-TOML 1:1" hätte die Host-Config zerschossen.

**Korrektur:** jeder Server in `servers.json` trägt **beide** Invocations — top-level `command`/`args` = Container (coding-engine, unverändert) + optionaler `host`-Block `{command,args,env}` = Windows-Host. Der Generator emittiert den **`host`-Block** in openfang-TOML + `.mcp.json` (beide laufen auf dem Host), die coding-engine nutzt weiter Container. Ein Tool erreicht die Host-Configs **nur** wenn `scope=global` UND `host`-Block vorhanden.

**Roster-Divergenz (auch gefunden):** `tavily` ist host-only (nicht im Container-Registry → mit `active:false` aufgenommen, host-Block aktiv). `supabase`/`desktop`/`supermemory`/`n8n` sind container-only und brauchen erst ein **Host-Binary**, bevor sie dem Host-Hub beitreten können (kein `host`-Block = nicht generiert). `.mcp.json` ist gitignored = lokales generiertes Artefakt.

---

## 2. Ist-Zustand (verifiziert)

Drei parallele Registries desselben Tool-Satzes:

| Registry | Form | Server | Konsument |
|---|---|---|---|
| `coding-engine/mcp_plugins/servers/servers.json` | JSON + `servers/<tool>/agent.py` (AutoGen-Adapter) + per-Projekt `.mcp-config.json` | 22 | coding-engine `MCPAgentPool.spawn(tool, task)` |
| `openfang.vibemind.toml(.template)` | TOML `[[mcp_servers]]` | ~35 | OpenFang-Hub `:4200/mcp` (Brain, Claude-Session via `mcp_stdio_bridge.py`) |
| `security/poc_*` | je eigener `mcp_server.py` + agent | 43 (davon ~22 Tool-Spiegel) | nur standalone `_test_*`-Skripte |

`qdrant`, `redis`, `playwright`, `time`, `filesystem`, `fetch`, `git`, `postgres`, `memory`, `tavily`, `context7`, `taskmanager` etc. liegen in 2–3 davon parallel.

**Skills-System (Vorbild für den Prompt-Store):** `skills/_indexer.py` upsertet jede `SKILL.md` in die Qdrant-Collection `vibemind_skills` (OpenAI `text-embedding-3-small`, 1536d, Cosine; Point-ID = stabiler sha1(Pfad)); Payload trägt `name/description/app/agents/trigger/confidence/attempts/successes`; `search(query, agent, limit)` filtert nach Agent-Sichtbarkeit. Adaptive Stats (confidence/attempts/successes) reinforced den Treffer.

---

## 3. Ziel-Architektur

Zwei getrennte Wahrheits-Ebenen (Infra vs. Kognition), zusammengeführt zur Laufzeit über Brain:

```
 EBENE 1 — Tool-Infra (WIE man den MCP spawnt)
   servers.json  ──mcp-sync──►  openfang.vibemind.toml [GENERIERTER Block]
   (Config-Wahrheit)       └──►  .mcp.json (Claude-Session)
        │                        (handgepflegt bleibt: brain, navigator,
        │                         spaces-ideas, security, system)
        ▼
   OpenFang-Hub :4200  ──►  X Tool-Agents (1 MCP-Tool je, generiert)

 EBENE 2 — Agent-Kognition (WAS der Agent tun soll)
   Supabase  `agent_prompts`  ◄── handgepflegte Prompt-Schablonen + Slot-Schema
        │  prompt-indexer (Spiegel von _indexer.py)
        ▼
   Qdrant  `vibemind_agent_prompts`  (semantischer Index der Schablonen)

 LAUFZEIT — Brain = Meta-Orchestrator
   Prompt ─► Brain.multihop_execute
              1. semantic-search `vibemind_agent_prompts` → Tool-Agent + Schablone
              2. lade Schablone aus Supabase `agent_prompts`
              3. RESOLVE Slots gezielt: kg_search + Vorschritt-Ergebnis + Config
                 (z.B. docker → "welches Image?" via kg_search/inspect)
              4. render strukturierte Prompt mit dyn. Values
              5. dispatch ► OpenFang Tool-Agent (POST /api/agents/<tool>/message)
              6. Ergebnis → nächster Hop oder Rückgabe
              7. update confidence/attempts/successes (adaptiv)
```

**Kernprinzipien:**
- **X Tool-Agents, kein Mega-Agent.** Jeder Agent hat genau 1 MCP-Tool → keine Disambiguierung, kein 71-Tool-Loop (vermeidet die ToolScopeSelector-Krücke auf Tool-Ebene).
- **Slots = Kontext-Kontrakt.** Die benannten Slots der Schablone sagen Brain exakt, welchen Kontext es liefern muss — „gezielt", nicht „alles reinkippen".
- **Brain liefert Kontext, nicht der Tool-Agent.** Der Tool-Agent ist dumm/fokussiert; Brain beschafft die Daten (kg_search, Hops, Config) und füllt die Slots.

---

## 4. Komponenten

### C1 — `servers.json` als Tool-Infra-Wahrheit
- **Zweck:** einzige handgepflegte Registry der MCP-Spawn-Definitionen (command/args/env/transport) für den generischen Tool-Layer.
- **Interface:** JSON-Liste; je Eintrag `{ key, command, args, env, transport, scope: "global"|"coding-only" }`. `scope` markiert coding-spezifische (npm, prisma, claude-code, dev, tests, fungus_mcp) → NICHT in den Hub generiert.
- **Ort:** Entscheidung — bleibt zunächst `coding-engine/mcp_plugins/servers/servers.json` (Minimal-Disruption), Option später nach `shared/mcp/servers.json` zu heben (coding-engine `MCPRegistry` repointet dann nur den Pfad).
- **Deps:** keine.

### C2 — `mcp-sync` Generator
- **Zweck:** schreibt aus `servers.json` (Einträge mit `scope: global`) (a) den Tool-`[[mcp_servers]]`-Block der openfang-TOML und (b) `.mcp.json`.
- **Interface:** `python tools/mcp_sync.py [--check]`. Idempotent. Schreibt NUR zwischen Marker-Kommentaren (`# >>> generated:tools` … `# <<< generated:tools`); alles außerhalb (brain, navigator, security, system) bleibt unangetastet.
- **Verifikation:** `--check` = CI-Gate, schlägt fehl wenn TOML/`.mcp.json` vom Generat abweichen (verhindert Hand-Drift).
- **Deps:** C1.

### C3 — Tool-Agents im OpenFang-Hub
- **Zweck:** je generischem Tool ein fokussierter OpenFang-Agent mit genau diesem 1 MCP-Tool gescoped.
- **Interface:** OpenFang-Agent `tool-<name>` (z.B. `tool-docker`); `POST /api/agents/tool-<name>/message` mit der gerenderten strukturierten Prompt; gibt JSON zurück.
- **Registrierung:** generiert/idempotent über OpenFang-API (POST Agent → PUT Tool-Scope → restart; Achtung Memory-Gotcha: PATCH droppt system_prompt → fresh POST). System-Prompt = die generische Schablone aus C4.
- **Deps:** C2 (TOML), C4 (Schablone).

### C4 — Prompt-Store: Supabase `agent_prompts` + Qdrant `vibemind_agent_prompts`
- **Zweck:** kanonischer, durchsuchbarer Speicher der Agent-Prompt-Schablonen — modelliert nach dem Skills-System.
- **Supabase `agent_prompts` (Wahrheit, strukturiert):**

  | Spalte | Typ | Bedeutung |
  |---|---|---|
  | `id` | uuid | PK |
  | `tool` | text | = `servers.json`-Key (FK-Konzept zur Infra-Ebene) |
  | `agent_name` | text | `tool-<name>` |
  | `description` | text | wofür (für Embedding) |
  | `trigger` | text | wann (für Embedding) |
  | `prompt_template` | text | generische Schablone mit `{slots}` |
  | `slots` | jsonb | `{ name: {type, source: prompt\|kg\|hop\|config, required} }` = Kontext-Kontrakt |
  | `output_schema` | jsonb | erwartetes Rückgabe-Format |
  | `visibility` | text[] | welche Meta-Agents/Caps (analog skills `agents`, inkl. `*`) |
  | `confidence`/`attempts`/`successes` | float/int/int | adaptiv (wie skills) |
  | `last_adjusted`/`updated_at` | timestamptz | |

- **Qdrant `vibemind_agent_prompts` (Index):** Spiegel von `_indexer.py` — embed(`description + trigger + tool`), Payload = Kernfelder + `supabase_id`, Point-ID = stabiler sha1(`tool`). `search(query, visibility, limit)`.
- **Deps:** Supabase (core), Qdrant (core, :6340).

### C5 — `prompt-indexer`
- **Zweck:** Supabase-Rows → Qdrant upserten; direkter Spiegel von `skills/_indexer.py` (gleiche embed/ensure_collection/upsert/search-Struktur, Quelle = Supabase statt SKILL.md).
- **Interface:** `python tools/prompt_indexer.py --rebuild | --tool docker | --search "<query>"`. Aufgerufen nach Schablonen-Edit + vom Meta-Agent nach Lernen (confidence-Update).
- **Deps:** C4.

### C6 — Brain Meta-Orchestrator
- **Zweck:** der eine Prompt-Eingang; beschafft gezielt Kontext und dispatcht an Tool-Agents.
- **Interface:** bestehendes `multihop_execute` (der reale Cap-Pipeline-Entry, Memory). Erweiterung: ein Resolver-Schritt der (1) `vibemind_agent_prompts` durchsucht, (2) Slots aus `kg_search` + Hop-Ergebnissen + Session/Projekt-Config füllt, (3) die strukturierte Prompt rendert, (4) an `tool-<name>` dispatcht, (5) Stats zurückschreibt.
- **Deps:** C3, C4, C5, bestehendes Brain `kg_search`/`multihop_execute`.

---

## 5. Datenfluss (E2E-Beispiel)

Prompt: **„deploy nginx als container"**
1. Brain `multihop_execute` → embed → `vibemind_agent_prompts`-Search → Treffer `tool-docker` (Schablone „du bist der docker-Tool-Agent, nutze NUR das docker-MCP …").
2. Lade Schablone + Slots aus Supabase: Slots = `{ image:{source:kg, required}, name:{source:prompt}, ports:{source:kg, required:false} }`.
3. Resolve: `image` → `kg_search("welches nginx image standard")` → `nginx:alpine`; `name` → aus Prompt; `ports` → Default/KG.
4. Render: „Starte einen Container aus Image `nginx:alpine` namens `nginx` …".
5. `POST /api/agents/tool-docker/message` → Agent ruft docker-MCP `run` auf → JSON-Ergebnis.
6. Ergebnis zurück an Brain → ggf. nächster Hop (z.B. `tool-site-verifier` Health-Check) → Antwort.
7. `successes++`, `confidence`-Update via `prompt-indexer`.

---

## 6. De-Dup / Migration

- **Kanonisch:** `servers.json` (generischer Tool-Layer). `scope`-Feld trennt global vs. coding-only.
- **Generiert (kein Hand-Edit mehr):** openfang-TOML-Tool-Block, `.mcp.json`.
- **Gelöscht:** die ~22 `security/poc_*`-**Tool-Spiegel** (filesystem, github, postgres, qdrant, supabase, redis, n8n, playwright, tavily, context7, brave_search, fetch, time, memory, supermemory, taskmanager, windows_core, desktop, grpc_host, git, fungus_mcp).
- **Unverändert:** coding-engine (konsumiert `servers.json` nativ).
- **Gesondert (Security, NICHT angefasst):** die echten Defensiv-PoCs (network_monitor, firewall, event_log, botnet_detector, endpoint_hardening, site_verifier, vuln_scanner, forensics, canary, red_blue, os_shield, alerter, injection_chain, captcha_eval, …) bleiben eigene Registry/Welt; die 6 schon im Hub bleiben wie sie sind.

---

## 7. Security-Abgrenzung

Der generische Tool-Agent-Hub und die Security-PoCs sind **getrennte Registries**. Security-Tools werden NIE über den `mcp-sync`-Generator oder den `agent_prompts`-Store geführt. Begründung: andere Risikoklasse, andere Sichtbarkeit, eigene Audit-Anforderungen (Memory: sensible Sozialdaten/Security gesondert).

---

## 8. Error-Handling & Testing

- **Generator-Drift:** `mcp-sync --check` + `prompt-indexer` als CI-Gate.
- **Slot-Resolve-Fehler:** required-Slot nicht auflösbar → Brain bricht den Hop ehrlich ab (kein Raten), filed Gap (bestehendes GapSentinel-Muster).
- **Tool-Agent-Ausfall:** OpenFang `OpenFangUnavailable` + bounded retry (bestehendes Muster).
- **Ground-Truth:** Erfolg eines Tool-Calls NUR aus unabhängiger Verifikation (Memory: nie Op-Selbstbericht) — z.B. docker-run → `docker ps`-Re-Query, nicht „nicht geworfen".
- **Tests:** (a) `mcp-sync` Round-Trip (servers.json → TOML/.mcp.json deterministisch); (b) `prompt-indexer` search-Treffer; (c) E2E 1 Tool-Agent live über OpenFang (echter MCP-Call + Ground-Truth-Verify); (d) Brain Slot-Resolve mit kg_search-Mock-frei (No-Mocks).

---

## 9. Entscheidungen (Default, überschreibbar) & Risiken

**Entscheidungen mit Default — damit der Plan eindeutig ist:**
1. **`servers.json`-Ort:** bleibt zunächst `coding-engine/mcp_plugins/servers/` (Minimal-Disruption); Move nach `shared/mcp/` ist eine optionale Folge-Phase (nur Pfad-Repoint in `MCPRegistry`).
2. **Brain-Resolver:** neuer **flag-gated** Schritt in `multihop_execute` (Default, analog Routing-Production-System) — kein eigener Service, kill-switchbar.
3. **Slot-`source`:** `prompt` → `hop` → `config` → `kg` in dieser Reihenfolge; ein nicht-auflösbarer **required**-Slot fällt auf `source: ask` (Rückfrage an den Aufrufer) zurück, **nie** Raten.

**Zu verifizieren während der Umsetzung (Risiken):**
4. **OpenFang-Agent-Generierung:** Idempotenz gegen die PATCH-droppt-system_prompt-Gotcha (fresh POST + Scope-PUT + restart).
5. **Live-vs-Template-Config:** `~/.openfang/config.toml` (live) liegt außerhalb Repo — der Generator muss das echte Ziel schreiben, nicht nur `.template`; Marker-Region dort anlegen.
6. **`kg_search`-Zuverlässigkeit:** liefert es Werte wie „welches Image" robust? Falls nicht → `source: ask`-Fallback greift (siehe #3).
