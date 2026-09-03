<#
.SYNOPSIS
    VibeMind Master Debug Launcher - starts the entire ecosystem
.DESCRIPTION
    Orchestrates Docker services, Python venvs, Node services, Electron app.
    Reads configuration from vibemind.config.json (created by setup.ps1).
.PARAMETER Modules
    Comma-separated list of modules to start (overrides config for this session)
.PARAMETER SkipDocker
    Skip all Docker services
.PARAMETER DryRun
    Print what would be started without starting anything
.PARAMETER HealthTimeout
    Max seconds to wait for Docker health checks (default: 120)
#>
param(
    [string]$Modules = "",
    [switch]$SkipDocker,
    [switch]$SkipCleanup,
    [switch]$DryRun,
    # Phase A: Brain runs as a container by default (fixes the pyenv double-
    # spawn structurally). -BrainNative falls back to the legacy venv path
    # for dev velocity (venv restart ~35s vs container build ~120s).
    [switch]$BrainNative,
    # Phase B: the unified Docker Swarm stack (infra/swarm/vibemind-stack.yml)
    # is the default. -Legacy falls back to the old per-compose world (the 9
    # separate `docker compose -p vibemind-<x> up -d` projects) for dev
    # velocity / debugging a single service in isolation. Default = stack.
    [switch]$Legacy,
    [int]$HealthTimeout = 120
)

$ErrorActionPreference = "Continue"
$script:ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:CONFIG_FILE = Join-Path $ROOT "vibemind.config.json"
$script:ROOT_ENV = Join-Path $ROOT ".env"
$script:LOG_DIR = Join-Path $ROOT "logs"
$script:PROCESSES = @{}
$script:DOCKER_PROJECTS = @()
# Phase B: set by Invoke-SwarmStackDeploy when the unified Swarm stack is the
# active path (default, i.e. NOT -Legacy). Stop-AllServices tears it down on
# exit (§C decision: Ctrl+C removes the stack; named volumes persist).
$script:SWARM_STACK = $null
$script:HealthJobs = @{}
# On-disk registry of spawned PIDs so an external tool (vm-procs.ps1) can
# track/kill exactly the processes this launcher owns, even though the
# in-memory $script:PROCESSES table dies with the script. Append-only JSONL;
# truncated once per run below so it reflects the current launcher session.
$script:REGISTRY_FILE = Join-Path $script:LOG_DIR "services.registry.jsonl"

# ── Helpers ───────────────────────────────────────────────────────

function Register-SpawnedProcess {
    <#
    .SYNOPSIS
        Append one JSONL line recording a process this launcher spawned.
    .DESCRIPTION
        Source of truth for vm-procs.ps1. Each line: name, pid, command,
        port (0 if none/unknown), runtime hint, started timestamp, session.
        Best-effort — never throws into the start path.
    #>
    param(
        [string]$Name, [int]$ProcId, [string]$Command,
        [int]$Port = 0, [string]$Runtime = ""
    )
    try {
        $rec = [ordered]@{
            name    = $Name
            pid     = $ProcId
            command = $Command
            port    = $Port
            runtime = $Runtime
            started = (Get-Date -Format "o")
            session = $PID            # the launcher's own PID = session id
        }
        $line = ($rec | ConvertTo-Json -Compress -Depth 4)
        $dir = Split-Path $script:REGISTRY_FILE
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $script:REGISTRY_FILE -Value $line -Encoding utf8 -ErrorAction SilentlyContinue
    } catch {}
}

function Get-ServicePort {
    <#
    .SYNOPSIS
        Map a launcher service name to its primary TCP port via CONFIG.ports.
        Returns 0 when the service has no single network port (debug_agent).
    #>
    param([string]$Name)
    if (-not $CONFIG) { return 0 }
    $map = @{
        brain_dashboard    = $CONFIG.ports.brain_dashboard
        brain_api          = $CONFIG.ports.brain_api
        bridge             = $CONFIG.ports.bridge
        la_fungus          = $CONFIG.ports.la_fungus_api
        automation_backend = $CONFIG.ports.automation_backend
        moire_server       = $CONFIG.ports.moire_server
        debug_agent        = 0
        marketing_sync_a   = 0
        marketing_sync_b   = 0
        marketing_runner   = 0
        marketing_http     = 0
        bubble_predict_runner    = 0
        bubble_classifier_runner = 0
        bubble_dispatcher        = 0
    }
    if ($map.ContainsKey($Name)) { return [int]$map[$Name] }
    return 0
}

function Get-RuntimeHint {
    <#
    .SYNOPSIS
        Classify a command path as .venv / voice-venv / pyenv / native / node
        so the process frontend can flag the pyenv-vs-venv duplicate problem.
    #>
    param([string]$Command)
    if ($Command -match '\.venv312')      { return 'voice-venv' }
    if ($Command -match '\\\.venv\\')     { return '.venv' }
    if ($Command -match 'pyenv')          { return 'pyenv' }
    if ($Command -match 'node\.exe|npm')  { return 'node' }
    if ($Command -match 'electron\.exe')  { return 'electron' }
    if ($Command -match 'openfang')       { return 'native' }
    return 'other'
}

function Write-Status { param($svc, $status, $port, $url, $reason)
    $color = switch ($status) { "OK" { "Green" } "DOWN" { "Red" } "CRASH" { "Magenta" } "SKIP" { "DarkGray" } default { "Yellow" } }
    $dot = switch ($status) { "OK" { "●" } "DOWN" { "○" } "CRASH" { "✗" } "SKIP" { "-" } default { "?" } }
    $reasonField = if ($reason) { $reason } else { "" }
    $line = "  {0} {1,-20} {2,-8} {3,-20} {4}" -f $dot, $svc, ":$port", $reasonField, $url
    Write-Host $line -ForegroundColor $color
}

function Test-Port { param([int]$Port)
    try { (Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet) } catch { $false }
}

function Test-HttpHealth { param([string]$Url, [int]$Timeout = 5)
    try { $r = Invoke-WebRequest -Uri $Url -TimeoutSec $Timeout -UseBasicParsing -ErrorAction Stop; return $r.StatusCode -eq 200 } catch { return $false }
}

function Test-WorkerCmdlineAlive {
    <#
    .SYNOPSIS
        $true iff a python.exe whose CommandLine contains $Pattern is already
        running. Already-running guard for PORTLESS sidecars: Test-Port can't
        apply (no listener) and Invoke-PreflightCleanup only frees managed
        PORTS, so a worker surviving a crashed previous session would
        otherwise be started a second time.
    #>
    param([string]$Pattern)
    try {
        $hit = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$Pattern*" } |
            Select-Object -First 1
        return ($null -ne $hit)
    } catch { return $false }
}

function Start-ServiceProcess {
    param([string]$Name, [string]$WorkDir, [string]$Command, [string]$CmdArgs, [string]$LogFile, [hashtable]$ExtraEnv)
    $logDir = Split-Path $LogFile
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Command
    $psi.Arguments = $CmdArgs
    $psi.WorkingDirectory = $WorkDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    # Apply per-service env overrides into the child process env block
    if ($ExtraEnv) {
        foreach ($k in $ExtraEnv.Keys) {
            $psi.EnvironmentVariables[$k] = [string]$ExtraEnv[$k]
        }
    }
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
    } catch {
        Write-Host "    [WARN] Failed to start $Name : $_" -ForegroundColor Yellow
        return $null
    }
    if ($null -eq $proc) {
        Write-Host "    [WARN] $Name process returned null" -ForegroundColor Yellow
        return $null
    }
    # Give the process a moment to fail, then check if it's still alive.
    # 1500ms catches import-time ModuleNotFoundError / uvicorn config errors
    # before the async BeginOutputReadLine path can drop them.
    Start-Sleep -Milliseconds 1500
    if ($proc.HasExited) {
        # Drain stderr/stdout synchronously so the error isn't lost,
        # and write it to the log so the user can actually see what went wrong.
        $stderrText = ""
        $stdoutText = ""
        try { $stderrText = $proc.StandardError.ReadToEnd() } catch {}
        try { $stdoutText = $proc.StandardOutput.ReadToEnd() } catch {}
        try {
            $logDir2 = Split-Path $LogFile
            if (-not (Test-Path $logDir2)) { New-Item -ItemType Directory -Path $logDir2 -Force | Out-Null }
            $sw = [System.IO.StreamWriter]::new($LogFile, $true)
            $sw.WriteLine("=== [$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Name EARLY-EXIT code=$($proc.ExitCode) cmd=$Command $CmdArgs ===")
            if ($stdoutText) { $sw.WriteLine("[STDOUT]"); $sw.WriteLine($stdoutText) }
            if ($stderrText) { $sw.WriteLine("[STDERR]"); $sw.WriteLine($stderrText) }
            $sw.Close()
        } catch {}
        Write-Host "    [WARN] $Name exited immediately (exit code: $($proc.ExitCode))" -ForegroundColor Yellow
        if ($stderrText) {
            $stderrText -split "`n" | Select-Object -Last 5 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkYellow }
        }
        # Still register so the final crash-report sees the exit code
        $script:PROCESSES[$Name] = @{ Process = $proc; LogWriter = $null }
        return $null
    }
    # Async log capture — wrapped in SilentlyContinue because if the
    # process dies between the HasExited check and the Add() call,
    # PowerShell throws InvalidOperation on the dead handle.
    $outFile = $null
    $ErrorActionPreference_saved = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $outFile = [System.IO.StreamWriter]::new($LogFile, $true)
        $outFile.AutoFlush = $true
        $outFile.WriteLine("=== [$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Name started: $Command $CmdArgs ===")
        $proc.OutputDataReceived.Add({ param($s,$e) if ($e.Data) { $outFile.WriteLine($e.Data) } }.GetNewClosure())
        $proc.ErrorDataReceived.Add({ param($s,$e) if ($e.Data) { $outFile.WriteLine("[ERR] $($e.Data)") } }.GetNewClosure())
        $proc.EnableRaisingEvents = $true
        $nameCapture = $Name
        $proc.add_Exited({
            try {
                $proc.WaitForExit(2000) | Out-Null
                $outFile.WriteLine("=== [$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $nameCapture EXITED code=$($proc.ExitCode) ===")
                $outFile.Flush()
            } catch {}
        }.GetNewClosure())
        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()
    } catch {
        # Silently ignore — process may have died during setup
    }
    $ErrorActionPreference = $ErrorActionPreference_saved
    $script:PROCESSES[$Name] = @{ Process = $proc; LogWriter = $outFile }
    Register-SpawnedProcess -Name $Name -ProcId $proc.Id `
        -Command "$Command $CmdArgs" -Port (Get-ServicePort $Name) `
        -Runtime (Get-RuntimeHint $Command)
    return $proc
}

function Start-VenvPython {
    param([string]$Name, [string]$VenvPath, [string]$WorkDir, [string]$ScriptArgs, [string]$LogFile, [hashtable]$ExtraEnv)
    $python = Join-Path $VenvPath "Scripts/python.exe"
    if (-not (Test-Path $python)) {
        Write-Host "  [WARN] venv not found: $VenvPath" -ForegroundColor Yellow
        return $null
    }
    return Start-ServiceProcess -Name $Name -WorkDir $WorkDir -Command $python -CmdArgs $ScriptArgs -LogFile $LogFile -ExtraEnv $ExtraEnv
}

