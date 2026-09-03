# Design: `mcp/docker/` — Docker-CLI-MCP-Server

**Datum:** 2026-06-04
**Status:** Genehmigt (Brainstorming abgeschlossen)

## Ziel

Ein Python-FastMCP-stdio-Server, der die **Docker-CLI** als explizit benannte MCP-Tools
ausschreibt. Jeder relevante Docker-Befehl wird ein eigenes Tool mit klarer Beschreibung
und typisierten Parametern — die AI wählt anhand des Tool-Namens, nicht anhand von
CLI-Wissen.

Erreichbar für **beides**:
- **Claude Code** direkt (stdio-Eintrag)
- **Brain/OpenFang-Agenten** über `mcp_stdio_bridge.py` am OpenFang `:4200/mcp`-Hub
  (kein per-Agent-MCP-Eintrag — folgt dem Aggregator-Pattern des Projekts)

## Schlüssel-Entscheidungen

| Entscheidung | Wahl | Begründung |
|---|---|---|
| Backend | **Nur `docker` CLI-Subprozess** (kein docker-py SDK) | Ein mentales Modell, spiegelt das Swarm/Stack-Setup 1:1, keine Engine-API-Versionsfalle, keine extra Dependency. compose/build sind ohnehin nur als CLI-Plugins verfügbar. |
| Scope | Voll: container/image/network/volume/compose/stack/system | Deckt den realen Vibemind-Swarm-Workflow ab. |
| Sprache | **Python + FastMCP** | Konsistent mit bestehenden MCP-Servern im Projekt. |
| Ort | **`mcp/docker/`** — eigenes abgegrenztes Paket im Repo-Root | Sauber getrennt, eigenes README + pyproject, im Haupt-Repo versioniert (nicht im Submodule). |
| Safety | **Read frei, Write In-Tool-Approval** | Read-Tools laufen ohne Rückfrage; State-ändernde Tools brauchen Approval, das den exakten Befehl zeigt. |

## Vorhandener Code (recherchiert 2026-06-04)

Es gibt **keinen** nutzbaren Docker-MCP im Repo, aber wiederverwertbare Substanz:

- **`vibemind-os/ops/mcp/servers.json`** registriert einen Server `"docker"` →
  `python -m mcp_server_docker` (`active: true`), aber das Modul **existiert nicht**
  (weder im Repo noch als installiertes pip-Paket). **Toter Registry-Eintrag** — würde
  beim Start mit `ModuleNotFoundError` scheitern. → Im Plan aufräumen/auf unseren Server
  umbiegen.
- **`vibemind-os/spaces/coding/Coding_engine/mcp_plugins/servers/docker/agent.py`**
  (793 Zeilen) ist ein **autogen-Agent** (kein MCP), gehört zur Coding_engine. Aber er
  enthält erprobten Docker-CLI-Code, den wir recyceln:
  - `_run_docker_cmd(args, timeout)` — subprocess-Pattern, deckt unsere drei Fehlerklassen
    bereits ab (Timeout / FileNotFound / generisch). Kommentar im Code: *"avoids SDK
    compatibility issues"* — unabhängige Bestätigung unserer CLI-only-Entscheidung.
  - **Windows-Fixes:** `sys.stdout.reconfigure(encoding='utf-8')` (UTF-8-Konsole) — direkt
    übernehmen.
  - Konkrete Tool-Signaturen als Referenz: `list_containers(all)`, `container_logs(id, tail)`,
    `run_container(image, name, ports, env, detach)`, `docker_compose_up/down/ps(...)`.

**Recycling-Strategie:** `mcp/docker/` wird eigenständig neu gebaut (FastMCP-stdio,
nicht an Coding_engine gekoppelt), übernimmt aber das `_run_docker_cmd`-Pattern, den
UTF-8-Encoding-Fix und die Parameter-Formen als Vorlage.

**Sicherheitshärtung (Abweichung vom Vorbild):** `docker/agent.py` nutzt auf Windows
`shell=True` mit `" ".join(cmd)` — das ist **command-injection-anfällig**, sobald ein
Argument (Container-Name, `exec`-Command) Leerzeichen/Sonderzeichen enthält. Da unser
MCP auch von Agenten aufgerufen wird, läuft `docker_cli.run()` **ohne `shell=True`**: die
Argumentliste wird direkt als Array an `subprocess.run` übergeben (kein String-Join). Der
UTF-8-Fix wird über die explizite Subprocess-`encoding`/`env` statt über die Shell gelöst.

