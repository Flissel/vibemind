param(
    [string]$ApiKey = $env:MAILCOW_API_KEY,
    [string]$Base = $(if ($env:MAILCOW_URL) { "$env:MAILCOW_URL/api/v1" } else { "https://127.0.0.1:8443/api/v1" }),
    [string]$Domain = "vibemind.space"
)
$ErrorActionPreference = 'Stop'
if (-not $ApiKey) {
    Write-Error "MAILCOW_API_KEY env var not set. Source from .env or pass via -ApiKey '<key>'."
    exit 1
}
$h = @{ 'X-API-Key' = $ApiKey; 'Content-Type' = 'application/json' }

function New-RandomPassword {
    param([int]$Length = 24)
    $chars = (33..126) | Where-Object { $_ -notin (34,39,60,62,96,92,47) } | ForEach-Object { [char]$_ }
    -join (1..$Length | ForEach-Object { Get-Random -InputObject $chars })
}

function New-Mailbox {
    param([string]$Local, [string]$DisplayName, [int]$QuotaMB = 1024, [string]$Password)
    $body = @{
        local_part = $Local
        domain = $Domain
        name = $DisplayName
        quota = $QuotaMB
        password = $Password
        password2 = $Password
        active = 1
        force_pw_update = 0
        tls_enforce_in = 1
        tls_enforce_out = 1
    } | ConvertTo-Json
    try {
        $r = Invoke-RestMethod -Method Post -Uri "$Base/add/mailbox" -Headers $h -SkipCertificateCheck -Body $body -TimeoutSec 15
        return @{ ok = $true; resp = $r }
    } catch {
        $msg = ""
        if ($_.Exception.Response) {
            try { $msg = (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch {}
        }
        return @{ ok = $false; error = "$($_.Exception.Message) :: $msg" }
    }
}

# Two service accounts: marketing@ and noreply@
$accounts = @(
    @{ Local = "marketing"; Name = "VibeMind Marketing"; Quota = 2048 },
    @{ Local = "noreply"; Name = "VibeMind No-Reply"; Quota = 512 }
)

$created = @()
foreach ($a in $accounts) {
    $pw = New-RandomPassword -Length 32
    Write-Host ("Creating " + $a.Local + "@" + $Domain + " ...")
    $result = New-Mailbox -Local $a.Local -DisplayName $a.Name -QuotaMB $a.Quota -Password $pw
    if ($result.ok) {
        Write-Host "  OK"
        $created += @{ email = "$($a.Local)@$Domain"; password = $pw; name = $a.Name }
    } else {
        Write-Host "  ERROR: $($result.error)"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "CREDENTIALS - save these now:"
foreach ($c in $created) {
    Write-Host ""
    Write-Host ("  " + $c.email)
    Write-Host ("    password: " + $c.password)
}
Write-Host "=========================================="

# Output as machine-readable too
Write-Host ""
Write-Host "--- as .env-friendly key=value ---"
$created | ForEach-Object {
    $envKey = ($_.email -replace '@vibemind\.space','' -replace '-','_').ToUpper()
    Write-Host "MAILCOW_${envKey}_USER=$($_.email)"
    Write-Host "MAILCOW_${envKey}_PASS=$($_.password)"
}
