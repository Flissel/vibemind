<#
.SYNOPSIS
    Keep openclaw patched + self-heal the WhatsApp login, update only on need.

.DESCRIPTION
    Update policy (decided 2026-06): npm update is EXPENSIVE + risky, so we
    only pull it when the WhatsApp login is actually broken — a fresh openclaw
    can fix a protocol/session invalidation. A healthy login never triggers an
    update.

    Default run (e.g. stack-start hook, -SkipUpdate):
      1. re-apply VibeMind patches (idempotent, cheap)
      2. check WhatsApp login (creds.json):
           present  -> done, nothing else
           missing  -> pull `npm install -g openclaw@latest` (might fix it),
                       re-patch, then print a LOUD hint to run -Login.
                       NO interactive login spawned here (headless-safe).

    Interactive login (-Login): the deliberate "I'm here to scan" command.
      Runs the update-if-needed flow, then starts
      `openclaw channels login --channel whatsapp`. The patched openclaw
      writes a scannable QR PNG to the Desktop and opens it — scan it.

    The WhatsApp session lives in ~/.openclaw/credentials/whatsapp/ which
    npm does NOT touch, so a healthy login survives updates by itself.

.PARAMETER Login
    Start the interactive WhatsApp login after ensuring openclaw is patched
    (and updated if the login was missing). Use this when you're at the PC
    and ready to scan the QR PNG.

.PARAMETER Force
    Force `npm install -g openclaw@latest` even if the login looks healthy.

.PARAMETER SkipUpdate
    Never hit npm — only re-apply patches + report login status. Used by the
    stack-start hook (no network round-trip, no update, no spawned login).

.NOTES
    Stack-start hook:  pwsh -File scripts/openclaw_update.ps1 -SkipUpdate
    Login (manual):    pwsh -File scripts/openclaw_update.ps1 -Login
    Force update:      pwsh -File scripts/openclaw_update.ps1 -Force
#>
param(
    [switch]$Login,
    [switch]$Force,
    [switch]$SkipUpdate
)

$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$creds = Join-Path $env:USERPROFILE ".openclaw\credentials\whatsapp\default\creds.json"

function Write-OcLog([string]$msg, [string]$color = "Gray") {
    Write-Host "[openclaw-update] $msg" -ForegroundColor $color
}

function Test-WhatsAppLogin { return (Test-Path $creds) }

function Invoke-NpmUpdate {
    $current = ""
    try {
        $pkgPath = Join-Path (npm root -g 2>$null) "openclaw\package.json"
        if (Test-Path $pkgPath) {
            $current = (Get-Content -Raw $pkgPath | ConvertFrom-Json).version
        }
    } catch {}
    Write-OcLog "pulling openclaw@latest (current: $current) ..." "Cyan"
    npm install -g openclaw@latest 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    Write-OcLog "npm install done." "Green"
}

function Invoke-Patches {
    $patchScript = Join-Path $scriptDir "openclaw_apply_patches.ps1"
    if (Test-Path $patchScript) {
        & $patchScript
    } else {
        Write-OcLog "patch script not found: $patchScript" "Yellow"
    }
}

$loginOk = Test-WhatsAppLogin

# ── Update decision: only when login is broken (or forced/login asked) ────
$shouldUpdate = $false
if (-not $SkipUpdate) {
    if ($Force) {
        $shouldUpdate = $true
        Write-OcLog "Force — updating regardless of login state." "Cyan"
    } elseif (-not $loginOk) {
        $shouldUpdate = $true
        Write-OcLog "WhatsApp login MISSING — a fresh openclaw may fix a protocol/session break. Updating." "Yellow"
    } else {
        Write-OcLog "WhatsApp login healthy — no update needed." "Green"
    }
}

if ($shouldUpdate) { Invoke-NpmUpdate }

# ── Patches: always (cheap, idempotent, survives any npm overwrite) ───────
Invoke-Patches

# ── Re-check login after a possible update ────────────────────────────────
$loginOk = Test-WhatsAppLogin

# ── Interactive login: only when explicitly asked (-Login) ────────────────
if ($Login) {
    if ($loginOk) {
        Write-OcLog "Login already present — skipping interactive login. (use -Force to re-pair.)" "Green"
    } else {
        Write-OcLog "Starting interactive WhatsApp login. A scannable QR PNG opens on your Desktop — scan it with WhatsApp > Linked Devices." "Cyan"
        $ocBin = Join-Path (npm root -g 2>$null) "openclaw\openclaw.mjs"
        if (Test-Path $ocBin) {
            & node $ocBin channels login --channel whatsapp
        } else {
            Write-OcLog "openclaw.mjs not found at $ocBin" "Red"
        }
    }
} elseif (-not $loginOk) {
    # No interactive spawn at stack-start — just a loud, actionable hint.
    Write-OcLog "WhatsApp NOT logged in. When you're ready to scan, run:" "Yellow"
    Write-OcLog "    pwsh -File scripts/openclaw_update.ps1 -Login" "Yellow"
} else {
    Write-OcLog "WhatsApp login present (creds.json) — nothing to do." "Green"
}

Write-OcLog "complete." "Cyan"
exit 0