## Architektur

```
                    ┌──────────────────────────────┐
   Tool-Call  ──►   │  server.py (FastMCP, stdio)  │
                    │  Read frei / Write gated     │
                    └───────────────┬──────────────┘
                                    ▼
                    ┌──────────────────────────────┐
                    │  docker_cli.py               │
                    │  - run(args, ...) Subprozess │
                    │  - --format json Parsing     │
                    │  - Timeout / Fehler-Mapping  │
                    └───────────────┬──────────────┘
                                    ▼
            docker / docker compose / docker stack  (CLI)
```

`docker_cli.py` ist das **einzige** Modul, das Subprozesse startet. `server.py` ist eine
dünne Schicht: jedes Tool baut nur seine Argumentliste und delegiert an `docker_cli.run(...)`.
Kein Tool enthält Logik außer Argument-Mapping.

## Tool-Liste (~40 Tools)

🟢 = read (approval-frei) · 🔴 = write (In-Tool-Approval)

### Container
| Tool | Docker-Befehl | R/W |
|---|---|---|
| `container_ls` | `docker ps [-a]` | 🟢 |
| `container_inspect` | `docker inspect <id>` | 🟢 |
| `container_logs` | `docker logs [--tail N] [--since] <id>` | 🟢 |
| `container_stats` | `docker stats --no-stream` | 🟢 |
| `container_top` | `docker top <id>` | 🟢 |
| `container_start` | `docker start <id>` | 🔴 |
| `container_stop` | `docker stop <id>` | 🔴 |
| `container_restart` | `docker restart <id>` | 🔴 |
| `container_rm` | `docker rm [-f] <id>` | 🔴 |
| `container_exec` | `docker exec <id> <cmd>` | 🔴 |

### Images
| Tool | Befehl | R/W |
|---|---|---|
| `image_ls` | `docker images` | 🟢 |
| `image_inspect` | `docker image inspect <ref>` | 🟢 |
| `image_history` | `docker history <ref>` | 🟢 |
| `image_pull` | `docker pull <ref>` | 🔴 |
| `image_rm` | `docker rmi [-f] <ref>` | 🔴 |
| `image_build` | `docker build -t <tag> <ctx>` | 🔴 |

### Networks & Volumes
| Tool | Befehl | R/W |
|---|---|---|
| `network_ls` | `docker network ls` | 🟢 |
| `network_inspect` | `docker network inspect <name>` | 🟢 |
| `volume_ls` | `docker volume ls` | 🟢 |
| `volume_inspect` | `docker volume inspect <name>` | 🟢 |

### Compose
| Tool | Befehl | R/W |
|---|---|---|
| `compose_ps` | `docker compose ps` | 🟢 |
| `compose_logs` | `docker compose logs [--tail N]` | 🟢 |
| `compose_config` | `docker compose config` | 🟢 |
| `compose_up` | `docker compose up -d` | 🔴 |
| `compose_down` | `docker compose down` | 🔴 |
| `compose_restart` | `docker compose restart [svc]` | 🔴 |
| `compose_build` | `docker compose build` | 🔴 |

### Swarm / Stack (Vibemind-Stack)
| Tool | Befehl | R/W |
|---|---|---|
| `stack_ls` | `docker stack ls` | 🟢 |
| `stack_ps` | `docker stack ps <stack>` | 🟢 |
| `stack_services` | `docker stack services <stack>` | 🟢 |
| `service_ls` | `docker service ls` | 🟢 |
| `service_logs` | `docker service logs [--tail N] <svc>` | 🟢 |
| `service_inspect` | `docker service inspect <svc>` | 🟢 |
| `stack_deploy` | `docker stack deploy -c <file> <stack>` | 🔴 |
| `stack_rm` | `docker stack rm <stack>` | 🔴 |
| `service_scale` | `docker service scale <svc>=<n>` | 🔴 |
| `service_update` | `docker service update <svc>` | 🔴 |

### System
| Tool | Befehl | R/W |
|---|---|---|
| `system_info` | `docker info` | 🟢 |
| `system_df` | `docker system df` | 🟢 |
| `version` | `docker version` | 🟢 |
| `system_prune` | `docker system prune` (ohne `--volumes`) | 🔴 |

