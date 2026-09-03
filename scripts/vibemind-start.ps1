<#
.SYNOPSIS
    Vibemind validated server-mode start — through Phase 4 (E1a + E1b).
.DESCRIPTION
    Starts the Vibemind stack + native side:
      - Phase 0   : preflight (Docker reachable, swarm active)
      - Phase 0.5 : Ollama (host process, mirofish dependency)
      - Phase 1   : Docker Swarm stack (infra/swarm/vibemind-stack.yml)
      - Phase 1.5 : native exceptions — OpenFang (:4200) + Minibook compose
      - Phase 3   : venv services (la_fungus :8011, bridge :5150,
                    automation_backend :8007) + portless marketing bubble
                    sidecars (bubble_predict_runner / bubble_classifier_runner
                    / bubble_dispatcher). Skipped via -SkipVenv.
                    NOTE: brain-api :5001 is NOT here — the swarm stack
                    owns brain-api as its own service; starting it
                    natively would port-conflict (Launcher bug avoided
                    by code form — there is no flag that flips it on).
      - Phase 4   : Node services — moire_server :8766. Skipped via -SkipNode.
      - Phase 5   : Electron App (DevTools :9223) + OpenFang Debug-Agent
                    sidecar. Skipped via -SkipElectron. Server-mode hard-
                    codes SKIP_BRAIN_SPAWN=1 + BRAIN_PORT=5000 because the
                    swarm stack always owns Brain — Electron must not
                    spawn a competing venv Brain on :5000.
      - Phase 6   : Health gate — wait for all 1/1 + (healthy) + key
                    endpoints (HTTP + TCP) with overall timeout

    OPT-IN (E1d): -Interactive enters a Ctrl+C wait-loop after the health
    gate. On Ctrl+C / window-close / unhandled exception, all native
    services (Phase 3/4/5 — registry PIDs + managed-port backstop) are
    stopped. The swarm stack is INTENTIONALLY NOT torn down by Ctrl+C
    (use scripts/vibemind-stop.ps1 for that). Server-mode default
    (without -Interactive) exits 0 immediately so .exe / Scheduled Task
    runs are event-driven, not blocking.

    For full interactive Dev-mode use Vibemind.debug.ps1 (the Launcher).
    This script is intended for SERVER-MODE start (.exe / desktop icon /
    scheduled task) where only the persistent stack + native infra
    matter and there is no human-attached Ctrl+C lifecycle.

    Companion: scripts\vibemind-stop.ps1.
.PARAMETER HealthTimeout
    Seconds to wait for all services to converge + endpoints to answer.
    Default 180 (covers SBERT cold start ~60s + the slowest cold image pull).
.PARAMETER SkipOllama
    Skip the Phase 0.5 Ollama check (set if Ollama is managed externally).
.PARAMETER SkipNative
    Skip OpenFang + Minibook starts (Phase 1.5 — stack-only).
.PARAMETER SkipVenv
    Skip Phase 3 (venv services: la_fungus / bridge / automation_backend +
    bubble_predict_runner / bubble_classifier_runner / bubble_dispatcher).
.PARAMETER SkipNode
    Skip Phase 4 (moire_server).
.PARAMETER SkipElectron
    Skip Phase 5 (Electron App + OpenFang Debug-Agent).
.PARAMETER Interactive
    Opt into the Ctrl+C wait-loop (E1d, Dev-mode). Default OFF — server-
    mode exits 0 after the health gate. With this flag, the script blocks
    forever (30s tick, crash diagnostic) until Ctrl+C, then stops every
    registered native process. The swarm stack stays running across
    interactive sessions.
.PARAMETER DryRun
    Show what would happen, do nothing destructive.
.EXAMPLE
    .\scripts\vibemind-start.ps1
    .\scripts\vibemind-start.ps1 -SkipNative -SkipVenv -SkipNode  # E1a-equivalent
    .\scripts\vibemind-start.ps1 -DryRun
