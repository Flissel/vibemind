# ADR-0009 — Markdown+YAML-Manifest als Agenten-Erweiterungsformat

**Status:** Vorgeschlagen · **Kategorie:** B (übernehmen und erweitern) · **Phase:** 3
**Betrifft:** Erweiterbarkeit, Personas, Skills, Drittanbieter

---

## Goal

> Eine neue VibeMind-Agentenrolle entsteht durch **eine Markdown-Datei mit
> YAML-Frontmatter** — ohne Code-Änderung, mit strikter Validierung und
> durchgesetzten Berechtigungsgrenzen.

**Messbar erreicht, wenn:** Eine neue Rolle ist ohne Deployment installierbar; ein
Manifest mit `allowed_tools` kann die deklarierten Tools **nachweislich nicht**
überschreiten.

---

## Kontext

OpenWorker hat hier das ausgereifteste Erweiterungsformat des Vergleichsfelds
([15.5](../15-architekturvergleich.md#155-erweiterbarkeit)):

**Skill** (`skills/base.py`) = Anthropic-`SKILL.md`-Format, YAML-Frontmatter + Markdown,
mit **Progressive Disclosure**: beim Sessionstart nur Katalog (Name + Beschreibung) im
Kontext, Rumpf on demand per `load_skill(name)`.

**Persona** (`personas/manifest.py`) = `persona ⊇ skill` — dasselbe Format, mehr
Struktur: `family`, `tools` (Capability-IDs), `messaging`, `connectors`,
`default_permission_mode`, `recommended_models`, `skills`, `mcp`, `recommends`.

**Capability-Katalog** (`catalog.py`) = die stabile `id → Tool-Bundle`-Schicht, auf die
Personas verweisen, mit `requires` (Kontextvoraussetzungen) und `risk`
(für den Consent-Screen).

**Strikte Validierung:** Ein ungültiges Manifest wirft `ManifestError` statt still zu
degradieren — für Fremd-Personas genau richtig (`manifest.py:5-6`). Die ID ist auf einen
dateisystem-sicheren Slug beschränkt (kein `..`, keine Separatoren, kein `:*?"<>|`).

**Der Defekt:** `Skill.allowed_tools` wird geparst (`skills/base.py:73-80`), aber
**nirgends durchgesetzt** ([08 R-07](../08-security-risikoanalyse.md#r-07)). Ein Skill,
der `allowed-tools: read_file` deklariert, kann `run_shell` aufrufen. Das ist schlimmer
als kein Feld — es erzeugt falsches Vertrauen.

---

## Entscheidung

Format übernehmen, um VibeMind-Felder erweitern, **`allowed_tools` durchsetzen.**

```yaml
---
id: release-manager
name: Release Manager
family: knowledge
space: coding                     # NEU — VibeMind-Space-Bindung
role: supervisor                  # NEU — planner | supervisor | implementer | reviewer
tools: [files, search, git]       # Capability-IDs (aus OpenWorker)
allowed_tools:                    # NEU: WIRD DURCHGESETZT
  - local:read_file
  - mcp:github/*
mcp: [github]
skills: [changelog-writing]
default_permission_mode: interactive
model_policy:                     # NEU
  planning: claude-opus
  execution: claude-sonnet
budget:                           # NEU
  tokens: 200000
  wall_clock_s: 1800
  spend_eur: 5
escalation:                       # NEU
  on_blocked: supervisor
  on_budget_exceeded: human
recommends:
  - {kind: connector, ref: github, reason: "Releases und Tags", tier: core}
signature: "…"                    # NEU — Provenienz für Drittinstallation
---
<Markdown-Body = Systemprompt>
```

**Durchsetzung von `allowed_tools`:** Der Registry-View eines Agenten wird beim Bau
**gefiltert**. Ein nicht deklariertes Tool ist für diesen Agenten schlicht nicht
vorhanden — nicht „vorhanden, aber verboten". Das koppelt direkt an
[ADR-0007](ADR-0007-tool-registry-namespaces.md) (Rollen-Scoping) und wirkt als
Defense in Depth zusätzlich zur Policy-Engine.

**Weiter übernommen:** Progressive Disclosure (Katalog → `load_*`), strikte
Validierung mit klaren Fehlern, `recommends` für Verbindungen, slug-beschränkte IDs.

---

## Begründung

- **Markdown + YAML ist das richtige Format für prompt-lastige Artefakte.** Der
  Systemprompt *ist* der Rumpf — kein Escaping, kein JSON-Gefummel, versionierbar,
  diffbar, von Nicht-Entwicklern editierbar.
- **`persona ⊇ skill`** vermeidet zwei Formate für dasselbe Problem.
- **Progressive Disclosure ist nachweislich richtig** und sollte auch für Tools gelten
  ([ADR-0007](ADR-0007-tool-registry-namespaces.md)).
- **Capability-IDs statt roher Tool-Listen** ist die entscheidende Indirektion: Personas
  brechen nicht, wenn sich Tools ändern.
- **`allowed_tools` durchzusetzen kostet wenig** (Registry-Filter beim Bau) und
  schließt eine reale Lücke, sobald Personas aus dritter Hand installiert werden.

---

## Konsequenzen

**Positiv**
- Neue Rollen ohne Deployment.
- Versionierbar und reviewbar wie Code.
- Konsistente Struktur für Rollen, Budgets, Eskalation, Modellwahl.
- Least Privilege pro Rolle, strukturell durchgesetzt.

**Negativ / Kosten**
- **Manifest-Wildwuchs.** Viele fast identische Personas. Gegenmaßnahme: Vererbung
  (`extends: base-implementer`), die OpenWorker nicht hat.
- **Prompt-Qualität ist nicht validierbar.** Das Manifest kann strukturell korrekt und
  inhaltlich unbrauchbar sein. Gegenmaßnahme: Eval-Harness pro Persona (Phase 5.5).
- **Signaturen brauchen eine PKI.** Für interne Personas Overkill; **Empfehlung:**
  Signatur erst verpflichtend, wenn Personas aus externen Quellen installiert werden.
- Migration bestehender VibeMind-Agenten-TOMLs (OpenFang) auf das neue Format —
  oder ein Konverter.

**Risiko**
- **Persona-Installation ist Ausführung fremder Prompts.** Auch mit `allowed_tools` und
  Consent-Screen bleibt das ein Vertrauensakt. Gegenmaßnahme: Installation ist eine
  `EXTERNAL`-Aktion mit Genehmigungspflicht, der Consent-Screen zeigt die aggregierten
  Risikoklassen, und Fremd-Personas starten immer im restriktivsten Modus.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Reines Python/TOML** (OpenFang-Status quo) | Verworfen für neue Rollen: Prompt-Pflege in Code ist unhandlich. Bestehende TOMLs über Konverter migrieren |
| **JSON-Manifest** | Verworfen: mehrzeilige Prompts in JSON sind unlesbar und diff-feindlich |
| **Datenbank-gestützte Personas** | Verworfen für v1: verliert Versionierung und Review über Git. Sinnvoll erst mit einer Verwaltungs-UI, die Historie selbst führt |
| **Keine Struktur, nur Prompt-Dateien** | Verworfen: `tools`, `budget`, `role`, `allowed_tools` sind maschinell nötig |
| **`allowed_tools` weiterhin nicht durchsetzen** | Verworfen: falsches Sicherheitsgefühl ist schlimmer als gar keins |
