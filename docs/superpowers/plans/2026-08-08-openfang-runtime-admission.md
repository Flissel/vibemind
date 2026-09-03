# OpenFang Runtime Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Externe deterministische Brain-Tool-Aufrufe werden von OpenFang mit persistenter Approval-, Cost-, Replay- und Receipt-Autorität fail-closed ausgeführt.

**Architecture:** OpenFang erhält additive Runtime-Authority-Verträge, einen SQLite-Store und einen zentralen `RuntimeAdmissionService`. Die `/mcp tools/call`-Route wird bei aktivierter Konfiguration durch diesen Service geführt; Brain fordert planweite Approval und pro Invocation eine Cost-Reservation an und verwendet eine stabile Invocation-ID. Bestehende Agent-Loops und kognitive Handoff-V1-Verträge bleiben in dieser Lieferwelle unverändert.

**Tech Stack:** Rust 2021, Tokio, Axum, Serde, rusqlite, SHA-256, Python 3, FastAPI, pytest, Git-Submodule-Pins, V1-Governance-Tests.

**Design:** `docs/superpowers/specs/2026-08-08-openfang-runtime-admission-design.md`

---

## 1. Lieferzug und Merge-Reihenfolge

1. OpenFang-Branch `codex/openfang/runtime-admission-v1`: Tasks 1–6, mehrere kleine Commits, ein PR nach `main`.
2. VibeMind-OS-Branch `codex/brain/runtime-admission-client-v1`: Tasks 7–8, basiert auf aktuellem `origin/master`, pinnt den gemergten OpenFang-Commit, PR nach `master`.
3. Outer-Branches in Reihenfolge: Gitlink/Manifest, Ledger, Deployment-Regate; Task 9.
4. Task 10 ist ein read-only Golden Path auf dem deployten Stack. Deployment oder Proxmox-Mutation benötigt vor Ausführung eine request-spezifische Freigabe.

Jeder schreibende Task arbeitet in einem isolierten Worktree. Desktop-Worktrees und fremde Änderungen bleiben unberührt. Kein Branch wird gelöscht.

## 2. Dateistruktur

### OpenFang

- Create: `crates/openfang-types/src/runtime_admission.rs` — additive Wire- und Runtime-Typen.
- Modify: `crates/openfang-types/src/lib.rs` — Modul exportieren.
- Modify: `crates/openfang-types/src/config.rs` — flag-gated Runtime-Admission-Konfiguration.
- Create: `crates/openfang-memory/src/runtime_authority.rs` — SQLite-Store und atomare Transaktionen.
- Modify: `crates/openfang-memory/src/migration.rs` — Schema V9 mit drei Authority-Tabellen.
- Modify: `crates/openfang-memory/src/lib.rs` — Store exportieren.
- Create: `crates/openfang-kernel/src/runtime_admission.rs` — zentrale Zustandsmaschine, Clock und Singleflight.
- Modify: `crates/openfang-kernel/src/lib.rs` — Service exportieren.
- Modify: `crates/openfang-kernel/src/kernel.rs` — Service booten und `KernelHandle` implementieren.
- Modify: `crates/openfang-runtime/src/kernel_handle.rs` — schmale Admission-/Finalize-Ports.
- Create: `crates/openfang-runtime/src/runtime_execution.rs` — externer Ausführungs-Origin und Closure-basierter Invoker-Port.
- Create: `crates/openfang-runtime/src/result_receipt.rs` — Hash, konservative JSON-Redaction und Größenlimit.
- Modify: `crates/openfang-runtime/src/lib.rs` — Runtime-Module exportieren.
- Modify: `crates/openfang-api/src/routes.rs` — Authority-Routen, Header-Parser und MCP-Gate.
- Modify: `crates/openfang-api/src/server.rs` — neue authentifizierte Routen registrieren.
- Modify: `crates/openfang-api/tests/api_integration_test.rs` — reale Kernel-/HTTP-Integration ohne LLM- oder MCP-Netzwerk.

### VibeMind-OS / Brain

- Create: `brain/the_brain/core/openfang_runtime_authority.py` — Authority-Client und typisierte Pending-/Unknown-Ergebnisse.
- Modify: `brain/the_brain/core/capability_targets.py` — MCP-Aufruf mit server-issued Refs und stabiler Invocation-ID.
- Modify: `brain/the_brain/core/plan_schema.py` — additive positive `plan_revision`.
- Modify: `brain/the_brain/core/plan_executor.py` — Runtime-Kontext pro Hop; Pending ist pausiert, nicht fehlgeschlagen.
- Modify: `brain/the_brain/web/routers/introspection.py` — übermittelte Trace-ID bei Replay bewahren und Pending offen ausgeben.
- Create: `brain/the_brain/tests/test_openfang_runtime_authority.py` — Authority-Client-Vertrag.
- Modify: `brain/the_brain/tests/test_openfang_mcp_executor.py` — Transport, Replay und Error-Mapping.
- Modify: `brain/the_brain/tests/test_plan_executor_registered_openfang.py` — stabile Invocation und pausierter Plan.
- Modify: `brain/the_brain/tests/test_multihop_response_contract.py` — HTTP-Pending-/Replay-Vertrag.
- Modify: `brain/the_brain/tests/test_openfang_agent_manifest.py` — gemergten OpenFang-Pin und Runtime-Dateien prüfen.
- Modify: `openfang` — Gitlink auf den gemergten OpenFang-PR.

### Outer V1

- Modify: `vibemind-os` — Gitlink auf den gemergten Child-PR.
- Modify: `repo-manifest.yaml` — Child-/OpenFang-Pins und Parent-Pins.
- Modify: `tests/v1_governance/test_manifest.py` — Authority-Chain-Konstanten.
- Modify: `docs/governance/cockpit-reconciliation-ledger-v1.json` — append-only Merge- und Chain-Evidenz.
- Modify: `tools/v1_governance/reconciliation.py` — Closed-World-Fakten.
- Modify: `tests/v1_governance/test_cockpit_reconciliation_ledger.py` — neue Chain und Tamper-Negative.
- Modify: `scripts/deployment-readiness.ps1` — neue statische Pins.
- Modify: `tests/deployment/deployment-readiness.Tests.ps1` — Pin- und Superseded-Pin-Assertions.

---

### Task 1: Additive Runtime-Verträge und Konfiguration

**Repository:** OpenFang
**Branch:** `codex/openfang/runtime-admission-v1`

**Files:**
- Create: `crates/openfang-types/src/runtime_admission.rs`
- Modify: `crates/openfang-types/src/lib.rs`
- Modify: `crates/openfang-types/src/config.rs`

- [ ] **Step 1: Isolierten Worktree vom aktuellen Remote-Head erstellen**

```powershell
git -C E:\CodexWorktrees\outer-brain-coder-chain-acceptance\vibemind-os\openfang fetch origin main
git -C E:\CodexWorktrees\outer-brain-coder-chain-acceptance\vibemind-os\openfang worktree add -b codex/openfang/runtime-admission-v1 E:\CodexWorktrees\openfang-runtime-admission origin/main
git -C E:\CodexWorktrees\openfang-runtime-admission status --short --branch
```

Expected: sauberer Branch auf dem frisch gefetchten `origin/main`.

- [ ] **Step 2: Failing Contract-Tests zuerst schreiben**

In `runtime_admission.rs` Tests für diese geschlossenen Regeln anlegen:

```rust
fn valid_cost_request(max_cost_microusd: u64) -> RuntimeCostReservationRequestV1 {
    RuntimeCostReservationRequestV1 {
        contract_version: RuntimeAuthorityContractVersion::V1,
        correlation_id: "corr-1".into(),
        plan_id: "plan-1".into(),
        plan_revision: 1,
        space_id: "ideas".into(),
        agent_id: "00000000-0000-0000-0000-000000000001".into(),
        approval_ref: "approval:plan-1".into(),
        invocation_id: "brain:plan-1:1:step-1".into(),
        max_cost_microusd,
        ttl_seconds: 300,
    }
}

fn valid_context() -> RuntimeAdmissionContextV1 {
    RuntimeAdmissionContextV1 {
        invocation_id: "brain:plan-1:1:step-1".into(),
        caller_agent_id: "00000000-0000-0000-0000-000000000001".into(),
        approval_ref: "approval:plan-1".into(),
        cost_ref: "cost:step-1".into(),
        tool_name: "mcp_vibemind_db_ideas_list".into(),
        arguments_sha256: "a".repeat(64),
    }
}

#[test]
fn deterministic_zero_cost_reservation_is_valid_and_invocation_bound() {
    let request = valid_cost_request(0);
    assert!(request.validate().is_ok());
    assert_eq!(request.invocation_id, "brain:plan-1:1:step-1");
}

#[test]
fn admission_context_rejects_blank_refs_and_non_sha256_arguments_digest() {
    let mut context = valid_context();
    context.cost_ref = " ".into();
    assert!(context.validate().unwrap_err().contains("cost_ref"));

    let mut context = valid_context();
    context.arguments_sha256 = "abc".into();
    assert!(context.validate().unwrap_err().contains("arguments_sha256"));
}

#[test]
fn receipt_status_and_result_storage_modes_are_closed_enums() {
    assert!(serde_json::from_value::<ExecutionReceiptStatus>(json!("prepared")).is_ok());
    assert!(serde_json::from_value::<ExecutionReceiptStatus>(json!("retrying")).is_err());
    assert!(serde_json::from_value::<ResultStorageMode>(json!("digest_only")).is_ok());
}
```

