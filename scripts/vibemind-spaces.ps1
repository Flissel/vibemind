<#
.SYNOPSIS
    Manage the active Space selection for the VibeMind swarm stack.
.DESCRIPTION
    Companion to vibemind-start.ps1 / vibemind-stop.ps1. Lets the user
    toggle individual spaces (coding, mirofish, n8n, media, logging,
    core-phase-d) on/off WITHOUT tearing the whole stack down.

    Core (Brain + Rowboat + Qdrant + Supabase + neo4j-mirofish) is ALWAYS
    deployed; only the per-space service groups change.

    Persistent state: $env:USERPROFILE\.vibemind\launcher-state.json
        { "spaces": ["coding", "n8n"] }

    Ground truth = `docker stack services` (the state file is just a
    convenience for the UI; toggle merges into it). If the file is
    missing or invalid, defaults to no spaces (core only).

.PARAMETER Action
    list    -> JSON output: every known space + its current replicas counts
    state   -> print persistent state
    toggle  -> turn one space on/off + re-deploy
.PARAMETER Space
    Required for "toggle". One of: coding, mirofish, n8n, media, logging,
    core-phase-d.
.PARAMETER On
    Required for "toggle". "on" or "off".
.EXAMPLE
    .\scripts\vibemind-spaces.ps1 list
    .\scripts\vibemind-spaces.ps1 toggle n8n on
    .\scripts\vibemind-spaces.ps1 toggle coding off
#>
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet("list", "state", "toggle", "apply", "core-status", "presets-list", "presets-save", "presets-delete")]
    [string]$Action,

    # Position-1: for toggle = space-name; for presets-save/delete = preset-name; for apply = csv of spaces
    [Parameter(Position = 1)]
    [string]$Arg1 = "",

    # Position-2: for toggle = on|off; for presets-save = csv of spaces
    [Parameter(Position = 2)]
    [string]$Arg2 = ""
)

$ErrorActionPreference = "Stop"

$script:ROOT      = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script:STACK     = Join-Path $script:ROOT "infra\swarm\vibemind-stack.yml"
$script:STATE_DIR = Join-Path $env:USERPROFILE ".vibemind"
$script:STATE     = Join-Path $script:STATE_DIR "launcher-state.json"
$script:PRESETS   = Join-Path $script:STATE_DIR "presets.json"

. (Join-Path $PSScriptRoot 'lib\vibemind-helpers.ps1')

# Every space known to the UI. The label is what the user sees; profile is
# the yaml profile name; svcPattern matches stack-services output. These are
# kept in lockstep with vibemind-stack.yml profiles: declarations.
$script:KNOWN_SPACES = @(
    @{ name = "coding";        profile = "space-coding";    services = @("coding-postgres","coding-redis","gitea-postgres","coding-gitea","coding-vscode","coding-egress-proxy","coding-api","coding-worker","coding-openclaude","coding-frontend") }
    @{ name = "mirofish";      profile = "space-mirofish";  services = @("mirofish") }
    @{ name = "n8n";           profile = "space-n8n";       services = @("n8n") }
    @{ name = "media";         profile = "space-media";     services = @("media") }
    @{ name = "logging";       profile = "space-logging";   services = @("loki","promtail","grafana-vibemind") }
    @{ name = "core-phase-d";  profile = "core-phase-d";    services = @("brain-learner","brain-inference") }
)