function Invoke-SwarmStackDeploy {
    <#
    .SYNOPSIS
        Bring up the unified Docker Swarm stack (Phase B default path).
    .DESCRIPTION
        Replaces the legacy per-compose Phase 1 when NOT -Legacy. Steps:
        1. Ensure Swarm is active (auto `docker swarm init` if not — §A).
        2. Provision external secrets from .env (idempotent — existing skipped).
        3. `docker stack deploy` (--resolve-image never: all images are local
           :latest, no registry; mirrors the stack-file header note).
        4. Poll until the non-opt-in services converge (brain-learner /
           brain-inference are replicas:0 by design — excluded from "ready").
        Sets $script:SWARM_STACK so Ctrl+C tears it down (§C).
        Best-effort logging; never throws into the launcher main flow.
    #>
    $stackName = "vibemind"
    $stackFile = Join-Path $ROOT "infra\swarm\vibemind-stack.yml"
    $secretsScript = Join-Path $ROOT "scripts\swarm_secrets_init.ps1"

    if (-not (Test-Path $stackFile)) {
        Write-Host "  [ERROR] stack file not found: $stackFile" -ForegroundColor Red
        return
    }

    # 1. Swarm active? (§A: auto-init with a loud line)
    $swarmState = ""
    try { $swarmState = (docker info --format '{{.Swarm.LocalNodeState}}' 2>$null) } catch {}
    if ($swarmState -ne "active") {
        Write-Host "  [SWARM] Swarm inactive ('$swarmState') — running 'docker swarm init' (one-time, --advertise-addr 127.0.0.1)" -ForegroundColor Yellow
        docker swarm init --advertise-addr 127.0.0.1 2>&1 | Out-Null
        try { $swarmState = (docker info --format '{{.Swarm.LocalNodeState}}' 2>$null) } catch {}
        if ($swarmState -ne "active") {
            Write-Host "  [ERROR] Swarm could not be initialised — cannot deploy stack. Use -Legacy for the per-compose path." -ForegroundColor Red
            return
        }
        Write-Host "  [SWARM] Swarm is now active." -ForegroundColor Green
    }

    # 1.5 GPU-Auto-Setup (CUDA-Embedder) — GETEILTE Funktion aus lib/vibemind-helpers.ps1,
    # damit dieser Start-Pfad DIESELBE GPU-Logik wie vibemind-start.ps1 nutzt (kein Drift
    # wie beim Network-Race). Erkennt NVIDIA-GPU, mergt default-runtime:nvidia in daemon.json,
    # setzt $env:VIBEMIND_GPU_DEVICES -> brain-core bekommt die GPU. Ohne GPU: still raus.
    # Defensiv: wenn Helpers/Funktion fehlen, wird es uebersprungen (debug.ps1 nie brechen).
    try {
        $stackHelper = Join-Path $ROOT "scripts\lib\vibemind-helpers.ps1"
        if ((Test-Path $stackHelper) -and -not (Get-Command Get-StackProfileNames -ErrorAction SilentlyContinue)) {
            . $stackHelper
        }
        if (Get-Command Invoke-GpuSetup -ErrorAction SilentlyContinue) { Invoke-GpuSetup }
    } catch {
        Write-Host "  [WARN] GPU-Setup uebersprungen: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }

    # 2. Secrets (idempotent; skips existing). Non-fatal if the script warns.
    if (Test-Path $secretsScript) {
        Write-Host "  [SWARM] Provisioning secrets from .env (idempotent)..." -ForegroundColor Cyan
        try { & $secretsScript -EnvFile $script:ROOT_ENV 2>&1 | Out-Null } catch {
            Write-Host "  [WARN] swarm_secrets_init.ps1 reported: $($_.Exception.Message)" -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  [WARN] $secretsScript not found — deploying without secret provisioning (external secrets may be missing)" -ForegroundColor DarkYellow
    }

    # 2.5 Ensure local images exist. `docker stack deploy --resolve-image never`
    # does NOT build — a missing image = a service stuck "Rejected: No such
    # image" (silent partial start). swarm_image_builds.ps1 is the single
    # source of truth: it clones absent build sources (mirofish submodule),
    # detects missing images and builds ONLY those (0 builds on a warm repo,
    # self-healing when an image was pruned). Best-effort: a failed build is
    # reported loudly but doesn't abort the launch — the rest of the stack
    # still comes up, and Phase 6 / the readiness poll show what's down.
    $buildMap = Join-Path $ROOT "scripts\swarm_image_builds.ps1"
    if (Test-Path $buildMap) {
        Write-Host "  [SWARM] Ensuring local stack images are built..." -ForegroundColor Cyan
        try {
            . $buildMap
            $imagesOk = Invoke-EnsureStackImages -Root $ROOT
            if (-not $imagesOk) {
                Write-Host "  [SWARM] Some images are missing — affected services will be 0/1 until built." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  [WARN] swarm_image_builds.ps1 failed: $($_.Exception.Message) — deploying with whatever images exist." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  [WARN] $buildMap not found — skipping pre-build (missing images will show as 0/1)." -ForegroundColor DarkYellow
    }

    # 3. Render every declared profile, then deploy. Debug mode intentionally
    # keeps the full stack, but Swarm rejects Compose-only `profiles:` keys.
    # The existing renderer strips those keys without compose-format coercion.
    $renderedStackFile = $null
    try {
        $allProfiles = Get-StackProfileNames -StackFile $stackFile
        $renderedStackFile = ConvertTo-FilteredStack -StackFile $stackFile -Profiles $allProfiles

        # --resolve-image never: local-only :latest tags, no registry.
        # Cold-start network-race: `docker stack deploy` can try to create services
        # BEFORE the inline overlay net's control-plane object is name-resolvable,
        # failing the first services with "network ... not found" (exit 1). The net
        # IS created on the failed attempt, so retrying once it's inspect-resolvable
        # succeeds. This is the SAME hardened retry as Invoke-FilteredStackDeploy
        # (vibemind-helpers.ps1) — kept inline here because this interactive path
        # keeps no --prune by design, a different contract than the filtered launcher.
        # Previously this path piped
        # deploy output straight into Where-Object, so $LASTEXITCODE reflected the
        # ForEach-Object exit (always 0) — a network-race was silently swallowed
        # with no retry. Now: capture output, check docker's real exit, retry on the
        # network-race signature (5 attempts, inspect-poll then escalating backoff).
        Write-Host "  [SWARM] docker stack deploy -> $stackName" -ForegroundColor Cyan
        $maxAttempts = 5
        $netNames = @("${stackName}_vibemind-shared", "${stackName}_coding-egress")
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            $deployOut = docker stack deploy -c $renderedStackFile --resolve-image never $stackName 2>&1
            $deployExit = $LASTEXITCODE
            $deployOut |
                Where-Object { $_ -match 'Creating|Updating|error|Error' } |
                ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
            if ($deployExit -eq 0) { break }

            $isNetworkRace = ($deployOut | Where-Object { $_ -match 'network .* not found' }).Count -gt 0
            if (-not $isNetworkRace -or $attempt -eq $maxAttempts) {
                Write-Host "  [ERROR] stack deploy failed (exit $deployExit)$(if ($isNetworkRace) { ' — network-race retries exhausted' })" -ForegroundColor Red
                break
            }
            Write-Host "  [SWARM] network-race detected (attempt $attempt of $maxAttempts), waiting for overlay net(s)..." -ForegroundColor Yellow
            $netDeadline = (Get-Date).AddSeconds(20)
            do {
                $allUp = $true
                foreach ($n in $netNames) {
                    docker network inspect $n 2>&1 | Out-Null
                    if ($LASTEXITCODE -ne 0) { $allUp = $false }
                }
                if ($allUp) { break }
                Start-Sleep -Seconds 2
            } while ((Get-Date) -lt $netDeadline)
            if (-not $allUp) { Start-Sleep -Seconds ([math]::Min(2 * $attempt, 8)) }
        }
    }
    finally {
        if ($renderedStackFile) {
            Remove-Item -LiteralPath $renderedStackFile -Force -ErrorAction SilentlyContinue
        }
    }
    $script:SWARM_STACK = $stackName

    # 4. Readiness poll. replicas:0 services are opt-in (Phase D) — a 0/0 line
    # is HEALTHY-by-design, not pending. Treat N/N (N>0) OR 0/0 as ready.
    Write-Host "  [SWARM] Waiting for stack services to converge (timeout ${HealthTimeout}s)..." -ForegroundColor Cyan
    $deadline = (Get-Date).AddSeconds($HealthTimeout)
    while ((Get-Date) -lt $deadline) {
        $lines = @(docker stack services --format '{{.Name}} {{.Replicas}}' $stackName 2>$null)
        if ($lines.Count -eq 0) { Start-Sleep -Seconds 5; continue }
        $pending = @($lines | Where-Object {
            if ($_ -match '\s(\d+)/(\d+)\s*$') {
                # Ready iff replicas met: have == want. This also makes the
                # replicas:0 opt-in case (0/0) ready-by-design. (The old guard
                # `$want -gt 0 -or $want -eq 0` was a tautology — always true —
                # so it reduced to exactly this; kept the behaviour, dropped the
                # dead expression.)
                $have = [int]$Matches[1]; $want = [int]$Matches[2]
                $have -ne $want
            } else { $true }
        })
        if ($pending.Count -eq 0) {
            Write-Host "  [SWARM] All $($lines.Count) stack services converged." -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 5
    }
    # Loud, specific timeout report. A silent "continuing" WARN used to hide a
    # partial start (e.g. a service stuck "No such image"); now we name each
    # still-pending service AND surface its latest task error so the cause
    # (missing image, crash-loop, OOM) is visible without digging into Phase 6.
    $stillPending = @(docker stack services --format '{{.Name}} {{.Replicas}}' $stackName 2>$null |
        Where-Object { $_ -match '\s(\d+)/(\d+)\s*$' -and [int]$Matches[1] -ne [int]$Matches[2] })
    Write-Host "  [WARN] Stack readiness timed out after ${HealthTimeout}s — $($stillPending.Count) service(s) not converged:" -ForegroundColor Yellow
    foreach ($svcLine in $stillPending) {
        $svcName = ($svcLine -split '\s+')[0]
        # Latest task error for this service (e.g. 'No such image: ...').
        $err = docker service ps $svcName --no-trunc --format '{{.Error}}' 2>$null |
            Where-Object { $_ } | Select-Object -First 1
        if ($err) {
            Write-Host "    - $svcLine  ->  $err" -ForegroundColor Red
        } else {
            Write-Host "    - $svcLine  (starting / health pending)" -ForegroundColor DarkYellow
        }
    }
    Write-Host "  [SWARM] Continuing — Phase 6 health table shows live status." -ForegroundColor DarkYellow
}

function Stop-AllServices {
    Write-Host "`n  Shutting down..." -ForegroundColor Yellow

    # Stop tracked processes — use taskkill /T to kill the whole tree.
    # Plain Process.Kill() only kills the direct PID; uvicorn/npm spawn
    # children that would otherwise survive as orphans.
    foreach ($entry in $script:PROCESSES.GetEnumerator()) {
        try {
            $proc = $entry.Value.Process
            if ($proc -and -not $proc.HasExited) {
                # Tree-kill — covers uvicorn workers, npm-spawned node, etc.
                & taskkill.exe /F /T /PID $proc.Id 2>&1 | Out-Null
                Write-Host "  Stopped $($entry.Key) (PID=$($proc.Id) +tree)" -ForegroundColor Gray
            }
            if ($entry.Value.LogWriter) { $entry.Value.LogWriter.Close() }
        } catch {}
    }

    # Stop health probe jobs
    foreach ($entry in $script:HealthJobs.GetEnumerator()) {
        try { Stop-Job $entry.Value -ErrorAction SilentlyContinue; Remove-Job $entry.Value -Force -ErrorAction SilentlyContinue } catch {}
    }

    # Stop Docker projects (legacy per-compose mode; no-op in stack mode
    # because $script:DOCKER_PROJECTS stays empty there).
    foreach ($proj in $script:DOCKER_PROJECTS) {
        try {
            docker compose -p $proj down 2>&1 | Out-Null
            Write-Host "  Docker down: $proj" -ForegroundColor Gray
        } catch {}
    }

    # Phase B (§C): tear down the Swarm stack on exit. `docker stack rm`
    # removes services + the overlay net but NOT the named volumes
    # (brain_data / rowboat_mongo / neo4j_mirofish_data persist — data safe).
    # Next launch re-converges from scratch (~60-120s) but with a clean slate.
    if ($script:SWARM_STACK) {
        try {
            docker stack rm $script:SWARM_STACK 2>&1 | Out-Null
            Write-Host "  Swarm stack removed: $($script:SWARM_STACK) (named volumes preserved)" -ForegroundColor Gray
        } catch {}
    }

    # Kill stale Electron (the app spawns electron.exe via cmd.exe wrapper,
    # so it's not always reachable via $script:PROCESSES).
    taskkill /F /T /IM electron.exe 2>$null | Out-Null

    # Port-based garbage collection — anything still listening on a managed
    # port belongs to us. Mirrors Invoke-PreflightCleanup so a clean exit
    # leaves no orphans even if process tracking missed something.
    if ($CONFIG -and $CONFIG.ports) {
        $managedPorts = @(
            $CONFIG.ports.brain_dashboard, $CONFIG.ports.brain_api,
            $CONFIG.ports.bridge, $CONFIG.ports.la_fungus_api,
            $CONFIG.ports.automation_backend, $CONFIG.ports.media_server,
            $CONFIG.ports.moire_server, $CONFIG.ports.minibook_backend,
            $CONFIG.ports.electron_devtools
        ) | Where-Object { $_ -gt 0 }
        $ourBins = @('python.exe', 'node.exe', 'uvicorn.exe', 'electron.exe', 'npm.exe', 'cmd.exe')
        foreach ($port in $managedPorts) {
            try {
                $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
                foreach ($conn in $owners) {
                    $procPid = $conn.OwningProcess
                    if (-not $procPid -or $procPid -eq 0) { continue }
                    $proc = Get-Process -Id $procPid -ErrorAction SilentlyContinue
                    if (-not $proc) { continue }
                    if ($ourBins -notcontains "$($proc.ProcessName).exe") { continue }
                    & taskkill.exe /F /T /PID $procPid 2>&1 | Out-Null
                    Write-Host "  Reaped $($proc.ProcessName) PID=$procPid (held :$port)" -ForegroundColor DarkGray
                }
            } catch {}
        }
    }

    Write-Host ""
    Write-Host "  All services stopped." -ForegroundColor Green
}

function Invoke-PreflightCleanup {
    <#
    .SYNOPSIS
        Kill zombie Vibemind processes + sockets from a prior crashed run.
    .DESCRIPTION
        Scans managed ports (from CONFIG.ports + hardcoded 8099 eyeTerm) and
        kills any process listening on them whose executable path or command-
        line is rooted in the Vibemind repo. Also force-kills electron.exe
        (the script owns Electron lifecycle) and runs docker compose down for
        every project in CONFIG.docker so containers don't hold stale state.
    #>
    param([object]$Config, [string]$RootPath)
    Write-Host "  Pre-flight cleanup..." -ForegroundColor Cyan

    # --- Ports to free (from CONFIG.ports, filtered to ones this script manages) ---
    $managedPorts = @(
        $Config.ports.brain_dashboard, $Config.ports.brain_api,
        $Config.ports.brain_unified, $Config.ports.brain_memory,
        $Config.ports.bridge, $Config.ports.openfang, $Config.ports.moire_server,
        $Config.ports.electron_devtools, $Config.ports.minibook_backend,
        $Config.ports.minibook_frontend, $Config.ports.mirofish,
        $Config.ports.automation_backend, $Config.ports.automation_frontend,
        $Config.ports.automation_voice,
        $Config.ports.la_fungus_api, $Config.ports.openclaw_gateway,
        $Config.ports.n8n, $Config.ports.agentfarm_server, $Config.ports.agentfarm_ui,
        8099   # eyeTerm (not in config, but always spawned by voice/electron_backend)
    ) | Where-Object { $_ -and $_ -gt 0 } | Sort-Object -Unique

    $killed = @()

    # --- Kill processes listening on those ports (scoped by Vibemind path) ---
    foreach ($port in $managedPorts) {
        try {
            $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            foreach ($c in $conns) {
                $procPid = $c.OwningProcess
                if ($procPid -eq 0 -or $procPid -eq $PID) { continue }
                $proc = Get-Process -Id $procPid -ErrorAction SilentlyContinue
                if (-not $proc) { continue }

                # Identify only vibemind-relevant processes by path/commandline
                $isOurs = $false
                try {
                    $path = $proc.Path
                    if ($path -and $path -like "$RootPath*") { $isOurs = $true }
                } catch {}
                if (-not $isOurs) {
                    # Fallback for python/node where .Path is the runtime, not the script
                    try {
                        $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$procPid" -ErrorAction SilentlyContinue
                        if ($cim -and $cim.CommandLine -and $cim.CommandLine -like "*$RootPath*") {
                            $isOurs = $true
                        }
                    } catch {}
                }
                # Final fallback: if a managed port is held by a python/node/uvicorn
                # process that wasn't matched above, it is almost certainly ours
                # (module-style `python -m uvicorn x.y:app` hides the project path).
                # Only claim ports we explicitly manage, so this stays scoped.
                if (-not $isOurs -and ($proc.ProcessName -match "^(python|node|uvicorn)")) {
                    $isOurs = $true
                }

                if ($isOurs) {
                    $stopErr = $null
                    Stop-Process -Id $procPid -Force -ErrorAction SilentlyContinue -ErrorVariable stopErr
                    # Fallback: taskkill with /T (whole tree) when Stop-Process
                    # fails on processes spawned with elevated rights (uvicorn
                    # workers, MSIX-installed binaries, etc.)
                    Start-Sleep -Milliseconds 100
                    if (Get-Process -Id $procPid -ErrorAction SilentlyContinue) {
                        & taskkill.exe /F /T /PID $procPid 2>&1 | Out-Null
                    }
                    if (Get-Process -Id $procPid -ErrorAction SilentlyContinue) {
                        $killed += "  [WARN] could not kill $($proc.ProcessName) PID=$procPid port=$port (try as Admin)"
                    } else {
                        $killed += "  killed $($proc.ProcessName) PID=$procPid port=$port"
                    }
                }
            }
        } catch {}
    }

    # --- Kill electron.exe (all instances — the script owns Electron lifecycle) ---
    Get-Process -Name "electron" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        $killed += "  killed electron PID=$($_.Id)"
    }

    # --- Kill stale containers from older OpenClaw layout ---
    # coding-engine-openclaw was retired in favor of vibemind-openclaw bedienen
    # both Voice and Coding Engine on :18789. Drop the old container if it
    # somehow came back via cached compose state.
    try {
        $stale = docker ps -aq --filter "name=^/coding-engine-openclaw$" 2>$null
        if ($stale) {
            docker rm -f coding-engine-openclaw 2>&1 | Out-Null
            $killed += "  removed stale coding-engine-openclaw container"
        }
    } catch {}

    # --- Docker compose down for our projects (silent if nothing to down) ---
    # Phase B: ONLY in -Legacy mode. In stack mode this loop was the exact
    # screenshot bug — it `down`s projects the Swarm stack now owns (and
    # errors on composes that no longer exist), fighting the stack. The stack
    # is re-deployed idempotently (Invoke-SwarmStackDeploy reconciles in
    # place), so no per-compose down is needed or wanted there.
    if ($Legacy -and -not $SkipDocker) {
        $dockerProjects = @($Config.docker.PSObject.Properties.Name)
        foreach ($proj in $dockerProjects) {
            $compose = Join-Path $RootPath $Config.docker.$proj
            if (Test-Path $compose) {
                try {
                    docker compose -f $compose -p $proj down --remove-orphans 2>&1 | Out-Null
                } catch {}
            }
        }
        if ($dockerProjects.Count -gt 0) {
            $killed += "  docker compose down for $($dockerProjects.Count) projects"
        }

        # Phase A: the Brain runs as the `vibemind-brain` compose project
        # (docker-compose.brain-core.yml). It's NOT in CONFIG.docker, so down
        # it explicitly — otherwise a container from a prior run keeps :5000
        # and the fresh Brain can't bind. -p alone is enough for `down`.
        try {
            $brainComposeCleanup = Join-Path $RootPath "vibemind-os/brain/the_brain/docker-compose.brain-core.yml"
            if (Test-Path $brainComposeCleanup) {
                docker compose -f $brainComposeCleanup -p vibemind-brain down --remove-orphans 2>&1 | Out-Null
                $killed += "  docker compose down: vibemind-brain"
            }
        } catch {}
    }
    elseif (-not $SkipDocker) {
        # Stack mode: no per-compose down. `docker stack deploy` reconciles
        # existing services in place — tearing them down here would just add
        # a slow re-converge with zero benefit.
        $killed += "  stack mode — skipped per-compose down (stack deploy reconciles)"
    }

    # --- Report ---
    if ($killed.Count -eq 0) {
        Write-Host "    Nothing to clean up (already stopped)." -ForegroundColor DarkGray
    } else {
        $killed | ForEach-Object { Write-Host $_ -ForegroundColor DarkYellow }
    }

    # Brief settle so TIME_WAIT sockets age out a bit
    Start-Sleep -Milliseconds 800
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 0: Pre-flight
# ═══════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    VibeMind Debug Launcher" -ForegroundColor White
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host ""

# Load config
if (-not (Test-Path $script:CONFIG_FILE)) {
    Write-Host "  [ERROR] vibemind.config.json not found." -ForegroundColor Red
    Write-Host "  Run: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}
$CONFIG = Get-Content $script:CONFIG_FILE -Raw | ConvertFrom-Json

# Apply -Modules override
if ($Modules) {
    $selected = $Modules -split ','
    foreach ($prop in $CONFIG.modules.PSObject.Properties) {
        $prop.Value.enabled = $selected -contains $prop.Name
    }
    Write-Host "  Module override: $Modules" -ForegroundColor Yellow
}

# Load root .env
if (Test-Path $script:ROOT_ENV) {
    Get-Content $script:ROOT_ENV | ForEach-Object {
        if ($_ -match '^([A-Z][A-Z0-9_]+)=(.+)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
        }
    }
}

# Pre-flight cleanup: kill zombies from a prior crashed run (ports + docker)
if (-not $SkipCleanup) {
    Invoke-PreflightCleanup -Config $CONFIG -RootPath $ROOT
}

# Validate LLM keys
$hasLLM = $env:OPENROUTER_API_KEY -or $env:OPENAI_API_KEY -or $env:ANTHROPIC_API_KEY
if (-not $hasLLM) {
    Write-Host "  [ERROR] No LLM API key found in .env" -ForegroundColor Red
    exit 1
}

# Optional dependency: ffmpeg (used by Video Studio Live recording + faceswap audio mux).
# Resolution order matches routers/video.py:_resolve_ffmpeg(): FFMPEG_PATH → PATH → common installs.
function Resolve-Ffmpeg {
    if ($env:FFMPEG_PATH -and (Test-Path $env:FFMPEG_PATH)) { return $env:FFMPEG_PATH }
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $home = $env:USERPROFILE
    $candidates = @(
        "C:\ffmpeg\bin\ffmpeg.exe",
        "C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        "C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        (Join-Path $home "scoop\shims\ffmpeg.exe"),
        (Join-Path $home "AppData\Local\Programs\ffmpeg\bin\ffmpeg.exe"),
        (Join-Path $home "AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe")
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    return $null
}
$ffmpegBin = Resolve-Ffmpeg
if ($ffmpegBin) {
    Write-Host "  ffmpeg: $ffmpegBin" -ForegroundColor DarkGreen
    # Propagate to children so backend resolver picks the same binary even
    # when PATH ordering is weird (e.g. pyenv shims winning over real ffmpeg).
    if (-not $env:FFMPEG_PATH) { $env:FFMPEG_PATH = $ffmpegBin }
} else {
    Write-Host "  [WARN] ffmpeg not found — Video Studio Live recording + audio mux will be disabled." -ForegroundColor Yellow
    Write-Host "         Install: 'winget install ffmpeg' or 'scoop install ffmpeg'" -ForegroundColor DarkYellow
    Write-Host "         Or set FFMPEG_PATH=<absolute path to ffmpeg.exe> in .env" -ForegroundColor DarkYellow
}

# Force unbuffered Python stdout so child venv processes flush log lines live
[Environment]::SetEnvironmentVariable("PYTHONUNBUFFERED", "1", "Process")

# Create log dirs
$logSubDirs = @("voice", "brain", "automation_ui", "la_fungus", "bridge", "coding_engine", "openfang", "marketing")
foreach ($d in $logSubDirs) {
    $p = Join-Path $script:LOG_DIR $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# Rotate prior non-empty logs → .prev so each run starts fresh but history stays
Get-ChildItem -Path $script:LOG_DIR -Recurse -Filter "*.log" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Length -gt 0) {
        $prev = "$($_.FullName).prev"
        try {
            if (Test-Path $prev) { Remove-Item $prev -Force -ErrorAction SilentlyContinue }
            Move-Item -Path $_.FullName -Destination $prev -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

# Reset the spawn registry so it reflects only THIS launcher session.
# vm-procs.ps1 reads it to know which PIDs the launcher owns.
try {
    if (Test-Path $script:REGISTRY_FILE) {
        Move-Item -Path $script:REGISTRY_FILE -Destination "$($script:REGISTRY_FILE).prev" -Force -ErrorAction SilentlyContinue
    }
} catch {}

# Port conflict check
Write-Host "  Checking for port conflicts..." -ForegroundColor Gray
$conflicts = @()
foreach ($portProp in $CONFIG.ports.PSObject.Properties) {
    $port = $portProp.Value
    $mod = $portProp.Name
    # Only check ports for enabled modules
    $line = netstat -ano 2>$null | Select-String ":${port}\s" | Select-String "LISTENING" | Select-Object -First 1
    if ($line) {
        $parts = ($line.Line.Trim() -split '\s+')
        $procId = $parts[-1]
        $procName = try { (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName } catch { "unknown" }
        $conflicts += @{ Port = $port; Name = $mod; PID = $procId; Process = $procName }
    }
}
if ($conflicts.Count -gt 0) {
    Write-Host "  [WARN] Port conflicts detected:" -ForegroundColor Yellow
    foreach ($c in $conflicts) {
        Write-Host "    :$($c.Port) ($($c.Name)) used by $($c.Process) [PID $($c.PID)]" -ForegroundColor Yellow
    }
}

# Enabled modules summary
$enabled = @()
foreach ($prop in $CONFIG.modules.PSObject.Properties) { if ($prop.Value.enabled) { $enabled += $prop.Name } }
Write-Host "  Modules: $($enabled -join ', ')" -ForegroundColor White
Write-Host ""

if ($DryRun) {
    Write-Host "  [DRY RUN] Would start the above modules. Exiting." -ForegroundColor Yellow
    exit 0
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 0.5: Ollama (host-side, needed by Mirofish + Brain LLM-clones)
# ═══════════════════════════════════════════════════════════════════
# Ollama is a separate process — not Docker — and Mirofish container points
# to host.docker.internal:11434. If it's not running, mirofish-app fails its
# embedding calls and discourse stays empty. Auto-start if missing.
$ollamaUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $ollamaUp = $true }
} catch {}

if ($ollamaUp) {
    Write-Host "  Phase 0.5: Ollama already running on :11434" -ForegroundColor Green
} else {
    Write-Host "  Phase 0.5: Ollama not running -starting it..." -ForegroundColor Cyan
    $ollamaBin = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollamaBin)) {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { $ollamaBin = $cmd.Source }
    }
    if (Test-Path $ollamaBin) {
        $ollamaLog = Join-Path $env:TEMP "ollama-vibemind.log"
        $ollamaErr = Join-Path $env:TEMP "ollama-vibemind.err"
        $ollamaProc = Start-Process -FilePath $ollamaBin -ArgumentList "serve" `
            -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $ollamaLog -RedirectStandardError $ollamaErr
        if ($ollamaProc) {
            Register-SpawnedProcess -Name "ollama" -ProcId $ollamaProc.Id `
                -Command "$ollamaBin serve" -Port 11434 -Runtime "native"
        }
        # Wait up to 15s for it to be reachable so Mirofish container starts cleanly
        $deadline = (Get-Date).AddSeconds(15)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
            try {
                $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/version" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
                if ($r.StatusCode -eq 200) { $ollamaUp = $true; break }
            } catch {}
        }
        if ($ollamaUp) {
            Write-Host "    Ollama up on :11434 (logs: $ollamaLog)" -ForegroundColor Green
        } else {
            Write-Host "    [WARN] Ollama did not reach :11434 within 15s -Mirofish embeddings may fail" -ForegroundColor Yellow
        }
    } else {
        Write-Host "    [WARN] ollama.exe not found in PATH or %LOCALAPPDATA%\Programs\Ollama -skipping" -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 1: Docker Infrastructure
# ═══════════════════════════════════════════════════════════════════
if (-not $SkipDocker) {
    Write-Host "  Phase 1: Starting Docker services..." -ForegroundColor Cyan

    # Check Docker is running
    $dockerOk = $false
    try { docker info 2>&1 | Out-Null; $dockerOk = $true } catch {}
    if (-not $dockerOk) {
        Write-Host "  [WARN] Docker not running -skipping Docker services" -ForegroundColor Yellow
    } else {
        $composeJobs = @()

        # ── Minibook: NATIVE EXCEPTION (§E) — runs in BOTH modes.
        # Minibook is intentionally NOT in the Swarm stack yet (external/
        # minibook build context is empty — blocked, see stack-file header).
        # Until it can join the stack it stays a per-compose start even in
        # default stack mode, so its functionality is not lost.
        if ($CONFIG.modules.voice.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.voice_minibook
            if (Test-Path $f) {
                Write-Host "    Starting Minibook (native exception — not in stack)..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    docker compose -f $file --project-name vibemind-minibook up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-minibook"
            }
        }

        # ── Stack-owned services: ONLY in -Legacy mode. In default stack
        # mode MiroFish/Coding/Automation-Qdrant/n8n/AgentFarm/Rowboat are
        # all provided by the Swarm stack (Invoke-SwarmStackDeploy below);
        # starting the per-compose copies here would collide on ports
        # (the exact screenshot bug). -Legacy restores the old behaviour.
        if ($Legacy) {
            # Voice: MiroFish (remapped to 5101)
            $f2 = Join-Path $ROOT $CONFIG.docker.voice_mirofish
            if ($CONFIG.modules.voice.enabled -and (Test-Path $f2)) {
                Write-Host "    Starting MiroFish (:5101)..." -ForegroundColor Gray
                $envFile = Join-Path $ROOT ".env"
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file, $envFile)
                    Set-Location $root
                    $env:MIROFISH_HOST_PORT = "5101"
                    # --env-file ensures MIROFISH_LLM_API_KEY etc. reach the
                    # compose context (else mirofish-app crashes on missing key).
                    if (Test-Path $envFile) {
                        docker compose --env-file $envFile -f $file --project-name vibemind-mirofish up -d 2>&1
                    } else {
                        docker compose -f $file --project-name vibemind-mirofish up -d 2>&1
                    }
                } -ArgumentList $ROOT, $f2, $envFile
                $script:DOCKER_PROJECTS += "vibemind-mirofish"
            }

        # Coding Engine
        if ($CONFIG.modules.coding_engine.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.coding_engine
            if (Test-Path $f) {
                Write-Host "    Starting Coding Engine stack..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    docker compose -f $file --project-name vibemind-coding up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-coding"
            }
        }
        }  # end if ($Legacy) — stack-owned per-compose starts (part 1)

        # Brain — no longer started via Docker (no image built).
        # Brain Dashboard (port 5000) is started as a venv Python process
        # in Phase 3 alongside Brain API (5001). Swarm runs inside the unified
        # brain_server.py (via web/routers/swarm.py) — no separate process needed.

        # ── OpenFang: NATIVE, runs in BOTH modes (§B). It's a pre-built Rust
        # binary, NOT in the Swarm stack — so it must start regardless of
        # -Legacy. Pulled out of the $Legacy gate (single source, no dup).
        # OpenFang — start the pre-built binary directly instead of Docker.
        # Building the Rust project in Docker takes 10-30 minutes; the
        # release binary at target/release/openfang.exe is already compiled.
        if ($CONFIG.modules.openfang.enabled) {
            $ofPort = $CONFIG.ports.openfang
            # Check if OpenFang is already running
            $ofAlready = Test-HttpHealth -Url "http://localhost:${ofPort}/api/health" -Timeout 2
            if ($ofAlready) {
                Write-Host "    OpenFang already running (:${ofPort})" -ForegroundColor Gray
            } else {
                $ofDir = Join-Path $ROOT "vibemind-os/openfang"
                $ofBin = Join-Path $ofDir "target/release/openfang.exe"
                $ofConfig = Join-Path $ofDir "openfang.vibemind.toml"
                if (Test-Path $ofBin) {
                    Write-Host "    Starting OpenFang (native binary :${ofPort})..." -ForegroundColor Gray
                    # OpenFang self-daemonizes — the parent process exits immediately.
                    # Use Start-Process (fire-and-forget) then health-check to confirm.
                    $ofStartArgs = "start"
                    if (Test-Path $ofConfig) { $ofStartArgs += " --config `"$ofConfig`"" }
                    $ofLog = Join-Path $script:LOG_DIR "openfang/openfang.log"
                    $ofErr = Join-Path $script:LOG_DIR "openfang/openfang.err.log"
                    $ofScripts = Join-Path $ROOT "scripts"
                    $ofOriginalPath = $env:PATH
                    $ofOriginalWrapperDir = $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR
                    try {
                        $env:PATH = "$ofScripts;$ofOriginalPath"
                        $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofScripts
                        Start-Process -FilePath $ofBin -ArgumentList $ofStartArgs -WorkingDirectory $ofDir -WindowStyle Hidden -RedirectStandardOutput $ofLog -RedirectStandardError $ofErr
                    } finally {
                        $env:PATH = $ofOriginalPath
                        if ($null -eq $ofOriginalWrapperDir) { Remove-Item Env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR -ErrorAction SilentlyContinue }
                        else { $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofOriginalWrapperDir }
                    }
                    # Wait for daemon to boot (up to 10s)
                    $ofReady = $false
                    for ($i = 0; $i -lt 10; $i++) {
                        Start-Sleep -Seconds 1
                        $ofReady = Test-HttpHealth -Url "http://localhost:${ofPort}/api/health" -Timeout 2
                        if ($ofReady) { break }
                    }
                    if ($ofReady) {
                        Write-Host "    OpenFang ready (:${ofPort})" -ForegroundColor Green
                        # OpenFang self-daemonized — the spawn PID is dead. Record
                        # the real listener so vm-procs.ps1 can resolve+kill it by port.
                        $ofPid = 0
                        try {
                            $ofConn = Get-NetTCPConnection -LocalPort $ofPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
                            if ($ofConn) { $ofPid = [int]$ofConn.OwningProcess }
                        } catch {}
                        Register-SpawnedProcess -Name "openfang" -ProcId $ofPid `
                            -Command "$ofBin $ofStartArgs" -Port $ofPort -Runtime "native"
                    } else {
                        Write-Host "    [WARN] OpenFang started but health check failed on :${ofPort}" -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "    [WARN] OpenFang binary not found at $ofBin — run 'cargo build --release' in vibemind-os/openfang/" -ForegroundColor Yellow
                }
            }
        }

        # ── Stack-owned per-compose starts (part 2): Automation-Qdrant /
        # n8n / AgentFarm / Rowboat — again ONLY in -Legacy (all in the
        # Swarm stack otherwise). Gate re-opened here after the
        # unconditional OpenFang block.
        if ($Legacy) {
        # Automation UI (Qdrant)
        if ($CONFIG.modules.automation_ui.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.automation_ui
            if (Test-Path $f) {
                Write-Host "    Starting Automation UI (Qdrant)..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    docker compose -f $file --project-name vibemind-automation up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-automation"
            }
        }

        # n8n Workflow Builder (port 15678)
        if ($CONFIG.modules.n8n.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.n8n
            if (Test-Path $f) {
                Write-Host "    Starting n8n (:$($CONFIG.ports.n8n))..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    docker compose -f $file --project-name vibemind-n8n up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-n8n"
            }
        }

        # AgentFarm / AutoGen (ports 8080, 3457)
        if ($CONFIG.modules.agentfarm.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.agentfarm
            if (Test-Path $f) {
                Write-Host "    Starting AgentFarm (:$($CONFIG.ports.agentfarm_server))..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    docker compose -f $file --project-name vibemind-agentfarm up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-agentfarm"
            }
        }

        # Rowboat Knowledge Graph (port 3100)
        if ($CONFIG.modules.rowboat.enabled) {
            $f = Join-Path $ROOT $CONFIG.docker.rowboat
            if (Test-Path $f) {
                Write-Host "    Starting Rowboat (:$($CONFIG.ports.rowboat))..." -ForegroundColor Gray
                $composeJobs += Start-Job -ScriptBlock {
                    param($root, $file)
                    Set-Location $root
                    $env:PORT = "3100"
                    docker compose -f $file --project-name vibemind-rowboat up -d 2>&1
                } -ArgumentList $ROOT, $f
                $script:DOCKER_PROJECTS += "vibemind-rowboat"
            }
        }
        }  # end if ($Legacy) — stack-owned per-compose starts (part 2)

        # ── Default (NOT -Legacy): bring up the unified Swarm stack. This
        # replaces every stack-owned per-compose start above. Minibook +
        # OpenFang already started unconditionally; the stack provides
        # qdrant/brain-core/media/n8n/rowboat×5/mirofish+neo4j.
        if (-not $Legacy) {
            Invoke-SwarmStackDeploy
        }

        # Wait for all compose jobs (only Minibook in stack mode; the full
        # set in -Legacy). No-op when $composeJobs is empty.
        if ($composeJobs.Count -gt 0) {
            Write-Host "    Waiting for Docker containers..." -ForegroundColor Gray
            $composeJobs | Wait-Job -Timeout 60 | Out-Null
            $composeJobs | ForEach-Object { Receive-Job $_ 2>&1 | Out-Null; Remove-Job $_ -Force }
        }

        # Phase 2 prewarm probes removed — Phase 6 owns all readiness checks
        # against the same $services table, so prewarming here only created
        # cache drift when URLs disagreed. Phase 6 jobs run in parallel.
        $script:HealthJobs = @{}
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 3: Python Venv Services
# ═══════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  Phase 3: Starting Python services..." -ForegroundColor Cyan

# Consolidated venv: all Py 3.11 services (bridge, brain, la-fungus, automation_ui)
# share one venv at the project root. voice has its own .venv312 (Py 3.12 constraint).
$sharedVenv = Join-Path $ROOT $CONFIG.venvs.shared

# Brain API (venv -port 5001, 5002)
if ($CONFIG.modules.brain.enabled) {
    $brainDir = Join-Path $ROOT $CONFIG.modules.brain.path
    $brainVenv = $sharedVenv

    # Dashboard / Main Brain Server (5000) — EventRoutingHead + SBERT + SpaceRoutingHead
    # This is the critical service that handles /api/cortex/classify and /api/cortex/route.
    # Takes ~35s to start due to SBERT model loading + RadialNetwork init.
    #
    # Phase A: containerised by default. The container runs `start_server.py 5000`
    # (passes the app OBJECT to uvicorn — no import-string fork, so NO pyenv-3.11
    # double-spawn). -BrainNative keeps the legacy venv path for dev velocity.
    $brainPort = $CONFIG.ports.brain_dashboard
    if ((-not $Legacy) -and (-not $BrainNative) -and (-not $SkipDocker)) {
        # Phase B / §D: default STACK mode — the Swarm stack's `brain-core`
        # service already owns :5000. Starting the vibemind-brain compose
        # here would collide on :5000 (the exact class of bug this whole
        # integration removes). So: do NOT start Brain here in stack mode;
        # Invoke-SwarmStackDeploy (Phase 1) brought brain-core up.
        # -BrainNative still gives venv, -Legacy still gives the compose.
        Write-Host "    Brain Dashboard: provided by Swarm stack (brain-core :$brainPort) — not started here" -ForegroundColor Gray
        Register-SpawnedProcess -Name "brain_dashboard" -ProcId 0 `
            -Command "swarm stack vibemind (brain-core)" `
            -Port $brainPort -Runtime "container"
    }
    elseif ($BrainNative -or $SkipDocker) {
        # Legacy venv path (also used when -SkipDocker since the container needs Docker).
        Start-VenvPython -Name "brain_dashboard" -VenvPath $brainVenv -WorkDir $brainDir `
            -ScriptArgs "start_server.py $brainPort" `
            -LogFile (Join-Path $script:LOG_DIR "brain/dashboard.log")
        Write-Host "    Brain Dashboard starting (venv :$brainPort) — SBERT loading (~35s)..." -ForegroundColor Gray
    } else {
        # -Legacy: the standalone vibemind-brain compose (Phase A path).
        $brainCompose = Join-Path $brainDir "docker-compose.brain-core.yml"
        if (Test-Path $brainCompose) {
            Write-Host "    Brain Dashboard: docker compose -p vibemind-brain up -d (:$brainPort)..." -ForegroundColor Gray
            $bcJob = Start-Job -ScriptBlock {
                param($root, $compose, $envFile)
                Set-Location $root
                docker compose --env-file $envFile -f $compose --project-name vibemind-brain up -d 2>&1
            } -ArgumentList $brainDir, $brainCompose, $script:ROOT_ENV
            $bcJob | Wait-Job -Timeout 180 | Out-Null
            Receive-Job $bcJob 2>&1 | Out-Null
            Remove-Job $bcJob -Force -ErrorAction SilentlyContinue
            $script:DOCKER_PROJECTS += "vibemind-brain"
            # Record the container so vm-procs.ps1 can track it (PID 0 = resolve
            # by port; the registry consumer treats 0 as "find live :port owner").
            Register-SpawnedProcess -Name "brain_dashboard" -ProcId 0 `
                -Command "docker compose -p vibemind-brain (brain-core)" `
                -Port $brainPort -Runtime "container"
            Write-Host "    Brain Dashboard container starting — SBERT loading (~35s)..." -ForegroundColor Gray
        } else {
            Write-Host "    [WARN] $brainCompose not found — falling back to venv" -ForegroundColor Yellow
            Start-VenvPython -Name "brain_dashboard" -VenvPath $brainVenv -WorkDir $brainDir `
                -ScriptArgs "start_server.py $brainPort" `
                -LogFile (Join-Path $script:LOG_DIR "brain/dashboard.log")
        }
    }

    # API Server (5001)
    Start-VenvPython -Name "brain_api" -VenvPath $brainVenv -WorkDir $brainDir `
        -ScriptArgs "production/api_server.py" `
        -LogFile (Join-Path $script:LOG_DIR "brain/api_server.log")
    Write-Host "    Brain API started (:$($CONFIG.ports.brain_api))" -ForegroundColor Gray
}

# La-Fungus Search (port 8011)
if ($CONFIG.modules.la_fungus.enabled) {
    $lfDir = Join-Path $ROOT $CONFIG.modules.la_fungus.path
    $lfVenv = $sharedVenv
    Start-VenvPython -Name "la_fungus" -VenvPath $lfVenv -WorkDir $lfDir `
        -ScriptArgs "-m uvicorn embeddinggemma.realtime.server:app --port $($CONFIG.ports.la_fungus_api) --host 127.0.0.1" `
        -LogFile (Join-Path $script:LOG_DIR "la_fungus/search_api.log") `
        -ExtraEnv @{ PYTHONPATH = (Join-Path $lfDir "src") }
    Write-Host "    La-Fungus Search started (:$($CONFIG.ports.la_fungus_api))" -ForegroundColor Gray

    # fungus-search MCP server (HTTP/SSE on :8412) — what Claude Code's MCP
    # (.mcp.json type:sse -> :8412/sse) connects to. MUST run persistent: stdio
    # mode cold-starts the 50s index+model load on EVERY tool call (Claude spawns
    # a fresh stdio proc per call) and never hits the loaded instance. The HTTP
    # server loads the 56k-doc index ONCE on the GPU and stays up. Kept in sync
    # with vibemind-start.ps1 Phase 3 'fungus_mcp_http'. See memory
    # feedback_fungus_index_corruption.
    Start-VenvPython -Name "fungus_mcp_http" -VenvPath $lfVenv -WorkDir $lfDir `
        -ScriptArgs "mcp_server.py --http 8412" `
        -LogFile (Join-Path $script:LOG_DIR "la_fungus/mcp_http.log") `
        -ExtraEnv @{
            FUNGUS_DEVICE      = "cuda"
            FUNGUS_CODEBASE    = (Join-Path $ROOT "vibemind-os")
            FUNGUS_EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
        }
    Write-Host "    Fungus MCP HTTP server started (:8412/sse)" -ForegroundColor Gray
}

# Bridge (port 5100 -depends on Brain + OpenFang)
if ($CONFIG.modules.bridge.enabled) {
    $bridgeDir = Join-Path $ROOT "vibemind-os/bridge"
    $bridgeVenv = $sharedVenv
    $bridgeEnv = @{
        BRAIN_URL = "http://localhost:$($CONFIG.ports.brain_dashboard)"
        OPENFANG_URL = "http://localhost:$($CONFIG.ports.openfang)"
        PYTHONPATH = (Join-Path $bridgeDir "src")
    }
    Start-VenvPython -Name "bridge" -VenvPath $bridgeVenv -WorkDir $bridgeDir `
        -ScriptArgs "-m uvicorn bridge.main:app --port $($CONFIG.ports.bridge) --host 127.0.0.1" `
        -LogFile (Join-Path $script:LOG_DIR "bridge/bridge.log") `
        -ExtraEnv $bridgeEnv
    Write-Host "    Bridge started (:$($CONFIG.ports.bridge))" -ForegroundColor Gray
}

# Automation UI Backend (port 8007)
if ($CONFIG.modules.automation_ui.enabled) {
    $auDir = Join-Path $ROOT $CONFIG.modules.automation_ui.path
    $auBackend = Join-Path $auDir "backend"
    if (Test-Path (Join-Path $auBackend "server.py")) {
        Start-VenvPython -Name "automation_backend" -VenvPath $sharedVenv -WorkDir $auBackend `
            -ScriptArgs "server.py" `
            -LogFile (Join-Path $script:LOG_DIR "automation_ui/backend.log") `
            -ExtraEnv @{ PORT = "$($CONFIG.ports.automation_backend)" }
        Write-Host "    Automation Backend started (:$($CONFIG.ports.automation_backend))" -ForegroundColor Gray
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 4: Node Services
# ═══════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  Phase 4: Starting Node services..." -ForegroundColor Cyan

# MoireServer (port 8766)
# The Moire tracker source has historically lived in several locations.
# Canonical is now the vibemind-os submodule (spaces/desktop/Automation_ui);
# the project-root path is kept as a legacy fallback.
if ($CONFIG.modules.voice.enabled) {
    $moireCandidates = @(
        (Join-Path $ROOT "vibemind-os/spaces/desktop/Automation_ui/moire_tracker"),
        (Join-Path $ROOT "Automation_ui/moire_tracker"),
        (Join-Path $ROOT "MoireTracker_v2"),
        (Join-Path $ROOT "vibemind-os/MoireTracker_v2")
    )
    $moireRoot = $moireCandidates | Where-Object { Test-Path (Join-Path $_ "package.json") } | Select-Object -First 1
    if ($moireRoot) {
        if (-not (Test-Port $CONFIG.ports.moire_server)) {
            Start-ServiceProcess -Name "moire_server" -WorkDir $moireRoot `
                -Command "npm" -CmdArgs "start" `
                -LogFile (Join-Path $script:LOG_DIR "voice/moire_server.log")
            Write-Host "    MoireServer started (:$($CONFIG.ports.moire_server))" -ForegroundColor Gray
        } else {
            Write-Host "    MoireServer already running (:$($CONFIG.ports.moire_server))" -ForegroundColor Gray
        }
    } else {
        Write-Host "    [WARN] moire_tracker not found in any known location -skipping MoireServer" -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 4.5: Marketing-Sync Workers (DB <-> Vault Markdown)
# ═══════════════════════════════════════════════════════════════════
# Two long-running Python sidecars that keep Supabase marketing.* in
# sync with ~/.rowboat/knowledge/Marketing/People/ markdown files.
#
# Worker A (worker_db_to_fs.py): polls marketing.sync_outbox every ~30s,
#   renders affected handles as Markdown, atomic-writes to the vault.
#   Dependencies: supabase-db reachable via `docker exec` (Phase 1 stack).
#
# Worker B (worker_fs_to_db.py): watchdog observer on the vault folder.
#   On file DELETE, propagates DELETE FROM marketing.accounts using a
#   session-scoped GUC `marketing.sync_origin = 'fs'` so the trigger does
#   not emit a loop-back event. File MODIFY is logged but not propagated
#   (Phase 1 policy: body section is file-only, frontmatter is DB-source).
#
# Both workers share a content-hash store at
# ~/.rowboat/knowledge/Marketing/.sync_hashes.json for echo prevention.
# Tracked as `marketing_sync_a` and `marketing_sync_b` so the dashboard's
# Verify=process rows turn green when they're alive.
#
# Sync system status: Foundations Schicht 2 done (2026-06-02), 23/23 tests.
# Reference: spaces/marketing/sync/README.md
# marketing module may not be in vibemind.config.json yet — default to on
# unless an explicit `marketing.enabled = false` exists.
$marketingEnabled = $true
if ($CONFIG.modules.PSObject.Properties.Name -contains 'marketing') {
    $marketingEnabled = [bool]$CONFIG.modules.marketing.enabled
}
if ($marketingEnabled) {
    Write-Host ""
    Write-Host "  Phase 4.5: Starting Marketing-Sync Workers..." -ForegroundColor Cyan

    $syncWorkerA = Join-Path $ROOT "spaces/marketing/sync/worker_db_to_fs.py"
    $syncWorkerB = Join-Path $ROOT "spaces/marketing/sync/worker_fs_to_db.py"

    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $syncWorkerA) -and (Test-Path $syncWorkerB)) {
        # Worker A — DB to FS
        Start-VenvPython -Name "marketing_sync_a" -VenvPath $sharedVenv -WorkDir $ROOT `
            -ScriptArgs "-u -m spaces.marketing.sync.worker_db_to_fs" `
            -LogFile (Join-Path $script:LOG_DIR "marketing/worker_db_to_fs.log") `
            -ExtraEnv @{
                PYTHONUNBUFFERED = "1"
                PYTHONIOENCODING = "utf-8"
            }
        Write-Host "    Marketing Sync A (DB->FS) started" -ForegroundColor Gray

        # Worker B — FS to DB
        Start-VenvPython -Name "marketing_sync_b" -VenvPath $sharedVenv -WorkDir $ROOT `
            -ScriptArgs "-u -m spaces.marketing.sync.worker_fs_to_db" `
            -LogFile (Join-Path $script:LOG_DIR "marketing/worker_fs_to_db.log") `
            -ExtraEnv @{
                PYTHONUNBUFFERED = "1"
                PYTHONIOENCODING = "utf-8"
            }
        Write-Host "    Marketing Sync B (FS->DB) started" -ForegroundColor Gray
    } else {
        Write-Host "    [SKIP] marketing-sync workers not found (spaces/marketing/sync/) -skipping" -ForegroundColor Yellow
    }

    # Marketing Runner — standalone Redis-stream consumer for marketing.*
    # events. Sidesteps the voice-swarm submodule symlink problem. See
    # spaces/marketing/agents/marketing_agent.py for the CUT-OVER RULE.
    $marketingRunner = Join-Path $ROOT "spaces/marketing/agents/runner.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $marketingRunner)) {
        Start-VenvPython -Name "marketing_runner" -VenvPath $sharedVenv -WorkDir $ROOT `
            -ScriptArgs "-u -m spaces.marketing.agents.runner" `
            -LogFile (Join-Path $script:LOG_DIR "marketing/runner.log") `
            -ExtraEnv @{
                PYTHONUNBUFFERED = "1"
                PYTHONIOENCODING = "utf-8"
                REDIS_URL = "redis://localhost:6379/0"
            }
        Write-Host "    Marketing Runner (events:tasks:marketing) started" -ForegroundColor Gray
    } else {
        Write-Host "    [SKIP] marketing-runner not found (spaces/marketing/agents/runner.py)" -ForegroundColor Yellow
    }

    # Marketing HTTP — Phase-1 read-only API + static mockup serve on 127.0.0.1:5510.
    $marketingHttp = Join-Path $ROOT "spaces/marketing/api/server.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $marketingHttp)) {
        Start-VenvPython -Name "marketing_http" -VenvPath $sharedVenv -WorkDir $ROOT `
            -ScriptArgs "-u -m spaces.marketing.api.server" `
            -LogFile (Join-Path $script:LOG_DIR "marketing/http.log") `
            -ExtraEnv @{
                PYTHONUNBUFFERED = "1"
                PYTHONIOENCODING = "utf-8"
                MARKETING_HTTP_PORT = "5510"
                MARKETING_HTTP_BIND = "127.0.0.1"
            }
        Write-Host "    Marketing HTTP (http://127.0.0.1:5510/mockup/) started" -ForegroundColor Gray
    } else {
        Write-Host "    [SKIP] marketing-api not found (spaces/marketing/api/server.py)" -ForegroundColor Yellow
    }

    # Marketing Webhook-Delivery Worker (Schicht 5.3) -- drains
    # marketing.webhook_events + fans out signed POSTs to configured
    # subscriptions. Polls every 5s. Lifecycle events (sent / bounce /
    # open / click / unsubscribe / reply) land here from the send-workers
    # + tracking-routes. Without this process, the webhook-bus accumulates
    # events but never delivers them.
    $marketingWebhookWorker = Join-Path $ROOT "spaces/marketing/workers/webhook_delivery.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $marketingWebhookWorker)) {
        Start-VenvPython -Name "marketing_webhook_delivery" -VenvPath $sharedVenv -WorkDir $ROOT `
            -ScriptArgs "-u -m spaces.marketing.workers.webhook_delivery" `
            -LogFile (Join-Path $script:LOG_DIR "marketing/webhook_delivery.log") `
            -ExtraEnv @{
                PYTHONUNBUFFERED = "1"
                PYTHONIOENCODING = "utf-8"
                WEBHOOK_DELIVERY_POLL_INTERVAL_S = "5"
            }
        Write-Host "    Marketing Webhook Delivery (webhook_events -> subscriptions) started" -ForegroundColor Gray
    } else {
        Write-Host "    [SKIP] webhook-delivery worker not found (spaces/marketing/workers/webhook_delivery.py)" -ForegroundColor Yellow
    }

    # Bubble-Pipeline Sidecars (Schicht 8.0) — three portless polling loops.
    # All three are idempotent + crash-safe (re-pick on restart) BUT must not
    # run twice in parallel (double-poll = double LLM cost / double fan-out).
    # They hold no port, so Invoke-PreflightCleanup cannot reap survivors of a
    # crashed session — hence the Test-WorkerCmdlineAlive guard per worker.

    # Bubble Predict Runner -- post_draft bubbles (status=predicting) ->
    # Mirofish persona-sim -> mirofish_score + status ready_to_post.
    $bubblePredictRunner = Join-Path $ROOT "spaces/marketing/workers/bubble_predict_runner.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $bubblePredictRunner)) {
        if (Test-WorkerCmdlineAlive -Pattern "spaces.marketing.workers.bubble_predict_runner") {
            Write-Host "    Bubble Predict Runner already running -skipping (idempotent)" -ForegroundColor Gray
        } else {
            Start-VenvPython -Name "bubble_predict_runner" -VenvPath $sharedVenv -WorkDir $ROOT `
                -ScriptArgs "-u -m spaces.marketing.workers.bubble_predict_runner" `
                -LogFile (Join-Path $script:LOG_DIR "marketing/bubble_predict_runner.log") `
                -ExtraEnv @{
                    PYTHONUNBUFFERED = "1"
                    PYTHONIOENCODING = "utf-8"
                }
            Write-Host "    Bubble Predict Runner (predicting -> Mirofish -> ready_to_post) started" -ForegroundColor Gray
        }
    } else {
        Write-Host "    [SKIP] bubble-predict runner not found (spaces/marketing/workers/bubble_predict_runner.py)" -ForegroundColor Yellow
    }

    # Bubble Classifier Runner -- unclassified top-level bubbles ->
    # gpt-4o-mini assigns category/color/channels. OPENAI_API_KEY comes from
    # the worker's own repo-.env fallback-loader — no key material here.
    $bubbleClassifierRunner = Join-Path $ROOT "spaces/marketing/workers/bubble_classifier_runner.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $bubbleClassifierRunner)) {
        if (Test-WorkerCmdlineAlive -Pattern "spaces.marketing.workers.bubble_classifier_runner") {
            Write-Host "    Bubble Classifier already running -skipping (idempotent)" -ForegroundColor Gray
        } else {
            Start-VenvPython -Name "bubble_classifier_runner" -VenvPath $sharedVenv -WorkDir $ROOT `
                -ScriptArgs "-u -m spaces.marketing.workers.bubble_classifier_runner" `
                -LogFile (Join-Path $script:LOG_DIR "marketing/bubble_classifier_runner.log") `
                -ExtraEnv @{
                    PYTHONUNBUFFERED = "1"
                    PYTHONIOENCODING = "utf-8"
                }
            Write-Host "    Bubble Classifier (unclassified -> gpt-4o-mini category) started" -ForegroundColor Gray
        }
    } else {
        Write-Host "    [SKIP] bubble-classifier runner not found (spaces/marketing/workers/bubble_classifier_runner.py)" -ForegroundColor Yellow
    }

    # Bubble Dispatcher -- classified marketing bubbles -> one
    # broadcast_proposal per channel + approval-request against the
    # Marketing-API :5510. MARKETING_PROPOSAL_API_KEY comes from the worker's
    # own repo-.env fallback-loader — no key material here.
    $bubbleDispatcher = Join-Path $ROOT "spaces/marketing/workers/bubble_dispatcher.py"
    if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $bubbleDispatcher)) {
        if (Test-WorkerCmdlineAlive -Pattern "spaces.marketing.workers.bubble_dispatcher") {
            Write-Host "    Bubble Dispatcher already running -skipping (idempotent)" -ForegroundColor Gray
        } else {
            Start-VenvPython -Name "bubble_dispatcher" -VenvPath $sharedVenv -WorkDir $ROOT `
                -ScriptArgs "-u -m spaces.marketing.workers.bubble_dispatcher" `
                -LogFile (Join-Path $script:LOG_DIR "marketing/bubble_dispatcher.log") `
                -ExtraEnv @{
                    PYTHONUNBUFFERED = "1"
                    PYTHONIOENCODING = "utf-8"
                }
            Write-Host "    Bubble Dispatcher (classified -> broadcast_proposals + approval) started" -ForegroundColor Gray
        }
    } else {
        Write-Host "    [SKIP] bubble-dispatcher not found (spaces/marketing/workers/bubble_dispatcher.py)" -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 5: Electron + Debug Agent
# ═══════════════════════════════════════════════════════════════════
if ($CONFIG.modules.voice.enabled) {
    Write-Host ""
    Write-Host "  Phase 5: Starting Voice (Electron)..." -ForegroundColor Cyan

    $voiceDir = Join-Path $ROOT $CONFIG.modules.voice.path
    $electronExe = Join-Path $voiceDir "electron-app/node_modules/electron/dist/electron.exe"

    if (Test-Path $electronExe) {
        # Stale electron.exe already killed in Phase 0 Invoke-PreflightCleanup

        # CRITICAL: Unset ELECTRON_RUN_AS_NODE (set by Claude Code IDE).
        # Without this, Electron runs as plain Node.js and any Electron flag
        # like --remote-debugging-port becomes "bad option" because Node.js
        # doesn't know it. PowerShell's $env: clear doesn't always propagate
        # to child processes started via Start-Process, so we use cmd /c with
        # an explicit "set ELECTRON_RUN_AS_NODE=" to guarantee the clear.
        $electronDir = Join-Path $voiceDir "electron-app"
        $debugPort = $CONFIG.ports.electron_devtools
        $electronLog = Join-Path $script:LOG_DIR "voice/electron.log"
        $electronErr = Join-Path $script:LOG_DIR "voice/electron.err.log"
        # Phase A4: when Brain runs as the container (NOT -BrainNative / not
        # -SkipDocker), tell Electron NOT to spawn its own competing venv Brain
        # on :5000 (main.js honours SKIP_BRAIN_SPAWN). Same `set VAR=&` chain
        # as the ELECTRON_RUN_AS_NODE clear so it reaches the child env.
        $brainSkipPrefix = ""
        if (-not $BrainNative -and -not $SkipDocker) {
            $brainSkipPrefix = "set SKIP_BRAIN_SPAWN=1& set BRAIN_PORT=$($CONFIG.ports.brain_dashboard)& "
        }
        $cmdLine = "${brainSkipPrefix}set ELECTRON_RUN_AS_NODE=& `"$electronExe`" --remote-debugging-port=$debugPort --enable-logging `"$electronDir`""
        Start-Process cmd -ArgumentList "/c", $cmdLine -WorkingDirectory $voiceDir -RedirectStandardOutput $electronLog -RedirectStandardError $electronErr
        Write-Host "    Electron started (DevTools :$debugPort)" -ForegroundColor Gray

        # Wait for Electron to boot
        Write-Host "    Waiting for Electron (8s)..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 8

        # cmd /c wrapper exited once electron.exe took over — record the real
        # electron PID via its DevTools port so vm-procs.ps1 can manage it.
        try {
            $elConn = Get-NetTCPConnection -LocalPort $debugPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            $elPid = if ($elConn) { [int]$elConn.OwningProcess } else { 0 }
            Register-SpawnedProcess -Name "voice_electron" -ProcId $elPid `
                -Command $electronExe -Port $debugPort -Runtime "electron"
        } catch {}

        # Start Debug Agent — OpenFang `debugger` agent sidecar.
        # Replaces the legacy `electron_debug_agent.py` CDP listener: the
        # real debugger now lives in vibemind-os/openfang/agents/debugger
        # and is reachable via POST :4200/api/agents/{id}/message. This
        # launcher resolves that agent id, caches it under
        # logs/openfang/debugger_agent.id, and stays alive so the
        # dashboard's `Debug Agent` (Verify=process) row stays green.
        # OpenFang itself is started one phase earlier (see the OpenFang
        # service row in PHASE 6), so by here :4200 is up — the launcher
        # also retries internally during its boot budget.
        $debuggerLauncher = Join-Path $ROOT "scripts/openfang_debugger_launch.py"
        if ((Test-Path "$sharedVenv/Scripts/python.exe") -and (Test-Path $debuggerLauncher)) {
            Start-VenvPython -Name "debug_agent" -VenvPath $sharedVenv -WorkDir (Join-Path $ROOT "scripts") `
                -ScriptArgs "-u openfang_debugger_launch.py" `
                -LogFile (Join-Path $script:LOG_DIR "openfang/debug_agent.log") `
                -ExtraEnv @{
                    PYTHONUNBUFFERED = "1"
                    OPENFANG_URL     = "http://127.0.0.1:$($CONFIG.ports.openfang)"
                }
            Write-Host "    Debug Agent started (OpenFang debugger sidecar)" -ForegroundColor Gray
        }
    } else {
        Write-Host "    [WARN] Electron not installed. Run: cd vibemind-os/voice/electron-app; npm install" -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════════════
#  PHASE 6: Status Dashboard
# ═══════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    VibeMind Debug -Service Status" -ForegroundColor White
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host ""

# Verify modes:
#   http200    — 200 = OK, anything else (incl. 4xx) = DOWN
#   httpAlive  — any HTTP response = OK (Kong returning 404 still proves it's up)
#   httpJson   — 200 + JSON body containing required key = OK
#   tcp        — port-bound = OK (last resort: Mongo/Rowboat have no http probe)
#   process    — registered in $script:PROCESSES and not exited = OK (no network)
#
# Budgets are upper bounds for the polling job. Each job retries on a 1s tick
# until success or budget exhaustion.
$services = @(
    # Brain
    @{ Name = "Brain Dashboard"; Module = "brain";          Port = $CONFIG.ports.brain_dashboard;    Url = "http://localhost:$($CONFIG.ports.brain_dashboard)/api/health"; Verify = "http200"; Budget = 60; ProcessKey = "brain_dashboard" }
    @{ Name = "Brain API";       Module = "brain";          Port = $CONFIG.ports.brain_api;          Url = "http://localhost:$($CONFIG.ports.brain_api)/health";          Verify = "http200"; Budget = 60; ProcessKey = "brain_api" }
    # Infrastructure
    # Bridge mounts its routes under the /bridge prefix (router.py:128 →
    # GET /bridge/health). The old probe hit /health (404) so a HEALTHY
    # bridge always showed "error". /bridge/health is the real endpoint.
    @{ Name = "Bridge";          Module = "bridge";         Port = $CONFIG.ports.bridge;             Url = "http://localhost:$($CONFIG.ports.bridge)/bridge/health";      Verify = "http200"; Budget = 20; ProcessKey = "bridge" }
    # La-Fungus has no /health endpoint — /docs is the only public route and
    # only renders after the FastAPI app is fully constructed, so it's a usable
    # readiness signal here even if not strictly health.
    @{ Name = "La-Fungus Search";Module = "la_fungus";      Port = $CONFIG.ports.la_fungus_api;      Url = "http://localhost:$($CONFIG.ports.la_fungus_api)/docs";        Verify = "http200"; Budget = 20; ProcessKey = "la_fungus" }
    # Voice
    @{ Name = "Minibook";        Module = "voice";          Port = $CONFIG.ports.minibook_backend;   Url = "http://localhost:$($CONFIG.ports.minibook_backend)/api/v1/agents"; Verify = "http200"; Budget = 20 }
    @{ Name = "MiroFish";        Module = "voice";          Port = $CONFIG.ports.mirofish;           Url = "http://localhost:$($CONFIG.ports.mirofish)/health";           Verify = "http200"; Budget = 20 }
    # /json/version returns a JSON object whose Browser field identifies the
    # specific Chromium build, so we both prove DevTools is alive and that
    # we're talking to VibeMind's electron rather than another tool's chromium.
    @{ Name = "Voice Electron";  Module = "voice";          Port = $CONFIG.ports.electron_devtools;  Url = "http://localhost:$($CONFIG.ports.electron_devtools)/json/version"; Verify = "httpJson"; JsonKey = "Browser"; Budget = 10 }
    # Desktop
    # Backend loads paddle / openrouter / video services etc. — cold start
    # ~12-15s typical, can spike to 30s+ on first run (pycache compile, AV
    # scan, OneDrive interference). 60s budget mirrors the brain services.
    @{ Name = "Automation BE";   Module = "automation_ui";  Port = $CONFIG.ports.automation_backend;  Url = "http://localhost:$($CONFIG.ports.automation_backend)/api/health/health"; Verify = "http200"; Budget = 60; ProcessKey = "automation_backend" }
    # Agents
    @{ Name = "OpenFang";        Module = "openfang";       Port = $CONFIG.ports.openfang;           Url = "http://localhost:$($CONFIG.ports.openfang)/api/health";       Verify = "http200"; Budget = 20 }
    @{ Name = "OpenClaw";        Module = "openclaw";       Port = $CONFIG.ports.openclaw_gateway;   Url = "http://localhost:$($CONFIG.ports.openclaw_gateway)/healthz";  Verify = "http200"; Budget = 20 }
    # Workflows
    @{ Name = "n8n Workflows";   Module = "n8n";            Port = $CONFIG.ports.n8n;                Url = "http://localhost:$($CONFIG.ports.n8n)/healthz";               Verify = "http200"; Budget = 20 }
    @{ Name = "AgentFarm API";   Module = "agentfarm";      Port = $CONFIG.ports.agentfarm_server;   Url = "http://localhost:$($CONFIG.ports.agentfarm_server)";          Verify = "http200"; Budget = 20 }
    # Data
    @{ Name = "Rowboat";         Module = "rowboat";        Port = $CONFIG.ports.rowboat;            Url = "tcp";                                                          Verify = "tcp";     Budget = 10 }
    @{ Name = "MongoDB";         Module = "rowboat";        Port = 37017;                            Url = "tcp";                                                          Verify = "tcp";     Budget = 10 }
    # Supabase Kong returns 404 with JSON body for unrouted paths even when
    # healthy — a 4xx still proves the gateway is up, hence httpAlive.
    @{ Name = "Supabase API";    Module = "voice";          Port = 54321;                            Url = "http://localhost:54321/";                                      Verify = "httpAlive"; Budget = 10 }
    @{ Name = "Supabase Studio"; Module = "voice";          Port = 54323;                            Url = "http://localhost:54323/";                                      Verify = "http200"; Budget = 10 }
    # Coding
    @{ Name = "Coding Engine";   Module = "coding_engine";  Port = $CONFIG.ports.coding_api;         Url = "http://localhost:$($CONFIG.ports.coding_api)/docs";           Verify = "http200"; Budget = 60 }
    @{ Name = "Coding Frontend"; Module = "coding_engine";  Port = $CONFIG.ports.coding_frontend;    Url = "http://localhost:$($CONFIG.ports.coding_frontend)";           Verify = "http200"; Budget = 20 }
    # Tracked processes that don't have a public network surface or weren't
    # previously visible in the dashboard at all.
    @{ Name = "Media Server";    Module = "voice";          Port = $CONFIG.ports.media_server;       Url = "http://localhost:$($CONFIG.ports.media_server)/";             Verify = "http200"; Budget = 10; ProcessKey = "media_server" }
    @{ Name = "Debug Agent";     Module = "openfang";       Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "debug_agent" }
    @{ Name = "Marketing Sync A";Module = "marketing";      Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "marketing_sync_a" }
    @{ Name = "Marketing Sync B";Module = "marketing";      Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "marketing_sync_b" }
    @{ Name = "Marketing Runner";Module = "marketing";      Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "marketing_runner" }
    @{ Name = "Bubble Predict";  Module = "marketing";      Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "bubble_predict_runner" }
    @{ Name = "Bubble Classifier";Module = "marketing";     Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "bubble_classifier_runner" }
    @{ Name = "Bubble Dispatcher";Module = "marketing";     Port = 0;                                Url = "process";                                                      Verify = "process"; Budget = 5;  ProcessKey = "bubble_dispatcher" }
    @{ Name = "Marketing HTTP";  Module = "marketing";      Port = 5510;                             Url = "http://localhost:5510/api/health";                             Verify = "http200"; Budget = 10; ProcessKey = "marketing_http" }
    @{ Name = "MoireServer";     Module = "voice";          Port = $CONFIG.ports.moire_server;       Url = "tcp";                                                          Verify = "tcp";     Budget = 10; ProcessKey = "moire_server" }
)

# Phase B / Step 5: in default STACK mode the unified Swarm stack publishes
# DIFFERENT host ports than the standalone composes. Without this override
# the dashboard probes dead standalone ports and shows HEALTHY stack
# services as DOWN (exactly the screenshot: Rowboat :3000, Mongo :37017).
# -Legacy keeps the original ports. The "__stack_internal__" Module sentinel
# reuses the existing module-disabled SKIP path (foreach below: a Module not
# in $CONFIG.modules yields $null -> SKIP) for services the stack keeps
# overlay-internal (rowboat-mongo/redis have NO published host port).
if (-not $Legacy) {
    $stackOverride = @{
        "Rowboat"  = @{ Port = 3100; Url = "http://localhost:3100/"; Verify = "httpAlive" }  # stack publishes 3100->3000, Next.js / no /health
        "MongoDB"  = @{ Skip = $true }                                                        # stack rowboat-mongo: overlay-internal, no host port
        # MiroFish :5101 / n8n :15678 / Brain :5000 — stack host ports already
        # equal the config ports, no override needed. (rowboat-agents :3101,
        # media :9877, neo4j-mirofish :7475 are extra stack surfaces; left out
        # of the minimal change — add as visibility rows later if wanted.)
    }
    foreach ($svc in $services) {
        if ($stackOverride.ContainsKey($svc.Name)) {
            $o = $stackOverride[$svc.Name]
            if ($o.Skip) {
                $svc.Module = "__stack_internal__"   # -> SKIP via existing module-disabled path
            } else {
                if ($o.Port)   { $svc.Port   = $o.Port }
                if ($o.Url)    { $svc.Url    = $o.Url }
                if ($o.Verify) { $svc.Verify = $o.Verify }
            }
        }
    }
}

# Build status for each service: skip, crash-detect, or async-probe
$svcStatus  = [ordered]@{}  # Name → "OK" | "DOWN" | "CRASH" | "SKIP"
$svcReason  = @{}           # Name → short reason string for DOWN rows
$asyncJobs  = @{}           # Name → Job

foreach ($svc in $services) {
    $modEnabled = $CONFIG.modules.($svc.Module).enabled
    if (-not $modEnabled) {
        $svcStatus[$svc.Name] = "SKIP"
        continue
    }

    # Crash detection: if we're tracking the process and it has already exited
    # non-zero, no point probing the network.
    $procKey = $svc.ProcessKey
    if ($procKey -and $script:PROCESSES.ContainsKey($procKey)) {
        $proc = $script:PROCESSES[$procKey].Process
        if ($proc -and $proc.HasExited -and $proc.ExitCode -ne 0) {
            $svcStatus[$svc.Name] = "CRASH"
            $svcReason[$svc.Name] = "exit:$($proc.ExitCode)"
            continue
        }
    }

    # Process-only services (e.g. Debug Agent) — no network probe.
    if ($svc.Verify -eq "process") {
        if ($procKey -and $script:PROCESSES.ContainsKey($procKey)) {
            $proc = $script:PROCESSES[$procKey].Process
            if ($proc -and -not $proc.HasExited) {
                $svcStatus[$svc.Name] = "OK"
            } else {
                $svcStatus[$svc.Name] = "DOWN"
                $svcReason[$svc.Name] = "process-exited"
            }
        } else {
            $svcStatus[$svc.Name] = "DOWN"
            $svcReason[$svc.Name] = "not-tracked"
        }
        continue
    }

    # Network probe — runs in a background job so probes execute in parallel.
    $asyncJobs[$svc.Name] = Start-Job -ScriptBlock {
        param($Url, $Port, $Verify, $JsonKey, $Budget)
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $lastReason = "timeout"
        while ($sw.Elapsed.TotalSeconds -lt $Budget) {
            try {
                if ($Verify -eq "tcp") {
                    # 127.0.0.1 not "localhost" — same Docker-loopback
                    # flakiness fix as the HTTP branch.
                    $ok = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet
                    if ($ok) { return @{ Ok = $true } }
                    $lastReason = "connection-refused"
                } else {
                    # 2026-05-19: was TimeoutSec 3 + literal "localhost".
                    # Both caused chronic FALSE "timeout" on healthy
                    # Docker-forwarded services (Brain/Minibook/MiroFish/
                    # n8n/Bridge): 3s is too short for a busy container's
                    # first response, and Invoke-WebRequest against
                    # "localhost" is flaky for Docker port-forwards where
                    # 127.0.0.1 answers instantly. 8s + IPv4 literal fixes
                    # the false-reds without masking real outages (budget
                    # loop still bounds total wait).
                    $probeUrl = $Url -replace 'localhost', '127.0.0.1'
                    $r = Invoke-WebRequest -Uri $probeUrl -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
                    if ($Verify -eq "httpAlive") {
                        return @{ Ok = $true }
                    } elseif ($Verify -eq "http200") {
                        if ($r.StatusCode -eq 200) { return @{ Ok = $true } }
                        $lastReason = "wrong-status:$($r.StatusCode)"
                    } elseif ($Verify -eq "httpJson") {
                        if ($r.StatusCode -ne 200) {
                            $lastReason = "wrong-status:$($r.StatusCode)"
                        } else {
                            try {
                                $obj = $r.Content | ConvertFrom-Json -ErrorAction Stop
                                if (-not $JsonKey -or $null -ne $obj.$JsonKey) { return @{ Ok = $true } }
                                $lastReason = "wrong-shape"
                            } catch {
                                $lastReason = "wrong-shape"
                            }
                        }
                    }
                }
            } catch {
                $msg = $_.Exception.Message
                if ($msg -match "actively refused|target machine actively") { $lastReason = "connection-refused" }
                elseif ($msg -match "timed out|timeout")                    { $lastReason = "timeout" }
                elseif ($msg -match "remote name could not")                { $lastReason = "dns" }
                else                                                          { $lastReason = "error" }
            }
            Start-Sleep -Milliseconds 1000
        }
        return @{ Ok = $false; Reason = $lastReason }
    } -ArgumentList $svc.Url, $svc.Port, $svc.Verify, $svc.JsonKey, $svc.Budget
}

# Wait for all async probes (parallel). The longest budget bounds total wait.
if ($asyncJobs.Count -gt 0) {
    @($asyncJobs.Values) | Wait-Job | Out-Null
    foreach ($name in @($asyncJobs.Keys)) {
        $result = Receive-Job $asyncJobs[$name]
        Remove-Job $asyncJobs[$name] -Force
        $ok = $false; $reason = "unknown"
        if ($result) { $ok = [bool]$result.Ok; if ($result.Reason) { $reason = $result.Reason } }
        if ($ok) {
            $svcStatus[$name] = "OK"
        } else {
            $svcStatus[$name] = "DOWN"
            $svcReason[$name] = $reason
        }
    }
}

# Print in original order
foreach ($svc in $services) {
    $st = $svcStatus[$svc.Name]
    $urlDisplay = if ($st -eq "SKIP") { "---" } else { $svc.Url }
    $reason = $svcReason[$svc.Name]
    Write-Status -svc $svc.Name -status $st -port $svc.Port -url $urlDisplay -reason $reason
}

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Logs: $script:LOG_DIR" -ForegroundColor Gray
Write-Host ""

# ═══════════════════════════════════════════════════════════════════
#  PHASE 7: Main Loop -Wait for Ctrl+C
# ═══════════════════════════════════════════════════════════════════

# Belt-and-braces shutdown hook — fires when the host is closing the
# session (window X-button, killed shell, etc.) where the `finally` below
# would otherwise be skipped. Same body as Stop-AllServices but suppresses
# any host-write errors the engine can't render at that point.
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -SupportEvent -Action {
    try { Stop-AllServices } catch {}
} | Out-Null

# Console-close handler (red-X on the launcher window). PowerShell does
# not surface the Win32 close event natively, so register the .NET
# AppDomain ProcessExit which fires for both clean exits and external
# termination (taskkill, parent process closed, etc.).
try {
    [System.AppDomain]::CurrentDomain.add_ProcessExit({
        try { Stop-AllServices } catch {}
    })
} catch {}

try {
    # Keep script alive
    while ($true) {
        Start-Sleep -Seconds 30

        # Periodic health check: report each crash once, then drop the entry
        # so the next iteration doesn't re-report the same dead process.
        # Snapshot the keys because we mutate $script:PROCESSES inside the loop.
        $reported = @()
        foreach ($name in @($script:PROCESSES.Keys)) {
            $entry = $script:PROCESSES[$name]
            if ($entry.Process.HasExited) {
                $code = $entry.Process.ExitCode
                if ($code -ne 0) {
                    Write-Host "  [CRASH] $name exited with code $code -- check logs" -ForegroundColor Red
                    $logFileGuess = Get-ChildItem -Path $script:LOG_DIR -Recurse -Filter "$name*.log" -ErrorAction SilentlyContinue | Select-Object -First 1
                    if ($logFileGuess) {
                        $tail = Get-Content $logFileGuess.FullName -Tail 5 -ErrorAction SilentlyContinue
                        if ($tail) { $tail | ForEach-Object { Write-Host "           $_" -ForegroundColor DarkGray } }
                    }
                }
                $reported += $name
            }
        }
        foreach ($name in $reported) { $script:PROCESSES.Remove($name) }
    }
} finally {
    Stop-AllServices
}
