<#
.SYNOPSIS
    VibeMind Interactive Setup Wizard
.DESCRIPTION
    Configures API keys, selects modules, creates venvs, installs dependencies.
    Inspired by OpenClaw's onboard flow.
.PARAMETER NonInteractive
    Skip prompts, use defaults
.PARAMETER SkipDocker
    Skip Docker prerequisite checks
.PARAMETER Force
    Overwrite existing configuration
#>
param(
    [switch]$NonInteractive,
    [switch]$SkipDocker,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$script:ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:CONFIG_FILE = Join-Path $ROOT "vibemind.config.json"
$script:ROOT_ENV = Join-Path $ROOT ".env"
$script:OS_ROOT = Join-Path $ROOT "vibemind-os"

# ── Colors ────────────────────────────────────────────────────────
function Write-Step  { param($n, $msg) Write-Host "`n[$n/8] " -ForegroundColor Cyan -NoNewline; Write-Host $msg -ForegroundColor White }
function Write-Ok    { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "  [ERROR] $msg" -ForegroundColor Red }
function Write-Info  { param($msg) Write-Host "  $msg" -ForegroundColor Gray }

# ═══════════════════════════════════════════════════════════════════
#  BANNER
# ═══════════════════════════════════════════════════════════════════
Clear-Host
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    VibeMind Setup Wizard" -ForegroundColor White
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "  Configure API keys, modules, and dependencies." -ForegroundColor Gray
Write-Host ""

# ═══════════════════════════════════════════════════════════════════
#  STEP 1: Prerequisites
# ═══════════════════════════════════════════════════════════════════
Write-Step 1 "Checking prerequisites..."

$prereqs = @{}
$critical = $true

# Docker
if (-not $SkipDocker) {
    try {
        $dv = (docker --version 2>&1) -replace 'Docker version ', '' -replace ',.*', ''
        Write-Ok "Docker $dv"
        $prereqs["docker"] = $true
        try {
            $dcv = (docker compose version 2>&1) -replace '.*v', ''
            Write-Ok "Docker Compose $dcv"
        } catch {
            Write-Warn "Docker Compose not found (docker compose plugin)"
        }
    } catch {
        Write-Warn "Docker not found -Docker modules will be unavailable"
        Write-Info "Install: https://docs.docker.com/desktop/install/windows-install/"
        $prereqs["docker"] = $false
    }
} else {
    Write-Info "Docker check skipped (-SkipDocker)"
    $prereqs["docker"] = $false
}

# Node.js
try {
    $nv = (node --version 2>&1) -replace 'v', ''
    $major = [int]($nv -split '\.')[0]
    if ($major -ge 18) { Write-Ok "Node.js $nv" } else { Write-Warn "Node.js $nv (>= 18 recommended)" }
    $prereqs["node"] = $true
} catch {
    Write-Err "Node.js not found -Voice and Automation_ui will not work"
    Write-Info "Install: https://nodejs.org/"
    $prereqs["node"] = $false
    $critical = $false
}

# Python
try {
    $pv = (python --version 2>&1) -replace 'Python ', ''
    $parts = $pv -split '\.'
    if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) { Write-Ok "Python $pv" } else { Write-Warn "Python $pv (>= 3.11 recommended)" }
    $prereqs["python"] = $true
} catch {
    Write-Err "Python not found -Brain, Bridge, La-Fungus will not work"
    Write-Info "Install: https://www.python.org/downloads/"
    $prereqs["python"] = $false
    $critical = $false
}

# Git
try {
    $gv = (git --version 2>&1) -replace 'git version ', ''
    Write-Ok "Git $gv"
    $prereqs["git"] = $true
} catch {
    Write-Warn "Git not found"
    $prereqs["git"] = $false
}

if (-not $critical) {
    Write-Err "Critical prerequisites missing (Node.js or Python). Install them and re-run."
    exit 1
}

# ═══════════════════════════════════════════════════════════════════
#  STEP 2: API Keys
# ═══════════════════════════════════════════════════════════════════
Write-Step 2 "Configuring API keys..."

# Load existing .env if present
$envMap = @{}
if (Test-Path $script:ROOT_ENV) {
    Get-Content $script:ROOT_ENV | ForEach-Object {
        if ($_ -match '^([^#]\S+?)=(.+)$') {
            $envMap[$Matches[1]] = $Matches[2]
        }
    }
    Write-Info "Loaded existing .env with $($envMap.Count) keys"
}

