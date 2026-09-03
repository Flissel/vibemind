BeforeAll {
    $script:DeterminismRepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $script:DeterminismValidator = Join-Path $script:DeterminismRepositoryRoot 'infra\proxmox\image_determinism.py'
    $script:DeterminismPolicyPath = 'infra/proxmox/image-determinism-policy.json'
    $script:DeterminismContract = 'docs/contracts/proxmox-image-determinism-v1.md'
    $script:DeterminismRunbook = 'docs/runbooks/proxmox-image-pinning.md'

    $script:DeterminismPython = $null
    foreach ($candidate in @('python3', 'python')) {
        $resolved = Get-Command -Name $candidate -ErrorAction SilentlyContinue
        if ($resolved) {
            $script:DeterminismPython = $resolved.Source
            break
        }
    }

    $script:PinnedPostgres = 'postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777'
    $script:PinnedNginx = 'nginx:alpine@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752'

    function Invoke-ImageDeterminism {
        param(
            [Parameter(Mandatory)]
            [string]$RepositoryRoot
        )

        $output = & $script:DeterminismPython $script:DeterminismValidator --repo $RepositoryRoot 2>$null | Out-String
        $exitCode = $LASTEXITCODE
        [pscustomobject]@{
            ExitCode = $exitCode
            Report = $output | ConvertFrom-Json -Depth 16
        }
    }

    function Get-FindingCodes {
        param([Parameter(Mandatory)][pscustomobject]$Report)

        return @($Report.findings | ForEach-Object { $_.code })
    }

    function New-DeterminismPolicy {
        param([object[]]$Waivers = @())

        $policy = [ordered]@{
            schema_version = 'vibemind.image-determinism-policy.v1'
            manifests = [ordered]@{
                required = @(
                    'infra/proxmox/phase1-docker-compose.yml',
                    'infra/swarm/vibemind-stack.yml'
                )
                discovery_patterns = @('infra/proxmox/*-docker-compose.yml')
            }
            waivers = @($Waivers)
        }
        return ($policy | ConvertTo-Json -Depth 8)
    }

    function New-DeterminismFixture {
        param(
            [Parameter(Mandatory)]
            [string]$Path,

            [Parameter(Mandatory)]
            [string[]]$Phase1Images,

            [string[]]$StackImages,

            [string]$Policy,

            [switch]$SkipCommit
        )

        New-Item -ItemType Directory -Force -Path $Path | Out-Null
        & git -C $Path init -b main | Out-Null
        & git -C $Path config user.email 'tests@example.invalid'
        & git -C $Path config user.name 'Image Determinism Tests'

        function Format-ComposeServices {
            param([string[]]$Images)

            $lines = @('services:')
            for ($index = 0; $index -lt $Images.Count; $index++) {
                $lines += "  service-$($index):"
                $lines += "    image: $($Images[$index])"
            }
            return ($lines -join "`n") + "`n"
        }

        New-Item -ItemType Directory -Force -Path (Join-Path $Path 'infra\proxmox') | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $Path 'infra\swarm') | Out-Null

        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase1-docker-compose.yml') `
            -Value (Format-ComposeServices -Images $Phase1Images) -NoNewline
        $resolvedStackImages = if ($PSBoundParameters.ContainsKey('StackImages')) { $StackImages } else { @($script:PinnedNginx) }
        Set-Content -LiteralPath (Join-Path $Path 'infra\swarm\vibemind-stack.yml') `
            -Value (Format-ComposeServices -Images $resolvedStackImages) -NoNewline
        $resolvedPolicy = if ($PSBoundParameters.ContainsKey('Policy')) { $Policy } else { New-DeterminismPolicy }
        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\image-determinism-policy.json') `
            -Value $resolvedPolicy -NoNewline

        if (-not $SkipCommit) {
            & git -C $Path add -A | Out-Null
            & git -C $Path commit -m 'test: initialize image determinism fixture' | Out-Null
        }
        return $Path
    }
}

