# V1 Git-, Session- und PR-Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine testbare V1-Grundlage schaffen, die jede schreibende Codex-Arbeit an eine explizit freigegebene Session bindet, isolierte Worktrees erzwingt und PRs vor dem Merge reproduzierbar prüft.

**Architecture:** Ein kleines, plattformneutrales Python-Governance-Tool ist die ausführbare Wahrheit für Repo-Inventar, Git-Audit, Session-Request, Worktree-Erzeugung, Handoff und PR-Readiness. SmartGit visualisiert dieselben Git-Objekte. Versionierte YAML-Verträge und lokale, ignorierte Laufzeitakten trennen Policy von Session-Zustand. GitHub CI ruft exakt denselben lokalen Gate-Befehl auf.

**Tech Stack:** Git, Git Worktrees, Python 3.11, PyYAML 6, pytest 8, PowerShell 7, GitHub Actions, SmartGit

---

## Geltungsbereich und harte Grenzen

Dieser Plan ist **Plan 1** der V1-Orchestrierung. Er implementiert nur die Git-, Session-, Übergabe- und PR-Grundlage. Er startet keine Space-Session, ändert keine Anwendung, verschiebt keine Repositories, deployed nichts nach Proxmox und integriert OpenFang noch nicht.

Die Ausführung dieses Plans erfolgt bewusst in mehreren Codex-Task-Sessions. Jede Session benötigt vor ihrer Erstellung eine eigene ausdrückliche User-Freigabe. Ein `approval_reference` dokumentiert diese Freigabe, erzeugt sie aber nicht. Das Tool darf niemals eine Freigabe selbst setzen oder aus einem vorherigen `ok` ableiten.

Der aktuelle Remote-Default ist `master`; das freigegebene Zielmodell verwendet `main`. Dieser Plan schützt den jeweils im Manifest deklarierten Integrationsbranch und dokumentiert `main` als Ziel. Das tatsächliche Remote-Rename ist ein späterer, separat freizugebender Eingriff.

## Gate 0: Interaktives `cockpit-git`

Vor jeder Implementierungs-Session dieses Plans wird eine eigene, User-sichtbare Codex-Cockpit-Session mit folgendem Vertrag erstellt:

```yaml
session_id: cockpit-git
title: "V1 Cockpit · Git & Repositories"
session_type: space-cockpit
writes_allowed: false
objective: Audit the live V1 repository, worktree, branch, remote, submodule and PR topology and validate this governance plan against current evidence
repositories:
  - vibemind-v1
read_only_scope:
  - git metadata
  - worktree inventory
  - branch ancestry and remote parity
  - submodule topology and pins
  - existing Git instructions and SmartGit workflow
  - this implementation plan
expected_output:
  - authoritative integration remote and branch recommendation
  - dirty and overlapping scope map
  - worktree and stale-session inventory
  - manifest corrections required before implementation
  - validated or revised task ordering
  - exact approval card for task-platform-0001-governance-contracts
forbidden_actions:
  - modify tracked or untracked files
  - create or switch branches
  - create or remove worktrees
  - commit, push, merge or open a pull request
  - stash, reset, clean or delete
```

Die Zustimmung zu diesem Plan genehmigt `cockpit-git` nicht automatisch. Der Haupt-Orchestrator zeigt dem User die Freigabekarte und erstellt die Cockpit-Session erst nach einer neuen, eindeutig darauf bezogenen Bestätigung.

Das Cockpit beginnt mit den bereits bekannten, aber erneut zu prüfenden Befunden vom 2026-07-30: sechs Worktrees, ein absichtlich geschützter dirty Haupt-Checkout, ein sauberer Design-Worktree, ein erreichbarer `origin`-Remote, ein nicht erreichbarer `lab`-Remote und ein Design-Branch ohne Upstream. Diese Angaben sind Startpunkte, keine dauerhaft gültigen Tatsachen.

## Multi-Session-Ausführung

Der V1-Orchestrator erstellt, überwacht und integriert die folgenden Sessions. Eine Freigabe gilt ausschließlich für die konkret benannte Session und ihren Scope. Keine Session darf selbst eine Folgesession erzeugen, ihren Scope erweitern oder ihren eigenen PR mergen.

Mit „Session“ ist hier eine für den User sichtbare, eigenständige Codex-Session gemeint, kein unsichtbarer Wegwerf-Subagent. Innerhalb dieser Grundlage wird die Arbeit nicht automatisch in weitere Subagenten aufgefächert.

| Reihenfolge | Session-ID | Branch | Plan-Tasks | Abhängigkeit | Ergebnis |
|---|---|---|---|---|---|
| 1 | `task-platform-0001-governance-contracts` | `codex/platform/task-platform-0001-governance-contracts` | 1–3 | Design-PR integriert | Policy, Verträge und Repo-Manifest |
| 2A | `task-platform-0002-git-worktree-gate` | `codex/platform/task-platform-0002-git-worktree-gate` | 4–5 | Session 1 gemerged | Git-Audit und freigegebene Worktree-Erzeugung |
| 2B | `task-platform-0004-session-routines` | `codex/platform/task-platform-0004-session-routines` | 7 | Session 1 gemerged | Skills und SmartGit-/Lifecycle-Runbooks |
| 3 | `task-platform-0003-pr-readiness` | `codex/platform/task-platform-0003-pr-readiness` | 6 | Session 2A gemerged | Handoff- und PR-Readiness-Gate |
| 4 | `task-platform-0005-governance-integration` | `codex/platform/task-platform-0005-governance-integration` | 8–9 | Sessions 2B und 3 gemerged | gemeinsames lokales/CI-Gate und Gesamtnachweis |

Sessions 2A und 2B dürfen nach dem Merge von Session 1 parallel laufen, weil ihre Dateiscopes getrennt sind. Der Orchestrator prüft vor ihrer Erstellung dennoch den tatsächlichen Merge-Stand und mögliche Pfadüberlappungen.

Für jede Session gilt derselbe Ablauf:

