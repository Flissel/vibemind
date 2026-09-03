<#
.SYNOPSIS
    Vibemind validated server-mode stop — through Phase 4 (E1a + E1b).
.DESCRIPTION
    Symmetric counterpart to vibemind-start.ps1. Stops:
      - Phase 3 venv services (la_fungus :8011, bridge :5150,
                               automation_backend :8007 — tree-kill).
      - Phase 4 Node service (moire_server :8766 — tree-kill).
      - OpenFang native binary (resolved by port :4200 — same registry
                                pattern vm-procs.ps1 / Launcher use).
      - Minibook native compose (if started by start-script).
      - docker stack rm vibemind  (services + overlay net; NAMED VOLUMES
                                   persist — brain_data / rowboat_mongo /
                                   coding_postgres / neo4j_mirofish_data
                                   survive; data safe).
      - Ollama: NOT killed by default (it is a long-lived host service
                that other host things may also use). -StopOllama opts in.

    Companion: scripts\vibemind-start.ps1.
.PARAMETER KeepStack
    Stop only the native processes, leave the swarm stack running.
.PARAMETER KeepVenv
    Leave Phase 3 venv services (la_fungus / bridge / automation_backend) running.
.PARAMETER KeepNode
    Leave moire_server running.
.PARAMETER KeepElectron
    Leave Phase 5 (Electron + Debug-Agent) running.
.PARAMETER StopOllama
    Also stop the Ollama host process (default: leave running).
.PARAMETER DryRun
    Show what would happen, do nothing destructive.
.EXAMPLE
    .\scripts\vibemind-stop.ps1
    .\scripts\vibemind-stop.ps1 -KeepStack
    .\scripts\vibemind-stop.ps1 -KeepVenv -KeepNode  # only native infra down
    .\scripts\vibemind-stop.ps1 -DryRun
