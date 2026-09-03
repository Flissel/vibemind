# VibeMind V1 Multi-Session-Programm — Charter v1

**Datum:** 2026-08-13
**Status:** verbindlich
**Authority-Referenz:** `claude-user-goal:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13`
**Geltungsbereich:** Session-Portfolio, Session-Erstellung, Implementierungs-Ableitung, PR-/Merge-/Verifikations-Orchestrierung für VibeMind V1.

Diese Charter dokumentiert die dauerhafte User-Anweisung vom 2026-08-13 (Goal-Direktive an die Orchestrator-Session) verbindlich. Sie bestätigt die freigegebene Architektur, bindet das vollständige Cockpit-Portfolio und verschärft die Session-Erstellungsregel. Bei Widerspruch zu älteren Formulierungen in `docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md`, `docs/governance/standing-autonomous-mandate-v1.md`, `docs/runbooks/v1-session-lifecycle.md`, `AGENTS.md` oder `CLAUDE.md` hat diese Charter für die **Erstellung von Sessions** Vorrang. Alle übrigen Regeln dieser Dokumente bleiben unverändert in Kraft.

## 1. Orchestrator-Rolle

Die Rolle des **V1 Haupt-Orchestrators** liegt bei der vom User beauftragten Orchestrator-Session (aktuell: Claude-Code-Session `session_01SdA3ftgP3wciDbcFzKw4uk`, Arbeitsbranch `claude/vibemind-v1-multi-session-qh6pao`). Die Übernahme erfolgte durch die Goal-Direktive des Users; sie überträgt die in Abschnitt 8 des Portfolio-Designs definierten Orchestrator-Verantwortungen unverändert:

- kanonische Session-Liste und Statuspflege;
- Verhinderung doppelter oder überlappender Scopes;
- Prüfung von Merge-Basen und Abhängigkeiten;
- Lesen von Handoffs und Nachforderung fehlender Evidence;
- zentrale PR-Pflege (Titel, Beschreibung, Labels, Abhängigkeiten, CI, Reviews, Konflikte);
- Merge freigegebener, grüner PRs in deklarierter Reihenfolge;
- Post-Merge- und Integrationsverifikation;
- Rückmeldung an Parent-Cockpit und User.

Der Orchestrator arbeitet für seine eigene, begrenzte `docs`-/`code`-Arbeit (Governance-Dokumente, PR-Pflege, Verifikation) unter `standing-autonomy:v1` auf seinem vom User zugewiesenen Branch. Er erstellt keine Deployments, keine destruktiven Aktionen und löscht keine Branches oder Worktrees unter Standing Autonomy.

## 2. Verbindliche Architektur

Die im Dialog freigegebene Architektur aus `docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md` ist verbindlich:

- zwei strikt getrennte Session-Ebenen: dauerhafte, interaktive, zunächst **read-only Cockpit-Sessions** und zeitlich wie fachlich begrenzte **Implementierungs-Sessions**;
- Product-Runtime-Kette `Brain -> OpenFang -> Space-Agent -> MCP/Service`; Brain bleibt Control Plane, OpenFang die einzige Execution Engine;
- Cockpits besitzen keinen schreibenden Arbeitsauftrag und erzeugen keine PRs;
- Cockpits und Implementierungs-Sessions erzeugen keine weiteren Sessions und keine unsichtbaren Wegwerf-Subagenten.

## 3. Verbindliches Cockpit-Portfolio

Das vollständige Portfolio umfasst **mindestens ein interaktives, zunächst read-only Cockpit pro fachlichem Space** sowie eigene Plattform-Cockpits. Normative Mitgliedschaft und Session-IDs sind in `docs/governance/session-portfolio-registry-v1.json` registriert (22 Cockpits zusätzlich zum Haupt-Orchestrator):

**Plattform- und Querschnitts-Cockpits (8):** `cockpit-brain`, `cockpit-shared`, `cockpit-git`, `cockpit-deployment`, `cockpit-integration`, `cockpit-observability`, `cockpit-channels` — wie in der Goal-Direktive einzeln benannt — sowie `cockpit-openfang` aus dem freigegebenen Portfolio-Design.

**Fachliche Space-Cockpits (14):** `cockpit-ideas`, `cockpit-bubbles`, `cockpit-coding`, `cockpit-desktop`, `cockpit-research`, `cockpit-n8n`, `cockpit-agentfarm`, `cockpit-schedule`, `cockpit-rowboat`, `cockpit-minibook`, `cockpit-video`, `cockpit-flowzen`, `cockpit-mirofish`, `cockpit-marketing`.

Naming-Direktive (User, `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T09:58:00Z`): Der Space **AgentFarm / AutoGen wird zu „Captain Cook"** umbenannt. Bis zum Abschluss des kanonischen Rename-Tasks (Registry, Adapter, Allowlists, Kataloge — siehe Session-Request-Queue) bleiben alle technischen Identifier unverändert: `cockpit-agentfarm`, `agentfarm`-Prefixe und Registry-IDs sind weiterhin kanonisch; „Captain Cook" ist bis dahin Anzeige-Name.

