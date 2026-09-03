<#
.SYNOPSIS
    VibeMind process control TUI — track & kill exactly the processes the
    debug launcher owns, plus orphans/duplicates it can't see.
.DESCRIPTION
    Standalone. Does NOT need Vibemind.debug.ps1 running. Merges three views:
      1. logs/services.registry.jsonl  — what the launcher spawned (PID + port)
      2. live Get-NetTCPConnection on every vibemind.config.json port
      3. heuristic scan of vibemind python/node procs that bind no port
         (catches the hung pyenv-vs-.venv duplicate workers)

    Flags rows:
      DUP    same service name owns >1 live PID (pyenv/.venv double-spawn)
      ORPHAN registered/expected but its port has no listener
      ZOMBIE vibemind python/node proc holding no expected port
      EXTERN port held by a non-vibemind process (informational)

    Keys: <n> select row | k kill | t tree-kill | K kill ALL flagged
          a kill ALL vibemind | r refresh | q quit
.PARAMETER Once
    Print the table once and exit (no interactive loop). For scripting.
.PARAMETER KillFlagged
    Non-interactive: tree-kill every flagged (DUP/ORPHAN/ZOMBIE) row, then exit.
#>
param(
    [switch]$Once,
    [switch]$KillFlagged
)

$ErrorActionPreference = "Continue"
$ROOT          = Split-Path -Parent $MyInvocation.MyCommand.Path
$CONFIG_FILE   = Join-Path $ROOT "vibemind.config.json"
$REGISTRY_FILE = Join-Path $ROOT "logs\services.registry.jsonl"

if (-not (Test-Path $CONFIG_FILE)) {
    Write-Host "  [ERROR] vibemind.config.json not found at $CONFIG_FILE" -ForegroundColor Red
    exit 1
}
$CONFIG = Get-Content $CONFIG_FILE -Raw | ConvertFrom-Json

# Friendly display names keyed by config port-property name.
$PORT_LABELS = @{
    brain_dashboard = "Brain Dashboard"; brain_api = "Brain API"
    brain_unified = "Brain Unified"; brain_memory = "Brain Memory"
    bridge = "Bridge"; openfang = "OpenFang"; moire_server = "MoireServer"
    electron_devtools = "Voice Electron"; minibook_backend = "Minibook"
    minibook_frontend = "Minibook FE"; mirofish = "MiroFish"
    automation_backend = "Automation BE"; automation_frontend = "Automation FE"
    automation_voice = "Automation Voice"; coding_api = "Coding Engine"
    coding_frontend = "Coding Frontend"; la_fungus_api = "La-Fungus"
    openclaw_gateway = "OpenClaw"; n8n = "n8n"; agentfarm_server = "AgentFarm"
    agentfarm_ui = "AgentFarm UI"; rowboat = "Rowboat"; media_server = "Media Server"
}

# Precise signature for a *vibemind service* command line. Deliberately
# narrow: it must name a known service entrypoint. Generic python.exe with
# no service signature is NOT listed (avoids hoovering up unrelated python:
# MCP proxies, claude-code helpers, other venvs). The launcher registry is
# the authoritative source; this regex only backstops un-registered procs.
$SERVICE_SIG = 'web\.brain_server|web[/\\]brain_server|production[/\\]api_server\.py|bridge\.main|bridge[/\\]main|embeddinggemma\.realtime|la-fungus|electron-app[/\\]node_modules[/\\]electron|moire_tracker|automation_ui[/\\]backend[/\\]server\.py|electron_debug_agent\.py'

# Map a service command line to its canonical config-port name.
function Resolve-ServiceName {
    param([string]$Cmd)
    if (-not $Cmd) { return $null }
    if ($Cmd -match 'web\.brain_server|web[/\\]brain_server') { return 'brain_dashboard' }
    if ($Cmd -match 'production[/\\]api_server\.py')          { return 'brain_api' }
    if ($Cmd -match 'bridge\.main|bridge[/\\]main')           { return 'bridge' }
    if ($Cmd -match 'embeddinggemma\.realtime|la-fungus')     { return 'la_fungus' }
    if ($Cmd -match 'automation_ui[/\\]backend[/\\]server\.py') { return 'automation_backend' }
    if ($Cmd -match 'electron_debug_agent\.py')               { return 'debug_agent' }
    if ($Cmd -match 'moire_tracker')                          { return 'moire_server' }
    if ($Cmd -match 'electron-app[/\\]node_modules[/\\]electron') { return 'voice_electron' }
    return $null
}

