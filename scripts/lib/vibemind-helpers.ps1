<#
.SYNOPSIS
    Shared helpers for vibemind-start.ps1 / vibemind-stop.ps1 (E1 server-mode).
.DESCRIPTION
    Dot-source-only module. ALL functions are dependency-free: no $CONFIG,
    no $script:LOG_DIR, no $script:REGISTRY_FILE — everything goes through
    parameters. This is the entkopplung E1a originally lacked (the
    Pragmatismus-Trade was "copy inline, factor later"; this is later).

    Functions (alphabetical):
      Get-CrashedFromRegistry      crash detection for Wait-Interactive (E1d)
      Get-RuntimeHint              classify command path → runtime label
      Initialize-Registry          rotate logs/services.registry.jsonl → .prev
      Register-SpawnedProcess      append one JSONL line to registry
      Start-ServiceProcess         generic ProcessStartInfo spawner with async logs
      Start-VenvPython             resolve <venv>\Scripts\python.exe, delegate
      Stop-AllServicesFromRegistry kill all PIDs in registry + port backstop (E1d)
      Stop-ByPort                  resolve listener PID, kill (with -Tree)
      Test-HttpHealth              HTTP probe with PS7 IPv6→IPv4 rewrite
      Test-PortFree                $true iff nothing is listening on the port
      Test-RegisteredProcessAlive  registry-PID lookup + Get-Process check
      Wait-Interactive             30s tick loop + Ctrl+C trap (E1d)
      Write-Phase / Ok / Warn / Err  colored output

    Loaded by:
      scripts\vibemind-start.ps1
      scripts\vibemind-stop.ps1
.NOTES
    History: extracted 2026-05-20 from E1a inline helpers (commit bf7f9d0)
    + the parametrised parts of Vibemind.debug.ps1 (Z.53-234, Z.642-648,
    Z.1400-1450). See ~\.claude\plans\k-nnnen-wir-adative-skills-splendid-
    mochi.md "Commit 1" for the extraction rationale.
#>

# --- output helpers -------------------------------------------------------

function Write-Phase { param([string]$Msg) Write-Host ""; Write-Host "  $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "    $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "    $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "    $Msg" -ForegroundColor Red }

# --- HTTP / port probes ---------------------------------------------------

function Test-HttpHealth {
    <#
    .SYNOPSIS
        HTTP 2xx/3xx probe with the PS7 IPv6→IPv4 fix.
    .DESCRIPTION
        PS7's Invoke-WebRequest on http://localhost:<port> first tries IPv6
        ::1 and falls back slowly → 5s timeout HITS even though the service
        answers IPv4 instantly. Same class as the rowboat/media busybox-wget
        IPv6 trap. We rewrite `://localhost` → `://127.0.0.1` to dodge the
        resolution path entirely. (E1a §2 lesson, kept verbatim.)
    #>
    param([string]$Url, [int]$TimeoutSec = 5)
    $u = $Url -replace '://localhost(?=[:/])', '://127.0.0.1'
    try {
        $r = Invoke-WebRequest -Uri $u -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 400
    } catch { return $false }
}

function Test-PortFree {
    <#
    .SYNOPSIS
        $true iff nothing is currently listening on the local port.
    .DESCRIPTION
        Idempotency gate for service starts: skip if port already held.
        Same primitive as Stop-ByPort, inverted. Get-NetTCPConnection is
        IPv4+IPv6 aware so a ::1-only listener is also detected.
    #>
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        return ($null -eq $conn)
    } catch {
        return $true   # treat lookup failure as "free" — start will fail loudly if it isn't
    }
}

# --- process resolve / stop -----------------------------------------------