Aufträge, Erstergebnisse und Wellen-Priorisierung je Cockpit bleiben wie in Abschnitt 4 und 9 des Portfolio-Designs definiert. Eine Registry-Mitgliedschaft ist keine Aktivierungs-, Interaktivitäts- oder Live-Evidence; es gilt das Evidence-Modell aus `docs/runbooks/v1-session-lifecycle.md`.

## 4. Session-Erstellungsregel (verschärft, verbindlich)

**Jede Session wird nur nach individueller User-Freigabe erstellt.** Das gilt für Cockpit-Sessions **und** für Implementierungs-Sessions.

1. Ältere Formulierungen, nach denen Implementierungs-Sessions oder Routine-Cockpits unter `standing-autonomy:v1` ohne per-session User-Interaktion **erstellt** werden dürfen (Portfolio-Design Abschnitt 1, 6 und 13; `standing-autonomous-mandate-v1.md` „cockpit/task activation"; `AGENTS.md` „may create … bounded sessions"), sind für die Session-Erstellung durch diese Charter ersetzt.
2. `standing-autonomy:v1` bleibt unverändert gültig für die **Arbeit innerhalb bestehender, freigegebener Sessions** und für die orchestrator-eigene Routine-`docs`-/`code`-Arbeit: Audits, begrenzte Edits, Tests, Commits, Pushes, PR-Erstellung und -Pflege, grüne nicht-brechende Merges und Post-Merge-Verifikation.
3. Vor der Erstellung einer Cockpit-Session ist `python -m tools.v1_governance cockpit approval-check --repo . --cockpit <cockpit-id>` verpflichtend; die Freigabe wird im geschlossenen `docs/governance/cockpit-approval-ledger-v1.json` mit durabler Referenz geführt. Ein verweigerter oder nicht verfügbarer Check ist fail-closed.
4. Für Implementierungs-Sessions wird die individuelle Freigabe als durable Referenz im Session Request geführt (`approval_status: approved` plus benutzerbezogene `approval_reference`). Der Validator akzeptiert derzeit `codex-user-message:<thread-id>@<timestamp>` als individuelle Referenzform; eine äquivalente Referenzform für über die aktuelle Orchestrator-Session erteilte Freigaben (z. B. `claude-user-message:<session-id>@<timestamp>`) erfordert zuerst eine begrenzte `code`-Erweiterung von `tools/v1_governance` (siehe Abschnitt 7). Bis dahin gilt: keine passende Referenzform, keine Session — fail-closed.
5. Freigaben werden nicht rückwirkend erfunden, nicht aus Beobachtungen abgeleitet und nicht aus `standing-autonomy:v1` synthetisiert.

### 4a. Maintenance-Delegation (Amendment v1.1, 2026-08-13)