# True only for a recognised vibemind service: registered PID, repo-rooted
# path, OR a command line matching $SERVICE_SIG. Not "any python in the repo".
function Test-IsVibemindProc {
    param($Proc, [string]$CmdLine, [bool]$Registered = $false)
    if ($Registered) { return $true }
    if ($CmdLine -and $CmdLine -match $SERVICE_SIG) { return $true }
    try { if ($Proc -and $Proc.Path -and $Proc.Path -like "$ROOT*") { return $true } } catch {}
    return $false
}

function Get-CmdLine {
    param([int]$ProcId)
    try {
        $c = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue
        return $c.CommandLine
    } catch { return $null }
}

function Get-RuntimeHint {
    param([string]$Cmd, $Proc)
    if (-not $Cmd -and $Proc) { try { $Cmd = $Proc.Path } catch {} }
    if ($Cmd -match '\.venv312')           { return 'voicevenv' }
    if ($Cmd -match '\\\.venv\\|\.venv\\Scripts') { return '.venv' }
    if ($Cmd -match 'pyenv')               { return 'pyenv' }
    if ($Cmd -match 'electron\.exe')       { return 'electron' }
    if ($Cmd -match 'node\.exe|\\npm')     { return 'node' }
    if ($Cmd -match 'openfang')            { return 'native' }
    if ($Cmd -match 'python')              { return 'python' }
    return 'other'
}