1. Orchestrator zeigt Session-ID, Ziel, erlaubte Pfade, Abhängigkeiten, DoD und Risiken.
2. User gibt genau diese Session frei.
3. Orchestrator erzeugt Codex-Session, Worktree und Branch.
4. Session prüft den vorhandenen Code und bestätigt oder verfeinert ihren Task-Plan interaktiv; eine materielle Scope-Änderung benötigt eine neue User-Freigabe.
5. Session implementiert nur ihren freigegebenen Scope und liefert Handoff plus Evidence.
6. Orchestrator pflegt den PR, prüft Gates und übernimmt den Merge.
7. Folge-Sessions werden erst nach bestätigtem Merge ihrer Abhängigkeiten zur Freigabe vorgelegt.

Nach dem Handoff von `cockpit-git` legt der Haupt-Orchestrator dem User die empfohlene kanonische Remote-/Integrationsbranch-Entscheidung vor. Erst nach dieser Entscheidung pusht er den bereits freigegebenen Design-/Plan-Branch, erstellt und pflegt dessen Dokumentations-PR und merged ihn bei grünen Gates. Dieser Schritt erzeugt keine zusätzliche Codex-Session. Session 1 beginnt erst auf der bestätigten, integrierten Design-Basis.

## Ergebnisstruktur

```text
Vibemind_V1/
├── .agents/
│   ├── policies/
│   │   ├── git.yaml
│   │   └── session-approval.yaml
│   ├── skills/
│   │   ├── v1-pr-integration/SKILL.md
│   │   ├── v1-session-start/SKILL.md
│   │   └── v1-task-handoff/SKILL.md
│   └── templates/
│       ├── SESSION_REQUEST.yaml
│       └── TASK_HANDOFF.yaml
├── .github/
│   ├── pull_request_template.md
│   └── workflows/v1-governance.yml
├── docs/runbooks/
│   ├── smartgit-worktrees.md
│   └── v1-session-lifecycle.md
├── scripts/vibemind-governance.ps1
├── tests/
│   ├── architecture/test_v1_git_policy.py
│   └── v1_governance/
├── tools/v1_governance/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── errors.py
│   ├── git_state.py
│   ├── handoff.py
│   ├── manifest.py
│   ├── models.py
│   ├── pr_gate.py
│   ├── session.py
│   └── requirements.txt
├── AGENTS.md
└── repo-manifest.yaml
```

Lokaler, nicht versionierter Zustand liegt ausschließlich unter:

```text
.vibemind/state/session-requests/
.vibemind/state/handoffs/
.worktrees/
```

## Task 1: Direkte-Master-Regel durch die freigegebene Governance ersetzen

**Files:**
- Create: `AGENTS.md`
- Modify: `.gitignore`
- Modify: `CLAUDE.md`
- Modify: `WORKBOARD.md`
- Test: `tests/architecture/test_v1_git_policy.py`

- [ ] **Step 1: Zuerst den fehlschlagenden Policy-Test schreiben**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_local_worktrees_and_runtime_state_are_ignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".worktrees/" in ignored
    assert ".vibemind/state/" in ignored


def test_repo_instructions_require_approved_isolated_sessions() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    combined = f"{agents}\n{claude}".lower()
    assert "explizite user-freigabe" in combined
    assert "isolierter worktree" in combined
    assert "nicht direkt" in combined
    assert "commit directly to `master`" not in combined


def test_workboard_is_marked_legacy() -> None:
    board = (ROOT / "WORKBOARD.md").read_text(encoding="utf-8")
    assert "Legacy-Koordinationsprotokoll" in board
    assert "keine neuen Claims" in board
```

- [ ] **Step 2: Test ausführen und RED belegen**

Run: `python -m pytest tests/architecture/test_v1_git_policy.py -q`

Expected: FAIL, weil `.worktrees/`, `AGENTS.md` und die neue Policy noch fehlen.

- [ ] **Step 3: Lokale Laufzeitpfade ignorieren**

Am Ende von `.gitignore` ergänzen:

```gitignore
# V1 Codex governance: local worktrees and runtime records
.worktrees/
.vibemind/state/
```

- [ ] **Step 4: Repo-lokale Agentenregeln als `AGENTS.md` anlegen**

```markdown
# VibeMind V1 Agent Rules

## Source of truth

Git CLI, committed contracts and repository tests are authoritative. SmartGit is a visual client for the same Git state.

## Session gate

- Every new Codex Space Cockpit or Task Session needs explicit user approval before creation.
- A planning approval is not an implementation approval.
- Every writing Task Session uses one isolated worktree and one `codex/<space>/<task-id>-<slug>` branch.
- Never invent, infer, or self-issue an approval reference.

## Git and integration

- Do not commit directly to the protected integration branch (`master` during migration, target `main`).
- Audit worktrees, dirty state, ancestry, remote parity and submodules before edits, merge, cleanup or push claims.
- Preserve unrelated and pre-existing changes.
- Use Conventional Commits and narrowly scoped commits.
- The V1 orchestrator maintains PR metadata, dependencies, CI, reviews, merge order, submodule pins and post-merge verification.
- Never delete a worktree or branch without explicit cleanup approval.

## Authority gates

Normal green code PRs already covered by an approved task may be merged by the orchestrator. Deployments, destructive operations, breaking contracts, database migrations, secret changes, Proxmox mutations and large repository moves need a fresh explicit user approval.

## Verification

No task is complete without exact test evidence, commit SHA, integration status and remaining blockers. Live claims must be based on live evidence and fail closed.
```

- [ ] **Step 5: `CLAUDE.md` vollständig durch dieselben Regeln ersetzen**

`CLAUDE.md` erhält denselben Autoritätskern wie `AGENTS.md`, plus diese V1-spezifische Reihenfolge:

```markdown
# Vibemind V1 — project CLAUDE.md

## Arbeitsmodell

