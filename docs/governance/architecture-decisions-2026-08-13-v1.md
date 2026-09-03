# V1 Architekturentscheidungen — 2026-08-13

**Status:** entschieden, umsetzungspendent
**Referenz:** `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T16:12:00Z`
**Anlass:** Das Cockpit `cockpit-brain` hat seinen Repo-first-Audit abgeschlossen und fünf offene Architekturfragen an den User eskaliert. Vier davon sind hier entschieden; die fünfte liegt beim Cockpit `cockpit-channels`.

Dieses Dokument hält die Entscheidungen fest und leitet die Umsetzungstasks ab. Es ändert selbst **keinen** Vertrag: die Anpassung von `docs/contracts/*`, Schemas und Routing erfolgt ausschließlich in den abgeleiteten, separat geprüften Tasks. Bis deren Merge bleibt der dokumentierte Ist-Zustand gültig.

## Ausgangslage

Die Fragen entstanden aus belegten Widersprüchen zwischen Vertragsebene, Design-Spec und gemessenem Laufzeitverhalten. Die Belege stammen aus einer Recherche im Superproject; das Submodul `vibemind-os` war dabei nicht ausgecheckt, weshalb alle Aussagen über Registry-, Router- und Agent-Code **referenziert, nicht verifiziert** sind. Jeder abgeleitete Task muss seine Grundlage aus frischer Repository-Evidence bestätigen.

## E1 — Agent-Selection-Autorität: zweistufig

**Frage:** Wer wählt den ausführenden Space-Agenten?

**Konflikt:** `docs/contracts/brain-openfang-handoff-v1.md` sagt „OpenFang alone may later select agents, tools, and providers". `intent_validation/00_MASTER.md` hält als gemessenen Befund fest: „Brain wählt den Spezialagenten via `execution_target` — OpenFang ist KEIN Selektor". `docs/superpowers/specs/2026-07-30-v1-space-orchestration-design.md` beschreibt eine dritte Variante: Brain plant Rollen, OpenFang löst sie auf.

**Entscheidung (Empfehlung des Orchestrators, vom User zur Entscheidung delegiert):** **zweistufig**. Brain benennt die kanonische **Agent-Rolle**; OpenFang bindet sie an eine konkrete **Instanz, einen Provider und ein Modell**.

**Begründung:** Diese Variante versöhnt beide Quellen, ohne einen der bestehenden Verträge zu brechen. `execution_target` bleibt als Feld erhalten — nur seine Semantik wird präzisiert (Rolle statt Instanz), was den Routing-Umbau heute vermeidet. Gleichzeitig bleibt OpenFang alleiniger Eigentümer von Provider-, Kosten- und Instanzentscheidungen, wie es die Execution-Boundary verlangt. Die Alternative „Ist-Zustand legalisieren" wäre billiger, hätte aber eine Breaking-Contract-Änderung an `brain-openfang-handoff-v1.md` erzwungen; die Alternative „OpenFang selektiert vollständig" wäre der reinste, aber teuerste Weg und hätte `execution_target` entfernt.

**Nicht entschieden:** ob Rollen aus `space_agent_registry.yml` oder aus `capabilities.yaml` stammen. Beide Quellen existieren nebeneinander; die Vereinheitlichung gehört in den abgeleiteten Task.

## E2 — Arch-Gap-Dispatch: OpenClaude als Ziel, bis dahin fail-closed

**Frage:** Was passiert mit Capabilities, die korrekt klassifizieren, aber kein `execution_target` haben?

**Befund:** `security_scan`, `log_analysis`, `site_check`, `incident_response`, `code_search`, `knowledge_query` und `email_action` klassifizieren korrekt, dispatchen aber nicht. Der Nutzer erhält laut `intent_validation/00_MASTER.md` eine „hohle Apologie" — die Aktion findet nie statt. „Scan for keys" über Telegram bewirkt faktisch nichts.

**Entscheidung (User):** Diese Capabilities sollen über **OpenClaude** ausgeführt werden.

**Verbindliche Zwischenstufe:** Bis die OpenClaude-Anbindung real verdrahtet, allowlisted und mit korreliertem Readback belegt ist, antwortet das System **fail-closed** — explizit „nicht verfügbar" mit Grund, niemals eine Entschuldigung, die eine Ausführung suggeriert. Das entspricht `docs/ARCHITECTURE.md` (kein Target → Reject) und dem Fallback-Verbot.

**Zu prüfen:** OpenClaude liegt als Submodul `vibemind-os/openclaude` und ist lokal nicht ausgecheckt. Ob es die genannten Capabilities tatsächlich abdeckt — insbesondere `email_action` mit externem Versand und `security_scan` — ist **unbelegt** und muss vor jeder Verdrahtung geprüft werden. Externe Sends und Security-Scans bleiben eigenständig autorisierungspflichtig; diese Entscheidung erteilt dafür keine Freigabe.