function Stop-ByPort {
    <#
    .SYNOPSIS
        Resolve the listener PID for a port and kill it.
    .PARAMETER Port
        TCP port to resolve.
    .PARAMETER Name
        Human-readable label for log lines.
    .PARAMETER Tree
        If $true, use taskkill /F /T (tree-kill) — needed for uvicorn /
        npm / electron which spawn worker subprocesses. Default: $false
        (single Stop-Process).
    .PARAMETER CmdLinePattern
        Optional regex against process CommandLine for a second-pass
        reap. Catches multiprocessing.fork orphans whose PPID was
        reparented before the tree-kill walked the tree (the
        automation_backend Windows quirk). Only matched processes from
        a repo path are killed.
    .PARAMETER RepoRoot
        Optional repo root. When supplied with CmdLinePattern, only
        processes whose CommandLine ALSO contains RepoRoot are reaped
        (path-scope guard — don't kill unrelated python processes).
    .PARAMETER DryRun
        Report what would happen, do nothing.
    .NOTES
        This is the pattern OpenFang/Ollama needed in E1a (self-daemonised
        binary or wrapper script — spawn PID is dead, the LISTENER is the
        real process). Generalised here so E1b/c/d don't copy-paste.
    #>
    param(
        [int]$Port,
        [string]$Name,
        [switch]$Tree,
        [string]$CmdLinePattern = '',
        [string]$RepoRoot = '',
        [switch]$DryRun
    )
    $conn = $null
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    } catch {}
    if (-not $conn) {
        Write-Warn "Nothing listening on :$Port — $Name not running"
    } else {
        $procId = [int]$conn.OwningProcess
        $alive = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($DryRun) {
            $how = if ($Tree) { "taskkill /F /T /PID $procId" } else { "Stop-Process -Id $procId" }
            Write-Warn "[DryRun] Would $how (listener on :$Port)"
        } elseif (-not $alive) {
            Write-Warn "Listener on :$Port owned by dead PID $procId (kernel ghost) — sweeping orphans"
        } else {
            try {
                if ($Tree) {
                    & taskkill.exe /F /T /PID $procId 2>&1 | Out-Null
                    Write-Ok "$Name stopped (pid $procId on :$Port, tree)"
                } else {
                    Stop-Process -Id $procId -Force -ErrorAction Stop
                    Write-Ok "$Name stopped (pid $procId on :$Port)"
                }
            } catch {
                Write-Warn "Could not stop $Name pid ${procId}: $($_.Exception.Message)"
            }
        }
    }
    # Second pass — reap orphans (multiprocessing.fork that lost its
    # parent before taskkill /T could walk to it). Only path-scoped.
    if ($CmdLinePattern -and $RepoRoot -and -not $DryRun) {
        try {
            $orphans = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.CommandLine -and
                    $_.CommandLine -match $CmdLinePattern -and
                    $_.CommandLine -like "*$RepoRoot*"
                }
            foreach ($o in $orphans) {
                try {
                    & taskkill.exe /F /T /PID $o.ProcessId 2>&1 | Out-Null
                    Write-Host "      Reaped orphan PID=$($o.ProcessId) $($o.CommandLine.Substring(0, [Math]::Min(80, $o.CommandLine.Length)))" -ForegroundColor DarkGray
                } catch {}
            }
        } catch {}
    } elseif ($CmdLinePattern -and $RepoRoot -and $DryRun) {
        try {
            $orphans = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.CommandLine -and
                    $_.CommandLine -match $CmdLinePattern -and
                    $_.CommandLine -like "*$RepoRoot*"
                }
            foreach ($o in $orphans) {
                Write-Warn "[DryRun] Would taskkill /F /T /PID $($o.ProcessId) (orphan: $($o.CommandLine.Substring(0, [Math]::Min(80, $o.CommandLine.Length))))"
            }
        } catch {}
    }
}

# --- registry I/O (vm-procs.ps1 contract) ---------------------------------