1. Vor jeder Arbeit Repo, Worktrees, Dirty State, Branch-Ancestry, Remote-Parität und Submodule prüfen.
2. Vor dem Erstellen jeder Space-Cockpit- oder Task-Session eine explizite User-Freigabe einholen.
3. Schreibende Arbeit nur in einem isolierten Worktree auf `codex/<space>/<task-id>-<slug>` ausführen.
4. Nicht direkt auf dem geschützten Integrationsbranch committen (`master` während der Migration, Ziel `main`).
5. TDD, enger Scope, Conventional Commits und reproduzierbare Evidence verwenden.
6. Übergabe und PR-Readiness mit `python -m tools.v1_governance` prüfen.
7. PR-Pflege und Merge-Reihenfolge liegen beim V1-Orchestrator.

Eine Planfreigabe ist keine Implementierungsfreigabe. Ein gespeicherter Approval-Verweis dokumentiert nur eine echte User-Freigabe; er erzeugt sie nicht.

Deployments, destruktive Aktionen, Breaking Changes, DB-Migrationen, Secrets, Proxmox-Mutationen, große Repo-Verschiebungen sowie Branch-/Worktree-Löschungen benötigen eine separate explizite User-Freigabe.

## Bestehende Arbeit schützen

Fremde oder vorbestehende Änderungen niemals verwerfen, überschreiben, stashen oder in den eigenen Commit aufnehmen. Bei Scope-Überlappung stoppen und den User einbeziehen.

## WORKBOARD

`WORKBOARD.md` bleibt als historischer Snapshot erhalten. Keine neuen Claims eintragen. Neue Koordination läuft über freigegebene Session Requests, Task Handoffs und später den Brain Task Ledger.
```

- [ ] **Step 6: Historische WORKBOARD-Daten erhalten, aber am Dateianfang stilllegen**

Vor den bestehenden Inhalt von `WORKBOARD.md` setzen:

```markdown
> **Legacy-Koordinationsprotokoll:** Dieser Inhalt bleibt als historischer Snapshot erhalten. Ab der V1-Governance-Umstellung werden hier keine neuen Claims eingetragen. Neue Arbeit benötigt einen freigegebenen Session Request, einen isolierten Worktree und einen PR-Handoff.

```

Keine vorhandene Tabellenzeile löschen oder umformulieren.

- [ ] **Step 7: Test erneut ausführen**

Run: `python -m pytest tests/architecture/test_v1_git_policy.py -q`

Expected: `3 passed`.

- [ ] **Step 8: Commit**

```powershell
git add .gitignore AGENTS.md CLAUDE.md WORKBOARD.md tests/architecture/test_v1_git_policy.py
git commit -m "docs: establish v1 git governance"
```

## Task 2: Getypte Session- und Handoff-Verträge einführen

**Files:**
- Create: `.agents/policies/git.yaml`
- Create: `.agents/policies/session-approval.yaml`
- Create: `.agents/templates/SESSION_REQUEST.yaml`
- Create: `.agents/templates/TASK_HANDOFF.yaml`
- Create: `tools/v1_governance/__init__.py`
- Create: `tools/v1_governance/errors.py`
- Create: `tools/v1_governance/models.py`
- Create: `tools/v1_governance/requirements.txt`
- Test: `tests/v1_governance/test_models.py`

- [ ] **Step 1: Vertrags-Tests schreiben**

Die Tests müssen mindestens beweisen:

```python
import pytest

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.models import SessionRequest


VALID = {
    "schema_version": 1,
    "session_id": "task-coding-1042",
    "session_type": "task",
    "space": "coding",
    "objective": "Add the async code-generation start endpoint",
    "repositories": ["vibemind-v1"],
    "allowed_paths": ["tools/v1_governance/**", "tests/v1_governance/**"],
    "writes_allowed": True,
    "approval_status": "approved",
    "approval_reference": "user-message:2026-07-30T12:00:00+02:00",
    "base_ref": "origin/master",
    "branch": "codex/coding/task-coding-1042-codegen-start",
    "risk_class": "code",
}


def test_approved_task_request_is_valid() -> None:
    request = SessionRequest.from_mapping(VALID)
    assert request.is_approved


@pytest.mark.parametrize("field", ["approval_reference", "branch"])
def test_approved_writing_request_requires_gate_fields(field: str) -> None:
    data = {**VALID, field: ""}
    with pytest.raises(GovernanceError):
        SessionRequest.from_mapping(data)


def test_cockpit_cannot_write() -> None:
    data = {
        **VALID,
        "session_type": "space-cockpit",
        "writes_allowed": True,
    }
    with pytest.raises(GovernanceError, match="read-only"):
        SessionRequest.from_mapping(data)


def test_root_wildcard_scope_is_rejected() -> None:
    data = {**VALID, "allowed_paths": ["**"]}
    with pytest.raises(GovernanceError, match="broad scope"):
        SessionRequest.from_mapping(data)
```

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/v1_governance/test_models.py -q`

Expected: import error für `tools.v1_governance`.

- [ ] **Step 3: Minimale Modelle implementieren**

`errors.py`:

```python
class GovernanceError(ValueError):
    """A fail-closed V1 governance validation error."""
```

`models.py` verwendet `dataclasses`, `Literal`, `Mapping[str, object]` und kleine Narrowing-Helper. Zulässige Werte:

```python
SESSION_TYPES = {"space-cockpit", "task"}
APPROVAL_STATES = {"pending", "approved", "denied"}
RISK_CLASSES = {
    "docs",
    "code",
    "deployment",
    "destructive",
    "breaking-contract",
    "database-migration",
    "secrets",
    "proxmox",
    "repo-move",
}
BRANCH_PATTERN = re.compile(
    r"^codex/[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$"
)
FORBIDDEN_SCOPES = {"*", "**", "/", ".", "./"}
```

`SessionRequest.from_mapping()` muss alle Felder typisieren, leere Listen ablehnen und folgende Invarianten erzwingen:

