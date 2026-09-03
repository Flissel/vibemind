BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    . (Join-Path $repoRoot "scripts\vibemind-supabase-cutover-audit.ps1") -LibraryMode
}

Describe "VibeMind Supabase cutover audit" {
    BeforeEach {
        $fixtureRoot = Join-Path $TestDrive ([guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
    }

    It "finds active local Supabase overrides and runtime fallbacks" {
        Set-Content -LiteralPath (Join-Path $fixtureRoot ".env") `
            -Value "SUPABASE_URL=http://localhost:54321" -Encoding utf8
        New-Item -ItemType Directory -Path (Join-Path $fixtureRoot "app") | Out-Null
        Set-Content -LiteralPath (Join-Path $fixtureRoot "app\client.py") `
            -Value 'URL = os.environ.get("SUPABASE_URL", "http://host.docker.internal:54321")' `
            -Encoding utf8
        Set-Content -LiteralPath (Join-Path $fixtureRoot "app\remote.py") `
            -Value 'URL = "http://192.168.178.65:54321"' -Encoding utf8

        $findings = @(Get-VibeMindSupabaseCutoverFinding -RootPath $fixtureRoot)

        $findings.Count | Should -Be 2
        $findings.Target | Should -Contain "localhost:54321"
        $findings.Target | Should -Contain "host.docker.internal:54321"
    }

    It "ignores documentation, tests, examples, backups, and local database definitions" {
        $ignoredFiles = @(
            "docs\guide.md",
            "tests\test_client.py",
            ".env.example",
            ".env.bak-pre-cutover",
            "infra\swarm\supabase\kong.yml",
            ".claude\worktrees\foreign-session\app.py",
            "vibemind-os\la-fungus-search\.fungus_cache\chunks.json",
            "scripts\status_probe_server.py",
            "scripts\vibemind-spaces.ps1",
            "Vibemind.debug.ps1"
        )
        foreach ($relativePath in $ignoredFiles) {
            $path = Join-Path $fixtureRoot $relativePath
            New-Item -ItemType Directory -Path (Split-Path $path) -Force | Out-Null
            Set-Content -LiteralPath $path -Value "SUPABASE_URL=http://localhost:54321" -Encoding utf8
        }

        @(Get-VibeMindSupabaseCutoverFinding -RootPath $fixtureRoot).Count | Should -Be 0
    }

    It "returns only file, line, variable, and target without exposing adjacent values" {
        Set-Content -LiteralPath (Join-Path $fixtureRoot ".env") `
            -Value @(
                "SUPABASE_ANON_KEY=do-not-report-this-value",
                "SUPABASE_URL=http://127.0.0.1:54321"
            ) -Encoding utf8

        $finding = Get-VibeMindSupabaseCutoverFinding -RootPath $fixtureRoot | Select-Object -First 1

        $finding.PSObject.Properties.Name | Should -Be @("Path", "LineNumber", "Variable", "Target")
        ($finding | ConvertTo-Json -Compress) | Should -Not -Match "do-not-report-this-value"
    }

    It "ignores local Supabase service metadata but still finds consumers in the main stack" {
        $stackPath = Join-Path $fixtureRoot "infra\swarm\vibemind-stack.yml"
        New-Item -ItemType Directory -Path (Split-Path $stackPath) -Force | Out-Null
        Set-Content -LiteralPath $stackPath -Value @(
            "API_EXTERNAL_URL: http://127.0.0.1:54321",
            "SUPABASE_PUBLIC_URL: http://127.0.0.1:54321",
            "SUPABASE_URL=http://host.docker.internal:54321"
        ) -Encoding utf8

        $findings = @(Get-VibeMindSupabaseCutoverFinding -RootPath $fixtureRoot)

        $findings.Count | Should -Be 1
        $findings[0].Variable | Should -Be "SUPABASE_URL"
    }

    It "requires runtime injection for every sensitive Phase 2b environment value" {
        $composePath = Join-Path $repoRoot "infra\proxmox\phase2b-docker-compose.yml"
        $sensitiveNames = @(
            "POSTGRES_PASSWORD", "PGPASSWORD", "DB_PASSWORD", "PG_META_DB_PASSWORD",
            "JWT_SECRET", "GOTRUE_JWT_SECRET", "PGRST_JWT_SECRET", "API_JWT_SECRET",
            "METRICS_JWT_SECRET", "AUTH_JWT_SECRET", "DB_ENC_KEY", "SECRET_KEY_BASE",
            "ANON_KEY", "SUPABASE_ANON_KEY", "SERVICE_KEY", "SUPABASE_SERVICE_KEY",
            "LOGFLARE_PRIVATE_ACCESS_TOKEN", "LOGFLARE_PUBLIC_ACCESS_TOKEN"
        )

        $assignments = @(
            Get-Content -LiteralPath $composePath |
                Select-String -Pattern '^\s+(?<name>[A-Z][A-Z0-9_]+):\s+(?<value>.+)$' |
                Where-Object { $_.Matches[0].Groups["name"].Value -in $sensitiveNames }
        )

        $assignments.Count | Should -Be 22
        foreach ($assignment in $assignments) {
            $assignment.Matches[0].Groups["value"].Value |
                Should -Match '^\$\{[A-Z0-9_]+:\?[A-Z0-9_]+ is required\}$'
        }
    }
}
