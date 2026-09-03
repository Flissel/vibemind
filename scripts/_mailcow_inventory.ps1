param(
    [string]$ApiKey = $env:MAILCOW_API_KEY,
    [string]$Base = $(if ($env:MAILCOW_URL) { "$env:MAILCOW_URL/api/v1" } else { "https://127.0.0.1:8443/api/v1" })
)
$ErrorActionPreference = 'Continue'
if (-not $ApiKey) {
    Write-Error "MAILCOW_API_KEY env var not set. Source from .env or pass via -ApiKey '<key>'."
    exit 1
}
$headers = @{ 'X-API-Key' = $ApiKey }

function Get-Endpoint {
    param([string]$Path)
    try {
        return Invoke-RestMethod -Uri "$Base$Path" -Headers $headers -SkipCertificateCheck -TimeoutSec 8
    } catch {
        return @{ ERROR = $_.Exception.Message }
    }
}

Write-Host "=== STATUS ==="
$ver = Get-Endpoint "/get/status/version"
$ver | ConvertTo-Json -Depth 3

Write-Host ""
Write-Host "=== DOMAINS ==="
$domains = Get-Endpoint "/get/domain/all"
$domains | Format-Table domain_name, active, max_num_aliases_for_domain, max_num_mboxes_for_domain, mailboxes, defquota, maxquota, relayhost, dkim_selector

Write-Host ""
Write-Host "=== MAILBOXES ==="
$mailboxes = Get-Endpoint "/get/mailbox/all"
$mailboxes | Format-Table username, name, domain, active, quota, messages, percent_in_use, last_imap_login, last_pop3_login, last_smtp_login

Write-Host ""
Write-Host "=== ALIASES ==="
$aliases = Get-Endpoint "/get/alias/all"
if ($aliases -is [array]) {
    $aliases | Format-Table id, address, goto, domain, active
} else { "(no aliases or error: $($aliases | ConvertTo-Json -Compress))" }

Write-Host ""
Write-Host "=== RESOURCES ==="
$res = Get-Endpoint "/get/resource/all"
if ($res -is [array]) { $res | Format-Table name, domain, kind, active } else { "(none)" }

Write-Host ""
Write-Host "=== DKIM (per domain) ==="
foreach ($d in $domains) {
    $dkim = Get-Endpoint "/get/dkim/$($d.domain_name)"
    Write-Host ("--- " + $d.domain_name)
    if ($dkim -and $dkim.dkim_txt) {
        Write-Host ("  selector: " + $dkim.dkim_selector)
        Write-Host ("  length:   " + $dkim.length)
        Write-Host ("  pubkey:   " + ($dkim.pubkey -replace '(.{40}).+', '$1...truncated'))
    } else {
        Write-Host "  (no DKIM key or error)"
    }
}

Write-Host ""
Write-Host "=== SYNCJOBS ==="
$sj = Get-Endpoint "/get/syncjobs/all/no_log"
if ($sj -is [array]) { $sj | Format-Table id, user2, host1, port1, active } else { "(none)" }

Write-Host ""
Write-Host "=== APP PASSWORDS (per mailbox) ==="
foreach ($mb in $mailboxes) {
    $apps = Get-Endpoint "/get/app-passwd/all/$($mb.username)"
    if ($apps -is [array] -and $apps.Count -gt 0) {
        Write-Host ("--- " + $mb.username)
        $apps | Format-Table id, name, protocols, active
    }
}

Write-Host ""
Write-Host "=== QUEUE (active mail queue) ==="
$q = Get-Endpoint "/get/mailq/all"
if ($q -is [array] -and $q.Count -gt 0) { $q | Select-Object -First 5 | Format-Table } else { "(empty)" }

Write-Host ""
Write-Host "=== FAIL2BAN (recent banned ips) ==="
$fb = Get-Endpoint "/get/fail2ban"
if ($fb) {
    Write-Host ("ban_time: " + $fb.ban_time)
    Write-Host ("max_attempts: " + $fb.max_attempts)
    Write-Host ("ips banned now:")
    $fb.active_bans | ForEach-Object { "  $_" }
}

Write-Host ""
Write-Host "=== STATUS - CONTAINERS ==="
$cs = Get-Endpoint "/get/status/containers"
if ($cs) {
    $cs.PSObject.Properties | ForEach-Object {
        $svc = $_.Value
        "{0,-30}  {1,-10}  cpu={2}  mem={3}" -f $_.Name, $svc.state, $svc.cpu_usage, $svc.mem_usage
    }
}

Write-Host ""
Write-Host "=== STATUS - VMAIL ==="
$vm = Get-Endpoint "/get/status/vmail"
if ($vm) { $vm | ConvertTo-Json -Depth 2 }

Write-Host ""
Write-Host "=== STATUS - SOLR ==="
$solr = Get-Endpoint "/get/status/solr"
if ($solr) { $solr | ConvertTo-Json -Depth 2 }

Write-Host ""
Write-Host "=== POLICIES (rspamd settings, last 5) ==="
$pl = Get-Endpoint "/get/policy_wl_domain"
if ($pl -is [array]) { $pl | Select-Object -First 5 | Format-Table } else { "(none)" }