```python
if session_type == "space-cockpit" and writes_allowed:
    raise GovernanceError("space-cockpit sessions are read-only")
if writes_allowed and approval_status != "approved":
    raise GovernanceError("writing sessions require approved status")
if approval_status == "approved" and not approval_reference.strip():
    raise GovernanceError("approved sessions require an approval reference")
if writes_allowed and not BRANCH_PATTERN.fullmatch(branch):
    raise GovernanceError("writing sessions require a valid codex branch")
if any(scope.strip() in FORBIDDEN_SCOPES for scope in allowed_paths):
    raise GovernanceError("broad scope is forbidden")
```

- [ ] **Step 4: Versionierte Policy-Dateien anlegen**

`.agents/policies/git.yaml`:

```yaml
schema_version: 1
feature_branch_pattern: '^codex/[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$'
current_integration_branch: master
target_integration_branch: main
direct_commits_to_integration_branch: false
force_push_to_integration_branch: false
delete_branch_requires_user_approval: true
delete_worktree_requires_user_approval: true
required_preflight:
  - worktrees
  - dirty_state
  - ancestry
  - remote_parity
  - submodules
```

`.agents/policies/session-approval.yaml`:

```yaml
schema_version: 1
approval_authority: user
auto_approval_allowed: false
planning_approval_implies_implementation: false
session_types:
  space-cockpit:
    writes_allowed: false
    purpose: discovery-specification-backlog
  task:
    writes_allowed: true
    isolated_worktree_required: true
high_risk_classes:
  - deployment
  - destructive
  - breaking-contract
  - database-migration
  - secrets
  - proxmox
  - repo-move
```

- [ ] **Step 5: Vorlagen anlegen**

`SESSION_REQUEST.yaml` bleibt absichtlich `pending`:

```yaml
schema_version: 1
session_id: task-coding-1042
session_type: task
space: coding
objective: Add the async code-generation start endpoint
repositories:
  - vibemind-v1
allowed_paths:
  - services/coding/**
  - tests/coding/**
writes_allowed: true
approval_status: pending
approval_reference: ""
base_ref: origin/master
branch: codex/coding/task-coding-1042-codegen-start
risk_class: code
```

`TASK_HANDOFF.yaml`:

```yaml
schema_version: 1
session_id: task-coding-1042
branch: codex/coding/task-coding-1042-codegen-start
commits: []
tests: []
evidence: []
dependencies: []
deployment_status: not_required
remaining_blockers: []
```

- [ ] **Step 6: Dependencies festlegen, GREEN ausführen und committen**

`tools/v1_governance/requirements.txt`:

```text
PyYAML>=6.0,<7
pytest>=8,<9
```

Run: `python -m pytest tests/v1_governance/test_models.py -q`

Expected: alle Tests grün.

```powershell
git add .agents/policies .agents/templates tools/v1_governance tests/v1_governance/test_models.py
git commit -m "feat: define v1 session contracts"
```

## Task 3: Das aktuelle Repo-Inventar maschinenlesbar und ehrlich machen

**Files:**
- Create: `repo-manifest.yaml`
- Create: `tools/v1_governance/manifest.py`
- Test: `tests/v1_governance/test_manifest.py`

- [ ] **Step 1: Tests für Pfad, Gitlink und Remote schreiben**

Die Tests erzeugen in `tmp_path` ein Superprojekt mit einem lokalen Submodule. Benenne die fünf Tests exakt `test_manifest_accepts_matching_submodule`, `test_manifest_rejects_missing_path`, `test_manifest_rejects_submodule_without_gitlink`, `test_manifest_rejects_unexpected_remote` und `test_current_default_can_differ_from_approved_target`. Jeder Test arrangiert genau einen Zustand, ruft `validate_manifest()` auf und vergleicht die vollständige Liste der Issue-Codes. Der Happy Path erwartet `[]`; die Negativfälle erwarten jeweils genau `missing-path`, `missing-gitlink` oder `remote-mismatch`. Der Migrationsfall erwartet keine Issue, wenn `current_integration_branch: master` und `target_integration_branch: main` deklariert sind.

Jeder temporäre Git-Aufruf nutzt Argumentlisten mit `shell=False`; lokale Test-Remotes verwenden keine Netzwerkverbindung.

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/v1_governance/test_manifest.py -q`

Expected: import error für `manifest`.

- [ ] **Step 3: Manifest implementieren**

`repo-manifest.yaml` beschreibt nur bestätigten Ist-Zustand und die separat freizugebende Migration:

```yaml
schema_version: 1
superproject:
  id: vibemind-v1
  path: .
  current_integration_branch: master
  target_integration_branch: main
  branch_rename_status: approval-required
repositories:
  - id: vibemind-os
    path: vibemind-os
    kind: submodule
    remote: https://github.com/Flissel/vibemind-os.git
    required: true
    migration_state: nested-legacy
    owner: platform
submodule_policy:
  recursive_inventory_required: true
  pin_change_requires_separate_commit: true
  nested_submodules_target_state: remove-gradually
```

`manifest.py` stellt diese öffentlichen, vollständig typisierten Schnittstellen bereit:

```python
@dataclass(frozen=True)
class ManifestIssue:
    code: str
    path: str
    message: str


def load_manifest(path: Path) -> Mapping[str, object]:
    """Load YAML and raise GovernanceError unless the root is a mapping."""


def validate_manifest(
    repo_root: Path,
    manifest_path: Path,
) -> list[ManifestIssue]:
    """Return every deterministic manifest issue; return an empty list on success."""