## E3 — Multi-Verb-Dekomposition: immer

**Frage:** Ab wann wird ein Intent mit mehreren Verben dekomponiert?

**Befund:** „Mach erst A, dann B, dann C" läuft heute als 1-Hop-Plan. Die Testerwartung in `intent_validation/cat0_routing_sanity.json` fordert `expect_level: "hard"`, also den SoM-Planer. `docs/contracts/brain-plan-v1.md` erlaubt Task-DAGs, während `docs/contracts/brain-openfang-handoff-v1.md` pro Handoff genau einen Plan-Node überträgt.

**Entscheidung (User):** **immer** dekomponieren. Ab zwei unabhängigen Verben erzeugt Brain einen mehrstufigen Plan über den hard/SoM-Pfad; die Task-DAG wird Node für Node an OpenFang übergeben.

**Konsequenz:** Vorhersagbares Verhalten und korrekte Reihenfolge-Semantik, erkauft mit höherer Latenz und höheren Kosten bei einfachen Ketten. Die Definition von „unabhängiges Verb" (Abgrenzung zu Adverbialen und Aufzählungen innerhalb eines Verbs) gehört in den abgeleiteten Task und braucht Testfälle.

## E4 — Non-Space-Intents: eigener Space

**Frage:** Wie werden Smalltalk, Wissensfragen und Meta/Reject im Plan-Modell abgebildet?

**Befund:** Diese Kategorien existieren real und sind getestet (`routed_via: "easy-chat"`, `actual_target: "(none)"`, Kategorie 0 geschlossen 7/7). `shared/contracts/schemas/brain-plan-v1.schema.json` verlangt aber `participating_spaces` mit `minItems: 1`, und der Space-Enum kennt nur die kanonischen Spaces. Ein Intent ohne Space ist damit nicht als Plan darstellbar.

**Entscheidung (User):** ein **eigener Space** für diese Kategorien. Smalltalk, Wissensfragen, Meta und Reject laufen über einen dedizierten, kanonisch registrierten Space statt über eine Schema-Lockerung.

**Nachtrag (User, `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-14T13:45:00Z`):** Der Space heißt **`system`**. Der Name wird kanonische Registry-Identität im Umsetzungstask `task-brain-0020-non-space-space-registration-v1`.

**Konsequenz und Auflage:** Der neue Space durchläuft den vollständigen Prozess aus `docs/SPACES.md` („Adding or changing a Space"): Registry-Identität, Event-Kontrakt, Agent, MCP-Allowlist, Tests, Katalogeintrag. Er ist ausdrücklich ein Space **ohne** externe Mutationen und ohne eigene Datenhoheit. Wichtig: Das Plan-Schema bleibt unverändert — genau das ist der Vorteil dieser Variante gegenüber `minItems: 0`. Der Name des Space ist noch offen und wird im Umsetzungstask mit dem User festgelegt.

## E5 — HTTP-Intent-Kanal: offen, beim Channels-Cockpit

Der getestete Intent-Eingang `POST :5000/api/multihop/execute` hat keine Entsprechung in `docs/contracts/channel-intent-v1.md`, das `channel_kind` auf `voice | desktop-chat | openclaw | space-chat` schließt. Ob dieser Eingang ein vertraglich definierter Kanal wird oder Test-Harness bleibt, bereitet `cockpit-channels` als Entscheidungsvorlage vor. Bis dahin gilt: kein vertraglicher HTTP-Kanal.

## Abgeleitete Tasks

Alle vier Tasks sind freigabe- und umsetzungspendent. Sie ändern Verträge, Schemas oder Routing und sind damit **keine** Routine-`docs`/`code`-Arbeit unter der Maintenance-Delegation: jeder braucht eine eigene Risikoklassifikation, und die Breaking-Contract-Anteile brauchen request-spezifische Authority.

| Task | Entscheidung | Parent-Cockpit | Risiko |
|---|---|---|---|
| `task-brain-0018-agent-role-selection-contract-v1` | E1 | `cockpit-brain` | breaking-contract (Handoff-Semantik) |
| `task-integration-0007-archgap-failclosed-then-openclaude-v1` | E2 | `cockpit-integration` | zweistufig: fail-closed ist `code`; OpenClaude-Anbindung braucht Runtime-Authority |
| `task-brain-0019-multi-verb-decomposition-v1` | E3 | `cockpit-brain` | `code` plus Testerwartungs-Abgleich |
| `task-brain-0020-non-space-space-registration-v1` | E4 | `cockpit-brain` | neuer Space nach `docs/SPACES.md`, berührt Registry und Kataloge |

Der Orchestrator legt diese Tasks den zuständigen Cockpits zur Verfeinerung vor. Die Cockpits präzisieren Scope, Tests und Definition of Done; erst danach entstehen Session-Requests.