# Core-service inventory for the launcher UI core-panel. Ports + URLs verified
# against vibemind-stack.yml (containers) and vibemind-start.ps1 (native). kind:
#   container = under `vibemind_<name>` in `docker stack services`
#   native    = launched by vibemind-start.ps1 Phase 0.5/1.5/3 (not in stack)
# health_url is what `Test-HttpHealth` polls. user_url is the browser-openable
# URL for the quick-link arrow (empty string = no UI, hide the arrow).
$script:CORE_SERVICES = @(
    # === Container core ===
    @{ name = "qdrant";              kind = "container"; port = 6730;  health_url = "http://localhost:6730/healthz";          user_url = "" }
    @{ name = "brain-core";          kind = "container"; port = 5000;  health_url = "http://localhost:5000/api/health";       user_url = "http://localhost:5000" }
    @{ name = "brain-api";           kind = "container"; port = 5001;  health_url = "http://localhost:5001/health";           user_url = "" }
    @{ name = "brain-autotrain-drain"; kind = "container"; port = 0;   health_url = "";                                       user_url = "" }
    @{ name = "rowboat";             kind = "container"; port = 3100; health_url = "http://localhost:3100/";                  user_url = "http://localhost:3100" }
    @{ name = "rowboat-agents";      kind = "container"; port = 3101; health_url = "http://localhost:3101/health";            user_url = "" }
    @{ name = "rowboat-mongo";       kind = "container"; port = 27017; health_url = "";                                       user_url = "" }
    @{ name = "rowboat-redis";       kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "rowboat-jobs-worker"; kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "neo4j-mirofish";      kind = "container"; port = 7475; health_url = "http://localhost:7475/";                  user_url = "http://localhost:7475" }
    @{ name = "supabase-db";         kind = "container"; port = 54322; health_url = "";                                       user_url = "" }
    @{ name = "supabase-kong";       kind = "container"; port = 54321; health_url = "http://localhost:54321/";                user_url = "http://localhost:54321" }
    @{ name = "supabase-studio";     kind = "container"; port = 54323; health_url = "http://localhost:54323/";                user_url = "http://localhost:54323" }
    @{ name = "supabase-auth";       kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-rest";       kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-realtime";   kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-storage";    kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-pg-meta";    kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-analytics";  kind = "container"; port = 0;    health_url = "";                                        user_url = "" }
    @{ name = "supabase-inbucket";   kind = "container"; port = 54324; health_url = "";                                       user_url = "http://localhost:54324" }
    # === Native (started by vibemind-start.ps1) ===
    @{ name = "openfang";            kind = "native";    port = 4200; health_url = "http://localhost:4200/api/health";        user_url = "http://localhost:4200" }
    @{ name = "ollama";              kind = "native";    port = 11434; health_url = "http://localhost:11434/api/version";    user_url = "" }
    @{ name = "bridge";              kind = "native";    port = 5150; health_url = "http://localhost:5150/bridge/health";     user_url = "" }
    @{ name = "la-fungus";           kind = "native";    port = 8011; health_url = "";                                        user_url = "" }
    @{ name = "automation-ui";       kind = "native";    port = 8007; health_url = "http://localhost:8007/api/health";        user_url = "" }
)

# Defaults seeded into ~/.vibemind/presets.json on first list. User can save
# additional presets via presets-save; these three are NOT special — they can
# be overwritten by a user-save with the same name.
$script:DEFAULT_PRESETS = @(
    @{ name = "minimal"; spaces = @() }
    @{ name = "dev";     spaces = @("coding") }
    @{ name = "all";     spaces = @("coding","mirofish","n8n","media","logging") }
)

function Get-State {
    if (-not (Test-Path $script:STATE)) { return @{ spaces = @() } }
    try {
        $obj = Get-Content $script:STATE -Raw | ConvertFrom-Json
        if ($null -eq $obj.spaces) { return @{ spaces = @() } }
        return @{ spaces = @($obj.spaces) }
    } catch {
        return @{ spaces = @() }
    }
}

function Save-State {
    param([string[]]$Spaces)
    if (-not (Test-Path $script:STATE_DIR)) {
        New-Item -ItemType Directory -Path $script:STATE_DIR -Force | Out-Null
    }
    @{ spaces = @($Spaces) } | ConvertTo-Json -Compress | Set-Content -Path $script:STATE -Encoding utf8
}

function Get-StackServiceMap {
    # Returns @{ "service-name" = "have/want" } from docker stack services.
    # Empty hashtable if the stack doesn't exist.
    $map = @{}
    $out = docker stack services --format "{{.Name}} {{.Replicas}}" vibemind 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $map }
    foreach ($line in @($out)) {
        if ($line -match '^vibemind_(\S+)\s+(\d+/\d+)') {
            $map[$Matches[1]] = $Matches[2]
        }
    }
    return $map
}