```

Validierung muss fail-closed prüfen:

- `schema_version == 1`
- eindeutige Repository-IDs und Pfade
- Pfade bleiben nach `resolve()` innerhalb des Superprojekts
- `kind: submodule` stimmt mit `.gitmodules` und Mode `160000` in `git ls-files --stage` überein
- deklarierter `current_integration_branch` existiert lokal oder als `origin/<branch>`
- ein in `.gitmodules` vorhandener Pfad fehlt nicht im Manifest
- keine Secrets oder Zugangsdaten im Manifest

- [ ] **Step 4: GREEN und Commit**

```powershell
python -m pytest tests/v1_governance/test_manifest.py -q
python -c "from pathlib import Path; from tools.v1_governance.manifest import validate_manifest; issues=validate_manifest(Path('.'), Path('repo-manifest.yaml')); print(len(issues)); raise SystemExit(bool(issues))"
git add repo-manifest.yaml tools/v1_governance/manifest.py tests/v1_governance/test_manifest.py
git commit -m "feat: validate v1 repository manifest"
```

Expected: Tests grün und Validator druckt `0`.

## Task 4: Read-only Git- und Worktree-Audit implementieren

**Files:**
- Create: `tools/v1_governance/git_state.py`
- Create: `tools/v1_governance/cli.py`
- Create: `tools/v1_governance/__main__.py`
- Test: `tests/v1_governance/test_git_state.py`

- [ ] **Step 1: Audit-Tests schreiben**

Die Tests bauen temporäre Repositories auf und heißen exakt `test_audit_reports_branch_head_and_clean_state`, `test_audit_lists_dirty_paths_without_file_contents`, `test_audit_detects_linked_worktree`, `test_audit_reports_ahead_behind_against_remote` und `test_audit_reports_recursive_submodule_pins`. Sie vergleichen die konkreten `GitAudit`-Felder. Der Dirty-Test schreibt den Marker `sensitive-value` in eine Datei und stellt zusätzlich sicher, dass dieser Marker nicht in der serialisierten Audit-Ausgabe vorkommt.

Assertions dürfen keine Datei-Inhalte oder Environment-Werte in Evidence verlangen.

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/v1_governance/test_git_state.py -q`

- [ ] **Step 3: Sicheren Git-Runner und Audit implementieren**

`git_state.py` enthält mindestens:

```python
@dataclass(frozen=True)
class GitAudit:
    root: Path
    branch: str
    head: str
    dirty_paths: tuple[str, ...]
    worktrees: tuple[Mapping[str, str], ...]
    upstream: str | None
    ahead: int | None
    behind: int | None
    submodules: tuple[str, ...]


def run_git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if check and completed.returncode != 0:
        raise GovernanceError(
            f"git {' '.join(args)} failed with exit {completed.returncode}"
        )
    return completed.stdout.strip()


def audit_repository(root: Path) -> GitAudit:
    """Collect repository state without fetching or mutating Git state."""
```

Fehlermeldungen enthalten Befehl und Exitcode, aber nicht ungefiltertes `stderr`. `audit_repository()` nutzt:

```text
rev-parse --show-toplevel
symbolic-ref --short -q HEAD
rev-parse HEAD
status --porcelain=v1
worktree list --porcelain
rev-parse --abbrev-ref --symbolic-full-name @{upstream}
rev-list --left-right --count HEAD...@{upstream}
submodule status --recursive
```

- [ ] **Step 4: Read-only CLI hinzufügen**

`python -m tools.v1_governance audit --repo . --format json` gibt ein JSON-Objekt mit stabilen Keys aus. `--fetch` führt vor dem Audit explizit `git fetch origin --prune` aus; ohne Flag gibt es keinen Netzwerkzugriff. Exit `0` bedeutet Audit erfolgreich, nicht automatisch merge-ready.

- [ ] **Step 5: GREEN und Commit**

```powershell
python -m pytest tests/v1_governance/test_git_state.py -q
python -m tools.v1_governance audit --repo . --format json
git add tools/v1_governance tests/v1_governance/test_git_state.py
git commit -m "feat: add v1 git state audit"
```

## Task 5: Nur freigegebene Task-Worktrees erzeugen

**Files:**
- Create: `tools/v1_governance/session.py`
- Modify: `tools/v1_governance/cli.py`
- Test: `tests/v1_governance/test_session.py`

- [ ] **Step 1: Fail-closed Session-Tests schreiben**

Implementiere sieben unabhängige Tests mit den Namen `test_pending_request_cannot_create_worktree`, `test_cockpit_request_cannot_create_writing_worktree`, `test_dirty_base_checkout_is_rejected`, `test_existing_branch_is_rejected`, `test_existing_destination_is_rejected`, `test_dry_run_has_no_git_or_filesystem_side_effect` und `test_approved_request_creates_expected_branch_and_worktree`. Die ersten fünf vergleichen die genaue `GovernanceError`-Ursache. Der Dry-run vergleicht Branchliste und Dateisystem vor/nach dem Aufruf. Der Happy Path prüft Branchname, Worktree-Pfad und dass der neue HEAD exakt `base_ref` entspricht.

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/v1_governance/test_session.py -q`

- [ ] **Step 3: Session-Validierung und Worktree-Erzeugung implementieren**

```python
@dataclass(frozen=True)
class WorktreePlan:
    branch: str
    base_ref: str
    destination: Path
    command: tuple[str, ...]


def load_session_request(path: Path) -> SessionRequest:
    """Load and validate one versioned session request."""


def plan_task_worktree(
    repo_root: Path,
    request: SessionRequest,
    worktrees_root: Path,
) -> WorktreePlan:
    """Validate every gate and return the only permitted git worktree command."""


def create_task_worktree(repo_root: Path, plan: WorktreePlan) -> None:
    run_git(
        repo_root,
        "worktree",
        "add",
        "-b",
        plan.branch,
        str(plan.destination),
        plan.base_ref,
    )
```

`plan_task_worktree()` verweigert die Planung, wenn:

- Request nicht `approved`, nicht `task` oder nicht schreibend ist
- `approval_reference` leer ist
- Branch nicht der Policy entspricht
- Ziel nicht exakt unter dem aufgelösten `.worktrees/`-Root liegt
- Base-Checkout dirty ist
- Branch oder Ziel bereits existiert
- `base_ref` nicht auflösbar ist
- `base_ref` hinter seinem Remote liegt, sofern ein passender Remote-Ref existiert

Das Tool darf niemals `git clean`, `reset`, `stash`, Branch-Löschung oder Worktree-Löschung ausführen.

- [ ] **Step 4: CLI-Befehle hinzufügen**

```powershell
python -m tools.v1_governance session validate `
  --request .vibemind/state/session-requests/task-coding-1042.yaml

python -m tools.v1_governance session start `
  --repo . `
  --request .vibemind/state/session-requests/task-coding-1042.yaml `
  --worktrees-root .worktrees `
  --dry-run
```