# ── Collect: build one row list from registry + live ports + heuristic ──
function Get-ProcRows {
    $rows = New-Object System.Collections.ArrayList

    # (1) Registry — what the launcher spawned this session
    $registered = @{}    # pid -> @{name;port;runtime}
    if (Test-Path $REGISTRY_FILE) {
        Get-Content $REGISTRY_FILE -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $_.Trim()) { return }
            try {
                $r = $_ | ConvertFrom-Json
                # last write wins per pid (a service may re-register)
                if ($r.pid -and $r.pid -gt 0) {
                    $registered[[int]$r.pid] = @{ name = $r.name; port = [int]$r.port; runtime = $r.runtime }
                }
            } catch {}
        }
    }

    # (2) Live listeners on every config port
    $seenPids = @{}
    foreach ($pp in $CONFIG.ports.PSObject.Properties) {
        $port = [int]$pp.Value
        $key  = $pp.Name
        if ($port -le 0) { continue }
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        $label = if ($PORT_LABELS.ContainsKey($key)) { $PORT_LABELS[$key] } else { $key }
        # Canonical identity = the config port-key. Whatever process holds a
        # vibemind service port IS that service — even a stray pyenv worker.
        # That is precisely the identity we need so the DUP grouping (which
        # keys on Name) catches the pyenv-vs-.venv double-spawn.
        $isServicePort = $PORT_LABELS.ContainsKey($key)
        if ($conn) {
            $procId = [int]$conn.OwningProcess
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            $cmd  = Get-CmdLine $procId
            $reg  = $registered[$procId]
            # On a known service port the listener is ours by definition.
            # Off a service port (docker-published infra), judge by signature.
            $ours = if ($isServicePort) { $true }
                    else { Test-IsVibemindProc -Proc $proc -CmdLine $cmd -Registered ([bool]$reg) }
            $name = if ($isServicePort) { $key }
                    elseif ($reg) { $reg.name }
                    else { $label }
            $flag = ''
            if (-not $isServicePort) {
                # Docker infra ports (postgres/redis/gitea) — list quietly.
                $flag = if ($ours) { '' } else { 'infra' }
            }
            $null = $rows.Add([pscustomobject]@{
                Name    = $name
                Port    = $port
                PID     = $procId
                Runtime = Get-RuntimeHint -Cmd $cmd -Proc $proc
                Listen  = $true
                Ours    = $ours
                Reg     = [bool]$reg
                Cmd     = $cmd
                Flag    = $flag
            })
            $seenPids[$procId] = $true
        } else {
            # Expected service whose port is dead — only flag ORPHAN if the
            # launcher actually registered something for this port.
            $regForPort = $registered.GetEnumerator() | Where-Object { $_.Value.port -eq $port } | Select-Object -First 1
            if ($regForPort) {
                $rp = $regForPort.Value
                $null = $rows.Add([pscustomobject]@{
                    Name = $rp.name; Port = $port; PID = [int]$regForPort.Key
                    Runtime = $rp.runtime; Listen = $false; Ours = $true; Reg = $true
                    Cmd = ""; Flag = 'ORPHAN'
                })
            }
        }
    }

    # (3) Heuristic — vibemind SERVICE procs that bind NO expected port
    #     (the hung pyenv/.venv workers that never reach uvicorn serve).
    #     Strictly $SERVICE_SIG or registered: generic python.exe is ignored
    #     so we never list unrelated python (MCP proxies, claude-code, etc.).
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        $procId = [int]$_.ProcessId
        if ($seenPids.ContainsKey($procId)) { return }
        $cmd = $_.CommandLine
        $reg = $registered[$procId]
        $sig = $cmd -and ($cmd -match $SERVICE_SIG)
        if (-not $reg -and -not $sig) { return }   # not a known service → skip
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        $nm = if ($reg) { $reg.name } else { Resolve-ServiceName $cmd }
        if (-not $nm) { $nm = 'service?' }
        $null = $rows.Add([pscustomobject]@{
            Name = $nm; Port = 0; PID = $procId
            Runtime = Get-RuntimeHint -Cmd $cmd -Proc $proc
            Listen = $false; Ours = $true; Reg = [bool]$reg
            Cmd = $cmd
            Flag = 'ZOMBIE'   # a service proc with no port = stuck/dead spawn
        })
    }

    # (3.5) Containerised vibemind services. Phase A runs the Brain as the
    #       `vibemind-brain` compose project; more services follow in Phase B.
    #       A registry entry with pid 0 + runtime=container means "track by
    #       container, not PID". Surface the real container state so a
    #       crash/restart loop (e.g. missing torch) is visible, not silent.
    $containerNames = @{}   # registry: container-tracked service names
    if (Test-Path $REGISTRY_FILE) {
        Get-Content $REGISTRY_FILE -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $_.Trim()) { return }
            try {
                $r = $_ | ConvertFrom-Json
                if ($r.runtime -eq 'container') { $containerNames[$r.name] = [int]$r.port }
            } catch {}
        }
    }
    try {
        $psLines = docker ps -a --filter "name=vibemind-" --format "{{.Names}}|{{.Status}}|{{.Ports}}" 2>$null
        foreach ($pl in @($psLines)) {
            if (-not $pl) { continue }
            $parts = $pl -split '\|', 3
            $cname = $parts[0]; $cstat = $parts[1]; $cports = $parts[2]
            # Derive published host port (first "0.0.0.0:NNNN->")
            $cport = 0
            if ($cports -match '0\.0\.0\.0:(\d+)->') { $cport = [int]$Matches[1] }
            # Container state → flag. Running = ok; Restarting/Exited = the
            # symptom we want loud.
            $cflag = ''
            if     ($cstat -match '^Up')          { $cflag = '' }
            elseif ($cstat -match 'Restarting')   { $cflag = 'RESTART' }
            elseif ($cstat -match 'Exited|Dead')  { $cflag = 'EXITED' }
            else                                  { $cflag = 'CTR?' }
            $health = if ($cstat -match '\(healthy\)') { 'healthy' }
                      elseif ($cstat -match '\(unhealthy\)') { 'unhealthy' }
                      elseif ($cstat -match 'health: starting') { 'starting' }
                      else { '' }
            # Map to canonical service name if this is a known port.
            $cnm = $cname
            foreach ($pp in $CONFIG.ports.PSObject.Properties) {
                if ([int]$pp.Value -eq $cport -and $cport -gt 0) { $cnm = $pp.Name; break }
            }
            $rtLabel = if ($health) { "ctr:$health" } else { 'container' }
            $null = $rows.Add([pscustomobject]@{
                Name = $cnm; Port = $cport; PID = 0
                Runtime = $rtLabel; Listen = ($cstat -match '^Up')
                Ours = $true; Reg = $containerNames.ContainsKey($cnm)
                Cmd = "docker:$cname"
                Flag = $cflag
            })
        }
    } catch {}

    # (4) Duplicate detection — same Name with >1 live PID = the core
    #     pyenv-vs-.venv double-spawn bug. A listening row + zombie rows of
    #     the same service all get DUP so the user can cull the extras.
    #     Container rows (PID 0) are excluded from DUP grouping below.
    $byName = $rows | Where-Object { $_.PID -gt 0 -and $_.Ours -and $_.Name -ne 'service?' } | Group-Object Name
    foreach ($g in $byName) {
        if ($g.Count -gt 1) {
            foreach ($r in $g.Group) {
                if ($r.Flag -in '', 'ZOMBIE') { $r.Flag = 'DUP' }
            }
        }
    }

    # Friendly display label (Name stays the canonical key for grouping).
    foreach ($r in $rows) {
        $disp = if ($PORT_LABELS.ContainsKey($r.Name)) { $PORT_LABELS[$r.Name] } else { $r.Name }
        Add-Member -InputObject $r -NotePropertyName Disp -NotePropertyValue $disp -Force
    }

    # Stable sort: flagged first, then by name, then port.
    return $rows | Sort-Object @{E={ if ($_.Flag) {0} else {1} }}, Name, Port
}