function Invoke-ListAction {
    $state = Get-State
    $svcMap = Get-StackServiceMap
    $result = New-Object System.Collections.Generic.List[object]
    foreach ($s in $script:KNOWN_SPACES) {
        $running = 0; $want = 0
        foreach ($svc in $s.services) {
            if ($svcMap.ContainsKey($svc)) {
                $parts = $svcMap[$svc].Split("/")
                $running += [int]$parts[0]
                $want    += [int]$parts[1]
            }
        }
        $enabled = $state.spaces -contains $s.name
        $result.Add([pscustomobject]@{
            name           = $s.name
            profile        = $s.profile
            enabled        = $enabled
            service_count  = $s.services.Count
            replicas_have  = $running
            replicas_want  = $want
            healthy        = ($want -gt 0 -and $running -eq $want)
        }) | Out-Null
    }
    $result | ConvertTo-Json -Depth 4 -Compress
}

function Invoke-StateAction {
    $state = Get-State
    $state | ConvertTo-Json -Depth 4
}

function Invoke-ToggleAction {
    $space = $Arg1; $on = $Arg2
    if (-not $space) { Write-Err "toggle requires <space>"; exit 1 }
    if ($on -notin @("on","off")) { Write-Err "toggle requires on|off as 2nd arg"; exit 1 }
    $known = $script:KNOWN_SPACES | Where-Object { $_.name -eq $space }
    if (-not $known) {
        $list = ($script:KNOWN_SPACES | ForEach-Object { $_.name }) -join ", "
        Write-Err "unknown space '$space' — known: $list"
        exit 1
    }
    $state = Get-State
    $current = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($s in $state.spaces) { $current.Add($s) | Out-Null }

    if ($on -eq "on") {
        if (-not $current.Add($space)) { Write-Warn "$space already enabled — re-deploying anyway" }
    } else {
        if (-not $current.Remove($space)) { Write-Warn "$space already disabled — re-deploying anyway" }
    }
    $newSpaces = @($current)
    Save-State -Spaces $newSpaces

    $spacesArg = $newSpaces -join ","
    Write-Phase "Toggle $space $on  -> deploying with spaces=[$spacesArg]"
    $ok = Invoke-FilteredStackDeploy -StackFile $script:STACK -Spaces $spacesArg
    if ($ok) {
        Write-Ok "deploy ok — active spaces: $($newSpaces -join ', ')"
    } else {
        Write-Err "deploy failed — state file rolled back"
        # Rollback state on deploy failure
        if ($on -eq "on") { $current.Remove($space) | Out-Null } else { $current.Add($space) | Out-Null }
        Save-State -Spaces @($current)
        exit 2
    }
}

# === New actions (Launcher v2) ===

function Get-StackContainerStatus {
    # Returns @{ "service-name" = $true } for every container that has at
    # least one running task. Used by core-status to distinguish containers
    # the Stack knows about + reports as up vs ones that are missing or 0/1.
    $map = @{}
    $out = docker stack services --format "{{.Name}} {{.Replicas}}" vibemind 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $map }
    foreach ($line in @($out)) {
        if ($line -match '^vibemind_(\S+)\s+(\d+)/(\d+)') {
            $name = $Matches[1]
            $have = [int]$Matches[2]
            $want = [int]$Matches[3]
            $map[$name] = ($want -gt 0 -and $have -eq $want)
        }
    }
    return $map
}

function Invoke-CoreStatusAction {
    $containerStatus = Get-StackContainerStatus
    $result = New-Object System.Collections.Generic.List[object]
    foreach ($s in $script:CORE_SERVICES) {
        $healthy = $false
        if ($s.kind -eq "container") {
            # Container: trust docker stack first; if Stack-up=$true but we
            # have a health URL, double-check (the container task may be up
            # but the app inside not yet ready).
            $stackOk = $containerStatus.ContainsKey($s.name) -and $containerStatus[$s.name]
            if ($stackOk -and $s.health_url) {
                $healthy = Test-HttpHealth -Url $s.health_url -TimeoutSec 1
            } else {
                $healthy = $stackOk
            }
        } else {
            # Native: HTTP probe if we have a URL, else TCP port-listen probe.
            if ($s.health_url) {
                $healthy = Test-HttpHealth -Url $s.health_url -TimeoutSec 1
            } elseif ($s.port -gt 0) {
                $healthy = -not (Test-PortFree -Port $s.port)
            }
        }
        $result.Add([pscustomobject]@{
            name        = $s.name
            kind        = $s.kind
            port        = $s.port
            health_url  = $s.health_url
            user_url    = $s.user_url
            healthy     = $healthy
        }) | Out-Null
    }
    $result | ConvertTo-Json -Depth 4 -Compress
}