$keyDefs = @(
    @{ Name = "OPENROUTER_API_KEY";  Label = "OpenRouter API Key (recommended, all models)"; Prefix = "sk-or-";  Group = "required" }
    @{ Name = "OPENAI_API_KEY";      Label = "OpenAI API Key";                               Prefix = "sk-";     Group = "required" }
    @{ Name = "ANTHROPIC_API_KEY";   Label = "Anthropic API Key (Claude)";                   Prefix = "sk-ant-"; Group = "required" }
    @{ Name = "GROQ_API_KEY";        Label = "Groq API Key (free tier, fast)";               Prefix = "gsk_";    Group = "recommended" }
    @{ Name = "GITHUB_TOKEN";        Label = "GitHub Token (for Coding Engine)";             Prefix = "ghp_";    Group = "optional" }
    @{ Name = "DISCORD_BOT_TOKEN";   Label = "Discord Bot Token (notifications)";            Prefix = "";        Group = "optional" }
    @{ Name = "SUPERMEMORY_API_KEY"; Label = "Supermemory API Key (long-term memory)";       Prefix = "";        Group = "optional" }
    @{ Name = "GOOGLE_API_KEY";      Label = "Google API Key (Gemini)";                      Prefix = "AIza";    Group = "optional" }
)

$configured = @()

if (-not $NonInteractive) {
    Write-Host ""
    Write-Host "  Enter API keys (press Enter to skip, existing keys shown as ****):" -ForegroundColor Gray
    Write-Host ""

    $lastGroup = ""
    foreach ($kd in $keyDefs) {
        if ($kd.Group -ne $lastGroup) {
            $lastGroup = $kd.Group
            $groupLabel = switch ($kd.Group) { "required" { "REQUIRED (at least one)" } "recommended" { "RECOMMENDED" } "optional" { "OPTIONAL" } }
            Write-Host "  --- $groupLabel ---" -ForegroundColor DarkCyan
        }

        $existing = $envMap[$kd.Name]
        $prompt = "  $($kd.Label)"
        if ($existing) {
            $prompt += " [****$($existing.Substring([Math]::Max(0,$existing.Length-4)))]"
        }
        $prompt += ": "

        Write-Host $prompt -NoNewline -ForegroundColor White
        $val = Read-Host

        if ([string]::IsNullOrWhiteSpace($val)) {
            if ($existing) {
                $configured += $kd.Name
            }
        } else {
            $envMap[$kd.Name] = $val.Trim()
            $configured += $kd.Name
        }
    }
} else {
    # Non-interactive: use whatever is already in .env
    foreach ($kd in $keyDefs) {
        if ($envMap.ContainsKey($kd.Name) -and $envMap[$kd.Name]) { $configured += $kd.Name }
    }
}

