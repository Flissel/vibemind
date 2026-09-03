<#
.SYNOPSIS
    Provision Docker Swarm secrets from the repo .env + hardcoded Supabase
    demo-defaults (Phase A3 foundation + 11.U.H.2 Supabase migration).
.DESCRIPTION
    Two secret-Quellen werden hier provisioniert:

    1. $SECRET_MAP — .env-Keys → Docker-Secret-Namen (Phase A3).
       Wenn die .env-Variable leer ist, wird das Secret nicht angelegt;
       Idempotent: existierende Secrets bleiben (Docker-Secrets sind
       immutable — -Rotate zum Ersetzen).

    2. $SUPABASE_VALUES — hardcoded Demo-Werte (2026-05-20).
       Supabase-CLI generiert Demo-JWT-Keys die in 4+ Containern identisch
       sein müssen. Diese Werte sind öffentlich/dokumentiert (Supabase
       Local Dev Convention) — kein .env-Eintrag, keine Rotation hier.
       Rotation auf produktive Werte = eigene Security-Story
       (OPENSOURCE_RELEASE_CHECKLIST.md).

    Requires Swarm mode active (`docker swarm init` once).
.PARAMETER EnvFile
    Path to the .env (default: repo-root .env).
.PARAMETER Rotate
    Remove + recreate secrets that already exist (für .env-Updates;
    Supabase-Demo-Werte werden mit -Rotate ebenfalls neu geschrieben,
    aber das ist meist no-op weil die Werte ja konstant sind).
.PARAMETER DryRun
    Print what would be created/skipped, create nothing.
.EXAMPLE
    .\scripts\swarm_secrets_init.ps1 -DryRun
    .\scripts\swarm_secrets_init.ps1
    .\scripts\swarm_secrets_init.ps1 -Rotate
#>
param(
    [string]$EnvFile,
    [switch]$Rotate,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $EnvFile) { $EnvFile = Join-Path $ROOT ".env" }

if (-not (Test-Path $EnvFile)) {
    Write-Host "  [ERROR] .env not found: $EnvFile" -ForegroundColor Red
    exit 1
}

# .env key  ->  docker secret name. Names MUST match the external secrets in
# vibemind-os/coding-engine/infra/docker/docker-stack.yml:202-218 so the
# existing stack (and the future vibemind-stack.yml) resolves them.
$SECRET_MAP = [ordered]@{
    OPENROUTER_API_KEY         = "openrouter_api_key"
    ANTHROPIC_API_KEY          = "anthropic_api_key"
    OPENFANG_API_KEY           = "openfang_api_key"
    OPENAI_API_KEY             = "openai_api_key"
    GROQ_API_KEY               = "groq_api_key"
    DISCORD_BOT_TOKEN          = "discord_bot_token_engine"
    DISCORD_BOT_TOKEN_ANALYZER = "discord_bot_token_analyzer"
    OPENCLAW_GATEWAY_TOKEN     = "openclaw_gateway_token"
    POSTGRES_PASSWORD          = "postgres_password"
    REDIS_PASSWORD             = "redis_password"
}

# Supabase-CLI Demo-Defaults (Phase 11.U.H.2 — 2026-05-20):
# Hardcoded weil die supabase-CLI sie deterministisch generiert
# (identisch in ALLEN 4 Containern auth/rest/realtime/storage). Wir
# übernehmen sie 1:1 für den Stack-Service-Modus, sonst müssten wir
# ein eigenes JWT-Setup machen das mit dem alten Volume nicht kompatibel
# ist (das Volume hat schon Rows die per diesem anon-Key signiert sind).
# Diese Werte sind dokumentiert in supabase/docs (Local Dev Defaults) —
# sie sind öffentlich, kein Secret im echten Sinn. Für ein
# Open-Source-Release rotiert man sie via OPENSOURCE_RELEASE_CHECKLIST.md.
$SUPABASE_VALUES = [ordered]@{
    supabase_jwt_secret       = "<YOUR_JWT_SECRET_AT_LEAST_32_CHARS>"
    supabase_anon_key         = "<YOUR_SUPABASE_JWT>"
    supabase_service_role_key = "<YOUR_SUPABASE_JWT>"
}