function Get-RuntimeHint {
    <#
    .SYNOPSIS
        Classify a command path as .venv / voice-venv / pyenv / node /
        electron / native / other so vm-procs.ps1 / dashboards can flag
        the pyenv-vs-venv duplicate problem.
    .NOTES
        Verbatim mapping from Vibemind.debug.ps1:104-118 so the registry
        rows are compatible with vm-procs.ps1's classification.
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

function Initialize-Registry {
    <#
    .SYNOPSIS
        Reset the spawn registry so it reflects ONLY this start-script run.
    .DESCRIPTION
        Moves an existing logs/services.registry.jsonl to <path>.prev so
        vm-procs.ps1 sees only the current session's processes. Same
        behaviour as Vibemind.debug.ps1:642-648.
    #>
    param([string]$RegistryFile)
    try {
        $dir = Split-Path $RegistryFile
        if ($dir -and -not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        if (Test-Path $RegistryFile) {
            Move-Item -Path $RegistryFile -Destination "${RegistryFile}.prev" -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Register-SpawnedProcess {
    <#
    .SYNOPSIS
        Append one JSONL line recording a process this script spawned.
    .DESCRIPTION
        Source of truth for vm-procs.ps1. Schema (must stay stable for
        vm-procs.ps1 compatibility — file:113-125):
            name    : service name
            pid     : OS pid (0 = container-managed / no host pid)
            command : "<exe> <args>"
            port    : primary TCP port, 0 if none
            runtime : Get-RuntimeHint classification
            started : ISO-8601 timestamp
            session : the spawning process's PID (start-script's $PID)
        Best-effort — never throws.
    #>
    param(
        [string]$Name,
        [int]$ProcId,
        [string]$Command,
        [int]$Port = 0,
        [string]$Runtime = "",
        [string]$RegistryFile
    )
    try {
        $rec = [ordered]@{
            name    = $Name
            pid     = $ProcId
            command = $Command
            port    = $Port
            runtime = $Runtime
            started = (Get-Date -Format "o")
            session = $PID
        }
        $line = ($rec | ConvertTo-Json -Compress -Depth 4)
        $dir = Split-Path $RegistryFile
        if ($dir -and -not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        Add-Content -Path $RegistryFile -Value $line -Encoding utf8 -ErrorAction SilentlyContinue
    } catch {}
}

function Test-RegisteredProcessAlive {
    <#
    .SYNOPSIS
        Idempotency check for spawned processes without a fixed port
        (Debug-Agent in E1c).
    .DESCRIPTION
        Reads the most recent registry entry for $Name and checks whether
        that PID is still alive. Returns $true if alive, $false if dead /
        not in registry. The "most recent" search handles re-spawned
        services correctly (last write wins).
    #>
    param([string]$Name, [string]$RegistryFile)
    if (-not (Test-Path $RegistryFile)) { return $false }
    try {
        $lastPid = 0
        Get-Content $RegistryFile -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $entry = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($entry -and $entry.name -eq $Name -and $entry.pid -gt 0) {
                    $lastPid = [int]$entry.pid
                }
            } catch {}
        }
        if ($lastPid -le 0) { return $false }
        $p = Get-Process -Id $lastPid -ErrorAction SilentlyContinue
        return ($null -ne $p)
    } catch {
        return $false
    }
}

# --- process spawners -----------------------------------------------------

function Start-ServiceProcess {
    <#
    .SYNOPSIS
        Generic spawner with async log capture and early-exit diagnostic.
    .DESCRIPTION
        Parametrised port of Vibemind.debug.ps1:136-223. Differences:
        - No $script:PROCESSES global — caller manages process tracking
          if it needs to (we use the registry for stop-side resolution).
        - Mandatory -RegistryFile so Register-SpawnedProcess is called.
        - 1.5s post-spawn HasExited check so import-time errors are
          dumped to the log before the async pipeline can drop them.
    #>
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command,
        [string]$CmdArgs,
        [string]$LogFile,
        [hashtable]$ExtraEnv,
        [int]$Port = 0,
        [string]$RegistryFile
    )
    $logDir = Split-Path $LogFile
    if ($logDir -and -not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Command
    $psi.Arguments = $CmdArgs
    $psi.WorkingDirectory = $WorkDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    if ($ExtraEnv) {
        foreach ($k in $ExtraEnv.Keys) {
            $psi.EnvironmentVariables[$k] = [string]$ExtraEnv[$k]
        }
    }
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
    } catch {
        Write-Warn "Failed to start ${Name}: $_"
        return $null
    }
    if ($null -eq $proc) {
        Write-Warn "${Name} process returned null"
        return $null
    }
    # 1500ms catches import-time ModuleNotFoundError / uvicorn config errors
    # before the async BeginOutputReadLine path can drop them.
    Start-Sleep -Milliseconds 1500
    if ($proc.HasExited) {
        $stderrText = ""
        $stdoutText = ""
        try { $stderrText = $proc.StandardError.ReadToEnd() } catch {}
        try { $stdoutText = $proc.StandardOutput.ReadToEnd() } catch {}
        try {
            $sw = [System.IO.StreamWriter]::new($LogFile, $true)
            $sw.WriteLine("=== [$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Name EARLY-EXIT code=$($proc.ExitCode) cmd=$Command $CmdArgs ===")
            if ($stdoutText) { $sw.WriteLine("[STDOUT]"); $sw.WriteLine($stdoutText) }
            if ($stderrText) { $sw.WriteLine("[STDERR]"); $sw.WriteLine($stderrText) }
            $sw.Close()
        } catch {}
        Write-Warn "$Name exited immediately (exit code: $($proc.ExitCode))"
        if ($stderrText) {
            $stderrText -split "`n" | Select-Object -Last 5 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkYellow }
        }
        # Register so vm-procs/crash-reporters see the exit code
        if ($RegistryFile) {
            Register-SpawnedProcess -Name $Name -ProcId $proc.Id `
                -Command "$Command $CmdArgs" -Port $Port `
                -Runtime (Get-RuntimeHint $Command) -RegistryFile $RegistryFile
        }
        return $null
    }
    # Async log capture — wrapped because if the process dies between the
    # HasExited check and the Add() call, PowerShell throws InvalidOperation
    # on the dead handle.
    $outFile = $null
    $savedEAP = $ErrorActionPreference
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
    } catch {}
    $ErrorActionPreference = $savedEAP
    if ($RegistryFile) {
        Register-SpawnedProcess -Name $Name -ProcId $proc.Id `
            -Command "$Command $CmdArgs" -Port $Port `
            -Runtime (Get-RuntimeHint $Command) -RegistryFile $RegistryFile
    }
    return $proc
}

function Start-VenvPython {
    <#
    .SYNOPSIS
        Spawn <VenvPath>\Scripts\python.exe with given args.
    .DESCRIPTION
        Thin wrapper over Start-ServiceProcess. Warns and returns $null if
        the venv doesn't exist (so a missing venv doesn't fail the whole
        start; the service is just skipped).
    #>
    param(
        [string]$Name,
        [string]$VenvPath,
        [string]$WorkDir,
        [string]$ScriptArgs,
        [string]$LogFile,
        [hashtable]$ExtraEnv,
        [int]$Port = 0,
        [string]$RegistryFile
    )
    $python = Join-Path $VenvPath "Scripts/python.exe"
    if (-not (Test-Path $python)) {
        Write-Warn "venv not found: $VenvPath — skipping $Name"
        return $null
    }
    return Start-ServiceProcess -Name $Name -WorkDir $WorkDir `
        -Command $python -CmdArgs $ScriptArgs -LogFile $LogFile `
        -ExtraEnv $ExtraEnv -Port $Port -RegistryFile $RegistryFile
}