# Validate at least one LLM key
$llmKeys = @("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
$hasLLM = $false
foreach ($k in $llmKeys) { if ($envMap.ContainsKey($k) -and $envMap[$k]) { $hasLLM = $true } }
if (-not $hasLLM) {
    Write-Err "No LLM API key configured. At least one of OPENROUTER, OPENAI, or ANTHROPIC is required."
    exit 1
}

# Write root .env
$envLines = @("# VibeMind Root Environment -Generated by setup.ps1", "# $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "")
foreach ($kv in $envMap.GetEnumerator() | Sort-Object Name) {
    $envLines += "$($kv.Name)=$($kv.Value)"
}
$envLines | Out-File -FilePath $script:ROOT_ENV -Encoding utf8
Write-Ok "Root .env written with $($envMap.Count) keys"

# ═══════════════════════════════════════════════════════════════════
#  STEP 3: Module Selection
# ═══════════════════════════════════════════════════════════════════
Write-Step 3 "Select modules to enable..."

$config = Get-Content $script:CONFIG_FILE -Raw | ConvertFrom-Json
$moduleIds = @("voice", "automation_ui", "coding_engine", "brain", "openfang", "la_fungus", "openclaw", "bridge")

if (-not $NonInteractive) {
    Write-Host ""
    Write-Host "  Toggle modules by number, Enter to confirm:" -ForegroundColor Gray
    Write-Host ""

    $done = $false
    while (-not $done) {
        $i = 1
        foreach ($id in $moduleIds) {
            $mod = $config.modules.$id
            $state = if ($mod.enabled) { "[X]" } else { "[ ]" }
            $color = if ($mod.enabled) { "Green" } else { "DarkGray" }
            Write-Host "    $i. $state $id" -ForegroundColor $color
            $i++
        }
        Write-Host ""
        Write-Host "  Number to toggle (Enter to confirm): " -NoNewline -ForegroundColor White
        $choice = Read-Host

        if ([string]::IsNullOrWhiteSpace($choice)) {
            $done = $true
        } elseif ($choice -match '^\d+$') {
            $idx = [int]$choice - 1
            if ($idx -ge 0 -and $idx -lt $moduleIds.Count) {
                $id = $moduleIds[$idx]
                $config.modules.$id.enabled = -not $config.modules.$id.enabled
            }
        }
        if (-not $done) { Write-Host "" }
    }
}

# Update configured keys
$config.apiKeys.configured = $configured
$config | ConvertTo-Json -Depth 5 | Out-File -FilePath $script:CONFIG_FILE -Encoding utf8
Write-Ok "Config saved to vibemind.config.json"

$enabledModules = $moduleIds | Where-Object { $config.modules.$_.enabled }
Write-Info "Enabled: $($enabledModules -join ', ')"

# ═══════════════════════════════════════════════════════════════════
#  STEP 4: Docker Check
# ═══════════════════════════════════════════════════════════════════
Write-Step 4 "Checking Docker..."

if ($prereqs["docker"]) {
    try {
        docker info 2>&1 | Out-Null
        Write-Ok "Docker Desktop is running"
    } catch {
        Write-Warn "Docker Desktop not running -start it before using Vibemind.debug.ps1"
    }
} else {
    Write-Info "Docker not available -Docker-based services will be skipped"
}

# ═══════════════════════════════════════════════════════════════════
#  STEP 5: Distribute .env to modules
# ═══════════════════════════════════════════════════════════════════
Write-Step 5 "Distributing API keys to modules..."

$envTemplates = @{
    "vibemind-os"      = @{ example = "vibemind-os/.env.example";                    target = "vibemind-os/.env" }
    "voice"            = @{ example = "vibemind-os/voice/.env.example";               target = "vibemind-os/voice/.env" }
    "brain"            = @{ example = "vibemind-os/brain/the_brain/.env.example";     target = "vibemind-os/brain/the_brain/.env" }
    "openfang"         = @{ example = "vibemind-os/openfang/.env.example";            target = "vibemind-os/openfang/.env" }
    "coding_engine"    = @{ example = "vibemind-os/coding-engine/.env.example";       target = "vibemind-os/coding-engine/.env" }
    "automation_ui"    = @{ example = "vibemind-os/spaces/desktop/Automation_ui/.env.example";         target = "vibemind-os/spaces/desktop/Automation_ui/.env" }
    "automation_be"    = @{ example = "vibemind-os/spaces/desktop/Automation_ui/backend/.env.example"; target = "vibemind-os/spaces/desktop/Automation_ui/backend/.env" }
    "bridge"           = @{ example = "vibemind-os/bridge/.env.example";              target = "vibemind-os/bridge/.env" }
}

foreach ($entry in $envTemplates.GetEnumerator()) {
    $exPath = Join-Path $ROOT $entry.Value.example
    $tgPath = Join-Path $ROOT $entry.Value.target

    if (-not (Test-Path $exPath)) { continue }
    if ((Test-Path $tgPath) -and -not $Force) {
        Write-Info "$($entry.Key): .env exists (use -Force to overwrite)"
        continue
    }

    $lines = Get-Content $exPath
    $output = @()
    foreach ($line in $lines) {
        if ($line -match '^([A-Z][A-Z0-9_]+)=(.*)$') {
            $key = $Matches[1]
            if ($envMap.ContainsKey($key) -and $envMap[$key]) {
                $output += "$key=$($envMap[$key])"
            } else {
                $output += $line
            }
        } else {
            $output += $line
        }
    }
    $output | Out-File -FilePath $tgPath -Encoding utf8
    Write-Ok "$($entry.Key): .env distributed"
}

# ═══════════════════════════════════════════════════════════════════
#  STEP 6: Python Venvs
# ═══════════════════════════════════════════════════════════════════
Write-Step 6 "Setting up Python virtual environments..."

if ($prereqs["python"]) {
    $venvDefs = @{
        "brain"     = @{ venv = "vibemind-os/brain/the_brain/.venv";       req = "vibemind-os/brain/the_brain/requirements.txt" }
        "la_fungus" = @{ venv = "vibemind-os/la-fungus-search/.venv";      req = "vibemind-os/la-fungus-search/requirements.txt" }
        "bridge"    = @{ venv = "vibemind-os/bridge/.venv";                req = "vibemind-os/bridge/requirements.txt" }
    }

    foreach ($entry in $venvDefs.GetEnumerator()) {
        $modId = $entry.Key
        if (-not $config.modules.$modId.enabled) { continue }

        $venvPath = Join-Path $ROOT $entry.Value.venv
        $reqPath  = Join-Path $ROOT $entry.Value.req

        if (Test-Path $venvPath) {
            Write-Info "${modId}: venv exists"
        } else {
            Write-Host "  Creating venv for $modId..." -ForegroundColor Gray -NoNewline
            python -m venv $venvPath 2>&1 | Out-Null
            Write-Host " done" -ForegroundColor Green
        }

        if (Test-Path $reqPath) {
            Write-Host "  Installing deps for ${modId}..." -ForegroundColor Gray -NoNewline
            $oldEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            # Install vibemind-shared from local source first
            $sharedPath = Join-Path $ROOT "vibemind-os/shared"
            if (Test-Path $sharedPath) {
                & "$venvPath/Scripts/pip" install -e $sharedPath -q 2>&1 | Out-Null
            }
            & "$venvPath/Scripts/pip" install -r $reqPath -q 2>&1 | Out-Null
            $ErrorActionPreference = $oldEAP
            Write-Host " done" -ForegroundColor Green
        }
    }

    # Voice uses .venv312 (requires Python 3.12)
    if ($config.modules.voice.enabled) {
        $voiceVenv = Join-Path $ROOT "vibemind-os/voice/.venv312"
        if (Test-Path $voiceVenv) {
            Write-Info "voice: venv312 exists"
        } else {
            Write-Host "  Creating venv312 for voice (Python 3.12)..." -ForegroundColor Gray -NoNewline
            try {
                $py312 = (py -3.12 -c "import sys; print(sys.executable)" 2>$null)
                if ($py312) {
                    & $py312 -m venv $voiceVenv 2>&1 | Out-Null
                    $oldEAP3 = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                    $sharedPath = Join-Path $ROOT "vibemind-os/shared"
                    if (Test-Path $sharedPath) {
                        & "$voiceVenv/Scripts/pip" install -e $sharedPath -q 2>&1 | Out-Null
                    }
                    $voiceReq = Join-Path $ROOT "vibemind-os/voice/requirements.txt"
                    if (Test-Path $voiceReq) {
                        & "$voiceVenv/Scripts/pip" install -r $voiceReq -q 2>&1 | Out-Null
                    }
                    $ErrorActionPreference = $oldEAP3
                    Write-Host " done" -ForegroundColor Green
                } else {
                    Write-Warn "Python 3.12 not found (py -3.12). Install from python.org"
                }
            } catch {
                Write-Warn "voice venv312 creation failed: $_"
            }
        }
    }
} else {
    Write-Warn "Python not available -skipping venv setup"
}

# ═══════════════════════════════════════════════════════════════════
#  STEP 7: Node Dependencies
# ═══════════════════════════════════════════════════════════════════
Write-Step 7 "Installing Node.js dependencies..."

if ($prereqs["node"]) {
    $npmDirs = @()
    if ($config.modules.voice.enabled) {
        $npmDirs += "vibemind-os/voice/electron-app"
    }
    if ($config.modules.automation_ui.enabled) {
        $npmDirs += "vibemind-os/spaces/desktop/Automation_ui"
    }

    foreach ($dir in $npmDirs) {
        $full = Join-Path $ROOT $dir
        if (-not (Test-Path $full)) { Write-Warn "${dir}: directory not found"; continue }
        $nm = Join-Path $full "node_modules"
        if (Test-Path $nm) {
            Write-Info "${dir}: node_modules exists"
        } else {
            Write-Host "  npm install in $dir..." -ForegroundColor Gray
            Push-Location $full
            npm install --loglevel=error 2>&1 | Out-Null
            Pop-Location
            Write-Ok "${dir}: installed"
        }
    }
} else {
    Write-Warn "Node.js not available -skipping npm install"
}

# ═══════════════════════════════════════════════════════════════════
#  STEP 8: Git Submodules
# ═══════════════════════════════════════════════════════════════════
Write-Step 8 "Initializing Git submodules..."

if ($prereqs["git"]) {
    Push-Location $script:OS_ROOT
    $oldEAP2 = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    git submodule update --init 2>&1 | Out-Null
    $ErrorActionPreference = $oldEAP2
    Pop-Location

    # Verify key submodules
    $checkDirs = @("vibemind-os/openfang", "vibemind-os/shared", "vibemind-os/voice", "vibemind-os/brain/the_brain")
    $allOk = $true
    foreach ($d in $checkDirs) {
        $full = Join-Path $ROOT $d
        $items = Get-ChildItem $full -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne ".git" }
        if (-not $items -or $items.Count -eq 0) {
            Write-Warn "$d appears empty -may need manual init"
            $allOk = $false
        }
    }
    if ($allOk) { Write-Ok "All submodules initialized" }
} else {
    Write-Warn "Git not available -skipping submodule init"
}

# ═══════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    Setup Complete" -ForegroundColor Green
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Enabled modules: $($enabledModules -join ', ')" -ForegroundColor White
Write-Host "  API keys:        $($configured.Count) configured" -ForegroundColor White
Write-Host "  Config file:     vibemind.config.json" -ForegroundColor Gray
Write-Host "  Root .env:       .env" -ForegroundColor Gray
Write-Host ""
Write-Host "  Next step:" -ForegroundColor White
Write-Host "    .\Vibemind.debug.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Selective start:" -ForegroundColor White
Write-Host "    .\Vibemind.debug.ps1 -Modules voice,brain" -ForegroundColor Yellow
Write-Host ""