#>
param(
    [int]$HealthTimeout = 180,
    [switch]$SkipOllama,
    [switch]$SkipNative,
    [switch]$SkipVenv,       # E1b: skip Phase 3 (venv services)
    [switch]$SkipNode,       # E1b: skip Phase 4 (Moire)
    [switch]$SkipElectron,   # E1c: skip Phase 5 (Electron + Debug-Agent)
    [switch]$Interactive,    # E1d: opt-in Ctrl+C wait-loop (Dev mode)
    [string]$Spaces = "",    # Profile-Selection: comma list e.g. "coding,n8n". Empty = core only.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Resolve repo root (parent of this scripts/ dir)
$script:ROOT      = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script:STACK_FILE = Join-Path $script:ROOT "infra\swarm\vibemind-stack.yml"
$script:SECRETS_SCRIPT = Join-Path $script:ROOT "scripts\swarm_secrets_init.ps1"
$script:LOG_DIR   = Join-Path $script:ROOT "logs"
$script:REGISTRY_FILE = Join-Path $script:LOG_DIR "services.registry.jsonl"
$script:SHARED_VENV = Join-Path $script:ROOT ".venv"
$script:NATIVE_PROBES = @()  # filled by Invoke-VenvServices / Invoke-NodeServices; consumed by Wait-StackHealthy + Show-Status
if (-not (Test-Path $script:LOG_DIR)) { New-Item -ItemType Directory -Path $script:LOG_DIR | Out-Null }

# --- Helpers --------------------------------------------------------------
# Shared with vibemind-stop.ps1. Refactored out of inline copies 2026-05-20
# (Commit 1 of E1b/c/d plan — see ~\.claude\plans\k-nnnen-wir-adative-skills-
# splendid-mochi.md). Test-HttpHealth keeps the PS7 IPv6→IPv4 rewrite.
. (Join-Path $PSScriptRoot 'lib\vibemind-helpers.ps1')

# --- Transcript --------------------------------------------------------------
# Capture every line to logs/launcher/start-{ts}.log so the MCP tool
# `vibemind_launcher_logs` can surface it. Tauri's UI log fragment was
# uncopyable; this gives a full text capture for both UI-clicks and MCP
# triggers. Best-effort: a transcript failure must NEVER break the start.
$script:LAUNCHER_LOG_DIR = Join-Path $script:LOG_DIR "launcher"
$script:TRANSCRIPT_PATH = $null
try {
    if (-not (Test-Path $script:LAUNCHER_LOG_DIR)) {
        New-Item -ItemType Directory -Path $script:LAUNCHER_LOG_DIR -Force | Out-Null
    }
    $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:TRANSCRIPT_PATH = Join-Path $script:LAUNCHER_LOG_DIR "start-$ts.log"
    Start-Transcript -Path $script:TRANSCRIPT_PATH -IncludeInvocationHeader -Force | Out-Null
    # Stop the transcript on every exit path (exit 0/1/2, uncaught throw, Ctrl+C).
    Register-EngineEvent PowerShell.Exiting -Action {
        try { Stop-Transcript | Out-Null } catch {}
    } | Out-Null
    # Prune older than 20 transcripts to avoid unbounded growth.
    Get-ChildItem $script:LAUNCHER_LOG_DIR -Filter 'start-*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 20 |
        Remove-Item -Force -ErrorAction SilentlyContinue
} catch {
    # transcript not critical — keep going
}

# --- Phase 0: Preflight ---------------------------------------------------

function Invoke-Preflight {
    Write-Phase "Phase 0: Preflight"
    # 1. Docker reachable
    try { docker info 2>&1 | Out-Null } catch {
        Write-Err "Docker not reachable — start Docker Desktop first."
        exit 1
    }
    Write-Ok "Docker reachable"

    # 2. Swarm active (auto-init if not — same logic as Launcher Invoke-SwarmStackDeploy)
    $swarmState = ""
    try { $swarmState = (docker info --format '{{.Swarm.LocalNodeState}}' 2>$null) } catch {}
    if ($swarmState -ne "active") {
        if ($DryRun) {
            Write-Warn "[DryRun] Swarm inactive ('$swarmState') — would 'docker swarm init'"
        } else {
            Write-Warn "Swarm inactive ('$swarmState') — running 'docker swarm init --advertise-addr 127.0.0.1'"
            docker swarm init --advertise-addr 127.0.0.1 2>&1 | Out-Null
            try { $swarmState = (docker info --format '{{.Swarm.LocalNodeState}}' 2>$null) } catch {}
            if ($swarmState -ne "active") { Write-Err "Swarm could not be initialised"; exit 1 }
            Write-Ok "Swarm now active"
        }
    } else {
        Write-Ok "Swarm active"
    }

    # 3. Stack file exists
    if (-not (Test-Path $script:STACK_FILE)) {
        Write-Err "Stack file not found: $script:STACK_FILE"
        exit 1
    }
    Write-Ok "Stack file: $script:STACK_FILE"
}

# --- Phase 0.4: GPU-Auto-Setup -------------------------------------------
# Invoke-GpuSetup lebt jetzt in lib/vibemind-helpers.ps1 (dot-gesourct Z.93),
# damit Vibemind.debug.ps1 (separater Start-Pfad) DIESELBE Funktion nutzt —
# kein Drift wie beim Network-Race. Aufruf im Main unten via Invoke-GpuSetup.

# --- Phase 0.5: Ollama (host) ---------------------------------------------

function Invoke-OllamaCheck {
    if ($SkipOllama) { Write-Phase "Phase 0.5: Ollama (skipped)"; return }
    Write-Phase "Phase 0.5: Ollama"
    if (Test-HttpHealth -Url "http://localhost:11434/api/version" -TimeoutSec 3) {
        Write-Ok "Ollama already running on :11434"
        return
    }
    # Not running — try to start it (same locations the Launcher checks)
    $ollamaBin = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollamaBin)) {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { $ollamaBin = $cmd.Source }
    }
    if (-not (Test-Path $ollamaBin)) {
        Write-Warn "ollama.exe not found — mirofish embeddings may fail. Continuing."
        return
    }
    if ($DryRun) {
        Write-Warn "[DryRun] Would start ollama: $ollamaBin serve"
        return
    }
    Write-Ok "Starting Ollama: $ollamaBin serve"
    Start-Process -FilePath $ollamaBin -ArgumentList "serve" -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $script:LOG_DIR "ollama.out.log") `
        -RedirectStandardError  (Join-Path $script:LOG_DIR "ollama.err.log")
    # Wait up to 15s for it to come up
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-HttpHealth -Url "http://localhost:11434/api/version" -TimeoutSec 2) {
            Write-Ok "Ollama reachable on :11434"
            return
        }
    }
    Write-Warn "Ollama did not reach :11434 within 15s — continuing (mirofish may degrade)"
}

# --- Phase 1: Stack + native exceptions ----------------------------------

function Invoke-StackDeploy {
    Write-Phase "Phase 1: Stack deploy"
    # Secrets (idempotent — existing skipped)
    if (Test-Path $script:SECRETS_SCRIPT) {
        if ($DryRun) {
            Write-Warn "[DryRun] Would run secrets init: $script:SECRETS_SCRIPT"
        } else {
            Write-Ok "Provisioning secrets (idempotent)"
            try { & $script:SECRETS_SCRIPT 2>&1 | Out-Null } catch {
                Write-Warn "swarm_secrets_init.ps1: $($_.Exception.Message)"
            }
        }
    } else {
        Write-Warn "$script:SECRETS_SCRIPT not found — skipping secrets (existing secrets reused)"
    }

    # Stack deploy — profile-filtered render via ConvertTo-FilteredStack +
    # `docker stack deploy --prune`. --prune is REQUIRED for live toggle so
    # services from previously-active profiles get removed. Smoke test
    # 2026-05-25 confirmed `profiles:` is not understood by stack-deploy
    # natively, hence the render-then-deploy two-step.
    if ($DryRun) {
        Write-Warn "[DryRun] Would: render+deploy stack with Spaces='$Spaces'"
        return
    }
    Write-Ok "docker stack deploy vibemind (Spaces='$Spaces')"
    $ok = Invoke-FilteredStackDeploy -StackFile $script:STACK_FILE -Spaces $Spaces
    if (-not $ok) {
        Write-Err "stack deploy failed"
        throw "Invoke-FilteredStackDeploy returned `$false"
    }

    # Persist the selection so vibemind-spaces.ps1 list shows it accurately.
    $stateDir = Join-Path $env:USERPROFILE ".vibemind"
    if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Path $stateDir -Force | Out-Null }
    $spaceList = ConvertTo-SpaceList -Spaces $Spaces
    @{ spaces = @($spaceList) } | ConvertTo-Json -Compress |
        Set-Content -Path (Join-Path $stateDir "launcher-state.json") -Encoding utf8
}