function Get-Presets {
    if (-not (Test-Path $script:PRESETS)) {
        # Seed defaults on first call
        if (-not (Test-Path $script:STATE_DIR)) {
            New-Item -ItemType Directory -Path $script:STATE_DIR -Force | Out-Null
        }
        @{ presets = $script:DEFAULT_PRESETS } | ConvertTo-Json -Depth 4 |
            Set-Content -Path $script:PRESETS -Encoding utf8
        return $script:DEFAULT_PRESETS
    }
    try {
        $obj = Get-Content $script:PRESETS -Raw | ConvertFrom-Json
        if ($null -eq $obj.presets) { return @() }
        # Normalise into array of hashtables so callers see a stable shape
        return @($obj.presets | ForEach-Object {
            @{ name = $_.name; spaces = @($_.spaces) }
        })
    } catch {
        Write-Warn "presets.json malformed — returning empty list"
        return @()
    }
}

function Save-Presets {
    param([array]$Presets)
    if (-not (Test-Path $script:STATE_DIR)) {
        New-Item -ItemType Directory -Path $script:STATE_DIR -Force | Out-Null
    }
    @{ presets = $Presets } | ConvertTo-Json -Depth 4 |
        Set-Content -Path $script:PRESETS -Encoding utf8
}

function Invoke-PresetsListAction {
    $p = Get-Presets
    # Always emit a JSON array, even when empty
    if ($p.Count -eq 0) { "[]"; return }
    ConvertTo-Json -InputObject @($p) -Depth 4 -Compress
}

function Invoke-PresetsSaveAction {
    $name = $Arg1
    $spacesCsv = $Arg2
    if (-not $name) { Write-Err "presets-save requires <name>"; exit 1 }
    $spaces = @(ConvertTo-SpaceList -Spaces $spacesCsv)
    $existing = Get-Presets
    $kept = @($existing | Where-Object { $_.name -ne $name })
    $kept += @{ name = $name; spaces = $spaces }
    Save-Presets -Presets $kept
    Write-Ok "preset '$name' saved (spaces=[$($spaces -join ',')])"
}

function Invoke-PresetsDeleteAction {
    $name = $Arg1
    if (-not $name) { Write-Err "presets-delete requires <name>"; exit 1 }
    $existing = Get-Presets
    $kept = @($existing | Where-Object { $_.name -ne $name })
    if ($kept.Count -eq $existing.Count) {
        Write-Warn "preset '$name' not found — nothing to delete"
        return
    }
    Save-Presets -Presets $kept
    Write-Ok "preset '$name' deleted"
}

function Invoke-ApplyAction {
    # Deploy with the EXACT given space-csv, persist state, prune removed services.
    # Used by the UI's APPLY button (replaces multiple toggle calls).
    $spacesCsv = $Arg1
    $spaceList = ConvertTo-SpaceList -Spaces $spacesCsv
    Write-Phase "Apply spaces=[$($spaceList -join ',')]"
    $ok = Invoke-FilteredStackDeploy -StackFile $script:STACK -Spaces $spacesCsv
    if ($ok) {
        Save-State -Spaces @($spaceList)
        Write-Ok "apply ok — active spaces: $($spaceList -join ', ')"
    } else {
        Write-Err "apply failed — state file NOT updated"
        exit 2
    }
}

switch ($Action) {
    "list"            { Invoke-ListAction }
    "state"           { Invoke-StateAction }
    "toggle"          { Invoke-ToggleAction }
    "apply"           { Invoke-ApplyAction }
    "core-status"     { Invoke-CoreStatusAction }
    "presets-list"    { Invoke-PresetsListAction }
    "presets-save"    { Invoke-PresetsSaveAction }
    "presets-delete"  { Invoke-PresetsDeleteAction }
}