#>
param(
    [switch]$KeepStack,
    [switch]$KeepVenv,      # E1b: leave Phase 3 venv services running
    [switch]$KeepNode,      # E1b: leave Phase 4 Moire running
    [switch]$KeepElectron,  # E1c: leave Electron + Debug-Agent running
    [switch]$StopOllama,
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"

$script:ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Shared helpers (see scripts/lib/vibemind-helpers.ps1).
. (Join-Path $PSScriptRoot 'lib\vibemind-helpers.ps1')

# --- Transcript ----------------------------------------------------------
# Capture stop output to logs/launcher/stop-{ts}.log so the MCP tool
# `vibemind_launcher_logs` can surface it. Best-effort: never fail the stop.
$script:LAUNCHER_LOG_DIR = Join-Path $script:ROOT "logs\launcher"
try {
    if (-not (Test-Path $script:LAUNCHER_LOG_DIR)) {
        New-Item -ItemType Directory -Path $script:LAUNCHER_LOG_DIR -Force | Out-Null
    }
    $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stopLog = Join-Path $script:LAUNCHER_LOG_DIR "stop-$ts.log"
    Start-Transcript -Path $stopLog -IncludeInvocationHeader -Force | Out-Null
    Register-EngineEvent PowerShell.Exiting -Action {
        try { Stop-Transcript | Out-Null } catch {}
    } | Out-Null
    Get-ChildItem $script:LAUNCHER_LOG_DIR -Filter 'stop-*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 20 |
        Remove-Item -Force -ErrorAction SilentlyContinue
} catch {}

# --- 1. native exceptions ------------------------------------------------

function Stop-OpenFang {
    Write-Phase "OpenFang (native binary)"
    # OpenFang self-daemonises — the spawn PID dies immediately and the
    # listener is the real process. Resolve owner by port (same pattern
    # vm-procs.ps1 uses, registry-style). Generalised in Stop-ByPort.
    Stop-ByPort -Port 4200 -Name 'OpenFang' -DryRun:$DryRun
}

function Stop-Minibook {
    Write-Phase "Minibook (native compose)"
    $mbCompose = Join-Path $script:ROOT "vibemind-os\voice\docker-compose.minibook.yml"
    if (-not (Test-Path $mbCompose)) {
        Write-Warn "Minibook compose not found — nothing to stop"
        return
    }
    if ($DryRun) {
        Write-Warn "[DryRun] Would: docker compose -f $mbCompose -p vibemind-minibook down"
        return
    }
    Write-Ok "docker compose down: vibemind-minibook"
    docker compose -f $mbCompose -p vibemind-minibook down 2>&1 |
        Where-Object { $_ -match 'Stopped|Removed|error|Error' } |
        ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
}

# --- 2. Stack rm ---------------------------------------------------------

function Stop-Stack {
    Write-Phase "Swarm stack"
    if ($KeepStack) {
        Write-Warn "-KeepStack: leaving 'vibemind' stack running"
        return
    }
    # Check if the stack exists
    $exists = docker stack ls --format '{{.Name}}' 2>$null | Where-Object { $_ -eq 'vibemind' }
    if (-not $exists) {
        Write-Warn "Stack 'vibemind' not deployed — nothing to remove"
        return
    }
    if ($DryRun) {
        Write-Warn "[DryRun] Would: docker stack rm vibemind"
        return
    }
    Write-Ok "docker stack rm vibemind (named volumes persist — data safe)"
    docker stack rm vibemind 2>&1 |
        Where-Object { $_ -match 'Removing|error|Error' } |
        ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
    # docker stack rm is async — give it a moment for containers to die.
    # Not a hard wait (containers can take 30s+ to fully stop) — server-mode
    # stop reports success once rm is queued; tasks unwind in the background.
    Start-Sleep -Seconds 3
    Write-Ok "Stack removal queued (containers unwind asynchronously)"
}

# --- 3. Ollama (optional) ------------------------------------------------

function Stop-OllamaIfRequested {
    if (-not $StopOllama) {
        Write-Phase "Ollama (kept running — use -StopOllama to stop)"
        return
    }
    Write-Phase "Ollama (host process)"
    Stop-ByPort -Port 11434 -Name 'Ollama' -DryRun:$DryRun
}

# --- E1b: native venv + Node services ------------------------------------

function Stop-VenvServices {
    if ($KeepVenv) { Write-Phase "Phase 3 venv services (kept — -KeepVenv)"; return }
    Write-Phase "Phase 3 venv services (la_fungus, bridge, automation_backend)"
    # Tree-kill: uvicorn / FastAPI run with worker subprocesses.
    # CmdLinePattern + RepoRoot is a path-scoped second pass that catches
    # processes whose CommandLine contains the workdir but whose parent
    # PID was reparented before taskkill /T walked the tree. This is
    # narrow on purpose — we will NOT kill bare 'multiprocessing-fork'
    # children (no path in command line → impossible to scope safely).
    # Known limitation: automation_backend's multiprocessing children can
    # survive as kernel-ghost listeners on :8007. If a subsequent start
    # finds :8007 still held, use `vm-procs.ps1 -KillFlagged` or
    # `taskkill /F /IM python.exe` (last resort) to free it.
    Stop-ByPort -Port 8011 -Name 'la_fungus'          -Tree -DryRun:$DryRun `
        -CmdLinePattern 'la-fungus-search|embeddinggemma\.realtime' -RepoRoot $script:ROOT
    Stop-ByPort -Port 5150 -Name 'bridge'             -Tree -DryRun:$DryRun `
        -CmdLinePattern 'bridge\.main|vibemind-os\\bridge'           -RepoRoot $script:ROOT
    Stop-ByPort -Port 8007 -Name 'automation_backend' -Tree -DryRun:$DryRun `
        -CmdLinePattern 'Automation_ui\\backend\\server\.py'          -RepoRoot $script:ROOT
}

function Stop-NodeServices {
    if ($KeepNode) { Write-Phase "Phase 4 Node services (kept — -KeepNode)"; return }
    Write-Phase "Phase 4 Node services (moire_server)"
    Stop-ByPort -Port 8766 -Name 'moire_server' -Tree -DryRun:$DryRun
}

# --- E1c: Phase 5 Electron + Debug-Agent ---------------------------------

function Stop-Phase5 {
    if ($KeepElectron) { Write-Phase "Phase 5 (kept — -KeepElectron)"; return }
    Write-Phase "Phase 5 Electron (DevTools :9223) + Debug-Agent"

    # Electron — tree-kill via :9223 listener, PLUS path-filter backstop on
    # electron.exe (Electron processes spawn a Main + Renderer + multiple
    # Helper procs; the main holds :9223 but the helpers won't die from a
    # bare port-PID kill).
    # Wrapped in try so a Stop-Process failure here cannot prevent
    # Stop-DebugAgent below from running (the live-test 2026-05-20
    # showed a single-pass leaving the debug-agent alive when the
    # electron block had a transient error).
    try {
        Stop-ByPort -Port 9223 -Name 'voice_electron' -Tree -DryRun:$DryRun `
            -CmdLinePattern 'electron\.exe' -RepoRoot $script:ROOT
        # Backstop: any electron.exe whose path starts in vibemind-os\
        # voice\electron-app gets killed. Foreign Electrons (VSCode,
        # Discord, etc.) survive because the Path filter is repo-scoped.
        if (-not $DryRun -and -not $KeepElectron) {
            $repoElectrons = Get-Process electron -ErrorAction SilentlyContinue | Where-Object {
                $_.Path -and $_.Path -like "$script:ROOT\vibemind-os\voice\electron-app\*"
            }
            foreach ($p in $repoElectrons) {
                try {
                    Stop-Process -Id $p.Id -Force -ErrorAction Stop
                    Write-Host "      Killed straggler electron PID=$($p.Id) ($($p.Path))" -ForegroundColor DarkGray
                } catch {}
            }
        }
    } catch {
        Write-Warn "Electron stop encountered error: $($_.Exception.Message) — continuing with Debug-Agent"
    }

    # Debug-Agent — no fixed port. Resolve from registry + CommandLine
    # backstop (the launcher script is at scripts\openfang_debugger_launch.py).
    # MUST run even if the Electron block above had errors.
    Stop-DebugAgent
}

