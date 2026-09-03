# Slash-Commands (/commands)

_Erfasst 2026-06-23. Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview
Slash-Commands sind in Claude Code aufrufbare `/name`-Befehle. Im VibeMind-Kontext liegen sie auf
**zwei Ebenen**: projektspezifische Repo-/User-Commands (`~/.claude/commands/` + `.claude/commands/`,
als Markdown-Dateien mit Frontmatter) und globale Plugin-Commands (vom Claude-Code-Harness, nicht im Repo).
Sie sind **kein Laufzeit-Service** — sie laufen in der Claude-Code-Session, steuern aber VibeMind-Infra
(MCP-Restart, Memory, Notify).

## VibeMind-eigene Commands (`~/.claude/commands/`, 8 + 1 Projekt)

### MCP-Steuerung
| Command | Zweck |
|---|---|
| **/mcp-profile** | Wechselt das aktive MCP-Profil für das Vibemind_V1-Projekt (welche MCP-Server geladen sind) |
| **/mcp-restart** | Startet den **desktop-automation** MCP-Server neu (automatisch, dann weiterarbeiten) |
| **/mcp-restart-fungus** | Startet den **fungus-search** MCP-Server neu (Code-Suche) |
| **/mcp-restart-vibemind** | Startet den **vibemind** MCP-Server neu (Launcher/Brain/Bubbles-Control) |
| **/mcp-restart-issues** | Startet den **vibemind-issue-detector** MCP-Server neu |

> Die `mcp-restart-*` nutzen ein OCR-/UI-Automations-Skript (`mcp_self_restart.py`), das den `/mcp`-Panel-
> Reconnect klickt — braucht `rapidocr_onnxruntime` im venv (sonst schlägt es fehl, siehe fungus-Session).

### Memory / Brain
| Command | Zweck |
|---|---|
| **/scan** | End-of-Session Brain-Scan: extrahiert Merkenswertes, schlägt Memory-Diffs vor, schreibt nur nach OK |
| **/memory-review** | Reviewt ausstehende Memory-Diffs von VibeMind-Agenten; bei Accept → Memory + Auto-Sync nach Rowboat |

### Notify
| Command | Zweck |
|---|---|
| **/vibemind-notify** | Sendet eine Status-Notiz an den VibeMind-Chat (Session-Zusammenfassung via Game-Console / Electron-CDP :9223). Liegt doppelt: User-Level + Projekt-`.claude/commands/` |

### Knowledge-Graph (Skill)
| Command | Zweck |
|---|---|
| **/graphify** | Jeden Input (Code/Docs/Bilder) → persistenter Knowledge-Graph mit God-Nodes + Community-Detection; bei vorhandenem `graphify-out/` Query-First. Liegt als Skill (`~/.claude/skills/graphify/`) |

## Globale Plugin-/Harness-Commands (nicht im Repo)
Aus dem Claude-Code-Plugin-System (in jeder Session verfügbar, nicht VibeMind-spezifisch):
`/loop` (Self-paced/Intervall-Tasks), `/schedule` (Cloud-Cron), `/code-review` (+`ultra`),
`/verify`, `/run`, `/simplify`, `/security-review`, `/init`, plus die Superpowers-Skills
(brainstorming, debugging, TDD, …) und Plugin-Skills (feature-dev, plugin-dev, claude-supermemory …).
Diese werden über die Skill-/Command-Registry des Harness geladen, nicht aus dem VibeMind-Repo.

## Integration points
- **MCP-Layer:** die `mcp-restart-*` + `/mcp-profile` steuern genau die MCPs aus
  [`mcp-native-layer.md`](./mcp-native-layer.md) (fungus-search, vibemind, perception, …).
- **Memory:** `/scan` + `/memory-review` schreiben in den Memory-Store
  (`~/.claude/projects/.../memory/`) + syncen nach Rowboat (→ [`rowboat.md`](./rowboat.md)).
- **Notify:** `/vibemind-notify` nutzt denselben CDP-:9223-Pfad wie die Fernsteuerung
  (→ Plan `remote-control-feature.md`).

## Vollständigkeit / Gotchas
- **/mcp-restart-* hängt an OCR-Dep:** ohne `rapidocr_onnxruntime` im venv schlägt der UI-Klick fehl
  (verifiziert). Der fungus-MCP läuft jetzt ohnehin als persistenter HTTP-Server (Launcher Phase 3) →
  `/mcp-restart-fungus` ist nur noch für den stdio-Fall relevant.
- **/vibemind-notify doppelt** (User + Projekt) — Projekt-Version überschreibt; identischer Zweck.
- Keine Commands für die neuen Profile/Stacks — Stack-Start läuft über die Launcher (`Vibemind.debug.ps1
  -Spaces …`), nicht über Slash-Commands. Ein `/start-profile <name>`-Command wäre ein sinnvoller Zusatz
  (offen).