Describe 'Proxmox compose image determinism' -Tag 'ImageDeterminism' {
    BeforeAll {
        if (-not $script:DeterminismPython) {
            throw 'no python interpreter is available; the image determinism gate cannot be evaluated'
        }
    }

    It 'exposes the determinism validator as a versioned artifact' {
        Test-Path -LiteralPath $script:DeterminismValidator | Should -BeTrue
        (& git -C $script:DeterminismRepositoryRoot ls-files -- 'infra/proxmox/image_determinism.py').Trim() |
            Should -Be 'infra/proxmox/image_determinism.py'
        (& git -C $script:DeterminismRepositoryRoot ls-files -- $script:DeterminismPolicyPath).Trim() |
            Should -Be $script:DeterminismPolicyPath
    }

    It 'verifies the tracked deployment manifests of this repository' {
        $result = Invoke-ImageDeterminism -RepositoryRoot $script:DeterminismRepositoryRoot

        $result.Report.schema_version | Should -Be 'vibemind.image-determinism.v1'
        @($result.Report.findings).Count | Should -Be 0
        $result.Report.ready | Should -BeTrue
        $result.ExitCode | Should -Be 0
        @($result.Report.references | Where-Object status -eq 'floating').Count | Should -Be 0
        $result.Report.manifests | Should -Contain 'infra/proxmox/phase1-docker-compose.yml'
        $result.Report.manifests | Should -Contain 'infra/proxmox/phase2a-docker-compose.yml'
        $result.Report.manifests | Should -Contain 'infra/proxmox/phase2b-docker-compose.yml'
        $result.Report.manifests | Should -Contain 'infra/swarm/vibemind-stack.yml'
    }

    It 'documents the determinism rule in a versioned contract and runbook' {
        foreach ($artifact in @($script:DeterminismContract, $script:DeterminismRunbook)) {
            (& git -C $script:DeterminismRepositoryRoot ls-files -- $artifact).Trim() | Should -Be $artifact
        }
    }

    It 'fails closed on a floating image reference' -ForEach @(
        @{ Image = 'postgres:16-alpine' },
        @{ Image = 'redis:latest' },
        @{ Image = 'nginx' },
        @{ Image = 'gitea/gitea:1.23' },
        @{ Image = 'public.ecr.aws/supabase/kong:2.8.1' }
    ) {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive "floating-$([guid]::NewGuid().ToString('N'))") `
            -Phase1Images @($Image)

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        $result.ExitCode | Should -Be 2
        Get-FindingCodes -Report $result.Report | Should -Contain 'image-reference-not-deterministic'
    }

    It 'fails closed on a malformed digest' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'malformed-digest') `
            -Phase1Images @('postgres:16-alpine@sha256:abc123')

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'image-reference-not-deterministic'
    }

    It 'accepts a digest-pinned reference' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'pinned') `
            -Phase1Images @($script:PinnedPostgres)

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeTrue
        $result.ExitCode | Should -Be 0
        @($result.Report.references | Where-Object status -ne 'deterministic').Count | Should -Be 0
    }

    It 'accepts a waived locally built image' {
        $policy = New-DeterminismPolicy -Waivers @(
            [ordered]@{ image = 'vibemind-brain-core:latest'; reason = 'built on the deployment host; no registry digest exists' }
        )
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'waived') `
            -Phase1Images @('vibemind-brain-core:latest') -Policy $policy

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeTrue
        @($result.Report.references | Where-Object status -eq 'waived').Count | Should -Be 1
    }

    It 'fails closed on a waiver without a reason' {
        $policy = New-DeterminismPolicy -Waivers @(
            [ordered]@{ image = 'vibemind-brain-core:latest'; reason = '  ' }
        )
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'waiver-no-reason') `
            -Phase1Images @('vibemind-brain-core:latest') -Policy $policy

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'waiver-reason-missing'
    }

    It 'fails closed on a waiver for a registry-resolvable image' {
        $policy = New-DeterminismPolicy -Waivers @(
            [ordered]@{ image = 'public.ecr.aws/supabase/kong:2.8.1'; reason = 'we would rather not pin this one' }
        )
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'waiver-registry') `
            -Phase1Images @('public.ecr.aws/supabase/kong:2.8.1') -Policy $policy

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'waiver-not-admissible'
    }

    It 'fails closed on a stale waiver' {
        $policy = New-DeterminismPolicy -Waivers @(
            [ordered]@{ image = 'vibemind-retired-service:latest'; reason = 'built on the deployment host; no registry digest exists' }
        )
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'waiver-stale') `
            -Phase1Images @($script:PinnedPostgres) -Policy $policy

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'waiver-stale'
    }

    It 'fails closed when the versioned policy is absent' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'no-policy') `
            -Phase1Images @($script:PinnedPostgres) -SkipCommit
        Remove-Item -LiteralPath (Join-Path $fixture 'infra\proxmox\image-determinism-policy.json')
        & git -C $fixture add -A | Out-Null
        & git -C $fixture commit -m 'test: drop policy' | Out-Null

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'policy-unreadable'
    }

    It 'fails closed when a required manifest is absent' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'missing-manifest') `
            -Phase1Images @($script:PinnedPostgres) -SkipCommit
        Remove-Item -LiteralPath (Join-Path $fixture 'infra\swarm\vibemind-stack.yml')
        & git -C $fixture add -A | Out-Null
        & git -C $fixture commit -m 'test: drop required manifest' | Out-Null

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'manifest-unreadable'
    }

    It 'fails closed on an uncommitted manifest modification' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'dirty-manifest') `
            -Phase1Images @($script:PinnedPostgres)
        Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\phase1-docker-compose.yml') `
            -Value "services:`n  service-0:`n    image: postgres:16-alpine`n" -NoNewline

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'manifest-unreadable'
    }

    It 'fails closed on an untracked compose artifact that matches discovery' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'untracked-compose') `
            -Phase1Images @($script:PinnedPostgres)
        Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') `
            -Value "services:`n  extra:`n    image: $($script:PinnedNginx)`n" -NoNewline

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'manifest-untracked'
    }

    It 'covers an additional discovered Proxmox compose artifact' {
        $fixture = New-DeterminismFixture -Path (Join-Path $TestDrive 'discovered-compose') `
            -Phase1Images @($script:PinnedPostgres) -SkipCommit
        Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') `
            -Value "services:`n  extra:`n    image: redis:7-alpine`n" -NoNewline
        & git -C $fixture add -A | Out-Null
        & git -C $fixture commit -m 'test: add discovered compose artifact' | Out-Null

        $result = Invoke-ImageDeterminism -RepositoryRoot $fixture

        $result.Report.ready | Should -BeFalse
        $result.Report.manifests | Should -Contain 'infra/proxmox/extension-docker-compose.yml'
        Get-FindingCodes -Report $result.Report | Should -Contain 'image-reference-not-deterministic'
    }

    It 'fails closed outside a repository' {
        $result = Invoke-ImageDeterminism -RepositoryRoot (Join-Path $TestDrive 'does-not-exist')

        $result.Report.ready | Should -BeFalse
        Get-FindingCodes -Report $result.Report | Should -Contain 'repository-unavailable'
    }
}