**Bewusst weggelassen:** kein generischer `docker_raw(args)`-Fallback. Die AI soll immer
ein benanntes Tool wählen. Fehlt ein Befehl, wird ein neues Tool ergänzt.

## Result-Shape

Jedes Tool gibt dieselbe vorhersehbare Struktur zurück:

```jsonc
{
  "ok": true,                 // false bei non-zero exit
  "command": "docker ps -a",  // was tatsächlich lief (Transparenz)
  "data": [ ... ],            // geparstes JSON wenn --format json ging, sonst null
  "stdout": "…",              // roher stdout (immer da, falls data null)
  "stderr": "…",              // nur befüllt bei Bedarf
  "exit_code": 0
}
```

**Parsing-Regel:** Befehle mit `--format '{{json .}}'` (Listen, je Zeile ein JSON-Objekt)
oder `--format json` werden zu `data` geparst. `inspect`-Befehle liefern nativ ein
JSON-Array → direkt in `data`. Schlägt das Parsing fehl, bleibt `data: null` und der
rohe `stdout` ist trotzdem da — nie stiller Datenverlust.

## Fehlerbehandlung (drei Klassen)

1. **Docker nicht erreichbar** (Daemon down / Pipe weg) → `ok:false`, klare Message
   `"docker daemon not reachable"`. Jeder Call hat einen **Timeout (default 30s)**, damit
   ein hängender `docker ps` den MCP nicht blockiert (vgl. WSL-Mirrored-Hang im Projekt).
2. **Befehl schlägt fehl** (exit ≠ 0) → `ok:false`, `stderr` durchgereicht, kein Crash.
3. **Approval verweigert** (🔴-Tools) → sauberer `"approval denied by user"`-Return,
   keine Teil-Ausführung.

## Approval-Mechanismus

Die 🔴-Write-Tools rufen vor der Ausführung einen In-Tool-Approval-Hook (analog zum
`document`-MCP mit dynamischem pfad-basiertem Approval). Der Approval-Prompt zeigt **den
exakten Befehl**, der laufen würde — z.B. `docker stack rm vibemind` ist vor der Ausführung
sichtbar. Kein zusätzlich getippter Stack-Name nötig.

**Offen für den Implementierungsplan:** Die konkrete Approval-Mechanik bei einem
stdio-Server. Ein stdio-MCP hat keinen interaktiven UI-Prompt-Kanal — das `document`-MCP
löst das über einen pfad-basierten Approval-Store. Der Plan klärt, ob `approval.py` denselben
Store-/Allowlist-Ansatz übernimmt oder die MCP-Elicitation-Capability nutzt. Bis dahin gilt
als Fallback: 🔴-Tools führen nur aus, wenn ein Approval-Token vorliegt, sonst Rückgabe
`"approval denied by user"`.

## Paketstruktur

```
mcp/docker/
├── README.md            # Zweck, Tool-Liste, stdio + OpenFang-Bridge Setup
├── pyproject.toml       # fastmcp Dependency, entry-point
├── server.py            # FastMCP-Instanz + alle ~40 @mcp.tool Definitionen
├── docker_cli.py        # run(args, timeout, parse_json) Subprozess-Fundament
├── approval.py          # In-Tool-Approval-Hook für 🔴-Tools
└── tests/
    └── test_docker_cli.py   # mockt subprocess, prüft Result-Shape + Fehlerklassen
```

## Verifikation

- **Unit-Tests:** mocken `subprocess.run`, verifizieren Command-Bau, JSON-Parsing und die
  drei Fehlerklassen — **ohne** echtes Docker.
- **Smoke-Test:** manuell gegen die laufende Engine (29.5.2 / API 1.54) mit ein paar
  🟢-Read-Tools (`container_ls`, `stack_ls`, `version`).

## Integration

- **stdio-Eintrag** für Claude Code (in der MCP-Config).
- **OpenFang-Hub:** Registrierung über `mcp_stdio_bridge.py` am `:4200/mcp`-Hub
  (separater, manueller Schritt — kein Auto-Deploy in den Swarm).
- Beides im README dokumentiert.

## Umgebung (Stand 2026-06-04)

- Docker Engine **29.5.2 / API 1.54** läuft (Windows named pipe).
- `docker compose` **v5.1.4** verfügbar.
- `docker-py` **nicht** installiert — wird bewusst nicht gebraucht (CLI-only).
- Plattform: Windows 11, PowerShell-Shell.