In `config.rs` einen Test ergänzen:

```rust
#[test]
fn runtime_admission_defaults_disabled_and_bounded() {
    let cfg = RuntimeAdmissionConfig::default();
    assert!(!cfg.enabled);
    assert_eq!(cfg.receipt_max_bytes, 65_536);
    assert!(cfg.dispatch_stale_after_secs > 0);
}
```

- [ ] **Step 3: RED ausführen**

```powershell
cargo test --offline -p openfang-types runtime_admission --lib
```

Expected: FAIL, weil Modul und Typen noch fehlen.

- [ ] **Step 4: Additive Typen implementieren**

Die bestehenden `AuthorityAdmissionRequestV1`- und `CostReservationRequestV1`-Typen nicht verändern. In der neuen Datei mindestens diese Typen definieren:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeAuthorityContractVersion { V1 }

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimePlanApprovalRequestV1 {
    pub contract_version: RuntimeAuthorityContractVersion,
    pub correlation_id: String,
    pub plan_id: String,
    pub plan_revision: u64,
    pub space_id: String,
    pub agent_id: String,
    pub max_plan_cost_microusd: u64,
    pub ttl_seconds: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case", deny_unknown_fields)]
pub enum RuntimePlanApprovalOutcomeV1 {
    Denied { reason_code: String },
    PendingApproval { approval_ref: String },
    Approved { approval_ref: String, expires_at: DateTime<Utc> },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeCostReservationRequestV1 {
    pub contract_version: RuntimeAuthorityContractVersion,
    pub correlation_id: String,
    pub plan_id: String,
    pub plan_revision: u64,
    pub space_id: String,
    pub agent_id: String,
    pub approval_ref: String,
    pub invocation_id: String,
    pub max_cost_microusd: u64,
    pub ttl_seconds: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeAdmissionContextV1 {
    pub invocation_id: String,
    pub caller_agent_id: String,
    pub approval_ref: String,
    pub cost_ref: String,
    pub tool_name: String,
    pub arguments_sha256: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionReceiptStatus { Prepared, Dispatching, Succeeded, Failed, OutcomeUnknown }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResultStorageMode { RedactedEnvelope, DigestOnly }

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeCostReservationRecordV1 {
    pub cost_ref: String,
    pub approval_ref: String,
    pub invocation_id: String,
    pub correlation_id: String,
    pub plan_id: String,
    pub plan_revision: u64,
    pub space_id: String,
    pub agent_id: String,
    pub reserved_micro_usd: u64,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case", deny_unknown_fields)]
pub enum RuntimeCostReservationOutcomeV1 {
    Denied { reason_code: String },
    Reserved { reservation: RuntimeCostReservationRecordV1 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionReceiptV1 {
    pub invocation_id: String,
    pub correlation_id: String,
    pub plan_id: String,
    pub plan_revision: u64,
    pub space_id: String,
    pub agent_id: String,
    pub tool_name: String,
    pub arguments_sha256: String,
    pub approval_ref: String,
    pub cost_ref: String,
    pub status: ExecutionReceiptStatus,
    pub result_sha256: Option<String>,
    pub result_storage_mode: Option<ResultStorageMode>,
    pub result_envelope: Option<String>,
    pub error_class: Option<String>,
    pub prepared_at: DateTime<Utc>,
    pub dispatch_started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case", deny_unknown_fields)]
pub enum RuntimeAdmissionDecisionV1 {
    Denied { reason_code: String },
    PendingApproval { approval_ref: String },
    CostUnavailable { reason_code: String },
    Admitted { receipt: ExecutionReceiptV1 },
    InProgress { receipt: ExecutionReceiptV1 },
    Replay { receipt: ExecutionReceiptV1 },
    OutcomeUnknown { receipt: ExecutionReceiptV1 },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReceiptFinalStatus { Succeeded, Failed, OutcomeUnknown }

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReceiptFinalizationV1 {
    pub status: ReceiptFinalStatus,
    pub actual_cost_micro_usd: u64,
    pub result_sha256: Option<String>,
    pub result_storage_mode: Option<ResultStorageMode>,
    pub result_envelope: Option<String>,
    pub error_class: Option<String>,
}
```

Jede Request-/Context-Struktur erhält `validate()`. `max_cost_microusd == 0` ist gültig; Revision und TTL müssen positiv sein; IDs/Refs dürfen nach `trim()` nicht leer sein; `arguments_sha256` muss genau 64 ASCII-Hexzeichen enthalten.

In `config.rs` ergänzen:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct RuntimeAdmissionConfig {
    pub enabled: bool,
    pub receipt_max_bytes: usize,
    pub dispatch_stale_after_secs: u64,
}

impl Default for RuntimeAdmissionConfig {
    fn default() -> Self {
        Self { enabled: false, receipt_max_bytes: 65_536, dispatch_stale_after_secs: 300 }
    }
}
```

`KernelConfig` erhält `pub runtime_admission: RuntimeAdmissionConfig` mit Default und Validierung für positive Grenzen.

- [ ] **Step 5: GREEN und Regressionen ausführen**

```powershell
cargo test --offline -p openfang-types runtime_admission --lib
cargo test --offline -p openfang-types --lib
cargo check --offline -p openfang-types
```

Expected: alle drei Befehle PASS.

- [ ] **Step 6: Commit erstellen**

```powershell
git add crates/openfang-types/src/runtime_admission.rs crates/openfang-types/src/lib.rs crates/openfang-types/src/config.rs
git diff --cached --check
git commit -m "feat(types): define runtime admission contracts"
```

Expected: exakt drei Pfade im Commit.

---

### Task 2: SQLite-Schema und atomarer Authority-Store

**Files:**
- Create: `crates/openfang-memory/src/runtime_authority.rs`
- Modify: `crates/openfang-memory/src/migration.rs`
- Modify: `crates/openfang-memory/src/lib.rs`

- [ ] **Step 1: Migration- und Store-Tests schreiben**

Tests müssen diese Fälle konkret belegen:

```rust
#[test]
fn migration_v9_creates_runtime_authority_tables_and_is_idempotent() {
    let conn = Connection::open_in_memory().unwrap();
    run_migrations(&conn).unwrap();
    run_migrations(&conn).unwrap();
    for table in ["runtime_approvals", "cost_reservations", "execution_receipts"] {
        let count: i64 = conn.query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
            [table], |row| row.get(0),
        ).unwrap();
        assert_eq!(count, 1, "missing {table}");
    }
}

#[test]
fn concurrent_duplicate_admission_consumes_cost_once_and_creates_one_receipt() {
    // Zwei Threads, eine Barrier, gleiche invocation_id und cost_ref.
    // Genau ein Ergebnis ist Admitted; das andere ist InProgress oder Replay.
    // COUNT(execution_receipts)=1 und cost status='consumed'.
}

#[test]
fn same_refs_cannot_cross_agent_tool_or_arguments_digest() {
    // Nach erster Bindung drei mutierte Contexts prüfen.
    // Jeder StoreAdmission-Wert muss Denied sein.
}
```

- [ ] **Step 2: RED ausführen**

```powershell
cargo test --offline -p openfang-memory runtime_authority --lib
```

Expected: FAIL, weil Migration V9 und Store fehlen.

- [ ] **Step 3: Schema V9 implementieren**

`SCHEMA_VERSION` auf `9` erhöhen und `migrate_v9` mit folgendem Schema hinzufügen:

```sql
CREATE TABLE IF NOT EXISTS runtime_approvals (
    approval_ref TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL CHECK(plan_revision > 0),
    space_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    max_plan_cost_microusd INTEGER NOT NULL CHECK(max_plan_cost_microusd >= 0),
    status TEXT NOT NULL CHECK(status IN ('pending','approved','denied','expired')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    expires_at TEXT NOT NULL,
    UNIQUE(plan_id, plan_revision, space_id, agent_id)
);

CREATE TABLE IF NOT EXISTS cost_reservations (
    cost_ref TEXT PRIMARY KEY,
    approval_ref TEXT NOT NULL,
    invocation_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL CHECK(plan_revision > 0),
    space_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd >= 0),
    settled_micro_usd INTEGER CHECK(settled_micro_usd >= 0),
    status TEXT NOT NULL CHECK(status IN ('reserved','consumed','released','settled','held_unknown')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    settled_at TEXT
);

CREATE TABLE IF NOT EXISTS execution_receipts (
    invocation_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL CHECK(plan_revision > 0),
    space_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_sha256 TEXT NOT NULL,
    approval_ref TEXT NOT NULL,
    cost_ref TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('prepared','dispatching','succeeded','failed','outcome_unknown')),
    result_sha256 TEXT,
    result_storage_mode TEXT CHECK(result_storage_mode IN ('redacted_envelope','digest_only')),
    result_envelope TEXT,
    error_class TEXT,
    prepared_at TEXT NOT NULL,
    dispatch_started_at TEXT,
    finished_at TEXT
);
```

Zusätzlich Indizes auf Approval-Status/Expiry, Cost-Status/Expiry und Receipt-Status anlegen und Migration 9 in `migrations` protokollieren.

- [ ] **Step 4: Store mit Immediate-Transactions implementieren**

Die öffentliche Oberfläche ist exakt:

```rust
#[derive(Clone)]
pub struct RuntimeAuthorityStore { conn: Arc<Mutex<Connection>> }

pub enum StoreAdmission {
    Denied { reason_code: String },
    PendingApproval { approval_ref: String },
    Admitted { receipt: ExecutionReceiptV1 },
    InProgress { receipt: ExecutionReceiptV1 },
    Replay { receipt: ExecutionReceiptV1 },
    OutcomeUnknown { receipt: ExecutionReceiptV1 },
}

impl RuntimeAuthorityStore {
    pub fn new(conn: Arc<Mutex<Connection>>) -> Self;
    pub fn request_plan_approval(&self, request: &RuntimePlanApprovalRequestV1,
                                 auto_approve: bool, now: DateTime<Utc>)
        -> OpenFangResult<RuntimePlanApprovalOutcomeV1>;
    pub fn resolve_plan_approval(&self, approval_ref: &str, approved: bool,
                                 now: DateTime<Utc>) -> OpenFangResult<()>;
    pub fn reserve_cost(&self, request: &RuntimeCostReservationRequestV1,
                        now: DateTime<Utc>) -> OpenFangResult<RuntimeCostReservationOutcomeV1>;
    pub fn admit(&self, context: &RuntimeAdmissionContextV1,
                 now: DateTime<Utc>) -> OpenFangResult<StoreAdmission>;
    pub fn mark_dispatching(&self, invocation_id: &str,
                            now: DateTime<Utc>) -> OpenFangResult<ExecutionReceiptV1>;
    pub fn finalize(&self, invocation_id: &str, update: &ReceiptFinalizationV1,
                    now: DateTime<Utc>) -> OpenFangResult<ExecutionReceiptV1>;
    pub fn get_receipt(&self, invocation_id: &str)
        -> OpenFangResult<Option<ExecutionReceiptV1>>;
    pub fn reconcile_stale_dispatching(&self, cutoff: DateTime<Utc>,
                                       now: DateTime<Utc>) -> OpenFangResult<u64>;
}
```

`admit` verwendet `TransactionBehavior::Immediate`. In derselben Transaktion werden Approval/Cost exakt gebunden, ein `prepared`-Receipt eingefügt und der Cost-Status mit `WHERE status='reserved'` auf `consumed` gesetzt. Ein Unique-Konflikt liest das bestehende Receipt und klassifiziert ausschließlich anhand des gespeicherten Status; Bindungsdrift ist immer `Denied`.

`reserve_cost` summiert nicht final freigegebene Reservierungen derselben Approval in derselben Immediate-Transaction und verweigert eine Summe oberhalb `max_plan_cost_microusd`. Null-Reservierungen bleiben vollständig im selben Pfad.

- [ ] **Step 5: GREEN, Concurrency und Migration ausführen**

```powershell
cargo test --offline -p openfang-memory runtime_authority --lib -- --nocapture
cargo test --offline -p openfang-memory migration --lib
cargo test --offline -p openfang-memory --lib
```

Expected: PASS; Concurrency-Test meldet einen Receipt und eine Consumption.

- [ ] **Step 6: Commit erstellen**

```powershell
git add crates/openfang-memory/src/runtime_authority.rs crates/openfang-memory/src/migration.rs crates/openfang-memory/src/lib.rs
git diff --cached --check
git commit -m "feat(memory): persist runtime authority state"
```

---

### Task 3: Zentraler Kernel-Service und Recovery

**Files:**
- Create: `crates/openfang-kernel/src/runtime_admission.rs`
- Modify: `crates/openfang-kernel/src/lib.rs`
- Modify: `crates/openfang-kernel/src/kernel.rs`
- Modify: `crates/openfang-runtime/src/kernel_handle.rs`

- [ ] **Step 1: Behavioral RED-Tests mit Countern und Fake-Clock schreiben**

Im Testmodul eine `FakeRuntimeAuthorityRepository` mit exakt fünf `AtomicUsize`-Feldern (`approval_lookup_calls`, `cost_consumption_calls`, `dispatch_calls`, `receipt_write_calls`, `settlement_calls`) und eine `FakeClock` mit festem `2026-08-08T10:00:00Z` anlegen. Dann folgende Matrix als eigenständige Tests implementieren:

| Testname | Repository-Ergebnis | Exakte Assertions |
|---|---|---|
| `denied_approval_stops_before_cost_consumption_and_dispatch` | `Denied` beim Approval-Lookup | Approval `1`, alle anderen Counter `0` |
| `pending_approval_returns_only_approval_ref_without_cost_or_dispatch` | `PendingApproval` | Outcome trägt nur den Approval-Fingerprint; Cost/Dispatch/Receipt/Settlement `0` |
| `mismatched_expired_or_consumed_cost_ref_stops_before_dispatch` | je Subcase `Denied` mit festem Reason-Code | Dispatch `0`, Settlement `0` |
| `replay_returns_stored_receipt_without_redispatch_or_recharge` | finales `Succeeded`-Receipt | zweiter Admit liefert `Replay`; Dispatch/Settlement bleiben jeweils `1` |
| `concurrent_duplicate_invocations_singleflight_one_dispatch_one_charge` | zwei Tasks hinter `tokio::sync::Barrier` | genau ein `Admitted`; zweites Ergebnis `InProgress` oder `Replay`; Dispatch/Settlement `1` |
| `boot_recovery_marks_stale_dispatching_outcome_unknown` | ein altes `dispatching`-Receipt | Recovery count `1`, Receipt `OutcomeUnknown`, Cost `HeldUnknown` |

Pre-Dispatch-Tests verwenden als Invoker `|| async { panic!("dispatch must not run") }`. Damit schlägt jeder versehentliche Dispatch direkt fehl.

- [ ] **Step 2: RED ausführen**

```powershell
cargo test --offline -p openfang-kernel runtime_admission --lib
```

Expected: FAIL, weil Service und `KernelHandle`-Ports fehlen.

- [ ] **Step 3: Service und Clock implementieren**

```rust
pub trait RuntimeClock: Send + Sync {
    fn now(&self) -> DateTime<Utc>;
}

pub struct SystemRuntimeClock;

pub trait RuntimeAuthorityRepository: Send + Sync {
    fn request_plan_approval(&self, request: &RuntimePlanApprovalRequestV1,
                             auto_approve: bool, now: DateTime<Utc>)
        -> OpenFangResult<RuntimePlanApprovalOutcomeV1>;
    fn resolve_plan_approval(&self, approval_ref: &str, approved: bool,
                             now: DateTime<Utc>) -> OpenFangResult<()>;
    fn reserve_cost(&self, request: &RuntimeCostReservationRequestV1,
                    now: DateTime<Utc>) -> OpenFangResult<RuntimeCostReservationOutcomeV1>;
    fn admit(&self, context: &RuntimeAdmissionContextV1,
             now: DateTime<Utc>) -> OpenFangResult<StoreAdmission>;
    fn mark_dispatching(&self, invocation_id: &str,
                        now: DateTime<Utc>) -> OpenFangResult<ExecutionReceiptV1>;
    fn finalize(&self, invocation_id: &str, update: &ReceiptFinalizationV1,
                now: DateTime<Utc>) -> OpenFangResult<ExecutionReceiptV1>;
    fn get_receipt(&self, invocation_id: &str)
        -> OpenFangResult<Option<ExecutionReceiptV1>>;
    fn reconcile_stale_dispatching(&self, cutoff: DateTime<Utc>,
                                   now: DateTime<Utc>) -> OpenFangResult<u64>;
}

pub struct RuntimeAdmissionService {
    store: Arc<dyn RuntimeAuthorityRepository>,
    clock: Arc<dyn RuntimeClock>,
    singleflight: DashMap<String, Arc<tokio::sync::Mutex<()>>>,
    receipt_max_bytes: usize,
    dispatch_stale_after_secs: u64,
}

impl RuntimeAdmissionService {
    pub fn new(store: Arc<dyn RuntimeAuthorityRepository>,
               clock: Arc<dyn RuntimeClock>,
               receipt_max_bytes: usize,
               dispatch_stale_after_secs: u64) -> Self;
    pub fn request_plan_approval(&self, request: &RuntimePlanApprovalRequestV1,
                                 auto_approve: bool)
        -> OpenFangResult<RuntimePlanApprovalOutcomeV1>;
    pub fn resolve_plan_approval(&self, approval_ref: &str,
                                 approved: bool) -> OpenFangResult<()>;
    pub fn reserve_cost(&self, request: &RuntimeCostReservationRequestV1)
        -> OpenFangResult<RuntimeCostReservationOutcomeV1>;
    pub async fn admit(&self, context: &RuntimeAdmissionContextV1)
        -> OpenFangResult<RuntimeAdmissionDecisionV1>;
    pub fn mark_dispatching(&self, invocation_id: &str)
        -> OpenFangResult<ExecutionReceiptV1>;
    pub fn finalize(&self, invocation_id: &str, update: &ReceiptFinalizationV1)
        -> OpenFangResult<ExecutionReceiptV1>;
    pub fn mark_outcome_unknown(&self, invocation_id: &str, error_class: &str)
        -> OpenFangResult<ExecutionReceiptV1>;
    pub fn read_receipt(&self, invocation_id: &str)
        -> OpenFangResult<Option<ExecutionReceiptV1>>;
}
```

Direkt nach dem Trait wird `RuntimeAuthorityRepository for RuntimeAuthorityStore` implementiert. Jede der acht Trait-Methoden ruft die gleichnamige Store-Methode mit denselben Argumenten auf und gibt deren Ergebnis unverändert zurück; dadurch kann der Produktionsservice den SQLite-Store und der Testservice die Counter-Fake verwenden.

`admit` hält den per-Invocation-Singleflight-Guard bis zur Klassifikation. Persistente Unique-Constraints bleiben die Autorität nach Neustarts. Beim Boot ruft der Service `reconcile_stale_dispatching(now - configured_duration)` auf; diese Records werden niemals erneut dispatcht.

- [ ] **Step 4: Kernel und Trait verdrahten**

`OpenFangKernel` erhält:

```rust
pub runtime_admission: Arc<crate::runtime_admission::RuntimeAdmissionService>,
```

Beim Boot wird der Produktionsservice explizit mit `Arc::new(RuntimeAuthorityStore::new(memory.usage_conn()))`, `Arc::new(SystemRuntimeClock)` und den beiden Werten aus `config.runtime_admission` erstellt. Danach läuft einmal `reconcile_stale_dispatching`. `KernelHandle` erhält diese additiven Methoden mit fail-closed Defaults (`Err("runtime admission unavailable")`):

```rust
async fn admit_runtime_tool(&self, context: &RuntimeAdmissionContextV1)
    -> Result<RuntimeAdmissionDecisionV1, String>;
fn mark_runtime_dispatching(&self, invocation_id: &str)
    -> Result<ExecutionReceiptV1, String>;
fn finalize_runtime_tool(&self, invocation_id: &str, update: &ReceiptFinalizationV1)
    -> Result<ExecutionReceiptV1, String>;
fn mark_runtime_outcome_unknown(&self, invocation_id: &str, error_class: &str)
    -> Result<ExecutionReceiptV1, String>;
fn read_runtime_receipt(&self, invocation_id: &str)
    -> Result<Option<ExecutionReceiptV1>, String>;
```

`impl KernelHandle for OpenFangKernel` delegiert an den Service. Bestehende Trait-Testdoubles kompilieren durch die Default-Implementierungen unverändert.

- [ ] **Step 5: GREEN und Kernel-Regressionen ausführen**

```powershell
cargo test --offline -p openfang-kernel runtime_admission --lib -- --nocapture
cargo test --offline -p openfang-kernel --lib
cargo check --offline -p openfang-kernel
```

Expected: alle Tests PASS; kein LLM-/MCP-Prozess wird gestartet.

- [ ] **Step 6: Commit erstellen**

```powershell
git add crates/openfang-kernel/src/runtime_admission.rs crates/openfang-kernel/src/lib.rs crates/openfang-kernel/src/kernel.rs crates/openfang-runtime/src/kernel_handle.rs
git diff --cached --check
git commit -m "feat(kernel): coordinate runtime admission"
```

---

### Task 4: Externer Execution-Origin und datensparsames Receipt

**Files:**
- Create: `crates/openfang-runtime/src/runtime_execution.rs`
- Create: `crates/openfang-runtime/src/result_receipt.rs`
- Modify: `crates/openfang-runtime/src/lib.rs`
- Modify: `crates/openfang-runtime/src/tool_runner.rs`

- [ ] **Step 1: RED-Tests für Dispatch- und Receipt-Grenzen schreiben**

Für den Ausführungswrapper drei vollständige Fälle über eine `AtomicUsize dispatch_calls` und einen konfigurierbaren `FakeKernelHandle` schreiben:

| Testname | Kernel-Sequenz | Exakte Assertions |
|---|---|---|
| `external_denied_or_pending_never_calls_invoker` | einmal `Denied`, einmal `PendingApproval` | `dispatch_calls == 0` in beiden Subcases |
| `admitted_invocation_dispatches_once_and_persists_bound_receipt` | `Admitted`, `mark_dispatching` grün, `finalize` grün | `dispatch_calls == 1`, Receipt `Succeeded`, Cost settled `0` |
| `receipt_write_failure_after_dispatch_returns_outcome_unknown` | `Admitted`, Dispatch grün, `finalize` schlägt fehl | `dispatch_calls == 1`, Ergebnis `OutcomeUnknown`; zweiter Call dispatcht nicht |

Den Redaction-Test mit konkretem Inhalt hinzufügen:

```rust
#[test]
fn receipt_redaction_keeps_small_safe_json_but_never_plaintext_or_secret_keys() {
    let safe = receipt_payload(r#"{"count":2}"#, 65_536);
    assert_eq!(safe.storage_mode, ResultStorageMode::RedactedEnvelope);
    let secret = receipt_payload(r#"{"token":"synthetic-secret"}"#, 65_536);
    assert!(!secret.envelope.unwrap().contains("synthetic-secret"));
    let plain = receipt_payload("free-form potentially sensitive text", 65_536);
    assert_eq!(plain.storage_mode, ResultStorageMode::DigestOnly);
}
```

- [ ] **Step 2: RED ausführen**

```powershell
cargo test --offline -p openfang-runtime runtime_execution --lib
cargo test --offline -p openfang-runtime result_receipt --lib
```

Expected: FAIL, weil beide Module fehlen.

- [ ] **Step 3: Receipt-Hash und konservative Redaction implementieren**

```rust
pub struct ReceiptPayload {
    pub sha256: String,
    pub storage_mode: ResultStorageMode,
    pub envelope: Option<String>,
}

pub fn receipt_payload(content: &str, max_bytes: usize) -> ReceiptPayload {
    let sha256 = hex::encode(Sha256::digest(content.as_bytes()));
    let Ok(mut json) = serde_json::from_str::<serde_json::Value>(content) else {
        return ReceiptPayload { sha256, storage_mode: ResultStorageMode::DigestOnly, envelope: None };
    };
    redact_secret_keys(&mut json);
    let encoded = serde_json::to_string(&json).expect("JSON value serializes");
    if encoded.len() > max_bytes {
        ReceiptPayload { sha256, storage_mode: ResultStorageMode::DigestOnly, envelope: None }
    } else {
        ReceiptPayload { sha256, storage_mode: ResultStorageMode::RedactedEnvelope, envelope: Some(encoded) }
    }
}
```

`redact_secret_keys` ersetzt Werte unter case-insensitiven Schlüsseln `authorization`, `token`, `api_key`, `apikey`, `password`, `secret`, `credential`, `credentials` rekursiv durch `"[REDACTED]"`. Arrays werden rekursiv besucht. Nicht-JSON-Text bleibt immer `digest_only`.

- [ ] **Step 4: Runtime-Wrapper implementieren**

```rust
pub enum ExecutionOrigin {
    AgentLoop,
    ExternalMcp(RuntimeAdmissionContextV1),
}

pub enum RuntimeToolExecution {
    Completed { result: ToolResult, receipt: ExecutionReceiptV1, replayed: bool },
    PendingApproval { approval_ref: String },
    Denied { reason_code: String },
    CostUnavailable { reason_code: String },
    InProgress { invocation_id: String },
    OutcomeUnknown { invocation_id: String },
}

fn replay_from_receipt(receipt: ExecutionReceiptV1) -> RuntimeToolExecution {
    let is_error = receipt.status == ExecutionReceiptStatus::Failed;
    let content = receipt.result_envelope.clone().unwrap_or_else(|| {
        serde_json::json!({
            "status": "already_executed",
            "result_sha256": receipt.result_sha256,
            "result_storage_mode": "digest_only",
        }).to_string()
    });
    let result = ToolResult {
        tool_use_id: receipt.invocation_id.clone(),
        content,
        is_error,
    };
    RuntimeToolExecution::Completed { result, receipt, replayed: true }
}

pub async fn execute_external_mcp_tool<F, Fut>(
    context: RuntimeAdmissionContextV1,
    kernel: &Arc<dyn KernelHandle>,
    receipt_max_bytes: usize,
    invoke: F,
) -> RuntimeToolExecution
where
    F: FnOnce() -> Fut,
    Fut: Future<Output = ToolResult>,
{
    match kernel.admit_runtime_tool(&context).await {
        Ok(RuntimeAdmissionDecisionV1::Denied { reason_code }) =>
            RuntimeToolExecution::Denied { reason_code },
        Ok(RuntimeAdmissionDecisionV1::PendingApproval { approval_ref }) =>
            RuntimeToolExecution::PendingApproval { approval_ref },
        Ok(RuntimeAdmissionDecisionV1::CostUnavailable { reason_code }) =>
            RuntimeToolExecution::CostUnavailable { reason_code },
        Ok(RuntimeAdmissionDecisionV1::InProgress { receipt }) =>
            RuntimeToolExecution::InProgress { invocation_id: receipt.invocation_id },
        Ok(RuntimeAdmissionDecisionV1::Replay { receipt }) =>
            replay_from_receipt(receipt),
        Ok(RuntimeAdmissionDecisionV1::OutcomeUnknown { receipt }) =>
            RuntimeToolExecution::OutcomeUnknown { invocation_id: receipt.invocation_id },
        Ok(RuntimeAdmissionDecisionV1::Admitted { receipt }) => {
            let invocation_id = receipt.invocation_id.clone();
            if kernel.mark_runtime_dispatching(&invocation_id).is_err() {
                return RuntimeToolExecution::Denied {
                    reason_code: "dispatch_intent_not_durable".into(),
                };
            }
            let result = invoke().await;
            let encoded = serde_json::to_string(&result).unwrap_or_else(|_| "null".into());
            let payload = receipt_payload(&encoded, receipt_max_bytes);
            let update = ReceiptFinalizationV1 {
                status: if result.is_error { ReceiptFinalStatus::Failed }
                        else { ReceiptFinalStatus::Succeeded },
                actual_cost_micro_usd: 0,
                result_sha256: Some(payload.sha256),
                result_storage_mode: Some(payload.storage_mode),
                result_envelope: payload.envelope,
                error_class: result.is_error.then(|| "tool_error".into()),
            };
            match kernel.finalize_runtime_tool(&invocation_id, &update) {
                Ok(receipt) => RuntimeToolExecution::Completed {
                    result, receipt, replayed: false,
                },
                Err(_) => {
                    let _ = kernel.mark_runtime_outcome_unknown(
                        &invocation_id, "receipt_finalize_failed",
                    );
                    RuntimeToolExecution::OutcomeUnknown { invocation_id }
                }
            }
        }
        Err(_) => RuntimeToolExecution::Denied {
            reason_code: "runtime_admission_unavailable".into(),
        },
    }
}
```

Der Wrapper ruft die Closure ausschließlich nach `Admitted` und erfolgreichem `mark_dispatching` auf. Ein finales Receipt wird direkt als Replay zurückgegeben. Scheitert Finalize nach dem Closure-Aufruf, versucht der Wrapper sofort, `outcome_unknown`/`held_unknown` zu persistieren. Scheitert auch dieser Schreibversuch, bleibt das durable `dispatching`-Receipt bestehen; es wird weder im selben Prozess erneut ausgeführt noch nach einem Neustart redispatcht, weil die Boot-Recovery es vor neuer Admission auf `outcome_unknown` setzt.

`tool_runner.rs` erhält eine kleine Produktionsfunktion, die den vorhandenen `execute_tool`-Call als Closure an `execute_external_mcp_tool` übergibt. Bestehende Agent-Loop-Aufrufe bleiben auf `execute_tool` und damit ausdrücklich außerhalb dieser Phase. `exec_policy` beeinflusst nur den inneren Tool-Runner und kann den äußeren Admission-Wrapper nicht umgehen.

- [ ] **Step 5: GREEN und Runtime-Regressionen ausführen**

```powershell
cargo test --offline -p openfang-runtime runtime_execution --lib -- --nocapture
cargo test --offline -p openfang-runtime result_receipt --lib
cargo test --offline -p openfang-runtime --lib
```

Expected: PASS; Panic-Invoker bleibt für Deny/Pending/Replay unangetastet.

- [ ] **Step 6: Commit erstellen**

```powershell
git add crates/openfang-runtime/src/runtime_execution.rs crates/openfang-runtime/src/result_receipt.rs crates/openfang-runtime/src/lib.rs crates/openfang-runtime/src/tool_runner.rs
git diff --cached --check
git commit -m "feat(runtime): gate external tool dispatch"
```

---

### Task 5: Authority-API und `/mcp tools/call`-Gate

**Files:**
- Modify: `crates/openfang-api/src/routes.rs`
- Modify: `crates/openfang-api/src/server.rs`
- Modify: `crates/openfang-api/tests/api_integration_test.rs`

- [ ] **Step 1: API-RED-Tests schreiben**

Diese Tests verwenden den realen Test-Kernel und einen harmlosen test-only Invoker-Counter; sie starten keinen externen MCP-Server:

Der Test-Server erhält einen zweiten Konstruktor, der vor `OpenFangKernel::boot_with_config` `config.runtime_admission.enabled = true` setzt. Auto-Approve-Fälle setzen zusätzlich `config.approval.auto_approve = true`; der Pending-Fall verwendet `false` und löst die Approval nicht auf.

| Testname | Requestfolge | Exakte Assertions |
|---|---|---|
| `mcp_runtime_admission_requires_nonblank_refs_from_headers_and_never_arguments` | Refs nur in `params.arguments` | `error.data.authority_status == "denied"`, Dispatch `0` |
| `pending_approval_has_no_cost_reservation_receipt_or_dispatch` | Approval-Request liefert pending | keine Cost-Row, keine Receipt-Row, Dispatch `0` |
| `zero_cost_admitted_call_replays_without_second_dispatch` | identische String-ID zweimal | erster Result normal; zweiter `replayed == true`; eine Receipt-Row; Dispatch `1` |
| `concurrent_duplicate_calls_have_one_receipt_and_one_dispatch` | zwei Requests hinter Barrier | eine Receipt-Row; Dispatch `1`; zweites Ergebnis `in_progress` oder Replay |
| `same_refs_reject_changed_agent_tool_or_arguments` | gleiche Refs, je Subcase Agent/Tool/Args geändert | jeweils `denied`; Dispatch bleibt `1` vom ursprünglichen Call |

- [ ] **Step 2: RED ausführen**

```powershell
cargo test --offline -p openfang-api --test api_integration_test runtime_admission -- --nocapture
```

Expected: FAIL, weil Routen und Header-Parser fehlen.

- [ ] **Step 3: Reinen Header-/Context-Parser implementieren**

```rust
fn parse_runtime_admission_context(
    headers: &HeaderMap,
    request: &serde_json::Value,
    caller_agent_id: &str,
    tool_name: &str,
    arguments: &serde_json::Value,
) -> Result<RuntimeAdmissionContextV1, serde_json::Value> {
    let invocation_id = request.get("id").and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| authority_error("denied", "string invocation id required"))?;
    let approval_ref = required_header(headers, "X-OpenFang-Approval-Ref")?;
    let cost_ref = required_header(headers, "X-OpenFang-Cost-Ref")?;
    let context = RuntimeAdmissionContextV1 {
        invocation_id: invocation_id.to_owned(),
        caller_agent_id: caller_agent_id.to_owned(),
        approval_ref,
        cost_ref,
        tool_name: tool_name.to_owned(),
        arguments_sha256: canonical_json_sha256(arguments),
    };
    context.validate().map_err(|error| authority_error("denied", &error))?;
    Ok(context)
}
```

`canonical_json_sha256` sortiert Objektschlüssel rekursiv, erhält Array-Reihenfolge und hasht die kompakte UTF-8-Serialisierung. Headerwerte werden nur geparst und niemals in `arguments` geschrieben.

- [ ] **Step 4: Authentifizierte Authority-Routen hinzufügen**

In `server.rs` registrieren:

```rust
.route("/api/runtime/approvals/admit", post(routes::runtime_approval_admit))
.route("/api/runtime/approvals/resolve", post(routes::runtime_approval_resolve))
.route("/api/runtime/cost-reservations", post(routes::runtime_cost_reserve))
.route("/api/runtime/receipts/{invocation_id}", get(routes::runtime_receipt_get))
```

Die POST-Routen bleiben hinter der bestehenden API-Auth-Middleware. `runtime_approval_admit` ist idempotent über die planweite Unique-Bindung. `runtime_approval_resolve` akzeptiert ausschließlich:

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeApprovalResolveRequest {
    pub approval_ref: String,
    pub decision: RuntimeApprovalDecision,
}
```

`RuntimeApprovalDecision` ist die geschlossene Enum `approved | denied`.

- [ ] **Step 5: `/mcp tools/call` durch Runtime-Wrapper führen**

Nach bestehender Caller- und Tool-Scope-Prüfung:

```rust
if state.kernel.config.runtime_admission.enabled {
    let context = match parse_runtime_admission_context(
        &headers, &request, &caller_agent_id, tool_name, &arguments,
    ) {
        Ok(context) => context,
        Err(error) => return Json(mcp_error(&request, error)),
    };
    let outcome = openfang_runtime::tool_runner::execute_external_mcp_tool(
        context,
        &kernel_handle,
        state.kernel.config.runtime_admission.receipt_max_bytes,
        || async {
            openfang_runtime::tool_runner::execute_tool(
                "mcp-http",
                tool_name,
                &arguments,
                Some(&kernel_handle),
                Some(&caller_tool_names),
                Some(&caller_agent_id),
                Some(&skill_snapshot),
                Some(&state.kernel.mcp_connections),
                Some(&state.kernel.web_ctx),
                Some(&state.kernel.browser_ctx),
                None,
                None,
                Some(&state.kernel.media_engine),
                caller.manifest.exec_policy.as_ref(),
                if state.kernel.config.tts.enabled { Some(&state.kernel.tts_engine) } else { None },
                if state.kernel.config.docker.enabled { Some(&state.kernel.config.docker) } else { None },
                Some(&*state.kernel.process_manager),
            ).await
        },
    ).await;
    return Json(runtime_tool_execution_to_json_rpc(&request, outcome));
}
```

Bei deaktiviertem Flag bleibt der bisherige Pfad unverändert. Bei aktiviertem Flag ist ein Store-/Parser-/Admission-Fehler fail-closed. `tools/list` bleibt unverändert. Erfolgreiche Replays sind normale Results mit `replayed: true`; Pending/Deny/Cost/InProgress/Unknown verwenden `error.data.authority_status`.

- [ ] **Step 6: GREEN und API-Regressionen ausführen**

```powershell
cargo test --offline -p openfang-api --test api_integration_test runtime_admission -- --nocapture
cargo test --offline -p openfang-api --test api_integration_test mcp_tools -- --nocapture
cargo test --offline -p openfang-api --lib
```

Expected: PASS; alte Caller-/Scope-Tests bleiben grün.

- [ ] **Step 7: Commit erstellen**

```powershell
git add crates/openfang-api/src/routes.rs crates/openfang-api/src/server.rs crates/openfang-api/tests/api_integration_test.rs
git diff --cached --check
git commit -m "feat(api): enforce MCP runtime admission"
```

---

### Task 6: OpenFang-Gesamtverifikation und PR

**Files:** keine neuen Produktpfade; nur Review-Fixes innerhalb der Tasks 1–5.

- [ ] **Step 1: Format und Paketgates ausführen**

```powershell
cargo fmt --all -- --check
cargo test --offline -p openfang-types --lib
cargo test --offline -p openfang-memory --lib
cargo test --offline -p openfang-runtime --lib
cargo test --offline -p openfang-kernel --lib
cargo test --offline -p openfang-api --test api_integration_test -- --nocapture
cargo check --offline -p openfang-api
```

Expected: jeder Befehl PASS. Bei Host-Linkerfehlern keinen Code-Fix erfinden; Prozessbestand und Temp-Pfad diagnostizieren und denselben fokussierten Test nach bereinigtem Hostzustand einmal wiederholen.

- [ ] **Step 2: Scope-Review durchführen**

```powershell
git status --short
git diff origin/main...HEAD --check
git diff --name-only origin/main...HEAD
git log --oneline origin/main..HEAD
```

Expected: nur die in Abschnitt 2 genannten OpenFang-Pfade; Worktree sauber nach Commits. Synthetische Secretwerte dürfen ausschließlich in Redaction-Tests vorkommen und werden vor dem Push nochmals im Diff geprüft.

- [ ] **Step 3: Branch pushen und PR erstellen**

```powershell
git push -u origin codex/openfang/runtime-admission-v1
gh pr create --base main --head codex/openfang/runtime-admission-v1 --title "feat: enforce runtime authority for MCP tools" --body "Adds persistent fail-closed runtime approval, zero-capable single-use cost reservations, receipts and replay protection for external MCP tools. Includes RED/GREEN and offline package evidence. Runtime flag defaults off. No live MCP, provider, deployment or Agent-Loop claim."
```

Die PR-Beschreibung nennt RED/GREEN, Offline-Gates, `enabled=false` als Rollout-Default und die Nonclaims: kein Live-MCP, kein Provider, kein Deploy, keine Agent-Loop-Abdeckung.

- [ ] **Step 4: CI/Review pflegen und green non-breaking mergen**

Vor Merge Remote-Head und CI frisch prüfen. Review-Fixes reproduzieren und in kleinen Commits setzen. Bei grünem, nicht brechendem PR unter `standing-autonomy:v1` mergen; danach `origin/main` fetchen und Merge-SHA/Parents festhalten.

---

### Task 7: Brain-Authority-Client und stabile Invocation

**Repository:** VibeMind-OS
**Branch:** `codex/brain/runtime-admission-client-v1`

**Files:**
- Create: `brain/the_brain/core/openfang_runtime_authority.py`
- Create: `brain/the_brain/tests/test_openfang_runtime_authority.py`
- Modify: `brain/the_brain/core/capability_targets.py`
- Modify: `brain/the_brain/core/plan_schema.py`
- Modify: `brain/the_brain/core/plan_executor.py`
- Modify: `brain/the_brain/web/routers/introspection.py`
- Modify: `brain/the_brain/tests/test_openfang_mcp_executor.py`
- Modify: `brain/the_brain/tests/test_plan_executor_registered_openfang.py`
- Modify: `brain/the_brain/tests/test_multihop_response_contract.py`

- [ ] **Step 1: Child-Worktree erstellen und gemergten OpenFang-Pin materialisieren**

```powershell
git -C E:\CodexWorktrees\outer-brain-coder-chain-acceptance\vibemind-os fetch origin master
git -C E:\CodexWorktrees\outer-brain-coder-chain-acceptance\vibemind-os worktree add -b codex/brain/runtime-admission-client-v1 E:\CodexWorktrees\brain-runtime-admission origin/master
git -C E:\CodexWorktrees\brain-runtime-admission submodule update --init openfang
git -C E:\CodexWorktrees\brain-runtime-admission\openfang fetch origin main
git -C E:\CodexWorktrees\brain-runtime-admission\openfang checkout --detach origin/main
```

Expected: Child sauber; nested OpenFang exakt auf dem gemergten Runtime-Admission-Commit.

- [ ] **Step 2: Python-RED-Tests schreiben**

`test_openfang_runtime_authority.py` erhält lokale `_Response`, `_valid_context()` und eine sequenzielle Fake-Transportfunktion. Folgende Fälle werden vollständig ausgeführt:

| Testname | Fake-Responses | Exakte Assertions |
|---|---|---|
| `test_pending_approval_stops_before_cost_and_mcp` | Agents grün, Approval pending | Callfolge exakt `agents, approval`; kein Cost-/MCP-POST |
| `test_approved_zero_cost_invocation_uses_server_refs_and_stable_id` | Approval approved, Cost reserved, MCP grün | zwei identische Plan-/Hop-Eingaben erzeugen gleiche Request-ID; Cost request `0`; MCP arguments exakt `{"title": "focus"}` |
| `test_outcome_unknown_is_never_retried_or_reported_as_success` | MCP JSON-RPC error mit `authority_status=outcome_unknown` | `ok is False`, `retryable is False`, genau ein MCP-POST |
| `test_client_never_logs_or_returns_complete_authority_refs` | Remote-Fehler enthält synthetische Refs | weder Result noch `caplog.text` enthält vollständige Refs |

- [ ] **Step 3: RED ausführen**

```powershell
python -m pytest brain/the_brain/tests/test_openfang_runtime_authority.py brain/the_brain/tests/test_openfang_mcp_executor.py -q
```

Expected: FAIL, weil Client und stabile Runtime-Metadaten fehlen.

- [ ] **Step 4: Authority-Client implementieren**

```python
@dataclass(frozen=True)
class RuntimeInvocationContext:
    correlation_id: str
    plan_id: str
    plan_revision: int
    step_id: str
    space_id: str
    agent_name: str
    invocation_id: str

@dataclass(frozen=True)
class RuntimeAuthorityRefs:
    agent_id: str
    approval_ref: str
    cost_ref: str
    invocation_id: str

@dataclass(frozen=True)
class RuntimeAuthorityPending:
    approval_ref_fingerprint: str
    invocation_id: str

class OpenFangRuntimeAuthorityClient:
    def prepare_invocation(
        self, context: RuntimeInvocationContext,
    ) -> RuntimeAuthorityRefs | RuntimeAuthorityPending:
        # GET /api/agents with bounded safe retry
        # POST approval once, no retry for state-changing POST
        # pending returns before cost
        # approved -> POST zero-cost reservation -> refs
```

Die Approval-Request verwendet `max_plan_cost_microusd=0` und `ttl_seconds=300`; die Cost-Request verwendet `max_cost_microusd=0` und dieselbe TTL. POST-Aufrufe werden nicht automatisch wiederholt. Error bodies werden über die vorhandene `_redact_evidence`-Semantik bereinigt. Vollständige Authority-Refs erscheinen weder im Fehlertext noch in Logs.

- [ ] **Step 5: Plan-Revision und stabile ID implementieren**

`Plan` erhält `plan_revision: int = 1`; `to_dict`, `from_dict` und `validate_plan` verlangen eine positive Ganzzahl.

```python
def runtime_invocation_id(plan_id: str, plan_revision: int, step_id: str) -> str:
    canonical = f"{plan_id}\n{plan_revision}\n{step_id}".encode("utf-8")
    return "brain-mcp-" + hashlib.sha256(canonical).hexdigest()[:32]
```

`PlanExecutor` legt `plan_revision` in `plan_ctx`, erweitert `McpAuthority` um `space_id`/`event_id` und übergibt an `McpExecutor` ausschließlich `_runtime_authority`. `correlation_id` ist die vorhandene `trace_id`, ansonsten die stabile `plan_id`. Manuell eingereichte `approval_ref`/`cost_ref` in Tool-Arguments werden entfernt und dürfen die vom Authority-Client gelieferten Refs nicht überschreiben.

Wenn der bestehende Replanner einen neuen Plan liefert, wird vor der Aufnahme neuer Hops `plan.plan_revision += 1` gesetzt und derselbe Wert in `plan_ctx` aktualisiert. Ein Test mit gleicher `step_id`, aber geändertem Argument belegt, dass die neue Revision eine neue Invocation-ID erzeugt; Pending selbst löst keinen Replan aus.

- [ ] **Step 6: Pending als Pause statt Lern-Fehler behandeln**

`HopResult` erhält additive Felder:

```python
authority_status: Optional[str] = None
invocation_id: Optional[str] = None
pending: bool = False
```

Ein Pending-Hinweis stoppt weitere abhängige Hops, löst kein Replan, Timeout-Sentinel, Gap-Sentinel, Provider-Failure-Learning, Truth-Validation oder negative Reward-Aktualisierung aus. `PlanExecutor.execute` liefert:

```python
{
    "ok": False,
    "pending": True,
    "authority_status": "pending_approval",
    "plan": plan.to_dict(),
    "invocation_id": stable_id,
    "executed": executed,
}
```

Ein erneutes `POST /api/multihop/execute` mit demselben `plan`-Objekt verwendet dieselbe `plan_id`, `plan_revision`, `step_id` und damit dieselbe Invocation. `introspection.py` bewahrt eine vorhandene `plan.trace_id`; nur ein leerer Trace erhält eine neue ID.

- [ ] **Step 7: McpExecutor auf server-issued Refs umstellen**

Der bisherige zufällige `brain-mcp-{uuid}`-Wert wird für Plan-Aufrufe durch `RuntimeInvocationContext.invocation_id` ersetzt. Danach:

```python
refs = self.authority_client.prepare_invocation(runtime_context)
if isinstance(refs, RuntimeAuthorityPending):
    return {
        "ok": False,
        "authority_status": "pending_approval",
        "pending": True,
        "invocation_id": refs.invocation_id,
    }
execution_headers["X-OpenFang-Approval-Ref"] = refs.approval_ref
execution_headers["X-OpenFang-Cost-Ref"] = refs.cost_ref
request_id = refs.invocation_id
```

JSON-RPC `outcome_unknown` und `in_progress` bleiben nicht retrybar. `replayed: true` mit normalem Result wird als Erfolg weitergereicht, danach läuft der unabhängige Brain-Truth-Validator wie beim Erstaufruf.

- [ ] **Step 8: GREEN und Brain-Regressionen ausführen**

```powershell
python -m pytest brain/the_brain/tests/test_openfang_runtime_authority.py -q
python -m pytest brain/the_brain/tests/test_openfang_mcp_executor.py -q
python -m pytest brain/the_brain/tests/test_plan_executor_registered_openfang.py -q
python -m pytest brain/the_brain/tests/test_multihop_response_contract.py -q
```

Expected: alle vier Dateien PASS; Pending erzeugt weder MCP-POST noch negative Lernsignale.

- [ ] **Step 9: Brain-Commit erstellen**

```powershell
git add brain/the_brain/core/openfang_runtime_authority.py brain/the_brain/core/capability_targets.py brain/the_brain/core/plan_schema.py brain/the_brain/core/plan_executor.py brain/the_brain/web/routers/introspection.py brain/the_brain/tests/test_openfang_runtime_authority.py brain/the_brain/tests/test_openfang_mcp_executor.py brain/the_brain/tests/test_plan_executor_registered_openfang.py brain/the_brain/tests/test_multihop_response_contract.py
git diff --cached --check
git commit -m "feat(brain): acquire OpenFang runtime authority"
```

---

### Task 8: Child-Pin, Cross-Repo-Gates und PR

**Files:**
- Modify: `openfang`
- Modify: `brain/the_brain/tests/test_openfang_agent_manifest.py`

- [ ] **Step 1: Cross-Repo-Test zuerst auf den alten Gitlink richten**

Der neue Test liest aus dem materialisierten Gitlink:

```python
def test_pinned_openfang_exposes_runtime_admission_authority():
    root = Path(__file__).resolve().parents[3] / "openfang"
    for relative in (
        "crates/openfang-kernel/src/runtime_admission.rs",
        "crates/openfang-runtime/src/runtime_execution.rs",
        "crates/openfang-api/src/routes.rs",
    ):
        assert (root / relative).is_file(), relative
    routes = (root / "crates/openfang-api/src/routes.rs").read_text(encoding="utf-8")
    assert "X-OpenFang-Approval-Ref" in routes
    assert "X-OpenFang-Cost-Ref" in routes
```

- [ ] **Step 2: RED auf altem Pin ausführen**

```powershell
python -m pytest brain/the_brain/tests/test_openfang_agent_manifest.py -k runtime_admission_authority -q
```

Expected: FAIL auf fehlenden Runtime-Dateien im alten Pin.

- [ ] **Step 3: Gitlink auf gemergtes `origin/main` setzen**

```powershell
git -C openfang fetch origin main
git -C openfang checkout --detach origin/main
git add openfang brain/the_brain/tests/test_openfang_agent_manifest.py
```

Expected: `git diff --cached --submodule=short` zeigt genau den fortschreitenden OpenFang-Gitlink plus Cross-Repo-Test.

- [ ] **Step 4: Child-Gates ausführen**

```powershell
python -m pytest brain/the_brain/tests/test_openfang_agent_manifest.py -q
python -m pytest brain/the_brain/tests/test_openfang_runtime_authority.py brain/the_brain/tests/test_openfang_mcp_executor.py brain/the_brain/tests/test_plan_executor_registered_openfang.py brain/the_brain/tests/test_multihop_response_contract.py -q
python -m pytest brain/the_brain/tests/test_sync_openfang_agents.py brain/the_brain/tests/test_rowboat_mcp_server.py -q
python scripts/check_openfang_llm_config.py
python openfang/scripts/check_vibemind_agent_providers.py
```

Expected: PASS; keine Runtime-/Netzwerkverbindung.

- [ ] **Step 5: Pin-Commit, Push und PR**

```powershell
git commit -m "chore(openfang): pin runtime admission authority"
git push -u origin codex/brain/runtime-admission-client-v1
gh pr create --base master --head codex/brain/runtime-admission-client-v1 --title "feat: route deterministic MCP through runtime authority" --body "Adds stable per-hop invocation identity, nonblocking pending handling and server-issued Approval/Cost refs; pins the merged OpenFang runtime authority. Includes focused Brain and cross-repo static gates. No live or deployment claim."
```

CI und Review pflegen, dann den grünen nicht brechenden Child-PR unter `standing-autonomy:v1` mergen. Merge-SHA und Parents festhalten.

---

### Task 9: Outer-Pin, Ledger und statisches Deployment-Regate

**Repository:** Outer V1

- [ ] **Step 1: Gitlink-/Manifest-Branch erstellen und RED erzeugen**

```powershell
git fetch origin master
git worktree add -b codex/git/runtime-admission-chain-pin-v1 E:\CodexWorktrees\outer-runtime-admission-pin origin/master
git -C E:\CodexWorktrees\outer-runtime-admission-pin submodule update --init vibemind-os
git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os fetch origin master
git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os checkout --detach origin/master
git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os submodule update --init openfang
git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os\openfang fetch origin main
$childPin = git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os rev-parse origin/master
$openFangPin = git -C E:\CodexWorktrees\outer-runtime-admission-pin\vibemind-os\openfang rev-parse origin/main
Write-Output "CHILD=$childPin"
Write-Output "OPENFANG=$openFangPin"
```

Zuerst ausschließlich die beiden Testkonstanten in `tests/v1_governance/test_manifest.py` auf die ausgegebenen Werte setzen. Fokustest ausführen und den erwarteten stale Manifest-/Gitlink-Fehler sichern.

- [ ] **Step 2: Manifest und Outer-Gitlink reconciliieren**

`repo-manifest.yaml` erhält den ausgegebenen Child-Pin, den ausgegebenen OpenFang-Pin und denselben Child-Pin in allen Records mit `parent: vibemind-os`. Der Outer-Index erhält `vibemind-os` exakt auf `$childPin`; andere Gitlinks und Manifest-Pins bleiben bytegleich.

```powershell
python -m pytest tests/v1_governance/test_manifest.py -q
git add vibemind-os repo-manifest.yaml tests/v1_governance/test_manifest.py
git diff --cached --check
git diff --cached --name-only
git diff --check
git commit -m "chore(git): pin runtime admission chain"
```

Expected: Manifest-Suite PASS; Commit-Scope exakt `vibemind-os`, `repo-manifest.yaml`, `tests/v1_governance/test_manifest.py`.

- [ ] **Step 3: PR erstellen, pflegen und mergen**

```powershell
git push -u origin codex/git/runtime-admission-chain-pin-v1
gh pr create --base master --head codex/git/runtime-admission-chain-pin-v1 --title "chore: pin runtime admission chain" --body "Pins the merged VibeMind-OS and OpenFang runtime-admission chain and reconciles the closed manifest authority. Static only; no deployment or live claim."
gh pr checks --watch
gh pr merge --merge
git fetch origin master
git show -s --format="%H %P %s" origin/master
```

Expected: grüner Merge-PR; der ausgegebene Outer-Merge-SHA wird für den Ledger festgehalten.

- [ ] **Step 4: Append-only Ledger-Branch erstellen**

Vom neuen `origin/master` Branch `codex/observability/runtime-admission-ledger-v1` erstellen. Tests zuerst ergänzen: exakte neue OpenFang-, Child- und Outer-Merge-Records, neue Gitlink-Chain sowie zwei Tamper-Fälle für Child- und OpenFang-Pin. Der fokussierte RED-Lauf muss an fehlenden Records scheitern.

Danach ausschließlich folgende Pfade ändern:

```text
docs/governance/cockpit-reconciliation-ledger-v1.json
tools/v1_governance/reconciliation.py
tests/v1_governance/test_cockpit_reconciliation_ledger.py
```

Die JSON-`entries` werden nur angehängt; vorheriger Byte-/Strukturprefix bleibt identisch. Merge-Parents werden aus lokalen Gitobjekten belegt:

```powershell
$outerMerge = git rev-parse origin/master
$childMerge = git -C vibemind-os rev-parse origin/master
$openFangMerge = git -C vibemind-os\openfang rev-parse origin/main
git show -s --format="%H %P %s" $outerMerge
git -C vibemind-os show -s --format="%H %P %s" $childMerge
git -C vibemind-os\openfang show -s --format="%H %P %s" $openFangMerge
```

```powershell
python -m pytest tests/v1_governance/test_cockpit_reconciliation_ledger.py -q
python -c "from pathlib import Path; from tools.v1_governance.reconciliation import validate_reconciliation_ledger; root=Path.cwd(); validate_reconciliation_ledger(root, child_repo_root=root/'vibemind-os', openfang_repo_root=root/'vibemind-os'/'openfang')"
git add docs/governance/cockpit-reconciliation-ledger-v1.json tools/v1_governance/reconciliation.py tests/v1_governance/test_cockpit_reconciliation_ledger.py
git diff --cached --check
git diff --cached --name-only
git diff --check
git commit -m "chore(observability): record runtime admission chain"
git push -u origin codex/observability/runtime-admission-ledger-v1
gh pr create --base master --head codex/observability/runtime-admission-ledger-v1 --title "chore: record runtime admission chain" --body "Appends the merged OpenFang, VibeMind-OS and Outer runtime-admission provenance and updates the closed-world validator with tamper negatives. Static historical evidence only; no live or deployment claim."
gh pr checks --watch
gh pr merge --merge
git fetch origin master
```

Expected: volle Ledger-Suite und realer Validator PASS; grüner Ledger-PR gemergt und neuer `origin/master` für das Regate frisch gefetcht.

- [ ] **Step 5: Deployment-Regate-Branch erstellen**

Vom danach aktuellen `origin/master` Branch `codex/deployment/runtime-admission-regate-v1` erstellen. Zuerst Testpins in `tests/deployment/deployment-readiness.Tests.ps1` aktualisieren und den erwarteten RED gegen alte Production-Konstanten belegen. Dann nur diese zwei Pfade ändern:

```text
scripts/deployment-readiness.ps1
tests/deployment/deployment-readiness.Tests.ps1
```

Child-/OpenFang-Pins und die beiden Golden-Path-Fixture-Substitutionsquellen werden aktualisiert; Voice bleibt unverändert. Superseded-Pin-Negative schließen beide alten Pins aus.

```powershell
Invoke-Pester tests/deployment/deployment-readiness.Tests.ps1 -Output Detailed
python -m pytest tests/v1_governance/test_manifest.py tests/v1_governance/test_cockpit_reconciliation_ledger.py -q
git add scripts/deployment-readiness.ps1 tests/deployment/deployment-readiness.Tests.ps1
git diff --cached --check
git diff --cached --name-only
git diff --check
git commit -m "chore(deployment): re-gate runtime admission chain"
git push -u origin codex/deployment/runtime-admission-regate-v1
gh pr create --base master --head codex/deployment/runtime-admission-regate-v1 --title "chore: re-gate runtime admission chain" --body "Updates the static deployment-readiness pins and superseded-pin negatives for the merged runtime-admission chain. No deployment, Proxmox mutation or live Golden Path claim."
gh pr checks --watch
gh pr merge --merge
git fetch origin master
```

Expected: Pester vollständig PASS ohne `-CI` und ohne `testResults.xml`; Manifest/Ledger PASS; grüner Regate-PR gemergt. Das ist weiterhin nur statische Deployment-Readiness, kein Deploy.

---

### Task 10: Read-only Golden Path und Replay-Nachweis

**Authority:** Vor einer Deployment- oder Proxmox-Mutation anhalten und request-spezifische Freigabe einholen. Ist der neue Stand bereits extern deployt, bleibt dieser Task read-only.

- [ ] **Step 1: Remote- und Deploy-Parität read-only belegen**

Outer-, Child- und OpenFang-Remote-Heads frisch fetchen. Committed Gitlinks, laufende Image-/Service-Version und Runtime-Admission-Flag vergleichen. Bei Abweichung keine Live-Ausführung behaupten.

- [ ] **Step 2: Harmlosen deterministischen Testfall wählen**

Verwenden:

```text
Brain intent -> ideas.list -> brain-ideas -> OpenFang /mcp tools/call
-> vibemind-db -> Proxmox-Supabase read -> Brain truth:supabase Rücklese
```

Keine Schreib-, Lösch- oder Cleanup-Operation verwenden.

- [ ] **Step 3: Ersten Call mit neuer Authority-Kette ausführen**

Evidenz erfassen:

```text
plan_id, plan_revision, step_id, invocation_id
approval fingerprint und approved status
cost reservation/settlement = 0 Micro-USD
receipt transitions prepared -> dispatching -> succeeded|failed
OpenFang tool/server/agent binding
unabhängige truth:-Rücklese
```

Vollständige Refs, API-Keys und rohe sensible Resultate niemals ausgeben.

- [ ] **Step 4: Identischen Replay ausführen**

Den exakt selben Plan mit gleicher Revision und Hop-ID erneut einreichen. Akzeptanz:

```text
replayed=true
gleiche invocation_id
Receipt count bleibt 1
Dispatch count bleibt 1
Cost consumption/settlement bleibt 1 bei Betrag 0
Truth-Rücklese bleibt erfolgreich oder ehrlich unverified
```

- [ ] **Step 5: Abschlussbericht klassifizieren**

Getrennt berichten:

- `verified_static`: Gitlinks, Konfiguration, Tests.
- `reachable`: HTTP-/Service-Erreichbarkeit.
- `verified_live`: nur der tatsächlich beobachtete Call, Receipt, Replay und Truth-Read.
- `not_verified`: Agent-Turns, Streaming, LLM-Kosten, andere Spaces, Reboot/Backup/Restore und Proxmox-Cutover.

Kein `verified_live`, wenn Receipt, Replay-Counter, Cost `0` oder unabhängige Truth-Rücklese fehlen.

---

## 3. Finales Completion-Gate

Der Lieferzug ist erst abgeschlossen, wenn:

1. alle OpenFang-, Child- und Outer-PRs gemergt sind,
2. Remote-Heads und verschachtelte Gitlinks exakt übereinstimmen,
3. OpenFang-Pakettests, Brain-Fokussuiten, Manifest, Ledger und Pester grün sind,
4. alle Worktrees sauber sind und keine fremden Desktop-Dateien berührt wurden,
5. der Golden Path entweder mit vollständiger Live-Evidenz bestanden oder ausdrücklich als noch nicht deployt/nicht freigegeben klassifiziert ist.
