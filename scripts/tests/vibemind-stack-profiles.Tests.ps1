BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    . (Join-Path $repoRoot "scripts\lib\vibemind-helpers.ps1")

    function Get-RenderedServiceNames {
        param([string[]]$Profiles)

        $stackFile = Join-Path $repoRoot "infra\swarm\vibemind-stack.yml"
        $rendered = ConvertTo-FilteredStack -StackFile $stackFile -Profiles $Profiles
        try {
            $names = [System.Collections.Generic.List[string]]::new()
            $inServices = $false
            foreach ($line in Get-Content -LiteralPath $rendered -Encoding utf8) {
                if ($line -match '^services:\s*$') {
                    $inServices = $true
                    continue
                }
                if ($inServices -and $line -match '^[A-Za-z][A-Za-z0-9_-]*:\s*$') {
                    break
                }
                if ($inServices -and $line -match '^  ([A-Za-z][A-Za-z0-9_-]*):\s*$') {
                    $names.Add($Matches[1])
                }
            }
            return @($names)
        }
        finally {
            Remove-Item -LiteralPath $rendered -Force -ErrorAction SilentlyContinue
        }
    }

    function Get-SourceServiceNames {
        param([string]$StackFile)

        $names = [System.Collections.Generic.List[string]]::new()
        $inServices = $false
        foreach ($line in Get-Content -LiteralPath $StackFile -Encoding utf8) {
            if ($line -match '^services:\s*$') {
                $inServices = $true
                continue
            }
            if ($inServices -and $line -match '^[A-Za-z][A-Za-z0-9_-]*:\s*$') {
                break
            }
            if ($inServices -and $line -match '^  ([A-Za-z][A-Za-z0-9_-]*):\s*$') {
                $names.Add($Matches[1])
            }
        }
        return @($names)
    }
}

Describe "VibeMind stack profiles" {
    It "renders only the operational core when no space is selected" {
        $expected = @(
            "qdrant",
            "brain-core",
            "brain-api",
            "brain-autotrain-drain",
            "brain-loops",
            "embedding-service",
            "supabase-db",
            "supabase-auth",
            "supabase-rest",
            "supabase-realtime",
            "supabase-storage",
            "supabase-pg-meta",
            "supabase-analytics",
            "supabase-kong",
            "supabase-studio",
            "supabase-inbucket"
        ) | Sort-Object

        $actual = Get-RenderedServiceNames -Profiles @("core") | Sort-Object

        Compare-Object -ReferenceObject $expected -DifferenceObject $actual |
            Should -BeNullOrEmpty
    }

    It "discovers every profile declared by the source stack" {
        $stackFile = Join-Path $repoRoot "infra\swarm\vibemind-stack.yml"

        $actual = Get-StackProfileNames -StackFile $stackFile | Sort-Object
        $expected = @(
            "core-phase-d",
            "space-coding",
            "space-logging",
            "space-media",
            "space-mirofish",
            "space-n8n",
            "space-rowboat"
        )

        Compare-Object -ReferenceObject $expected -DifferenceObject $actual |
            Should -BeNullOrEmpty
    }

    It "renders every service through the all-profile sanitizer without profile keys" {
        $stackFile = Join-Path $repoRoot "infra\swarm\vibemind-stack.yml"
        $profiles = Get-StackProfileNames -StackFile $stackFile
        $rendered = ConvertTo-FilteredStack -StackFile $stackFile -Profiles $profiles
        try {
            (Get-Content -LiteralPath $rendered -Raw -Encoding utf8) |
                Should -Not -Match '(?m)^\s*profiles:\s*\['

            $actual = Get-RenderedServiceNames -Profiles $profiles | Sort-Object
            $expected = Get-SourceServiceNames -StackFile $stackFile | Sort-Object
            Compare-Object -ReferenceObject $expected -DifferenceObject $actual |
                Should -BeNullOrEmpty

            $envFile = Join-Path $repoRoot ".env"
            $createdEnvFile = $false
            if (-not (Test-Path -LiteralPath $envFile)) {
                New-Item -ItemType File -Path $envFile -ErrorAction Stop | Out-Null
                $createdEnvFile = $true
            }
            try {
                $parserOutput = @(docker stack config -c $rendered 2>&1)
                $parserExitCode = $LASTEXITCODE
                if ($parserExitCode -ne 0) {
                    $parserOutput | Out-Host
                }
                $parserExitCode | Should -Be 0
            }
            finally {
                if ($createdEnvFile) {
                    Remove-Item -LiteralPath $envFile -Force -ErrorAction SilentlyContinue
                }
            }
        }
        finally {
            Remove-Item -LiteralPath $rendered -Force -ErrorAction SilentlyContinue
        }
    }

    It "routes debug stack deployment through the all-profile sanitizer with cleanup" {
        $debugLauncher = Get-Content -LiteralPath (Join-Path $repoRoot "Vibemind.debug.ps1") -Raw -Encoding utf8

        $debugLauncher | Should -Match 'Get-StackProfileNames -StackFile \$stackFile'
        $debugLauncher | Should -Match 'ConvertTo-FilteredStack -StackFile \$stackFile -Profiles \$allProfiles'
        $debugLauncher | Should -Match '(?s)finally\s*\{.*Remove-Item -LiteralPath \$renderedStackFile'
        $debugLauncher | Should -Match 'docker stack deploy -c \$renderedStackFile --resolve-image never \$stackName'
        $debugLauncher | Should -Not -Match 'docker stack deploy -c \$stackFile'
        $debugLauncher | Should -Not -Match 'docker stack deploy -c \$renderedStackFile --prune'
        $debugLauncher | Should -Not -Match '(?m)^\s*Invoke-FilteredStackDeploy\b'
        $debugLauncher | Should -Match '\$maxAttempts = 5'
        $debugLauncher | Should -Match "network \.\* not found"
    }
}