Durable Direktive `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T13:09:00Z` („Du sollst das komplett maintainen"): Der User delegiert die komplette Programm-Maintenance an den Haupt-Orchestrator. Damit gilt, als materielles Amendment zu Abschnitt 4:

1. **Portfolio-Aktivierung:** Die Erstellung der verbleibenden registrierten Portfolio-Cockpits ist durch diese Direktive genehmigt. Der Orchestrator trägt die per-Cockpit-Einträge mit dieser Referenz in den geschlossenen Approval-Ledger ein (das `approval-check`-Gate bleibt verpflichtend) und aktiviert nach Wellen-Reihenfolge und Kapazität.
2. **Implementierungs-Admission:** Routine-`docs`-/`code`-Implementierungs-Sessions, die repo-first aus Cockpit-Empfehlungen oder der Session-Request-Queue abgeleitet sind, admissiert der Orchestrator unter dieser Referenz ohne weitere per-Session-Nachfrage — mit unverändertem vollständigem Gate-Ablauf (Task-Brief, `session validate`, isolierter Worktree, `codex/<space>/<task-id>`-Branch, Handoff, PR-Gate, Merge nur durch den Orchestrator).
3. **Unverändert user-gated bleiben:** Deployments, destruktive Aktionen, Breaking Contracts, DB-Migrationen, Secrets, Proxmox-Mutationen, externe Sends, große Repo-Verschiebungen, Branch-/Worktree-Löschungen sowie Produkt-Architekturentscheidungen (z. B. offene Cockpit-Architekturfragen). Für diese gilt weiterhin request-spezifische Authority.
4. **Rechenschaft und Widerruf:** Der Orchestrator berichtet fortlaufend über Aktivierungen, Admissionen, Merges und Verifikationen. Der User kann die Delegation jederzeit ganz oder teilweise widerrufen; ab Widerruf gilt wieder Abschnitt 4 unverändert.

## 5. Ableitung von Implementierungs-Sessions

Aus jedem Cockpit-Backlog leitet der Orchestrator Implementierungs-Sessions ausschließlich **repo-first geprüft und separat freigegeben** ab. Verpflichtende Reihenfolge je Session:

1. **Repo-first-Prüfung:** `python -m tools.v1_governance audit --repo .`, `python -m tools.v1_governance submodules readiness --repo .` und Prüfung von Worktrees, Dirty State, Branch-Ancestry, Remote-Parität und Scope-Überlappung.
2. **Task-Brief:** vollständig nach Portfolio-Design Abschnitt 6 (Session-ID, Parent-Cockpit, durable Request-Referenz, Ziel/Nicht-Ziele, Repositories, erlaubte Pfade, Base-Ref, Branch, Worktree, Abhängigkeiten, Merge-Position, Risikoklasse, Testbefehle, Definition of Done).
3. **Individuelle User-Freigabe** nach Abschnitt 4 dieser Charter.
4. **Validierung:** `python -m tools.v1_governance session validate --repo . --request <request.json>`; Worktree-Anlage nur über `session start` (erst `--dry-run`, dann `--execute`).
5. **Isolation:** genau ein isolierter Worktree pro Repository, genau ein Branch `codex/<space>/<task-id>-<slug>`; Schreiben nur in freigegebenen Pfaden; TDD und kleine Conventional Commits; Service-Commit und Superproject-Pin getrennt.
6. **Handoff und PR:** vollständiger Handoff mit exakten Tests, Evidence, Commit-SHAs, Abhängigkeiten und Restblockern; PR-Gate über `python -m tools.v1_governance pr check --repo . --request <request.json> --handoff <handoff.json>`. Implementierungs-Sessions mergen nicht selbst und erstellen keine weiteren Sessions.

## 6. Zentrale PR-Pflege, Merge-Reihenfolge und Verifikation

PR-Pflege, Merge-Reihenfolge und Verifikation liegen ausschließlich beim Haupt-Orchestrator. Es gilt die Grundreihenfolge aus Portfolio-Design Abschnitt 10 (Git-/Session-Grundlage → Shared Contracts → Brain-Planvertrag → Brain/OpenFang Gateway → Application/Service → OpenFang Space-Agent/Adapter → Superproject-Pin → Integration/Golden Path → Deployment-Konfiguration → freigegebenes Deployment → Release-Nachweis). Ein späterer Task basiert nur auf gemergten oder ausdrücklich als gestapelt genehmigten Abhängigkeiten. Post-Merge-Verifikation und Rückmeldung an Parent-Cockpit und User sind Teil jedes Merge-Zyklus; Ergebnisse ohne Tests, Evidence oder vollständigen Handoff sind nicht merge-ready.

## 7. Parallelisierung („maximal viele Threads")

Die Goal-Direktive verlangt maximale Parallelisierung der Implementierung. Verbindliche Auslegung:

- Der Orchestrator bereitet Session-Requests **gebündelt** vor, sodass der User viele Sessions in einem Durchgang **einzeln** freigeben kann; die Freigabe bleibt pro Session individuell.
- Freigegebene Implementierungs-Sessions laufen maximal parallel, begrenzt nur durch nicht-überlappende Pfad-Scopes, deklarierte Abhängigkeiten und die Merge-Grundreihenfolge.
- Parallelität ersetzt keine Gates: jede parallele Session behält Worktree-Isolation, eigenen Branch, eigenen Handoff und eigenes PR-Gate.
- Erster vorbereiteter Governance-Task für die Freigabe-Queue: begrenzte `code`-Erweiterung von `tools/v1_governance` um die individuelle Referenzform für Orchestrator-vermittelte User-Freigaben (Abschnitt 4.4), damit Batch-Freigaben validierbar werden.

## 8. Freigabe-Queue (Stand 2026-08-13)

Individuelle Erstellungs-Freigaben liegen laut `docs/governance/cockpit-approval-ledger-v1.json` ausschließlich für `cockpit-openfang` und `cockpit-agentfarm` vor. Die übrigen 20 Cockpits sind **freigabe-pendent** und werden dem User in Wellen-Reihenfolge (Portfolio-Design Abschnitt 9, beginnend mit `cockpit-git`) zur individuellen Freigabe vorgelegt. Implementierungs-Sessions werden je Task nach Abschnitt 5 vorgelegt. Diese Queue ist eine Priorisierung, keine Freigabe und keine Aktivierungs-Evidence.

## 9. Fail-closed-Verhalten

Die Fehler- und Konfliktregeln aus Portfolio-Design Abschnitt 11 gelten unverändert: fehlende Repositories, Contracts oder Zugänge werden gemeldet, nicht ersetzt; dirty Worktrees und fremd belegte Scopes stoppen schreibende Arbeit; unbestätigte Remote-Parität wird ausgewiesen; statische Registrierung ist kein Live-Nachweis; widersprechende Cockpits entscheidet der User auf Vorlage des Orchestrators. Fremde oder vorbestehende Änderungen werden niemals verworfen, überschrieben, gestasht oder mitcommittet.

## 10. Änderungen an dieser Charter

Materielle Änderungen (Portfolio-Umfang, Freigaberegel, Merge-Modell, Orchestrator-Rolle) erfordern eine neue, durabel referenzierte User-Direktive und eine neue Charter-Version. Redaktionelle Korrekturen sind Routine-`docs`-Arbeit unter `standing-autonomy:v1`.