function Invoke-NativeExceptions {
    if ($SkipNative) { Write-Phase "Phase 1.5: native exceptions (skipped)"; return }
    Write-Phase "Phase 1.5: native exceptions"

    # openclaw self-heal — keep VibeMind's openclaw patches applied (QR-as-PNG
    # etc.) so they survive `npm install -g openclaw`, and pull an update ONLY
    # when the WhatsApp login is broken (a fresh openclaw can fix a protocol/
    # session break). A healthy login => patches only, no npm round-trip, no
    # spawned interactive login (headless-safe). Best-effort: a failure must
    # never block the stack start. Runs BEFORE OpenFang since its
    # openclaw-visible agent shells out to openclaw.
    $ocPatch = Join-Path $script:ROOT "scripts\openclaw_update.ps1"
    if ((Test-Path $ocPatch) -and -not $DryRun) {
        try {
            & pwsh -NoProfile -ExecutionPolicy Bypass -File $ocPatch 2>&1 |
                ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        } catch {
            Write-Warn "openclaw patch hook failed (non-critical): $($_.Exception.Message)"
        }
    }

    # OpenFang — pre-built Rust binary (BOTH modes per Launcher §B); also documented in
    # vibemind-stack.yml comment block as "deliberately NOT in stack".
    $ofPort = 4200
    if (Test-HttpHealth -Url "http://localhost:$ofPort/api/health" -TimeoutSec 2) {
        Write-Ok "OpenFang already running (:$ofPort)"
    } else {
        $ofDir = Join-Path $script:ROOT "vibemind-os\openfang"
        $ofBin = Join-Path $ofDir "target\release\openfang.exe"
        $ofConfig = Join-Path $ofDir "openfang.vibemind.toml"
        if (-not (Test-Path $ofBin)) {
            Write-Warn "OpenFang binary not found at $ofBin — skipping (run 'cargo build --release')"
        } elseif ($DryRun) {
            Write-Warn "[DryRun] Would start OpenFang: $ofBin start"
        } else {
            Write-Ok "Starting OpenFang (native, :$ofPort)"
            $ofArgs = if (Test-Path $ofConfig) { "start --config `"$ofConfig`"" } else { "start" }
            $ofLogDir = Join-Path $script:LOG_DIR "openfang"
            if (-not (Test-Path $ofLogDir)) { New-Item -ItemType Directory -Path $ofLogDir | Out-Null }
            $ofScripts = Join-Path $script:ROOT "scripts"
            $ofOriginalPath = $env:PATH
            $ofOriginalWrapperDir = $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR
            try {
                $env:PATH = "$ofScripts;$ofOriginalPath"
                $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofScripts
                Start-Process -FilePath $ofBin -ArgumentList $ofArgs -WorkingDirectory $ofDir `
                    -WindowStyle Hidden `
                    -RedirectStandardOutput (Join-Path $ofLogDir "openfang.log") `
                    -RedirectStandardError  (Join-Path $ofLogDir "openfang.err.log")
            } finally {
                $env:PATH = $ofOriginalPath
                if ($null -eq $ofOriginalWrapperDir) { Remove-Item Env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR -ErrorAction SilentlyContinue }
                else { $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofOriginalWrapperDir }
            }
            # Best-effort wait up to 10s
            for ($i = 0; $i -lt 10; $i++) {
                Start-Sleep -Seconds 1
                if (Test-HttpHealth -Url "http://localhost:$ofPort/api/health" -TimeoutSec 2) {
                    Write-Ok "OpenFang ready (:$ofPort)"
                    break
                }
            }
        }
    }

    # Minibook — BLOCKED on external/minibook submodule (0 files). Compose
    # may still be there. Try it; warn if blocked. Documented in
    # vibemind-stack.yml NOT-in-stack list.
    $mbCompose = Join-Path $script:ROOT "vibemind-os\voice\docker-compose.minibook.yml"
    if (-not (Test-Path $mbCompose)) {
        Write-Warn "Minibook compose not found — skipping (BLOCKED in tasks/gaps.md B1)"
    } elseif ($DryRun) {
        Write-Warn "[DryRun] Would: docker compose -f $mbCompose -p vibemind-minibook up -d"
    } else {
        Write-Ok "Starting Minibook (native compose, not in stack)"
        docker compose -f $mbCompose -p vibemind-minibook up -d 2>&1 |
            Where-Object { $_ -match 'Creating|Started|Recreated|error|Error' } |
            ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
    }
}