Ohne `--execute` bleibt `session start` read-only und gibt den Plan aus. Mit `--execute` wird exakt ein Worktree erzeugt. Auch `--execute` verändert nie den Ausgangs-Checkout.

- [ ] **Step 5: GREEN und Commit**

```powershell
python -m pytest tests/v1_governance/test_session.py -q
git add tools/v1_governance/session.py tools/v1_governance/cli.py tests/v1_governance/test_session.py
git commit -m "feat: gate v1 task worktrees by approval"
```

## Task 6: Handoff und PR-Readiness als gemeinsames Gate implementieren

**Files:**
- Create: `tools/v1_governance/handoff.py`
- Create: `tools/v1_governance/pr_gate.py`
- Modify: `tools/v1_governance/cli.py`
- Test: `tests/v1_governance/test_pr_gate.py`

- [ ] **Step 1: Handoff- und Gate-Tests schreiben**

Schreibe sieben Tabellen-getriebene Tests mit den Namen `test_missing_test_evidence_blocks_pr`, `test_failed_test_blocks_pr`, `test_dirty_worktree_blocks_pr`, `test_branch_mismatch_blocks_pr`, `test_unmerged_dependency_blocks_pr`, `test_high_risk_change_requires_fresh_user_gate` und `test_green_code_handoff_is_ready`. Jeder Negativtest vergleicht `ready is False` sowie genau einen stabilen Reason-Code. Der Happy Path vergleicht `GateResult(ready=True, reasons=())`.

Ein grüner Code-Handoff enthält mindestens:

```yaml
commits:
  - sha: 0123456789abcdef0123456789abcdef01234567
    subject: "feat: add async job start"
tests:
  - command: python -m pytest tests/coding -q
    status: passed
    summary: 18 passed
evidence:
  - kind: test-output
    path: results/task-coding-1042/pytest.txt
dependencies: []
deployment_status: not_required
remaining_blockers: []
```

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/v1_governance/test_pr_gate.py -q`

- [ ] **Step 3: Handoff laden und vollständig validieren**

`handoff.py` modelliert `CommitEvidence`, `TestEvidence`, `DependencyEvidence` und `TaskHandoff`. Es lehnt unbekannte Statuswerte, abgekürzte SHAs, leere Test-Summaries und absolute Evidence-Pfade ab. Evidence-Dateien dürfen außerhalb von Tests fehlen, müssen aber innerhalb des Repo-Roots referenziert sein.

- [ ] **Step 4: PR-Gate implementieren**

```python
@dataclass(frozen=True)
class GateResult:
    ready: bool
    reasons: tuple[str, ...]


def evaluate_pr_readiness(
    request: SessionRequest,
    handoff: TaskHandoff,
    audit: GitAudit,
) -> GateResult:
    """Evaluate deterministic PR gates without mutating Git or remote state."""
```

Das Gate ist nur grün, wenn:

- Request explizit freigegeben ist
- Request-, Handoff- und aktueller Branch identisch sind
- Worktree clean ist
- mindestens ein vollständiger Commit gemeldet ist
- mindestens ein Test mit `status: passed` vorliegt
- Evidence nicht leer ist
- alle Dependencies `merged: true` sind
- keine verbleibenden Blocker existieren
- High-Risk-Klassen einen separaten `risk_approval_reference` im Handoff besitzen
- Deployment entweder `not_required`, `verified` oder `pending_user_approval` ist; letzteres erlaubt PR-Erstellung, aber keinen Deploy- oder Release-Claim

- [ ] **Step 5: CLI ergänzen**

```powershell
python -m tools.v1_governance pr check `
  --repo . `
  --request .vibemind/state/session-requests/task-coding-1042.yaml `
  --handoff .vibemind/state/handoffs/task-coding-1042.yaml
```

Exit `0`: bereit für PR-Pflege. Exit `2`: Gate nicht erfüllt, Gründe als JSON/lesbarer Text. Exit `1`: ungültiger Vertrag oder technischer Fehler.

- [ ] **Step 6: GREEN und Commit**

```powershell
python -m pytest tests/v1_governance/test_pr_gate.py -q
git add tools/v1_governance/handoff.py tools/v1_governance/pr_gate.py tools/v1_governance/cli.py tests/v1_governance/test_pr_gate.py
git commit -m "feat: enforce v1 pr readiness evidence"
```

## Task 7: Interaktive V1-Routinen und SmartGit-Runbook dokumentieren

**Files:**
- Create: `.agents/skills/v1-session-start/SKILL.md`
- Create: `.agents/skills/v1-task-handoff/SKILL.md`
- Create: `.agents/skills/v1-pr-integration/SKILL.md`
- Create: `docs/runbooks/v1-session-lifecycle.md`
- Create: `docs/runbooks/smartgit-worktrees.md`
- Modify: `tests/architecture/test_v1_git_policy.py`

- [ ] **Step 1: Architekturtest um Routinen erweitern**

Der Test liest alle fünf Dateien und prüft mindestens die Begriffe:

