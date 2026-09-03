# Globale Slash-Commands & Plugins (Harness, nicht im Repo)

_Erfasst 2026-06-23 aus `~/.claude/plugins/installed_plugins.json` + Session-Skill-Registry.
Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md). Diese Commands kommen vom Claude-Code-Harness
bzw. installierten Plugins — NICHT aus dem VibeMind-Repo (vgl. die VibeMind-eigenen in
[`slash-commands.md`](./slash-commands.md))._

## Built-in Harness-Commands (kein Plugin)
| Command | Zweck |
|---|---|
| **/loop** | Prompt/Slash-Command wiederkehrend oder selbst-getaktet ausführen (Intervall `5m …` oder dynamisch). In dieser Session intensiv genutzt (Profil-Crawls) |
| **/schedule** | Cloud-Cron: wiederkehrende Cloud-Agenten/Routinen, laufen auch nach Session-Ende |
| **/code-review** | Diff der aktuellen Branch reviewen (low→max effort; `ultra` = Multi-Agent-Cloud-Review). `/ultrareview` = deprecated Alias |
| **/verify** | Eine Code-Änderung durch echtes App-Laufenlassen verifizieren (PR/Fix bestätigen) |
| **/run** | Die App des Projekts starten + eine Änderung live sehen (CLI/Server/TUI/Electron/Browser) |
| **/simplify** | Geänderten Code auf Reuse/Vereinfachung/Effizienz prüfen + Fixes anwenden (nur Quality, keine Bug-Jagd) |
| **/security-review** | Security-Review der pending Branch-Änderungen |
| **/init** | Neue CLAUDE.md mit Codebase-Doku anlegen |
| **/fewer-permission-prompts** | Transcripts scannen → Allowlist häufiger read-only Bash/MCP-Calls in `.claude/settings.json` |

## Installierte Plugins (12, aus 2 Marketplaces)
Quelle: `claude-plugins-official` + `supermemory-plugins`.

### Mit eigenen /commands
| Plugin | Command(s) | Zweck |
|---|---|---|
| **code-review** | `/code-review` | PR/Diff-Review (s.o.) |
| **feature-dev** | `/feature-dev` | Geführte Feature-Entwicklung mit Codebase-Verständnis + Architektur-Fokus. Agents: code-architect, code-explorer, code-reviewer |
| **plugin-dev** | `/create-plugin` | End-to-End-Plugin-Erstellung. Agents: agent-creator, plugin-validator, skill-reviewer; Skills: plugin/command/hook/mcp/skill-development |
| **claude-md-management** | `/revise-claude-md` | CLAUDE.md mit Session-Learnings aktualisieren; Skill claude-md-improver |
| **claude-supermemory** | `/index`, `/logout`, `/project-config` | Codebase in Supermemory indexieren (persistenter Kontext); Skills super-save, super-search |
| **ralph-loop** | `/ralph-loop`, `/cancel-ralph`, `/help` | „Ralph"-Loop in der aktuellen Session starten/abbrechen |

### Skill-/MCP-/Agent-only (kein eigenes Top-Level /command)
| Plugin | Liefert | Zweck |
|---|---|---|
| **superpowers** | ~20 Skills + Bootstrap | brainstorming, systematic-debugging, test-driven-development, executing-plans, writing-plans, requesting/receiving-code-review, finishing-a-development-branch, using-git-worktrees, dispatching-parallel-agents, verification-before-completion … (`using-superpowers` lädt sie) |
| **claude-code-setup** | claude-automation-recommender Skill | Codebase analysieren → Hooks/Subagents/Skills/Plugins/MCP empfehlen |
| **frontend-design** | frontend-design Skill | Distinctive, production-grade Frontend-UIs bauen |
| **security-guidance** | Auto-Security-Review (Hook) | Prüft gepushte Commits auf Schwachstellen. **In dieser Session real ausgelöst** (CDP-Origin-Bypass-Fund → gefixt) |
| **context7** | MCP `query-docs` / `resolve-library-id` | Aktuelle Lib/Framework-Doku abrufen (statt aus Trainingsdaten) |
| **playwright** | MCP `browser_*` (23 Tools) | Browser-Automation/Testing (navigate, click, snapshot, screenshot …) |

## Integration / Bezug zu VibeMind
- **/loop** + **/schedule** = die Loop-Treiber dieser Doku-Crawls (8+7 Subagenten).
- **security-guidance** hat diese Session den **CDP-RCE-Fix** ausgelöst (`remote-allow-origins *`→Loopback).
- **context7 / playwright** sind MCP-Plugins — überschneiden sich mit der VibeMind-MCP-Schicht
  ([`mcp-native-layer.md`](./mcp-native-layer.md)), kommen aber vom Harness, nicht aus dem Repo.
- **superpowers** stellt die Prozess-Skills (brainstorming→TDD→verification), die VibeMind-Coding nutzt;
  die VibeMind-eigene coding-engine hat zusätzlich ~25 lokale Skills unter `coding-engine/.claude/skills/`
  (api-generation, debugging, docker-sandbox, e2e-testing … → eigener Scope).

## Gotchas
- **Doppelte Namen:** `/code-review` + `/security-review` existieren als Built-in UND via Plugin —
  identischer Zweck, Built-in greift.
- **superpowers-Bootstrap** (`using-superpowers`) erzwingt Skill-Invocation vor jeder Antwort — daher die
  „Using [skill]"-Hinweise. Kein VibeMind-Spezifikum.
- Diese Plugin-Commands sind **maschinen-/user-global** (`~/.claude/plugins/`), gelten also in JEDEM Projekt,
  nicht nur VibeMind — anders als die `mcp-restart-*`/`scan`/`notify` aus [`slash-commands.md`](./slash-commands.md).