# --- Phase 3: venv services (E1b) -----------------------------------------
# IMPORTANT: brain-api (:5001) is INTENTIONALLY ABSENT from this table.
# The swarm stack owns brain-api (infra/swarm/vibemind-stack.yml — see
# memory project_routing_matrix_autotrain). Starting it natively here would
# port-conflict the stack service (exactly the bug at Vibemind.debug.ps1:
# 1018-1022). The structural guarantee against re-introducing that bug is
# THE CODE FORM: brain_api is not enumerated below, and no flag flips it on.

function Test-WorkerCmdlineAlive {
    <#
    .SYNOPSIS
        $true iff a python.exe whose CommandLine contains $Pattern is already
        running. Already-running guard for PORTLESS sidecars (Port=0 rows in
        the Phase-3 table): Test-PortFree can't apply (no listener), and
        Test-RegisteredProcessAlive misses survivors of a previous session
        because Initialize-Registry rotates the registry per run.
    #>
    param([string]$Pattern)
    try {
        $hit = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$Pattern*" } |
            Select-Object -First 1
        return ($null -ne $hit)
    } catch { return $false }
}

function Invoke-VenvServices {
    if ($SkipVenv) { Write-Phase "Phase 3: venv services (skipped)"; return }
    Write-Phase "Phase 3: venv services"
    if (-not (Test-Path (Join-Path $script:SHARED_VENV "Scripts/python.exe"))) {
        Write-Warn "shared venv not found at $script:SHARED_VENV — skipping Phase 3"
        return
    }

    # Hardcoded table (same pattern as E1a — config.yaml is not read here).
    # ProbeKind: 'http' uses Test-HttpHealth in Phase 6, 'tcp' uses listener
    # detection. La-Fungus has no /health endpoint (uvicorn default) → TCP.
    # Port=0 rows are PORTLESS sidecars: idempotency gate = CommandLine match
    # on GuardPattern (not Test-PortFree), and ProbeKind 'none' keeps them out
    # of the Phase-6 health gate (it only knows http/tcp probes).
    $services = @(
        @{
            Name      = 'la_fungus'
            Port      = 8011
            WorkDir   = (Join-Path $script:ROOT 'vibemind-os\la-fungus-search')
            Args      = '-m uvicorn embeddinggemma.realtime.server:app --port 8011 --host 127.0.0.1'
            ExtraEnv  = @{ PYTHONPATH = (Join-Path $script:ROOT 'vibemind-os\la-fungus-search\src') }
            LogSubdir = 'la_fungus'
            LogFile   = 'search_api.log'
            ProbeKind = 'tcp'
            ProbeUrl  = ''
        },
        @{
            # fungus-search MCP server (HTTP/SSE on :8412). Claude Code's MCP
            # (.mcp.json type:sse -> :8412/sse) connects here. MUST run persistent:
            # stdio mode cold-starts the 50s index+model load on EVERY tool call
            # (Claude spawns a fresh stdio proc per call) → never hits the loaded
            # instance. The HTTP server loads ONCE on the GPU and stays up.
            # See memory feedback_fungus_index_corruption.
            Name      = 'fungus_mcp_http'
            Port      = 8412
            WorkDir   = (Join-Path $script:ROOT 'vibemind-os\la-fungus-search')
            Args      = 'mcp_server.py --http 8412'
            ExtraEnv  = @{
                FUNGUS_DEVICE      = 'cuda'
                FUNGUS_CODEBASE    = (Join-Path $script:ROOT 'vibemind-os')
                FUNGUS_EMBED_MODEL = 'Qwen/Qwen3-Embedding-0.6B'
            }
            LogSubdir = 'la_fungus'
            LogFile   = 'mcp_http.log'
            ProbeKind = 'tcp'
            ProbeUrl  = ''
        },
        @{
            Name      = 'bridge'
            Port      = 5150
            WorkDir   = (Join-Path $script:ROOT 'vibemind-os\bridge')
            Args      = '-m uvicorn bridge.main:app --port 5150 --host 127.0.0.1'
            ExtraEnv  = @{
                BRAIN_URL    = 'http://localhost:5000'
                OPENFANG_URL = 'http://localhost:4200'
                PYTHONPATH   = (Join-Path $script:ROOT 'vibemind-os\bridge\src')
            }
            LogSubdir = 'bridge'
            LogFile   = 'bridge.log'
            ProbeKind = 'http'
            ProbeUrl  = 'http://localhost:5150/bridge/health'
        },
        @{
            Name      = 'automation_backend'
            Port      = 8007
            WorkDir   = (Join-Path $script:ROOT 'vibemind-os\spaces\desktop\Automation_ui\backend')
            Args      = 'server.py'
            ExtraEnv  = @{ PORT = '8007' }
            LogSubdir = 'automation_ui'
            LogFile   = 'backend.log'
            ProbeKind = 'http'
            ProbeUrl  = 'http://localhost:8007/api/health'
        },
        @{
            # Bubble-Pipeline sidecar 1/3 (Schicht 8.0): post_draft bubbles
            # (status=predicting) -> Mirofish persona-sim -> ready_to_post.
            # Portless polling loop — idempotent + crash-safe (re-pick on
            # restart), but must not run twice (double-poll). Kept in sync
            # with Vibemind.debug.ps1 Phase 4.5.
            Name         = 'bubble_predict_runner'
            Port         = 0
            GuardPattern = 'spaces.marketing.workers.bubble_predict_runner'
            WorkDir      = (Join-Path $script:ROOT 'vibemind-os')
            Args         = '-u -m spaces.marketing.workers.bubble_predict_runner'
            ExtraEnv     = @{ PYTHONUNBUFFERED = '1'; PYTHONIOENCODING = 'utf-8' }
            LogSubdir    = 'marketing'
            LogFile      = 'bubble_predict_runner.log'
            ProbeKind    = 'none'
            ProbeUrl     = ''
        },
        @{
            # Bubble-Pipeline sidecar 2/3: unclassified top-level bubbles ->
            # gpt-4o-mini assigns category/color/channels. OPENAI_API_KEY via
            # the worker's own repo-.env fallback-loader — no key material here.
            Name         = 'bubble_classifier_runner'
            Port         = 0
            GuardPattern = 'spaces.marketing.workers.bubble_classifier_runner'
            WorkDir      = (Join-Path $script:ROOT 'vibemind-os')
            Args         = '-u -m spaces.marketing.workers.bubble_classifier_runner'
            ExtraEnv     = @{ PYTHONUNBUFFERED = '1'; PYTHONIOENCODING = 'utf-8' }
            LogSubdir    = 'marketing'
            LogFile      = 'bubble_classifier_runner.log'
            ProbeKind    = 'none'
            ProbeUrl     = ''
        },
        @{
            # Bubble-Pipeline sidecar 3/3: classified marketing bubbles -> one
            # broadcast_proposal per channel + approval-request against the
            # Marketing-API :5510. MARKETING_PROPOSAL_API_KEY via the worker's
            # own repo-.env fallback-loader.
            Name         = 'bubble_dispatcher'
            Port         = 0
            GuardPattern = 'spaces.marketing.workers.bubble_dispatcher'
            WorkDir      = (Join-Path $script:ROOT 'vibemind-os')
            Args         = '-u -m spaces.marketing.workers.bubble_dispatcher'
            ExtraEnv     = @{ PYTHONUNBUFFERED = '1'; PYTHONIOENCODING = 'utf-8' }
            LogSubdir    = 'marketing'
            LogFile      = 'bubble_dispatcher.log'
            ProbeKind    = 'none'
            ProbeUrl     = ''
        }
    )

    foreach ($s in $services) {
        if ($s.Port -gt 0) {
            if (-not (Test-PortFree -Port $s.Port)) {
                Write-Warn "$($s.Name): :$($s.Port) already held — skipping (idempotent)"
                continue
            }
        } elseif (Test-WorkerCmdlineAlive -Pattern $s.GuardPattern) {
            # portless sidecar — CommandLine match replaces the port gate
            Write-Warn "$($s.Name): already running (CommandLine match) — skipping (idempotent)"
            continue
        }
        if (-not (Test-Path $s.WorkDir)) {
            Write-Warn "$($s.Name): workdir missing ($($s.WorkDir)) — skipping"
            continue
        }
        $logDir = Join-Path $script:LOG_DIR $s.LogSubdir
        if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
        $log = Join-Path $logDir $s.LogFile
        if ($DryRun) {
            Write-Warn "[DryRun] Would start $($s.Name): python.exe $($s.Args)  (cwd=$($s.WorkDir))"
            continue
        }
        $portLabel = if ($s.Port -gt 0) { "(:$($s.Port))" } else { "(portless sidecar)" }
        Write-Ok "Starting $($s.Name) $portLabel"
        $p = Start-VenvPython -Name $s.Name -VenvPath $script:SHARED_VENV `
            -WorkDir $s.WorkDir -ScriptArgs $s.Args -LogFile $log `
            -ExtraEnv $s.ExtraEnv -Port $s.Port `
            -RegistryFile $script:REGISTRY_FILE
        if ($null -eq $p) {
            Write-Warn "$($s.Name): start failed — check $log"
        }
        # expose probe info for the health gate — ProbeKind 'none' rows are
        # intentionally NOT added (Wait-StackHealthy/Show-Status only know
        # http/tcp probes; a portless worker has no network surface to poll)
        if ($s.ProbeKind -ne 'none') {
            $script:NATIVE_PROBES += [pscustomobject]@{
                Name      = $s.Name
                Port      = $s.Port
                ProbeKind = $s.ProbeKind
                ProbeUrl  = $s.ProbeUrl
            }
        }
    }
}

# --- Phase 4: Node services (E1b) ----------------------------------------

function Invoke-NodeServices {
    if ($SkipNode) { Write-Phase "Phase 4: Node services (skipped)"; return }
    Write-Phase "Phase 4: Node services"
    # Moire :8766 — location probe across 4 candidates (Launcher Z.1071-1094)
    $candidates = @(
        (Join-Path $script:ROOT 'vibemind-os\spaces\desktop\Automation_ui\moire_tracker'),
        (Join-Path $script:ROOT 'Automation_ui\moire_tracker'),
        (Join-Path $script:ROOT 'vibemind-os\MoireTracker_v2'),
        (Join-Path $script:ROOT 'MoireTracker_v2')
    )
    $moireDir = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $moireDir) {
        Write-Warn "Moire source dir not found in any of 4 candidates — skipping"
        return
    }
    if (-not (Test-PortFree -Port 8766)) {
        Write-Warn "moire_server: :8766 already held — skipping (idempotent)"
        return
    }
    $logDir = Join-Path $script:LOG_DIR 'voice'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $log = Join-Path $logDir 'moire_server.log'
    if ($DryRun) {
        Write-Warn "[DryRun] Would start moire_server: npm start  (cwd=$moireDir)"
        $script:NATIVE_PROBES += [pscustomobject]@{ Name='moire_server'; Port=8766; ProbeKind='tcp'; ProbeUrl='' }
        return
    }
    Write-Ok "Starting moire_server (:8766) from $moireDir"
    $null = Start-ServiceProcess -Name 'moire_server' -WorkDir $moireDir `
        -Command 'npm' -CmdArgs 'start' -LogFile $log -Port 8766 `
        -RegistryFile $script:REGISTRY_FILE
    $script:NATIVE_PROBES += [pscustomobject]@{ Name='moire_server'; Port=8766; ProbeKind='tcp'; ProbeUrl='' }
}

# --- Phase 5: Electron + Debug-Agent (E1c) -------------------------------
# Server-mode = stack-mode: SKIP_BRAIN_SPAWN=1 and BRAIN_PORT=5000 are
# ALWAYS set (Brain always comes from the swarm stack). No -BrainNative /
# -SkipDocker branches like Vibemind.debug.ps1:1120-1127 — this script
# does not own a non-stack Brain path.

function Invoke-Phase5-Electron {
    if ($SkipElectron) { Write-Phase "Phase 5: Electron (skipped)"; return }
    Write-Phase "Phase 5: Electron (DevTools :9223)"
    $voiceDir    = Join-Path $script:ROOT 'vibemind-os\voice'
    $electronDir = Join-Path $voiceDir 'electron-app'
    $electronExe = Join-Path $electronDir 'node_modules\electron\dist\electron.exe'
    if (-not (Test-Path $electronExe)) {
        Write-Warn "Electron not installed (run: cd vibemind-os/voice/electron-app; npm install) — skipping"
        return
    }
    if (-not (Test-PortFree -Port 9223)) {
        Write-Warn "Electron: :9223 already held — skipping (idempotent)"
        $script:NATIVE_PROBES += [pscustomobject]@{ Name='voice_electron'; Port=9223; ProbeKind='http'; ProbeUrl='http://localhost:9223/json/version' }
        return
    }
    $logDir = Join-Path $script:LOG_DIR 'voice'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $electronLog = Join-Path $logDir 'electron.log'
    $electronErr = Join-Path $logDir 'electron.err.log'
    # Rotate previous logs to .prev so a fresh boot starts clean
    foreach ($f in @($electronLog, $electronErr)) {
        if (Test-Path $f) { Move-Item -Path $f -Destination "${f}.prev" -Force -ErrorAction SilentlyContinue }
    }
    # CRITICAL: clear ELECTRON_RUN_AS_NODE (set by Claude Code IDE; turns
    # Electron into plain Node, which then rejects --remote-debugging-port
    # as "bad option"). cmd /c with explicit `set VAR=&` guarantees the
    # clear reaches the child env. Hardcode SKIP_BRAIN_SPAWN + BRAIN_PORT
    # because server-mode = stack-mode (Brain always from swarm :5000).
    # DASHBOARD_DEV_URL: 2026-05-21 — Coding-Engine-Dashboard (Project-
    # Space im UI) lädt sonst file:/// aus dem uninstanced Submodule
    # `python/spaces/coding/Coding_engine/web-app/front/dist/index.html`
    # → Chromium "Not allowed to load local resource". Stack-Coding-
    # Frontend ist auf :5173 verfügbar, dort lassen wir Electron laden.
    # VIBEMIND_ENABLE_CDP=1 gates the CDP setup in main.js (remote-allow-origins
    # restricted to loopback CDP origins — NOT '*', which is RCE). The launcher
    # IS the trusted local context that needs CDP (notify/rowboat-ui), so enable
    # it here. The --remote-debugging-port flag opens the port; main.js sets the
    # matching remote-allow-origins so our localhost clients aren't 403'd.
    $cmdLine = "set SKIP_BRAIN_SPAWN=1& set BRAIN_PORT=5000& set DASHBOARD_DEV_URL=http://localhost:5173& set VIBEMIND_ENABLE_CDP=1& set ELECTRON_RUN_AS_NODE=& `"$electronExe`" --remote-debugging-port=9223 --enable-logging `"$electronDir`""
    if ($DryRun) {
        Write-Warn "[DryRun] Would launch: cmd /c $cmdLine"
        $script:NATIVE_PROBES += [pscustomobject]@{ Name='voice_electron'; Port=9223; ProbeKind='http'; ProbeUrl='http://localhost:9223/json/version' }
        return
    }
    Write-Ok "Launching Electron (cwd=$voiceDir)"
    Start-Process cmd -ArgumentList "/c", $cmdLine -WorkingDirectory $voiceDir `
        -RedirectStandardOutput $electronLog -RedirectStandardError $electronErr -WindowStyle Hidden
    # Wait for boot — Electron takes ~6-8s; DevTools port appears after
    # the BrowserWindow is created.
    Write-Host "    Waiting for Electron (8s)..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 8
    # cmd /c wrapper has long since exited — record the real electron PID
    # via the listener on :9223.
    $elPid = 0
    try {
        $elConn = Get-NetTCPConnection -LocalPort 9223 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($elConn) { $elPid = [int]$elConn.OwningProcess }
    } catch {}
    if ($elPid -gt 0) {
        Register-SpawnedProcess -Name 'voice_electron' -ProcId $elPid `
            -Command $electronExe -Port 9223 -Runtime 'electron' `
            -RegistryFile $script:REGISTRY_FILE
        Write-Ok "Electron up (PID=$elPid on :9223)"
    } else {
        Write-Warn "Electron started but :9223 not listening after 8s — check $electronLog"
    }
    $script:NATIVE_PROBES += [pscustomobject]@{ Name='voice_electron'; Port=9223; ProbeKind='http'; ProbeUrl='http://localhost:9223/json/version' }
}

function Invoke-Phase5-DebugAgent {
    if ($SkipElectron) { return }   # follows the Electron gate
    Write-Phase "Phase 5: OpenFang Debug-Agent sidecar"
    $debuggerLauncher = Join-Path $script:ROOT 'scripts\openfang_debugger_launch.py'
    if (-not (Test-Path $debuggerLauncher)) {
        Write-Warn "openfang_debugger_launch.py not found at $debuggerLauncher — skipping"
        return
    }
    # Idempotent: skip if registry says it's already alive.
    if (Test-RegisteredProcessAlive -Name 'debug_agent' -RegistryFile $script:REGISTRY_FILE) {
        Write-Warn "debug_agent already alive (registry) — skipping (idempotent)"
        return
    }
    $logDir = Join-Path $script:LOG_DIR 'openfang'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $log = Join-Path $logDir 'debug_agent.log'
    if ($DryRun) {
        Write-Warn "[DryRun] Would start debug_agent (python -u $debuggerLauncher)"
        return
    }
    if (-not (Test-Path (Join-Path $script:SHARED_VENV 'Scripts/python.exe'))) {
        Write-Warn "shared venv missing — cannot start debug_agent"
        return
    }
    Write-Ok "Starting OpenFang Debug-Agent (sidecar)"
    $null = Start-VenvPython -Name 'debug_agent' -VenvPath $script:SHARED_VENV `
        -WorkDir (Join-Path $script:ROOT 'scripts') `
        -ScriptArgs '-u openfang_debugger_launch.py' `
        -LogFile $log `
        -ExtraEnv @{ PYTHONUNBUFFERED='1'; OPENFANG_URL='http://127.0.0.1:4200' } `
        -RegistryFile $script:REGISTRY_FILE
}

# --- Phase 6: Health gate -------------------------------------------------

function Wait-StackHealthy {
    Write-Phase "Phase 6: Health gate (timeout ${HealthTimeout}s)"
    if ($DryRun) { Write-Warn "[DryRun] Would poll docker stack services + key endpoints"; return $true }

    $deadline = (Get-Date).AddSeconds($HealthTimeout)
    $activeSpaces = ConvertTo-SpaceList -Spaces $Spaces

    # Core endpoints — always tested. Coding-frontend etc. only tested when
    # their space is enabled.
    $stackEndpoints = @(
        @{ Name = "brain-core";       Url = "http://localhost:5000/api/health" }
        @{ Name = "rowboat";          Url = "http://localhost:3100/" }
    )
    if ($activeSpaces -contains "coding") {
        $stackEndpoints += @{ Name = "coding-api";      Url = "http://localhost:8000/health" }
        $stackEndpoints += @{ Name = "coding-frontend"; Url = "http://localhost:5173/" }
    }
    if ($activeSpaces -contains "mirofish") {
        $stackEndpoints += @{ Name = "mirofish";        Url = "http://localhost:5101/health" }
    }
    if ($activeSpaces -contains "n8n") {
        $stackEndpoints += @{ Name = "n8n";             Url = "http://localhost:15678/healthz" }
    }

    while ((Get-Date) -lt $deadline) {
        # 1. Stack replicas
        $lines = @(docker stack services --format '{{.Name}} {{.Replicas}}' vibemind 2>$null)
        if ($lines.Count -eq 0) { Start-Sleep -Seconds 3; continue }
        $pending = @($lines | Where-Object {
            if ($_ -match '\s(\d+)/(\d+)\s*$') {
                $have = [int]$Matches[1]; $want = [int]$Matches[2]
                # ready iff have == want (covers want > 0 AND the 0/0 opt-in case)
                -not ($have -eq $want)
            } else { $true }
        })

        if ($pending.Count -eq 0) {
            # 2. All stack endpoints :200/3xx
            $allOk = $true
            foreach ($ep in $stackEndpoints) {
                if (-not (Test-HttpHealth -Url $ep.Url -TimeoutSec 3)) { $allOk = $false; break }
            }
            # 3. Native probes (added by Phase 3/4 — empty if -SkipVenv -SkipNode)
            if ($allOk) {
                foreach ($probe in $script:NATIVE_PROBES) {
                    $ok = if ($probe.ProbeKind -eq 'http') {
                        Test-HttpHealth -Url $probe.ProbeUrl -TimeoutSec 3
                    } else {
                        -not (Test-PortFree -Port $probe.Port)
                    }
                    if (-not $ok) { $allOk = $false; break }
                }
            }
            if ($allOk) {
                $totalProbes = $stackEndpoints.Count + $script:NATIVE_PROBES.Count
                Write-Ok "All $($lines.Count) services converged + $totalProbes endpoints answering"
                return $true
            }
        }
        Start-Sleep -Seconds 5
    }
    Write-Warn "Health gate timed out after ${HealthTimeout}s"
    Write-Warn "Pending services:"
    docker stack services --format '{{.Name}} {{.Replicas}}' vibemind 2>$null |
        Where-Object { $_ -match '\s(\d+)/(\d+)\s*$' -and [int]$Matches[1] -ne [int]$Matches[2] } |
        ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
    foreach ($probe in $script:NATIVE_PROBES) {
        $ok = if ($probe.ProbeKind -eq 'http') {
            Test-HttpHealth -Url $probe.ProbeUrl -TimeoutSec 2
        } else {
            -not (Test-PortFree -Port $probe.Port)
        }
        if (-not $ok) { Write-Warn "  native probe DOWN: $($probe.Name) :$($probe.Port)" }
    }
    return $false
}

# --- Status summary -------------------------------------------------------

function Show-Status {
    Write-Phase "Status"
    docker stack services --format '  {{.Name}} {{.Replicas}}' vibemind 2>$null |
        Sort-Object | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
    Write-Host ""
    $activeSpaces = ConvertTo-SpaceList -Spaces $Spaces
    $eps = @(
        @{N="brain-core";       U="http://localhost:5000/api/health"}
        @{N="rowboat";          U="http://localhost:3100/"}
        @{N="OpenFang (native)";U="http://localhost:4200/api/health"}
    )
    if ($activeSpaces -contains "coding") {
        $eps += @{N="coding-api";       U="http://localhost:8000/health"}
        $eps += @{N="coding-frontend";  U="http://localhost:5173/"}
    }
    if ($activeSpaces -contains "mirofish") { $eps += @{N="mirofish"; U="http://localhost:5101/health"} }
    if ($activeSpaces -contains "n8n")      { $eps += @{N="n8n";      U="http://localhost:15678/healthz"} }
    foreach ($ep in $eps) {
        $ok = Test-HttpHealth -Url $ep.U -TimeoutSec 3
        $color = if ($ok) { 'Green' } else { 'Red' }
        $mark  = if ($ok) { 'OK' } else { 'DOWN' }
        Write-Host ("  {0,-22} {1,-4} {2}" -f $ep.N, $mark, $ep.U) -ForegroundColor $color
    }
    # E1b: native probes (added by Phase 3/4). Stays empty if -SkipVenv/-SkipNode.
    foreach ($probe in $script:NATIVE_PROBES) {
        $url = if ($probe.ProbeUrl) { $probe.ProbeUrl } else { "tcp://localhost:$($probe.Port)" }
        $ok = if ($probe.ProbeKind -eq 'http') {
            Test-HttpHealth -Url $probe.ProbeUrl -TimeoutSec 3
        } else {
            -not (Test-PortFree -Port $probe.Port)
        }
        $color = if ($ok) { 'Green' } else { 'Red' }
        $mark  = if ($ok) { 'OK' } else { 'DOWN' }
        Write-Host ("  {0,-22} {1,-4} {2}" -f $probe.Name, $mark, $url) -ForegroundColor $color
    }
}

# --- Main -----------------------------------------------------------------

Write-Host ""
Write-Host "  =============================================================" -ForegroundColor Cyan
Write-Host "    Vibemind validated start (Stack-Layer, E1a)" -ForegroundColor Cyan
Write-Host "  =============================================================" -ForegroundColor Cyan

# Rotate the spawn registry so vm-procs.ps1 sees only this session's procs.
Initialize-Registry -RegistryFile $script:REGISTRY_FILE

Invoke-Preflight
Invoke-OllamaCheck
Invoke-GpuSetup           # Phase 0.4 — CUDA-Embedder (auto, portabel; ohne GPU still uebersprungen)
Invoke-StackDeploy
Invoke-NativeExceptions
Invoke-VenvServices       # E1b: Phase 3 — venv services (skipped via -SkipVenv)
Invoke-NodeServices       # E1b: Phase 4 — Moire        (skipped via -SkipNode)
Invoke-Phase5-Electron    # E1c: Phase 5 — Electron     (skipped via -SkipElectron)
Invoke-Phase5-DebugAgent  # E1c: Phase 5 — Debug-Agent  (skipped via -SkipElectron)

$ok = Wait-StackHealthy
Show-Status

Write-Host ""
if ($ok) {
    Write-Host "  ✅ Stack-Layer up." -ForegroundColor Green
} else {
    Write-Host "  ⚠ Stack-Layer started but health gate did not pass fully." -ForegroundColor Yellow
    Write-Host "  Inspect:  docker stack services vibemind" -ForegroundColor Gray
}

# E1d: -Interactive enters the wait-loop. Server-mode (default) exits
# immediately so .exe / Scheduled Task runs are event-driven, not blocking.
if ($Interactive) {
    # Native ports that should be reaped on Ctrl+C if the registry-pid
    # lookup misses (the same list Stop-AllServicesFromRegistry uses
    # as a backstop). Stack is intentionally NOT included — Ctrl+C in
    # Dev-mode leaves the stack running between sessions.
    $managedPorts = @(8011, 5150, 8007, 8766, 9223)
    Wait-Interactive -RegistryFile $script:REGISTRY_FILE `
        -ManagedPorts $managedPorts -LogRoot $script:LOG_DIR
    # Wait-Interactive only returns when its `finally` block runs (after
    # Ctrl+C). At that point all native services have been stopped via
    # Stop-AllServicesFromRegistry.
    Write-Host "  Interactive session ended. Stack still up; run scripts/vibemind-stop.ps1 to tear it down." -ForegroundColor Gray
    exit 0
}

if ($ok) {
    Write-Host "  Server-mode: exit 0. Services running in background." -ForegroundColor Gray
    Write-Host "  Stop with: .\scripts\vibemind-stop.ps1" -ForegroundColor Gray
    exit 0
} else {
    Write-Host "  Stop:     .\scripts\vibemind-stop.ps1" -ForegroundColor Gray
    exit 2
}