# --- interactive-mode wait loop (E1d) -------------------------------------

function Get-CrashedFromRegistry {
    <#
    .SYNOPSIS
        Return a list of (Name, ExitCode, LogFile) for processes in the
        registry that are NOT alive any more — feeds the [CRASH] reporter
        in Wait-Interactive.
    .DESCRIPTION
        One-shot: each crashed PID is reported once per call. Caller is
        responsible for tracking which it has already reported (the wait
        loop keeps a hash).
        Only entries with pid>0 are considered (pid=0 = container row).
    #>
    param([string]$RegistryFile)
    $out = @()
    if (-not (Test-Path $RegistryFile)) { return $out }
    $latest = @{}   # name -> entry (last wins)
    Get-Content $RegistryFile -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $e = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($e -and $e.pid -gt 0) { $latest[$e.name] = $e }
        } catch {}
    }
    foreach ($name in $latest.Keys) {
        $e = $latest[$name]
        $alive = $false
        try { $alive = ($null -ne (Get-Process -Id ([int]$e.pid) -ErrorAction SilentlyContinue)) } catch {}
        if (-not $alive) {
            $out += [pscustomobject]@{ Name = $name; Pid = [int]$e.pid; Command = $e.command }
        }
    }
    return $out
}

function Stop-AllServicesFromRegistry {
    <#
    .SYNOPSIS
        Kill every PID in the registry (tree-kill) + reap managed ports.
    .DESCRIPTION
        Used by the interactive-mode Ctrl+C trap (E1d). Does NOT touch the
        swarm stack — leaving the stack running between interactive sessions
        is the symmetric Default of vibemind-stop.ps1 -KeepStack. To stop
        the stack too, call vibemind-stop.ps1 separately.
    .PARAMETER RegistryFile
        Path to logs/services.registry.jsonl.
    .PARAMETER ManagedPorts
        Optional array of ports to additionally reap as backstop (e.g.
        @(8011, 5150, 8007, 8766, 9223)) — catches anything the registry
        missed.
    #>
    param(
        [string]$RegistryFile,
        [int[]]$ManagedPorts = @()
    )
    $killed = @{}
    if (Test-Path $RegistryFile) {
        $latest = @{}
        Get-Content $RegistryFile -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $e = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($e -and $e.pid -gt 0) { $latest[$e.name] = $e }
            } catch {}
        }
        foreach ($name in $latest.Keys) {
            $e = $latest[$name]
            $procId = [int]$e.pid
            try {
                $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($p) {
                    & taskkill.exe /F /T /PID $procId 2>&1 | Out-Null
                    Write-Host "    Stopped $name (PID=$procId +tree)" -ForegroundColor Gray
                    $killed[$procId] = $true
                }
            } catch {}
        }
    }
    foreach ($port in $ManagedPorts) {
        try {
            $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($conn -and -not $killed[[int]$conn.OwningProcess]) {
                $procId = [int]$conn.OwningProcess
                & taskkill.exe /F /T /PID $procId 2>&1 | Out-Null
                Write-Host "    Reaped :$port (PID=$procId)" -ForegroundColor DarkGray
                $killed[$procId] = $true
            }
        } catch {}
    }
}