```python
required = {
    ".agents/skills/v1-session-start/SKILL.md": [
        "explicit user approval",
        "space-cockpit",
        "task",
        "never auto-approve",
    ],
    ".agents/skills/v1-task-handoff/SKILL.md": [
        "commit sha",
        "test evidence",
        "remaining blockers",
    ],
    ".agents/skills/v1-pr-integration/SKILL.md": [
        "merge order",
        "submodule pin",
        "post-merge",
    ],
    "docs/runbooks/smartgit-worktrees.md": [
        "visual client",
        "source of truth",
        "refresh",
    ],
}
```

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/architecture/test_v1_git_policy.py -q`

- [ ] **Step 3: `v1-session-start` schreiben**

Der Skill muss diese feste Reihenfolge vorschreiben:

1. Repo/Worktree/Dirty/Remote/Submodule-Audit read-only ausführen.
2. Bestehenden Code und Verträge im betroffenen Space lesen.
3. Interaktiv Ziel, Scope, Risiken, DoD und Teststrategie mit dem User definieren.
4. Einen `pending` Session Request aus der Vorlage erzeugen.
5. User um explizite Freigabe genau dieses Requests bitten und pausieren.
6. Erst nach neuer Freigabe `approval_status` und Referenz eintragen.
7. Dry-run zeigen; Worktree nur mit `--execute` erzeugen.
8. Nie automatisch implementieren, wenn nur ein Space Cockpit freigegeben wurde.

- [ ] **Step 4: `v1-task-handoff` schreiben**

Der Skill verlangt sauberen Scope, Conventional Commits, exakte Testbefehle/-resultate, Evidence-Pfade, Commit-SHAs, Dependencies, Deploy-Status und Restblocker. Er darf einen fehlgeschlagenen oder übersprungenen Test nie als grün umdeuten.

- [ ] **Step 5: `v1-pr-integration` schreiben**

Der Skill schreibt folgende Merge-Reihenfolge fest:

```text
shared contracts
-> Brain/OpenFang gateway
-> service repository
-> Space adapter
-> V1 submodule pin
-> integration tests
-> deployment configuration
-> Golden Path
-> release tag
```

Er trennt normale, bereits genehmigte Code-Merges von neuen High-Risk-Gates und verbietet Branch-/Worktree-Löschung ohne User-Freigabe.

- [ ] **Step 6: Runbooks schreiben**

`v1-session-lifecycle.md` dokumentiert Zustände:

```text
draft -> pending-user-approval -> approved -> active -> handoff-ready
      -> denied                         -> blocked
handoff-ready -> pr-open -> checks-green -> merged -> verified -> closed
```

`smartgit-worktrees.md` dokumentiert:

- SmartGit ist visueller Client, Git/Manifest/Governance-Gate sind Source of Truth
- Root-Repo öffnen und nach CLI-Worktree-Erzeugung refreshen
- Branch, Working Tree und Submodule-Pin vor Commit visuell prüfen
- keine SmartGit-Aktion zum Auto-Stash, Force-Push, Branch-Löschen oder Direkt-Merge auf Integration verwenden
- Konflikte nicht durch Wegwerfen fremder Änderungen lösen

- [ ] **Step 7: GREEN und Commit**

```powershell
python -m pytest tests/architecture/test_v1_git_policy.py -q
git add .agents/skills docs/runbooks tests/architecture/test_v1_git_policy.py
git commit -m "docs: add v1 session and integration routines"
```

## Task 8: Lokales Gate, PR-Template und CI auf denselben Vertrag setzen

**Files:**
- Create: `scripts/vibemind-governance.ps1`
- Create: `.github/pull_request_template.md`
- Create: `.github/workflows/v1-governance.yml`
- Modify: `tools/v1_governance/cli.py`
- Test: `tests/architecture/test_v1_ci_contract.py`

- [ ] **Step 1: CI-Vertragstest schreiben**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ci_runs_the_same_governance_checks_as_local_wrapper() -> None:
    workflow = (ROOT / ".github/workflows/v1-governance.yml").read_text("utf-8")
    wrapper = (ROOT / "scripts/vibemind-governance.ps1").read_text("utf-8")
    for command in (
        "validate-manifest",
        "pytest tests/architecture tests/v1_governance",
    ):
        assert command in workflow
        assert command in wrapper


def test_pr_template_requires_session_and_evidence() -> None:
    template = (ROOT / ".github/pull_request_template.md").read_text("utf-8")
    for heading in (
        "Session approval",
        "Scope",
        "Tests and evidence",
        "Dependencies and merge order",
        "Risk gate",
        "Post-merge verification",
    ):
        assert heading in template
```

- [ ] **Step 2: RED ausführen**

Run: `python -m pytest tests/architecture/test_v1_ci_contract.py -q`

- [ ] **Step 3: Manifest-Unterbefehl im gemeinsamen CLI exponieren**

`python -m tools.v1_governance validate-manifest --repo . --manifest repo-manifest.yaml` lädt das Manifest, gibt alle `ManifestIssue`-Objekte stabil als JSON aus und beendet sich bei leerer Issue-Liste mit Exit `0`, sonst mit Exit `2`. Vertrags- oder technische Fehler enden mit Exit `1`. Der Befehl mutiert weder Git noch Dateien.

- [ ] **Step 4: Lokalen PowerShell-Einstieg anlegen**

```powershell
[CmdletBinding()]
param(
    [ValidateSet('check', 'audit', 'validate-manifest')]
    [string]$Action = 'check',
    [string]$Repo = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Push-Location $Repo
try {
    switch ($Action) {
        'audit' {
            python -m tools.v1_governance audit --repo . --format json
        }
        'validate-manifest' {
            python -m tools.v1_governance validate-manifest --repo . --manifest repo-manifest.yaml
        }
        'check' {
            python -m tools.v1_governance validate-manifest --repo . --manifest repo-manifest.yaml
            python -m pytest tests/architecture tests/v1_governance -q
        }
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
```

- [ ] **Step 5: PR-Template anlegen**

```markdown
## Session approval

- Session ID:
- Approval reference:
- Approved objective:

## Scope

- Repositories and allowed paths:
- Out of scope:

## Tests and evidence

- Commands and exact results:
- Evidence paths:
- Commit SHAs:

## Dependencies and merge order

- Required PRs/pins:
- Position in merge chain:

## Risk gate

- Risk class:
- Additional user approval required/received:

## Post-merge verification

- Verification command or Golden Path:
- Remaining blockers:
```

- [ ] **Step 6: GitHub Workflow anlegen**

