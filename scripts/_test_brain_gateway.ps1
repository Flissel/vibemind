param([int]$TimeoutSec = 180)
$ErrorActionPreference = 'Stop'

$id = 'dd781246-e7ac-4364-a065-defce02d3d7f'  # brain-gateway from earlier listing
$msg = 'What is 2+2? Reply with just the number.'
$body = @{ message = $msg } | ConvertTo-Json -Compress
Write-Host "POST /api/agents/$id/message (brain-gateway)" -ForegroundColor Cyan
Write-Host "Msg: $msg"
Write-Host ""

$start = Get-Date
try {
    $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4200/api/agents/$id/message" `
        -ContentType 'application/json' -Body $body -TimeoutSec $TimeoutSec
    $elapsed = ((Get-Date) - $start).TotalSeconds
    Write-Host "--- response (${elapsed}s) ---" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 6
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    try {
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "Body: $($reader.ReadToEnd())" -ForegroundColor Yellow
        }
    } catch {}
    exit 1
}