function Wait-Interactive {
    <#
    .SYNOPSIS
        Block forever (30s tick) until Ctrl+C, then graceful Stop-All.
    .DESCRIPTION
        Used by vibemind-start.ps1 -Interactive (E1d). Server-mode default
        is `exit 0` immediately after the health gate — this loop is OPT-IN.
        Registers PowerShell.Exiting + AppDomain.ProcessExit traps and a
        finally-block so Ctrl+C / window-close / unhandled exception all
        unwind to Stop-AllServicesFromRegistry.
    .PARAMETER RegistryFile
        Path passed to Stop-AllServicesFromRegistry on exit.
    .PARAMETER ManagedPorts
        Port-backstop list (passed through).
    .PARAMETER LogRoot
        Optional root dir for log-tail on [CRASH] reports. If supplied,
        tails the last 5 lines from <LogRoot>\**\<name>.log when a
        registered service exits non-zero.
    #>
    param(
        [string]$RegistryFile,
        [int[]]$ManagedPorts = @(),
        [string]$LogRoot
    )
    # Belt + suspenders trap registration — same pattern as
    # Vibemind.debug.ps1:1408-1420.
    $stopScript = {
        try { Stop-AllServicesFromRegistry -RegistryFile $using:RegistryFile -ManagedPorts $using:ManagedPorts } catch {}
    }
    try {
        Register-EngineEvent -SourceIdentifier PowerShell.Exiting -SupportEvent -Action $stopScript | Out-Null
    } catch {}
    try {
        $regCopy = $RegistryFile
        $portsCopy = $ManagedPorts
        [System.AppDomain]::CurrentDomain.add_ProcessExit({
            try { Stop-AllServicesFromRegistry -RegistryFile $regCopy -ManagedPorts $portsCopy } catch {}
        })
    } catch {}

    $reportedCrashes = @{}
    try {
        Write-Host ""
        Write-Host "  Interactive mode — Ctrl+C to stop all native services." -ForegroundColor Cyan
        Write-Host "  (The swarm stack stays up; use vibemind-stop.ps1 to tear it down.)" -ForegroundColor Gray
        while ($true) {
            Start-Sleep -Seconds 30
            # Crash detection
            $crashed = Get-CrashedFromRegistry -RegistryFile $RegistryFile
            foreach ($c in $crashed) {
                if ($reportedCrashes[$c.Name]) { continue }
                $reportedCrashes[$c.Name] = $true
                Write-Host "  [CRASH] $($c.Name) PID=$($c.Pid) is no longer alive — check logs" -ForegroundColor Red
                if ($LogRoot) {
                    $candidate = Get-ChildItem -Path $LogRoot -Recurse -Filter "*$($c.Name)*.log" -ErrorAction SilentlyContinue | Select-Object -First 1
                    if ($candidate) {
                        Get-Content $candidate.FullName -Tail 5 -ErrorAction SilentlyContinue |
                            ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
                    }
                }
            }
        }
    } finally {
        Write-Host ""
        Write-Host "  Stopping all native services (stack stays up)..." -ForegroundColor Cyan
        Stop-AllServicesFromRegistry -RegistryFile $RegistryFile -ManagedPorts $ManagedPorts
    }
}

# --- Profile-filtered stack rendering -------------------------------------

function ConvertTo-SpaceList {
    <#
    .SYNOPSIS
        Normalise a "-Spaces" param value to a clean string array.
    .DESCRIPTION
        Accepts a comma-separated string (e.g. "coding,n8n") or an empty
        string. Returns @() when empty. Trims whitespace, drops empty
        entries, lower-cases. The single source of truth for parsing the
        space selection across vibemind-start.ps1 / vibemind-stop.ps1 /
        vibemind-spaces.ps1 / Vibemind.debug.ps1.
    #>
    param([string]$Spaces = "")
    if ([string]::IsNullOrWhiteSpace($Spaces)) { return @() }
    return @($Spaces.Split(",") | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ })
}

function Get-ComposeProfiles {
    <#
    .SYNOPSIS
        Build the COMPOSE_PROFILES list from a -Spaces selection.
    .DESCRIPTION
        Returns @("core", "space-<name>", ...). Core is always included.
        Pass the result to docker compose via --profile (one per entry).
    #>
    param([string[]]$Spaces = @())
    $profiles = @("core")
    foreach ($s in $Spaces) {
        if ($s) { $profiles += "space-$s" }
    }
    return $profiles
}

function Get-StackProfileNames {
    <#
    .SYNOPSIS
        Read every profile declared by a Compose-format stack file.
    .DESCRIPTION
        Returns unique profile names in stable sorted order. This supports
        callers that must preserve every service while still rendering away
        Compose-only `profiles:` keys for Docker Swarm.
    #>
    param([Parameter(Mandatory)][string]$StackFile)
    if (-not (Test-Path $StackFile)) { throw "StackFile not found: $StackFile" }

    $profiles = @{}
    foreach ($line in Get-Content -Path $StackFile -Encoding utf8) {
        if ($line -match '^\s*profiles:\s*\[([^\]]*)\]') {
            foreach ($profile in $Matches[1].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }) {
                $profiles[$profile] = $true
            }
        }
    }
    return @($profiles.Keys | Sort-Object)
}