# --- Preconditions -------------------------------------------------------
try {
    $swarmState = (docker info --format '{{.Swarm.LocalNodeState}}' 2>$null)
} catch {
    Write-Host "  [ERROR] docker not reachable." -ForegroundColor Red
    exit 1
}
if ($swarmState -ne "active") {
    Write-Host "  [ERROR] Swarm mode is '$swarmState'. Run once: docker swarm init" -ForegroundColor Red
    Write-Host "  (Secrets are a Swarm-only feature; Phase B deploys the stack.)" -ForegroundColor DarkYellow
    exit 1
}

# --- Parse .env (names + values, in-memory only) -------------------------
$envValues = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^([A-Z][A-Z0-9_]+)=(.*)$') {
        $envValues[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}

$existing = @{}
try {
    docker secret ls --format '{{.Name}}' 2>$null | ForEach-Object { $existing[$_] = $true }
} catch {}

$created = 0; $skipped = 0; $missing = 0; $rotated = 0

foreach ($key in $SECRET_MAP.Keys) {
    $secretName = $SECRET_MAP[$key]
    $val = $envValues[$key]

    if ([string]::IsNullOrWhiteSpace($val)) {
        Write-Host ("  - {0,-26} (.env key {1} empty/missing — skip)" -f $secretName, $key) -ForegroundColor DarkGray
        $missing++
        continue
    }

    if ($existing.ContainsKey($secretName)) {
        if ($Rotate) {
            if ($DryRun) {
                Write-Host ("  ~ {0,-26} would ROTATE (exists, -Rotate)" -f $secretName) -ForegroundColor Yellow
            } else {
                # A secret in use by a service can't be removed; surface that.
                docker secret rm $secretName 2>&1 | Out-Null
                $val | docker secret create $secretName - 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host ("  ~ {0,-26} ROTATED" -f $secretName) -ForegroundColor Yellow
                    $rotated++
                } else {
                    Write-Host ("  [WARN] {0} rotate failed (in use by a running service?)" -f $secretName) -ForegroundColor Red
                }
            }
        } else {
            Write-Host ("  = {0,-26} exists — skip (use -Rotate to replace)" -f $secretName) -ForegroundColor DarkGray
            $skipped++
        }
        continue
    }

    if ($DryRun) {
        Write-Host ("  + {0,-26} would CREATE (from {1})" -f $secretName, $key) -ForegroundColor Green
    } else {
        $val | docker secret create $secretName - 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("  + {0,-26} CREATED" -f $secretName) -ForegroundColor Green
            $created++
        } else {
            Write-Host ("  [WARN] {0} create failed" -f $secretName) -ForegroundColor Red
        }
    }
}

# === Supabase Demo-Secrets (Phase 11.U.H.2) ==============================
# Same idempotent pattern as above, but values come from $SUPABASE_VALUES
# (hardcoded supabase-CLI defaults) instead of .env. -Rotate only matters
# if upstream Supabase changes their CLI defaults (rare).
foreach ($secretName in $SUPABASE_VALUES.Keys) {
    $val = $SUPABASE_VALUES[$secretName]

    if ($existing.ContainsKey($secretName)) {
        if ($Rotate) {
            if ($DryRun) {
                Write-Host ("  ~ {0,-26} would ROTATE (exists, -Rotate, supabase demo)" -f $secretName) -ForegroundColor Yellow
            } else {
                docker secret rm $secretName 2>&1 | Out-Null
                $val | docker secret create $secretName - 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host ("  ~ {0,-26} ROTATED (supabase demo)" -f $secretName) -ForegroundColor Yellow
                    $rotated++
                } else {
                    Write-Host ("  [WARN] {0} rotate failed (in use by a running service?)" -f $secretName) -ForegroundColor Red
                }
            }
        } else {
            Write-Host ("  = {0,-26} exists — skip (supabase demo, use -Rotate)" -f $secretName) -ForegroundColor DarkGray
            $skipped++
        }
        continue
    }

    if ($DryRun) {
        Write-Host ("  + {0,-26} would CREATE (supabase demo)" -f $secretName) -ForegroundColor Green
    } else {
        $val | docker secret create $secretName - 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("  + {0,-26} CREATED (supabase demo)" -f $secretName) -ForegroundColor Green
            $created++
        } else {
            Write-Host ("  [WARN] {0} create failed" -f $secretName) -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host ("  Summary: created={0} rotated={1} skipped={2} missing={3} (dry-run={4})" -f `
    $created, $rotated, $skipped, $missing, [bool]$DryRun) -ForegroundColor Cyan
Write-Host "  Verify: docker secret ls" -ForegroundColor Gray