function Stop-DebugAgent {
    $registryFile = Join-Path $script:ROOT 'logs\services.registry.jsonl'
    $pidsToKill = @()
    # 1. Registry: last debug_agent entry
    if (Test-Path $registryFile) {
        try {
            Get-Content $registryFile -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $e = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
                    if ($e -and $e.name -eq 'debug_agent' -and $e.pid -gt 0) {
                        $pidsToKill += [int]$e.pid
                    }
                } catch {}
            }
        } catch {}
    }
    # 2. CommandLine backstop — only python.exe processes whose CommandLine
    #    contains openfang_debugger_launch. Restricting to Name='python.exe'
    #    prevents the obvious self-kill where a pwsh.exe whose commit message
    #    happens to contain this string would otherwise match (DryRun caught
    #    this 2026-05-20: a pwsh running `git commit -m '...openfang_debugger_
    #    launch...'` was flagged for kill).
    try {
        $cmdLineHits = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -eq 'python.exe' -and
            $_.CommandLine -and
            $_.CommandLine -match 'openfang_debugger_launch'
        }
        foreach ($p in $cmdLineHits) { $pidsToKill += [int]$p.ProcessId }
    } catch {}
    $pidsToKill = $pidsToKill | Sort-Object -Unique
    if ($pidsToKill.Count -eq 0) {
        Write-Warn "Debug-Agent not running (no registry entry, no cmdline match)"
        return
    }
    foreach ($procId in $pidsToKill) {
        $alive = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $alive) { continue }
        if ($DryRun) {
            Write-Warn "[DryRun] Would Stop-Process -Id $procId (debug_agent)"
        } else {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Ok "Debug-Agent stopped (PID=$procId)"
            } catch {
                Write-Warn "Could not stop debug_agent PID ${procId}: $($_.Exception.Message)"
            }
        }
    }
}

# --- Main ----------------------------------------------------------------

Write-Host ""
Write-Host "  =============================================================" -ForegroundColor Cyan
Write-Host "    Vibemind validated stop (Stack-Layer, E1a)" -ForegroundColor Cyan
Write-Host "  =============================================================" -ForegroundColor Cyan

# Order (native first, fast, then stack async, then optional Ollama):
# - E1c: Electron + Debug-Agent first (they depend on Brain :5000 + OpenFang :4200)
# - E1b: venv + Node services next (Bridge talks to Brain + OpenFang)
# - OpenFang + Minibook (consumed by Bridge / Debug-Agent above)
# - Stack last (named volumes persist)
Stop-Phase5
Stop-VenvServices
Stop-NodeServices
Stop-OpenFang
Stop-Minibook
Stop-Stack
Stop-OllamaIfRequested

Write-Host ""
Write-Host "  ✅ Stop sequence complete." -ForegroundColor Green
Write-Host "  Named volumes preserved: data is safe." -ForegroundColor Gray
Write-Host "  Restart with: .\scripts\vibemind-start.ps1" -ForegroundColor Gray