function ConvertTo-FilteredStack {
    <#
    .SYNOPSIS
        Render vibemind-stack.yml filtered by profiles to a temp file
        that `docker stack deploy` will accept.
    .DESCRIPTION
        `docker stack deploy` does NOT understand the `profiles:` key
        (unlike `docker compose up`). Smoke test 2026-05-25 confirmed
        "Additional property profiles is not allowed".

        Going through `docker compose config` to expand + filter introduces
        format-coercion bugs (cpus becomes float, ports.published becomes
        string, etc.) — stack-deploy rejects each. So this helper does the
        filtering DIRECTLY on the source YAML lines:

          1. Read every line of $StackFile.
          2. Detect `services:` start + each `  <name>:` service header.
          3. For each service block, peek at the next non-blank/non-comment
             line. If it's `    profiles: [...]`, parse the profile names.
             Keep the block iff any of its profiles ∈ $Profiles. Drop the
             `profiles:` line itself (stack rejects the key).
          4. Pass all non-services-section lines (top-level keys: configs,
             secrets, networks, volumes) through unchanged.
          5. Write to a temp file and return its path.

        This avoids ALL of docker compose config's format normalisations.
        The source YAML format is exactly preserved.

        Caller MUST `Remove-Item` the returned path after use (or pass it
        to `docker stack deploy -c <path> --prune`).
    .PARAMETER StackFile
        Absolute path to infra/swarm/vibemind-stack.yml.
    .PARAMETER Profiles
        Array of profile names, e.g. @("core","space-coding","space-n8n").
        Pass the output of Get-ComposeProfiles.
    .OUTPUTS
        [string] absolute path to the rendered yml.
    #>
    param(
        [Parameter(Mandatory)][string]$StackFile,
        [Parameter(Mandatory)][string[]]$Profiles
    )
    if (-not (Test-Path $StackFile)) { throw "StackFile not found: $StackFile" }
    if ($Profiles.Count -eq 0) { throw "Profiles array is empty — at least 'core' required" }

    $profileSet = @{}
    foreach ($p in $Profiles) { $profileSet[$p] = $true }

    $lines = Get-Content -Path $StackFile -Encoding utf8
    $output = New-Object System.Collections.Generic.List[string]
    $inServices = $false
    $i = 0
    while ($i -lt $lines.Length) {
        $line = $lines[$i]

        # Top-level section header `services:` / `configs:` / etc. at column 0
        if ($line -match '^([a-zA-Z][a-zA-Z0-9_-]*):\s*$') {
            $inServices = ($Matches[1] -eq 'services')
            $output.Add($line) | Out-Null
            $i++
            continue
        }

        # Service header inside services: section (exactly 2 spaces of indent)
        if ($inServices -and $line -match '^  ([a-zA-Z][a-zA-Z0-9_-]*):\s*$') {
            # Find the end of this service block (next 2-space-indent line or section change)
            $blockStart = $i
            $blockEnd = $i + 1
            while ($blockEnd -lt $lines.Length) {
                $bl = $lines[$blockEnd]
                if ($bl -match '^([a-zA-Z][a-zA-Z0-9_-]*):\s*$') { break }    # next top-level section
                if ($bl -match '^  [a-zA-Z][a-zA-Z0-9_-]*:\s*$') { break }    # next service
                $blockEnd++
            }
            # Extract profiles from the block (look for `    profiles: [a, b]`)
            $svcProfiles = @()
            for ($k = $blockStart + 1; $k -lt $blockEnd; $k++) {
                $bl = $lines[$k]
                if ($bl -match '^\s*profiles:\s*\[([^\]]*)\]') {
                    $svcProfiles = $Matches[1].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
                    break
                }
            }
            # Keep block iff one of its profiles is selected. Services with no
            # profiles: are conservative-included (treated as core-default).
            $keep = $false
            if ($svcProfiles.Count -eq 0) {
                $keep = $true
            } else {
                foreach ($sp in $svcProfiles) {
                    if ($profileSet.ContainsKey($sp)) { $keep = $true; break }
                }
            }
            if ($keep) {
                # Emit block, stripping any `    profiles:` line(s)
                for ($k = $blockStart; $k -lt $blockEnd; $k++) {
                    if ($lines[$k] -notmatch '^\s*profiles:\s*\[') {
                        $output.Add($lines[$k]) | Out-Null
                    }
                }
            }
            $i = $blockEnd
            continue
        }

        # Pass-through (top-level keys, comments, blank lines, etc.)
        $output.Add($line) | Out-Null
        $i++
    }

    # Write next to the original stack file so relative paths inside (env_file:
    # ../../.env, file: ./configs/..., build: ../..) resolve identically.
    # Hidden .* prefix + PID + GUID = unique, easy to git-ignore.
    $stackDir = Split-Path -Parent $StackFile
    $renderId = [guid]::NewGuid().ToString("N")
    $outPath = Join-Path $stackDir ".vibemind-stack-rendered-$PID-$renderId.yml"
    Set-Content -Path $outPath -Value $output -Encoding utf8
    return $outPath
}

