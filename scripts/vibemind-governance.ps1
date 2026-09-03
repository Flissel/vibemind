[CmdletBinding()]
param(
    [string]$RepositoryRoot = '',
    [string]$PythonCommand = 'python'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path -Path $PSScriptRoot -ChildPath '..'
}

function Invoke-GovernanceCommand {
    param([string[]]$Arguments)

    & $PythonCommand @Arguments
    $script:governanceExitCode = $LASTEXITCODE
}

$resolvedRepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
$exitCodes = [System.Collections.Generic.List[int]]::new()

Push-Location -LiteralPath $resolvedRepositoryRoot
try {
    Invoke-GovernanceCommand -Arguments @(
        '-m', 'tools.v1_governance', 'manifest', 'validate', '--repo', $resolvedRepositoryRoot, '--format', 'json'
    )
    $exitCodes.Add($governanceExitCode)
    Invoke-GovernanceCommand -Arguments @('-m', 'pytest', 'tests/architecture', 'tests/v1_governance')
    $exitCodes.Add($governanceExitCode)
}
finally {
    Pop-Location
}

if ($exitCodes | Where-Object { $_ -ne 0 -and $_ -ne 2 }) {
    exit 1
}
if ($exitCodes -contains 2) {
    exit 2
}
exit 0