```yaml
name: V1 Governance

on:
  pull_request:
  push:
    branches: [master, main]

jobs:
  governance:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install governance dependencies
        run: python -m pip install -r tools/v1_governance/requirements.txt
      - name: validate-manifest
        run: python -m tools.v1_governance validate-manifest --repo . --manifest repo-manifest.yaml
      - name: pytest tests/architecture tests/v1_governance
        run: python -m pytest tests/architecture tests/v1_governance -q
      - name: Reject dirty generated state
        shell: pwsh
        run: |
          if (git status --porcelain) {
            git status --short
            throw 'Governance checks changed tracked files.'
          }
```

Keine Secrets, Deploy-Schritte oder automatische Merges in diesen Workflow aufnehmen.

- [ ] **Step 7: GREEN und Commit**

```powershell
python -m pytest tests/architecture/test_v1_ci_contract.py -q
pwsh -File scripts/vibemind-governance.ps1 -Action check -Repo .
git add scripts/vibemind-governance.ps1 .github tools/v1_governance/cli.py tests/architecture/test_v1_ci_contract.py
git commit -m "ci: enforce v1 governance gate"
```

## Task 9: Gesamtnachweis und PR-Handoff erzeugen

**Files:**
- Create locally, ignored: `.vibemind/state/session-requests/task-platform-0005-governance-integration.yaml`
- Create locally, ignored: `.vibemind/state/handoffs/task-platform-0005-governance-integration.yaml`
- Modify only if verification exposes a defect: files from Tasks 1–8

- [ ] **Step 1: Unfertige Marker und Secret-Beispiele suchen**

```powershell
$markers = @('TO' + 'DO', 'T' + 'BD', 'PLACE' + 'HOLDER', 'change' + 'me', 'example-' + 'secret')
rg -n ($markers -join '|') AGENTS.md CLAUDE.md repo-manifest.yaml .agents tools/v1_governance scripts/vibemind-governance.ps1 docs/runbooks .github tests
if ($LASTEXITCODE -eq 0) { throw 'Unresolved marker found.' }
if ($LASTEXITCODE -ne 1) { throw "Marker scan failed with exit $LASTEXITCODE." }
```

Expected: keine ungeklärten Treffer. Dokumentative Negativbeispiele müssen explizit begründet sein oder entfernt werden.

- [ ] **Step 2: Gesamte Foundation verifizieren**

```powershell
python -m pip install -r tools/v1_governance/requirements.txt
python -m tools.v1_governance validate-manifest --repo . --manifest repo-manifest.yaml
python -m tools.v1_governance audit --repo . --format json
python -m pytest tests/architecture tests/v1_governance -q
pwsh -File scripts/vibemind-governance.ps1 -Action check -Repo .
git diff --check
git status --short --branch
```

Expected:

- Manifest: `0 issues`
- Audit: korrekter Branch/HEAD, keine geheimen Inhalte
- pytest: alle Tests passed
- Wrapper: Exit `0`
- `git diff --check`: keine Ausgabe
- Worktree: clean nach dem letzten Commit

- [ ] **Step 3: Handoff für genau diese Session vervollständigen**

Der lokale Handoff listet alle Commits aus Tasks 1–8, jeden exakten Testbefehl und sein Resultat, Manifest-/Audit-Evidence, Dependencies und Restblocker. Der Handoff wird mit `pr check` validiert:

```powershell
python -m tools.v1_governance pr check `
  --repo . `
  --request .vibemind/state/session-requests/task-platform-0005-governance-integration.yaml `
  --handoff .vibemind/state/handoffs/task-platform-0005-governance-integration.yaml
```

Expected: Exit `0` und `ready: true`.

- [ ] **Step 4: PR erstellen und vom V1-Orchestrator pflegen lassen**

Der Orchestrator:

1. prüft Branch, Commits, Remote-Parität und Gate erneut,
2. pusht den Feature-Branch,
3. erstellt den PR mit Session-ID, Approval, Scope, Tests, Evidence und Merge-Position,
4. pflegt CI/Reviews/Konflikte,
5. merged erst bei grünen Gates,
6. führt Post-Merge-Tests aus,
7. meldet exakten Merge-SHA und offene Punkte,
8. löscht Branch/Worktree **nicht**, bevor der User die Bereinigung freigibt.

## Definition of Done für Plan 1

- Kein schreibender V1-Task-Worktree kann ohne validen, explizit freigegebenen Session Request erstellt werden.
- Space Cockpits bleiben technisch read-only.
- Der Ausgangs-Checkout und fremde Änderungen bleiben unberührt.
- Repo-/Submodule-Inventar, Git-Zustand, Handoff und PR-Readiness sind lokal reproduzierbar.
- SmartGit und CLI zeigen dieselben Branches/Worktrees; SmartGit besitzt keine Sonderlogik.
- Lokaler Gate-Befehl und CI führen dieselben Prüfungen aus.
- Historische WORKBOARD-Inhalte bleiben erhalten, nehmen aber keine neuen Claims auf.
- Der bestehende `master`-zu-`main`-Übergang ist ehrlich dokumentiert und nicht stillschweigend ausgeführt.
- Es wurde keine Space-Session, kein Deployment, keine Repository-Verschiebung und keine OpenFang-Integration gestartet.

## Nachgelagerte, jeweils separat freizugebende Pläne

1. Brain Task Ledger und kanonische Space Registry
2. Brain → OpenFang Execution/Approval/Cost Gateway
3. Shared Memory, Task Brief, Approval, Todo und Evidence Contracts
4. Repo-Topologie und schrittweise Auflösung verschachtelter Submodule
5. Je Space ein interaktiver Cockpit-Plan und danach einzelne Task-Pläne
6. Separate Update-Spezifikationen für n8n, AgentFarm und Video
7. Minibook interne Projektion sowie OpenClaw-/Desktop-Zugriff im privaten Netz
8. Golden Paths, Proxmox-Deployment und Release-Gates