function Invoke-FilteredStackDeploy {
    <#
    .SYNOPSIS
        Render + deploy the stack with the given profile selection.
    .DESCRIPTION
        Combines ConvertTo-FilteredStack + `docker stack deploy --prune`.
        --prune is REQUIRED for live toggle to work: without it, services
        from previously-active profiles stay running. Verified 2026-05-25.

        Best-effort cleanup of the temp file on success or failure.
    .PARAMETER StackFile
        Absolute path to infra/swarm/vibemind-stack.yml.
    .PARAMETER Spaces
        Comma-separated space list, e.g. "coding,n8n". Empty = core only.
    .PARAMETER StackName
        Swarm stack name (default: vibemind).
    .OUTPUTS
        Boolean — $true on success, $false on deploy failure.
    #>
    param(
        [Parameter(Mandatory)][string]$StackFile,
        [string]$Spaces = "",
        [string]$StackName = "vibemind"
    )
    $spaceList = ConvertTo-SpaceList -Spaces $Spaces
    $profiles = Get-ComposeProfiles -Spaces $spaceList
    Write-Ok "Profiles: $($profiles -join ', ')"

    $rendered = $null
    try {
        $rendered = ConvertTo-FilteredStack -StackFile $StackFile -Profiles $profiles
        # Cold-start race: `docker stack deploy` sometimes tries to create
        # services BEFORE the inline overlay network's control-plane object is
        # name-resolvable, returning "network ... not found" and exit 1. The
        # network IS created on the failed attempt, so retrying after it
        # becomes inspect-resolvable almost always succeeds. A single fixed 2s
        # sleep was NOT always enough on a heavy cold start (network-race
        # detected 2026-06-09 with the old 3-attempt/fixed-2s loop, all retries
        # exhausted). New behaviour: 5 attempts; before each retry actively
        # poll `docker network inspect` for the stack's overlay net(s) until
        # they resolve (≤20s budget) — closing the read-after-write window
        # instead of guessing; escalating backoff (2/4/6/8s) as the fallback
        # for a non-resolvable / non-network-race transient. Inline-not-external
        # networks reconcile cleanly on re-deploy (an already-committed net is
        # reused, never re-created), so retrying is safe.
        $maxAttempts = 5
        # The overlay networks the stack declares inline (see vibemind-stack.yml
        # `networks:`). Only these gate the race; coding-egress is created on
        # every deploy (networks block is never profile-filtered).
        $netNames = @("${StackName}_vibemind-shared", "${StackName}_coding-egress")
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            $output = docker stack deploy -c $rendered --prune --resolve-image never $StackName 2>&1
            $exitCode = $LASTEXITCODE
            $output |
                Where-Object { $_ -match 'Creating|Updating|Removing|error|Error' } |
                ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
            if ($exitCode -eq 0) { return $true }

            # Detect the specific network-race signature; other errors don't retry.
            $isNetworkRace = ($output | Where-Object { $_ -match 'network .* not found' }).Count -gt 0
            if (-not $isNetworkRace -or $attempt -eq $maxAttempts) {
                return $false
            }
            Write-Warn "      network-race detected (attempt $attempt of $maxAttempts), waiting for overlay net(s) to become resolvable..."
            # Poll until both overlay nets are inspect-resolvable (the right
            # readiness gate for THIS race), bounded to ~20s so a genuine
            # convergence failure (down node / misconfig) still fast-fails on
            # the next iteration rather than blocking indefinitely.
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
            if (-not $allUp) {
                # Net never resolved within budget — fall back to escalating
                # backoff before the next deploy attempt.
                Start-Sleep -Seconds ([math]::Min(2 * $attempt, 8))
            }
        }
        return $false
    } catch {
        Write-Err "Invoke-FilteredStackDeploy: $($_.Exception.Message)"
        return $false
    } finally {
        if ($rendered -and (Test-Path $rendered)) {
            Remove-Item $rendered -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-GpuSetup {
    <#
    .SYNOPSIS
        CUDA-Setup-CHECK für den Brain-Embedder (sicher, nicht-destruktiv).
    .DESCRIPTION
        plans/brain-cuda-migration.md: der Qwen-Embedder ist auf CPU brutal langsam
        (~4-5s/encode, 328 Tools = 17min). Mit NVIDIA-GPU + CUDA-torch ~100-300x.

        WICHTIG (verifiziert 2026-06-20, harte Lehre): Docker Desktop auf WSL2
        REGENERIERT ~/.docker/daemon.json beim Start aus seinem Settings-Store
        (last-start-linux-daemon.json) — ein direkter daemon.json-Edit wird also beim
        nächsten Start PLATTGEMACHT (Timestamps bewiesen: nvidia 10:52 gesetzt, 11:02
        zurück). UND `docker desktop restart` fuhr Docker auf diesem System runter, brachte
        es NICHT wieder hoch (WSL-Distro Stopped) -> Launcher-Abbruch. DESHALB:
          - KEIN daemon.json-Direkt-Edit (verpufft)
          - KEIN `docker desktop restart` (crasht)
        Der persistente Weg ist Settings -> Docker Engine (JSON-Box). Das kann ein Skript
        nicht zuverlässig automatisieren -> diese Funktion CHECKT nur und ANLEITET.

        Swarm-Kontext: `docker stack deploy` ignoriert deploy.resources...devices
        ("Additional property devices is not allowed"), daher ist `default-runtime: nvidia`
        (jeder Container = nvidia-Runtime, inkl. Swarm-Tasks) der Standard-Workaround.
        Plain `docker run --gpus all` geht auf Docker Desktop OHNE daemon-Edit (Plumbing
        ist im WSL2-Daemon vorinstalliert, live verifiziert).

        Verhalten: GPU erkannt + Runtime schon nvidia -> $env:VIBEMIND_GPU_DEVICES=all,
        fertig. GPU erkannt, Runtime NOCH NICHT nvidia -> klare kopierbare Anleitung,
        Start läuft WEITER (Stack auf CPU-Fallback, nichts bricht). Keine GPU -> still raus.
        Nutzt Write-Host (kontextunabhängig — beide Launcher haben eigene Write-*).
    #>
    param([switch]$DryRun)

    Write-Host "`n=== Phase 0.4: GPU-Setup-Check (CUDA-Embedder) ===" -ForegroundColor Cyan
    if ($env:VIBEMIND_NO_GPU -eq "1") {
        Write-Host "  VIBEMIND_NO_GPU=1 — GPU-Check uebersprungen (CPU-Embedder)" -ForegroundColor DarkYellow
        return
    }
    # 1. GPU am Host? nvidia-smi. Kein GPU -> still raus (portabel, GPU-lose Hosts unberührt).
    $hasGpu = $false; $smi = $null
    try {
        $smi = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0 -and $smi) { $hasGpu = $true }
    } catch {}
    if (-not $hasGpu) {
        Write-Host "  Keine NVIDIA-GPU erkannt — CPU-Embedder (kein GPU-Setup noetig)" -ForegroundColor DarkYellow
        return
    }
    Write-Host "  [OK] GPU erkannt: $(($smi | Select-Object -First 1).Trim())" -ForegroundColor Green

    # 2. Läuft Docker schon mit nvidia-Default-Runtime? Dann ist alles fertig.
    $liveRuntime = ""
    try { $liveRuntime = (docker info --format '{{.DefaultRuntime}}' 2>$null) } catch {}
    if ($liveRuntime -eq "nvidia") {
        Write-Host "  [OK] Docker-DefaultRuntime=nvidia — brain-core (Swarm-Task) bekommt die GPU" -ForegroundColor Green
        $env:VIBEMIND_GPU_DEVICES = "all"
        # RAM-Hinweis (CUDA-torch + Embedder brauchen Luft).
        Test-WslMemoryForGpu
        return
    }

    # 3. GPU da, aber Runtime noch runc -> ANLEITEN (nicht automatisch ändern/neustarten).
    Write-Host "  [INFO] Docker-DefaultRuntime='$liveRuntime' (nicht nvidia) — Swarm-Tasks sehen die GPU noch nicht." -ForegroundColor Yellow
    Write-Host "  Stack startet jetzt auf CPU-Fallback (nichts bricht). Fuer GPU EINMALIG einrichten:" -ForegroundColor Yellow
    Write-Host "    1) Docker Desktop -> Settings -> Docker Engine (JSON-Box)" -ForegroundColor Gray
    Write-Host "    2) folgende Keys ergaenzen, dann 'Apply & restart':" -ForegroundColor Gray
    Write-Host '       "runtimes": { "nvidia": { "path": "nvidia-container-runtime", "runtimeArgs": [] } },' -ForegroundColor DarkGray
    Write-Host '       "default-runtime": "nvidia"' -ForegroundColor DarkGray
    Write-Host "    3) Settings -> Resources: WSL-RAM auf >=8GB (CUDA-torch braucht Luft; aktuell oft 2GB)" -ForegroundColor Gray
    Write-Host "    4) danach Launcher erneut — dieser Check bestaetigt dann nvidia." -ForegroundColor Gray
    Write-Host "  (Plain 'docker run --gpus all' geht schon ohne das; default-runtime ist NUR fuer den Swarm-Stack noetig.)" -ForegroundColor DarkGray
    Test-WslMemoryForGpu
    # $env:VIBEMIND_GPU_DEVICES bleibt leer -> Stack-File faellt auf CPU zurück (kein Bruch).
}

function Test-WslMemoryForGpu {
    <# WSL2-VM-RAM für CUDA-torch+Embedder prüfen. WICHTIG: bei WSL2-Backend gewinnt
       ~/.wslconfig [wsl2]memory=, NICHT der MemoryMiB-Wert in Docker-Desktop-settings-store
       (der ist dort oft veraltet/ignoriert — 2026-06-20 verifiziert: store sagte 2048,
       .wslconfig sagte 12GB, real galten 12GB). Also .wslconfig lesen. <8GB = knapp. #>
    try {
        $wslcfg = Join-Path $env:USERPROFILE ".wslconfig"
        if (Test-Path $wslcfg) {
            $line = Select-String -Path $wslcfg -Pattern '^\s*memory\s*=\s*(\d+)\s*([GMgm]B)' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($line) {
                $val = [int]$line.Matches[0].Groups[1].Value
                $unit = $line.Matches[0].Groups[2].Value.ToUpper()
                $gb = if ($unit -eq "GB") { $val } else { [math]::Round($val / 1024, 1) }
                if ($gb -lt 8) {
                    Write-Host "  [WARN] WSL-RAM (.wslconfig) = ${gb}GB (<8GB) — CUDA-torch+Embedder koennen OOM-en." -ForegroundColor DarkYellow
                } else {
                    Write-Host "  [OK] WSL-RAM (.wslconfig) = ${gb}GB — reicht fuer CUDA-Embedder" -ForegroundColor Green
                }
            }
        }
        # kein .wslconfig oder kein memory= -> WSL nutzt Default (50% des Host-RAM), meist genug; still.
    } catch {}
}
