[CmdletBinding()]
param(
    [string]$RootPath = (Split-Path $PSScriptRoot -Parent),
    [switch]$LibraryMode
)

Set-StrictMode -Version Latest

function Get-VibeMindSupabaseCutoverFinding {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RootPath
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RootPath -ErrorAction Stop).Path
    $rg = Get-Command rg -ErrorAction Stop
    $localTargetPattern = '(?i)https?://(?:localhost|127\.0\.0\.1|host\.docker\.internal):5432[1-3]'
    $searchPattern = "(?:SUPABASE_URL[^\r\n]*$localTargetPattern|$localTargetPattern)"
    $excludedPathPattern = '(?i)(^|[\\/])(?:\.git|\.claude[\\/]worktrees|\.fungus_cache|node_modules|graphify-out|backups|pitch-deck-2026|docs|tests|intent_validation)([\\/]|$)|' +
        '(^|[\\/])infra[\\/]swarm[\\/]supabase([\\/]|$)|' +
        '(^|[\\/])infra[\\/]proxmox([\\/]|$)|' +
        '(^|[\\/])supabase[\\/]migrate_sqlite_to_supabase\.py$|' +
        '(^|[\\/])scripts[\\/](?:status_probe_server\.py|vibemind-spaces\.ps1)$|' +
        '^Vibemind\.debug\.ps1$|' +
        '(^|[\\/])\.vibemind-stack-rendered-[^\\/]+\.yml$'

    $arguments = @(
        '--line-number', '--no-heading', '--color', 'never', '--hidden', '--no-ignore',
        '--glob', '*.py', '--glob', '*.ps1', '--glob', '*.ts', '--glob', '*.js',
        '--glob', '*.yml', '--glob', '*.yaml', '--glob', '*.json', '--glob', '*.toml',
        '--glob', '*.env', '--glob', '.env', '--glob', '.env.*',
        '--glob', '!**/.git/**', '--glob', '!**/node_modules/**',
        '--glob', '!**/.venv*/**', '--glob', '!**/__pycache__/**',
        '--glob', '!**/target/**', '--glob', '!**/dist/**', '--glob', '!**/build/**',
        '--glob', '!**/.next/**', '--glob', '!**/vendor/**', '--glob', '!**/logs/**',
        '--glob', '!**/backups/**', '--glob', '!**/pitch-deck-2026/**',
        '--glob', '!**/graphify-out/**', '--glob', '!**/intent_validation/**',
        '--glob', '!**/.claude/worktrees/**', '--glob', '!**/.fungus_cache/**',
        '--glob', '!**/docs/**', '--glob', '!**/tests/**',
        $searchPattern, '.'
    )

    Push-Location $resolvedRoot
    try {
        $rawMatches = @(& $rg.Source @arguments 2>$null)
        $rgExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($rgExitCode -notin @(0, 1)) {
        throw "rg cutover scan failed with exit code $rgExitCode"
    }

    foreach ($rawMatch in $rawMatches) {
        if ($rawMatch -notmatch '^(.*?):(\d+):(.*)$') {
            continue
        }

        $relativePath = $Matches[1] -replace '^\.[\\/]', ''
        $lineNumber = [int]$Matches[2]
        $line = $Matches[3]
        $leaf = Split-Path $relativePath -Leaf

        if ($relativePath -match $excludedPathPattern -or
            $leaf -match '^(?i)test[_-]' -or
            $leaf -match '(?i)\.Tests\.ps1$' -or
            $leaf -match '(?i)^\.env\.example$' -or
            $leaf -match '(?i)\.bak(?:[.-]|$)') {
            continue
        }
        if ($line -match '^\s*(?:#|//|/\*|\*|<!--)') {
            continue
        }
        if ($line -notmatch $localTargetPattern) {
            continue
        }

        $target = ([regex]::Match($line, $localTargetPattern).Value -replace '^https?://', '')
        $variableMatch = [regex]::Match($line, '\b(?:SUPABASE_URL|[A-Z][A-Z0-9_]*(?:URL|URI)|SUPA)\b')
        $variable = if ($variableMatch.Success) { $variableMatch.Value } else { 'literal' }
        $normalizedPath = $relativePath -replace '\\', '/'
        if ($normalizedPath -eq 'infra/swarm/vibemind-stack.yml' -and
            $variable -in @('API_EXTERNAL_URL', 'SUPABASE_PUBLIC_URL')) {
            continue
        }

        [pscustomobject][ordered]@{
            Path       = $relativePath
            LineNumber = $lineNumber
            Variable   = $variable
            Target     = $target
        }
    }
}

if (-not $LibraryMode) {
    $findings = @(Get-VibeMindSupabaseCutoverFinding -RootPath $RootPath)
    if ($findings.Count -gt 0) {
        $findings | Sort-Object Path, LineNumber | Format-Table -AutoSize
        Write-Error "Supabase cutover blocked: $($findings.Count) active local endpoint reference(s) remain."
        exit 2
    }

    Write-Output 'Supabase cutover consumer gate: PASS (no active local endpoint references).'
}