function Show-Table {
    param($Rows)
    # Clear-Host pokes $RawUI.CursorPosition which throws in a non-interactive
    # host (piped / redirected). Guard it so -Once works anywhere.
    try { Clear-Host } catch {}
    Write-Host ""
    Write-Host "  ===============================================================================" -ForegroundColor Cyan
    Write-Host "    VibeMind Process Control          $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
    Write-Host "  ===============================================================================" -ForegroundColor Cyan
    Write-Host ""
    $hdr = "  {0,-3} {1,-18} {2,-6} {3,-7} {4,-10} {5,-7} {6}" -f '#','Service','Port','PID','Runtime','Listen','Flag'
    Write-Host $hdr -ForegroundColor DarkGray
    Write-Host ("  " + ("-" * 75)) -ForegroundColor DarkGray
    $i = 0
    foreach ($r in $Rows) {
        $i++
        $listenTxt = if ($r.Port -eq 0) { '-' } elseif ($r.Listen) { 'yes' } else { 'NO' }
        $color = switch ($r.Flag) {
            'DUP'     { 'Yellow' }
            'ORPHAN'  { 'Red' }
            'ZOMBIE'  { 'Magenta' }
            'RESTART' { 'Red' }
            'EXITED'  { 'Magenta' }
            'CTR?'    { 'Yellow' }
            'EXTERN'  { 'DarkGray' }
            'PROXY'   { 'DarkGray' }
            default   { if ($r.Listen) { 'Green' } else { 'Gray' } }
        }
        $line = "  {0,-3} {1,-18} {2,-6} {3,-7} {4,-10} {5,-7} {6}" -f `
            $i, $r.Disp, $(if($r.Port){":$($r.Port)"}else{'-'}), $r.PID, $r.Runtime, $listenTxt, $r.Flag
        Write-Host $line -ForegroundColor $color
    }
    Write-Host ""
    Write-Host "  Flags: DUP=double-spawn  ORPHAN=port dead  ZOMBIE=svc w/o port  RESTART/EXITED=container down  EXTERN=foreign  infra=docker" -ForegroundColor DarkGray
    # Process flags are bulk-killable (K). Container flags are diagnostic —
    # a RESTART loop wants its CAUSE inspected (logs), not a blind rm -f, so
    # they're surfaced separately and excluded from bulk kill.
    $flagged = @($Rows | Where-Object { $_.Flag -in 'DUP','ORPHAN','ZOMBIE' })
    $ctrBad  = @($Rows | Where-Object { $_.Flag -in 'RESTART','EXITED','CTR?' })
    Write-Host ("  Bulk-killable (K): {0}   Container issues: {1}   Total: {2}" -f `
        $flagged.Count, $ctrBad.Count, $Rows.Count) -ForegroundColor DarkGray
    if ($ctrBad.Count -gt 0) {
        Write-Host ("  ! container(s) down: {0} — inspect logs (docker logs <name>), single-kill 't' to rm" -f `
            (($ctrBad | ForEach-Object { $_.Disp }) -join ', ')) -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  Keys: " -NoNewline -ForegroundColor White
    Write-Host "<n>" -NoNewline -ForegroundColor Cyan; Write-Host " select  " -NoNewline
    Write-Host "k" -NoNewline -ForegroundColor Cyan; Write-Host " kill  " -NoNewline
    Write-Host "t" -NoNewline -ForegroundColor Cyan; Write-Host " tree-kill  " -NoNewline
    Write-Host "K" -NoNewline -ForegroundColor Cyan; Write-Host " kill ALL flagged  " -NoNewline
    Write-Host "r" -NoNewline -ForegroundColor Cyan; Write-Host " refresh  " -NoNewline
    Write-Host "q" -NoNewline -ForegroundColor Cyan; Write-Host " quit"
    Write-Host ""
}

function Stop-Row {
    param($Row, [switch]$Tree)
    if (-not $Row) { return }
    # Container rows (PID 0, Cmd="docker:<name>") — stop via docker, not kill.
    if ($Row.Cmd -and $Row.Cmd -match '^docker:(.+)$') {
        $cname = $Matches[1]
        if ($Tree) {
            docker rm -f $cname 2>&1 | Out-Null
            Write-Host "  docker rm -f $cname" -ForegroundColor Yellow
        } else {
            docker stop $cname 2>&1 | Out-Null
            Write-Host "  docker stop $cname (use tree-kill 't' to rm -f)" -ForegroundColor Yellow
        }
        return
    }
    if ($Row.PID -le 0) {
        Write-Host "  (row has no killable PID — container not yet tracked?)" -ForegroundColor DarkYellow
        return
    }
    $procId = [int]$Row.PID
    # Self-protection: never kill this TUI or its parent shell. A /T tree-kill
    # of an ancestor would take us down too.
    if ($procId -eq $PID) {
        Write-Host "  refusing to kill self (PID $procId)" -ForegroundColor Red
        return
    }
    try {
        $myParent = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction SilentlyContinue).ParentProcessId
        if ($myParent -and $procId -eq [int]$myParent) {
            Write-Host "  refusing to kill parent shell (PID $procId)" -ForegroundColor Red
            return
        }
    } catch {}
    $alive = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $alive) {
        Write-Host "  PID $procId already gone." -ForegroundColor DarkGray
        return
    }
    if ($Tree) {
        & taskkill.exe /F /T /PID $procId 2>&1 | Out-Null
        Write-Host "  tree-killed $($Row.Name) PID=$procId (+children)" -ForegroundColor Yellow
    } else {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 150
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            & taskkill.exe /F /PID $procId 2>&1 | Out-Null
        }
        Write-Host "  killed $($Row.Name) PID=$procId" -ForegroundColor Yellow
    }
}

# ── Non-interactive modes ──────────────────────────────────────────
if ($KillFlagged) {
    $rows = Get-ProcRows
    $flagged = @($rows | Where-Object { $_.Flag -in 'DUP','ORPHAN','ZOMBIE' })
    if ($flagged.Count -eq 0) { Write-Host "  Nothing flagged. Clean." -ForegroundColor Green; exit 0 }
    Write-Host "  Tree-killing $($flagged.Count) flagged process(es)..." -ForegroundColor Yellow
    foreach ($r in $flagged) { Stop-Row -Row $r -Tree }
    exit 0
}
if ($Once) {
    Show-Table -Rows (Get-ProcRows)
    exit 0
}

# ── Interactive loop ───────────────────────────────────────────────
$selected = $null
while ($true) {
    $rows = @(Get-ProcRows)
    Show-Table -Rows $rows
    if ($selected -ge 1 -and $selected -le $rows.Count) {
        $sr = $rows[$selected - 1]
        Write-Host "  Selected #$selected → $($sr.Disp) PID=$($sr.PID) [$($sr.Flag)]" -ForegroundColor Cyan
    }
    Write-Host "  > " -NoNewline -ForegroundColor White
    $in = Read-Host
    $in = $in.Trim()
    if ($in -eq 'q') { Write-Host "  bye." -ForegroundColor Gray; break }
    elseif ($in -eq 'r') { $selected = $null; continue }
    elseif ($in -match '^\d+$') {
        $n = [int]$in
        if ($n -ge 1 -and $n -le $rows.Count) { $selected = $n }
        else { Write-Host "  out of range" -ForegroundColor DarkYellow; Start-Sleep 1 }
    }
    elseif ($in -eq 'k' -or $in -eq 't') {
        if ($selected -ge 1 -and $selected -le $rows.Count) {
            Stop-Row -Row $rows[$selected - 1] -Tree:($in -eq 't')
            $selected = $null
            Start-Sleep -Milliseconds 700
        } else { Write-Host "  select a row first (type its number)" -ForegroundColor DarkYellow; Start-Sleep 1 }
    }
    elseif ($in -eq 'K') {
        $flagged = @($rows | Where-Object { $_.Flag -in 'DUP','ORPHAN','ZOMBIE' })
        if ($flagged.Count -eq 0) { Write-Host "  nothing flagged" -ForegroundColor DarkGray; Start-Sleep 1; continue }
        Write-Host "  Tree-kill $($flagged.Count) flagged process(es)? [y/N] " -NoNewline -ForegroundColor Yellow
        if ((Read-Host) -eq 'y') {
            foreach ($r in $flagged) { Stop-Row -Row $r -Tree }
            $selected = $null
            Start-Sleep -Milliseconds 900
        }
    }
    elseif ($in -eq 'a') {
        $ours = @($rows | Where-Object { $_.Ours -and $_.PID -gt 0 })
        Write-Host "  Tree-kill ALL $($ours.Count) vibemind process(es)? [y/N] " -NoNewline -ForegroundColor Red
        if ((Read-Host) -eq 'y') {
            foreach ($r in $ours) { Stop-Row -Row $r -Tree }
            $selected = $null
            Start-Sleep -Milliseconds 900
        }
    }
    else { Write-Host "  unknown key" -ForegroundColor DarkYellow; Start-Sleep 1 }
}
