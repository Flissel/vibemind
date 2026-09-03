# Vibemind_V1 — project CLAUDE.md

> **Merge-Hinweis (2026-08-25):** Diese Datei ist die Zusammenführung der beiden
> `CLAUDE.md`-Forks (lokale Betriebslinie und `origin/master`-Governance-Linie), die
> seit `bece5e6` (2026-07-14) getrennt liefen. Beide Arbeitsmodelle bleiben gültig —
> sie gelten für **verschiedene Akteure**, nicht gegeneinander. Siehe
> `docs/operations/2026-08-01-repository-fork-diagnosis.md`.

## Arbeitsmodell nach Akteur

Dieses Repo wird von zwei Sorten Agenten bearbeitet. Sie haben **unterschiedliche**
Branch-Regeln — das ist Absicht, kein Widerspruch.

**Codex-Sessions → Branch-per-Task.**

1. Vor jeder Arbeit Repo, Worktrees, Dirty State, Branch-Ancestry, Remote-Parität und Submodule prüfen.
2. Routine-`docs`-/`code`-Prozesse unter `standing-autonomy:v1` ohne per-session User-Interaktion aktivieren und selbstständig fortführen; neue Sessions (Cockpit wie Implementierung) jedoch nur nach individueller User-Freigabe erstellen (`docs/governance/multi-session-program-charter-v1.md`).
3. Schreibende Arbeit nur in einem isolierten Worktree auf `codex/<space>/<task-id>-<slug>` ausführen.
4. Nicht direkt auf dem geschützten Integrationsbranch committen (`master` während der Migration, Ziel `main`).
5. TDD, enger Scope, Conventional Commits und reproduzierbare Evidence verwenden.
6. Übergabe und PR-Readiness mit `python -m tools.v1_governance` prüfen.
7. PR-Pflege und Merge-Reihenfolge liegen beim V1-Orchestrator.

**Claude-Code-Sessions → direkt auf `master`.**
Mehrere Claude-Code-Sessions arbeiten hier gleichzeitig. Damit ihre Diffs füreinander
sichtbar bleiben und Branches nicht still auseinanderlaufen, wird **direkt auf `master`**
committet — im äußeren Repo wie im `vibemind-os`-Submodul. Keine Feature-Branches für
neue Arbeit, außer der User verlangt für einen konkreten Grund einen. Das überschreibt
den globalen „never commit directly to master"-Default; der User hat es für dieses Repo
wegen des Concurrent-Agent-Setups ausdrücklich autorisiert (2026-07-14).

**Branch-Hygiene (beide Akteure).** Task-Branches werden nach dem Merge zeitnah gelöscht.
Der Branch-per-Task-Modus hatte bis 2026-08-25 auf 197 Refs aufgestaut; die Konsolidierung
ist in `docs/operations/2026-08-25-branch-consolidation.md` dokumentiert.

`standing-autonomy:v1` dokumentiert die echte dauerhafte Nutzeranweisung für begrenzte `docs`- und `code`-Arbeit. Sie ersetzt keine Task-Grenzen, Tests oder Evidence und darf nicht auf höhere Risikoklassen erweitert werden.

Deployments, destruktive Aktionen, Breaking Changes, DB-Migrationen, Secrets, Proxmox-Mutationen, große Repo-Verschiebungen sowie Branch-/Worktree-Löschungen benötigen request-spezifische Autorität und dürfen `standing-autonomy:v1` nicht verwenden.

## Bestehende Arbeit schützen

Fremde oder vorbestehende Änderungen niemals verwerfen, überschreiben, stashen oder in den eigenen Commit aufnehmen. Bei Scope-Überlappung fail-closed stoppen, den Blocker dokumentieren und andere sichere Aufgaben ohne User-Unterbrechung fortführen.

Konkret:

- Vor jedem checkout/merge/stash zuerst `git status` — dieses Repo hat regelmäßig echte
  vorbestehende uncommittete Arbeit (Pitch-Deck-Dateien, andere laufende Edits), die nicht
  dir gehört. Niemals verwerfen; stashen oder reversibel umgehen.
- Auf Anzeichen achten, dass eine andere Session mitten in einer Änderung an derselben
  Datei steckt (ein Wert, der sich zwischen zwei eigenen Reads ändert,
  `VIBEMIND_RESTART_NONCE`-artige Bump-Muster, ein `index.lock`, der wiederkehrt). Dann
  pausieren und verifizieren, statt anzunehmen, die Luft sei rein.
- Niemals force-pushen, niemals Branches force-löschen, niemals Hooks umgehen — ohne
  ausdrückliche Aufforderung. Diese Defaults aus der globalen `CLAUDE.md` gelten weiter.

## Koordinations-Protokoll (versöhnt, D1 — 2026-08-18)

Dieses Repo hatte zwei widersprechende Koordinations-Protokolle in seinen zwei
`CLAUDE.md`-Forks (lokale Linie: „Claim = Pflicht"; `origin/master`: „WORKBOARD ist nur
historischer Snapshot, keine neuen Claims"). Das war die dokumentierte Wurzel des Forks
(s. `docs/operations/2026-08-01-repository-fork-diagnosis.md`). **Entscheidung des Users
(D1): beide Ebenen koexistieren — WORKBOARD bleibt die Live-Lock, Codex' Session-Layer
ergänzt sie.** Diese Sektion ist die kanonische Auflösung des `CLAUDE.md`-Konflikts beim
Merge der beiden Linien.

**Ebene 1 — WORKBOARD als Live-Lock (Pflicht, NICHT nur Snapshot).**
Vor Arbeit an geteilten Ressourcen (infra/, vibemind-os-Kern, Proxmox-VM, Stack-Deploys,
geteilte Spaces): `WORKBOARD.md` im Repo-Root lesen, eigenen Claim eintragen und sofort
committen; bei fremdem aktivem Claim auf dem Zielbereich ausweichen oder den User fragen.
„Wer fasst JETZT was an" wird hier git-atomar sichtbar. Format steht im Board selbst.

**Ebene 2 — Codex' Session-Layer (ergänzend, ersetzt Ebene 1 nicht).**
Freigegebene Session Requests, Task Handoffs und der Brain Task Ledger sind der Kanal für
koordinierte, freigegebene Task-Übergabe zwischen Sessions/Codex. Sie laufen *zusätzlich*
zum WORKBOARD, nicht statt seiner — die Live-Lock bleibt das WORKBOARD.

**Finaler Koordinator bleibt der User.** Bei Konflikt zwischen den Ebenen: WORKBOARD-Claim
gewinnt für „wer arbeitet jetzt woran", der Session-Layer für „welche Task wurde formal
übergeben".

## Submodul `vibemind-os`

Die beiden Linien pinnen strukturell verschiedene Submodul-Stände: `82127e4` (Codex-Linie,
kein `spaces/`-Verzeichnis) und die Betriebslinie (mit `spaces/`, inkl. Marketing). Der
Submodul-Fork ist **noch nicht aufgelöst** — offene Entscheidung #3 der Fork-Diagnose.
Bis dahin gilt: `master` pinnt `82127e4`, und `spaces/marketing` lebt weiter im **äußeren**
Repo, weil der gepinnte Submodul-Stand keinen Ersatz dafür enthält. Wer den Gitlink bumpt,
muss diese Verdopplung mit auflösen.
