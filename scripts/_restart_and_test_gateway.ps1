param()
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$OfDir = Join-Path $Root "vibemind-os/openfang"
$OfBin = Join-Path $OfDir "target/release/openfang.exe"
$OfConfig = Join-Path $OfDir "openfang.vibemind.toml"
$OfLog = Join-Path $Root "logs/openfang/openfang.log"
$OfErr = Join-Path $Root "logs/openfang/openfang.err.log"
$NpmDir = Join-Path $env:APPDATA "npm"
$OfScripts = Join-Path $Root "scripts"

Write-Host "=== Start OpenFang ===" -ForegroundColor Cyan
$origPath = $env:PATH
$origClaudeCode = $env:CLAUDECODE
$origClaudeSessionId = $env:CLAUDE_CODE_SESSION_ID
$origClaudeEntrypoint = $env:CLAUDE_CODE_ENTRYPOINT
$origAiAgent = $env:AI_AGENT
$origWrapperDir = $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR
try {
    $env:PATH = "$OfScripts;$NpmDir;$origPath"
    $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $OfScripts
    Remove-Item Env:CLAUDECODE -ErrorAction SilentlyContinue
    Remove-Item Env:CLAUDE_CODE_SESSION_ID -ErrorAction SilentlyContinue
    Remove-Item Env:CLAUDE_CODE_ENTRYPOINT -ErrorAction SilentlyContinue
    Remove-Item Env:AI_AGENT -ErrorAction SilentlyContinue
    Start-Process -FilePath $OfBin -ArgumentList @('start','--config',$OfConfig) `
        -WorkingDirectory $OfDir -WindowStyle Hidden `
        -RedirectStandardOutput $OfLog -RedirectStandardError $OfErr
} finally {
    $env:PATH = $origPath
    if ($origClaudeCode) { $env:CLAUDECODE = $origClaudeCode }
    if ($origClaudeSessionId) { $env:CLAUDE_CODE_SESSION_ID = $origClaudeSessionId }
    if ($origClaudeEntrypoint) { $env:CLAUDE_CODE_ENTRYPOINT = $origClaudeEntrypoint }
    if ($origAiAgent) { $env:AI_AGENT = $origAiAgent }
    if ($null -eq $origWrapperDir) { Remove-Item Env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR -ErrorAction SilentlyContinue }
    else { $env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $origWrapperDir }
}

Write-Host "=== Wait for ready ===" -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest 'http://127.0.0.1:4200/api/health' -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if (-not $ready) {
    Write-Host "OpenFang did not come up within 30s" -ForegroundColor Red
    exit 2
}
Write-Host "ready" -ForegroundColor Green

Write-Host ""
Write-Host "=== Resolve brain-gateway id (fresh from /api/agents) ===" -ForegroundColor Cyan
$agents = Invoke-RestMethod 'http://127.0.0.1:4200/api/agents' -TimeoutSec 10
$bg = $agents | Where-Object { $_.name -eq 'brain-gateway' } | Select-Object -First 1
if (-not $bg) {
    Write-Host "brain-gateway not registered (found $($agents.Count) agents)" -ForegroundColor Red
    exit 3
}
Write-Host "id: $($bg.id)"
Write-Host "provider: $($bg.model_provider) / $($bg.model_name)"

Write-Host ""
Write-Host "=== POST simple message ===" -ForegroundColor Cyan
$body = @{ message = 'Reply with exactly the digit 4 and nothing else.' } | ConvertTo-Json -Compress
$start = Get-Date
try {
    $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4200/api/agents/$($bg.id)/message" `
        -ContentType 'application/json' -Body $body -TimeoutSec 90
    $el = ((Get-Date) - $start).TotalSeconds
    Write-Host "--- response (${el}s) ---" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "Body: $($reader.ReadToEnd())" -ForegroundColor Yellow
        } catch {}
    }
    Write-Host ""
    Write-Host "--- err-log tail ---" -ForegroundColor Yellow
    Get-Content $OfErr -Tail 8 -ErrorAction SilentlyContinue | ForEach-Object {
        ($_ -replace "`e\[[0-9;]*m","") | Out-Host
    }
    exit 4
}
