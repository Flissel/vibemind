BeforeAll {
    $script:PreflightScript = Join-Path $PSScriptRoot '..\..\scripts\deployment-readiness.ps1'
    $script:PowerShell = (Get-Command pwsh -ErrorAction Stop).Source
    function New-ReadinessFixture {
        param(
            [Parameter(Mandatory)]
            [string]$Path,

            [switch]$GoldenPath,

            [switch]$PassThru
        )

        $source = "$Path-submodule-source"
        New-Item -ItemType Directory -Force -Path $source | Out-Null
        & git -C $source init -b main | Out-Null
        & git -C $source config user.email 'tests@example.invalid'
        & git -C $source config user.name 'Deployment Readiness Tests'
        New-Item -ItemType Directory -Force -Path (Join-Path $source 'config') | Out-Null
        Set-Content -LiteralPath (Join-Path $source 'README.md') -Value 'submodule source' -NoNewline
        Set-Content -LiteralPath (Join-Path $source 'llm_config.yml.example') -Value 'providers: {}' -NoNewline
        Set-Content -LiteralPath (Join-Path $source 'config\space_agent_registry.yml') -Value 'spaces: {}' -NoNewline
        & git -C $source add README.md llm_config.yml.example config
        & git -C $source commit -m 'test: initialize submodule source' | Out-Null

        $openFangPin = $null
        $voicePin = $null
        if ($GoldenPath) {
            foreach ($nestedRepository in @('openfang', 'voice')) {
                $nestedSource = "$Path-$nestedRepository-source"
                New-Item -ItemType Directory -Force -Path $nestedSource | Out-Null
                & git -C $nestedSource init -b main | Out-Null
                & git -C $nestedSource config user.email 'tests@example.invalid'
                & git -C $nestedSource config user.name 'Deployment Readiness Tests'
                Set-Content -LiteralPath (Join-Path $nestedSource 'README.md') -Value "$nestedRepository source" -NoNewline
                & git -C $nestedSource add README.md
                & git -C $nestedSource commit -m "test: initialize $nestedRepository source" | Out-Null
                & git -C $source -c protocol.file.allow=always submodule add $nestedSource $nestedRepository | Out-Null
                if ($nestedRepository -eq 'openfang') {
                    $openFangPin = (& git -C $nestedSource rev-parse HEAD).Trim()
                } else {
                    $voicePin = (& git -C $nestedSource rev-parse HEAD).Trim()
                }
            }
            & git -C $source add .gitmodules openfang voice
            & git -C $source commit -m 'test: add nested golden path submodules' | Out-Null
        }
        $gitlinkPin = (& git -C $source rev-parse HEAD).Trim()

        New-Item -ItemType Directory -Force -Path $Path | Out-Null
        & git -C $Path init -b main | Out-Null
        & git -C $Path config user.email 'tests@example.invalid'
        & git -C $Path config user.name 'Deployment Readiness Tests'
        $validatorModule = Join-Path $Path 'tools\v1_governance'
        New-Item -ItemType Directory -Force -Path $validatorModule | Out-Null
        Set-Content -LiteralPath (Join-Path $Path 'tools\__init__.py') -Value '' -NoNewline
        Set-Content -LiteralPath (Join-Path $validatorModule '__init__.py') -Value '' -NoNewline
        @'
import json
import pathlib
import re
import subprocess
import sys

repository = pathlib.Path(sys.argv[sys.argv.index("--repo") + 1])
manifest = (repository / "repo-manifest.yaml").read_text(encoding="utf-8")
expected = re.search(r"expected_gitlink_pin:\s*([0-9a-f]{40})", manifest)
actual = subprocess.run(
    ["git", "-C", str(repository), "rev-parse", "HEAD:vibemind-os"],
    capture_output=True,
    check=False,
    text=True,
).stdout.strip()
ready = expected is not None and expected.group(1) == actual
findings = [] if ready else [{"code": "gitlink-manifest-mismatch", "path": "repo-manifest.yaml"}]
print(json.dumps({"ready": ready, "findings": findings}))
sys.exit(0 if ready else 2)
'@ | Set-Content -LiteralPath (Join-Path $validatorModule '__main__.py') -NoNewline
        New-Item -ItemType Directory -Force -Path (Join-Path $Path 'infra\proxmox') | Out-Null
        Set-Content -LiteralPath (Join-Path $Path 'vibemind.config.json') -Value '{}' -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase1-docker-compose.yml') -Value 'services: {}' -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase1-configs-manifest.json') -Value '{}' -NoNewline
        @'
services:
  remote-embedding-client:
    image: example.invalid/vibemind/remote-provider-client:latest
    environment:
      - EMBEDDING_MODEL=text-embedding-3-small
'@ | Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase2a-docker-compose.yml') -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase2b-docker-compose.yml') -Value 'services: {}' -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'infra\proxmox\phase2-required-vars.txt') -Value 'EXAMPLE_REQUIRED_VARIABLE' -NoNewline
        New-Item -ItemType Directory -Force -Path (Join-Path $Path 'docs\runbooks') | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $Path 'docs\contracts') | Out-Null
        Set-Content -LiteralPath (Join-Path $Path 'docs\runbooks\proxmox-reboot.md') -Value '# Reboot' -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'docs\runbooks\proxmox-backup-restore.md') -Value '# Backup and restore' -NoNewline
        Set-Content -LiteralPath (Join-Path $Path 'docs\runbooks\proxmox-cutover-rollback.md') -Value '# Cutover and rollback' -NoNewline
        @'
# Proxmox No-Model Runtime V1

No model may execute on the Proxmox host or in any VM, container, service, worker, or job scheduled on it.
This prohibition covers LLM, embedding, reranking, OCR and vision, speech recognition, TTS, lip-sync, image, video, and any other model inference.
Model weights, model caches, accelerators assigned for inference, and model-serving runtimes are forbidden inside the Proxmox boundary.
Brain, OpenFang, Spaces, and workers may run there only when they perform no inference and route every model request to an approved provider outside the Proxmox boundary; missing remote authority fails closed.
Provider model identifiers such as `EMBEDDING_MODEL` are configuration only and never authorize local weights or inference.
'@ | Set-Content -LiteralPath (Join-Path $Path 'docs\contracts\proxmox-no-model-runtime-v1.md') -NoNewline
        if ($GoldenPath) {
            New-Item -ItemType Directory -Force -Path (Join-Path $Path 'docs\contracts') | Out-Null
            New-Item -ItemType Directory -Force -Path (Join-Path $Path 'docs\superpowers\specs') | Out-Null
            New-Item -ItemType Directory -Force -Path (Join-Path $Path 'docs\governance') | Out-Null
            New-Item -ItemType Directory -Force -Path (Join-Path $Path 'shared\contracts\brain\v1') | Out-Null
            @'
# Brain OpenFang Space Reference Path V1

Brain is the control plane.
OpenFang is the execution engine.
No direct fallback is permitted.
The Space-Agent and MCP/Service adapter precede independent Truth/Evidence.
OpenFang accepts a separately admissible handoff, creates or correlates `approval_id` and `cost_id`.

| Identifier | Owner at creation | What it correlates | What it does not prove |
| --- | --- | --- | --- |
| `approval_id` | OpenFang | the policy decision for executable work | that an external action occurred |
| `cost_id` | OpenFang | the cost-policy or ledger record | cost settlement or provider billing |

Truth/Evidence is independent of the actor making the claim.
Independent Truth/Evidence is required; transport or tool success alone is insufficient.
'@ | Set-Content -LiteralPath (Join-Path $Path 'docs\contracts\brain-openfang-space-reference-path-v1.md') -NoNewline
            Set-Content -LiteralPath (Join-Path $Path 'docs\superpowers\specs\2026-07-30-v1-space-orchestration-design.md') -Value 'Jeder ausführbare Intent läuft über Brain zu OpenFang und von dort zum zuständigen Space-Agenten und der bestehenden Application.' -NoNewline
            Set-Content -LiteralPath (Join-Path $Path 'docs\contracts\space-execution-contract-v1.md') -Value '| OpenFang | execution, permissions, approvals, providers, and costs | shared contract ownership |' -NoNewline
            @'
Transport success is not `verified_live`.
An HTTP 2xx response is not `verified_live`.
Registry matches are not `verified_live`.
'@ | Set-Content -LiteralPath (Join-Path $Path 'docs\contracts\observability-evidence-governance-v2.md') -NoNewline
            Set-Content -LiteralPath (Join-Path $Path 'shared\contracts\brain\v1\brain-plan-lifecycle-v1.schema.json') -Value '{"status":{"enum":["execution_deferred"]}}' -NoNewline
            Set-Content -LiteralPath (Join-Path $Path 'shared\contracts\brain\v1\brain-openfang-handoff-v1.schema.json') -Value '{"execution_boundary":{"const":"openfang"},"approval_ref":{},"cost_ref":{}}' -NoNewline
            @"
{"entries":[{"kind":"historical-gitlink-chain","links":[{"path":"vibemind-os","target_commit":"$gitlinkPin"},{"path":"openfang","target_commit":"$openFangPin"},{"path":"voice","target_commit":"$voicePin"}]}]}
"@ | Set-Content -LiteralPath (Join-Path $Path 'docs\governance\cockpit-reconciliation-ledger-v1.json') -NoNewline
        }
        @"
schema_version: 1
repositories:
  - id: vibemind-os
    parent: vibemind-v1
    path: vibemind-os
    kind: submodule
    expected_gitlink_pin: $gitlinkPin
"@ | Set-Content -LiteralPath (Join-Path $Path 'repo-manifest.yaml') -NoNewline
        & git -C $Path add vibemind.config.json infra docs repo-manifest.yaml tools
        if ($GoldenPath) {
            & git -C $Path add shared
        }
        & git -C $Path commit -m 'test: initialize deployment fixture' | Out-Null
        & git -C $Path -c protocol.file.allow=always submodule add $source vibemind-os | Out-Null
        & git -C $Path commit -am 'test: add deployment submodule' | Out-Null
        if ($GoldenPath) {
            & git -C (Join-Path $Path 'vibemind-os') -c protocol.file.allow=always submodule update --init | Out-Null
        }
        $basePin = (& git -C $Path rev-parse HEAD).Trim()
        & git -C $Path update-ref refs/remotes/origin/master $basePin

        if ($PassThru) {
            return [pscustomobject]@{
                BasePin = $basePin
                OuterChildPin = $gitlinkPin
                OpenFangPin = $openFangPin
                VoicePin = $voicePin
            }
        }
    }

    function Invoke-ReadinessPreflight {
        param(
            [Parameter(Mandatory)]
            [string]$RepositoryRoot,

            [switch]$LiveProbes,

            [string]$PythonCommand,

            [string]$ProxmoxUri,

            [string]$SupabaseUri,

            [string]$QdrantUri,

            [string]$CallerDirectory,

            [string]$PreflightScript = $script:PreflightScript
        )

        $reportPath = Join-Path $RepositoryRoot 'results\deployment-readiness.json'
        $arguments = @(
            '-NoProfile',
            '-File', $PreflightScript,
            '-RepositoryRoot', $RepositoryRoot,
            '-OutputPath', $reportPath
        )
        if ($LiveProbes) { $arguments += '-LiveProbes' }
        if ($PythonCommand) { $arguments += @('-PythonCommand', $PythonCommand) }
        if ($ProxmoxUri) { $arguments += @('-ProxmoxUri', $ProxmoxUri) }
        if ($SupabaseUri) { $arguments += @('-SupabaseUri', $SupabaseUri) }
        if ($QdrantUri) { $arguments += @('-QdrantUri', $QdrantUri) }
        $locationPushed = $false
        try {
            if ($CallerDirectory) {
                Push-Location -LiteralPath $CallerDirectory
                $locationPushed = $true
            }
            & $script:PowerShell @arguments | Out-Null
        } finally {
            if ($locationPushed) {
                Pop-Location
            }
        }
        [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json -Depth 16
        }
    }

    function New-GoldenPathPreflightScript {
        param(
            [Parameter(Mandatory)]
            [string]$FixtureRoot,

            [Parameter(Mandatory)]
            [pscustomobject]$Pins,

            [string]$RequiredOuterChildPin = $Pins.OuterChildPin,

            [string]$RequiredOpenFangPin = $Pins.OpenFangPin,

            [string]$RequiredVoicePin = $Pins.VoicePin
        )

        $fixtureScript = Join-Path $FixtureRoot 'deployment-readiness-controlled-fixture.ps1'
        $content = Get-Content -LiteralPath $script:PreflightScript -Raw
        foreach ($replacement in @(
            @{ From = '1a78d9e42fc90b0463185d7af5442d75a6894a52'; To = $Pins.BasePin },
            @{ From = '62b50ce1336ce88fd162c79a66b8ede3b3b43144'; To = $Pins.BasePin },
            @{ From = '99d41a795ac7538fb32927664a301d318d62e725'; To = $Pins.BasePin },
            @{ From = '82127e44944495e5cb47d22e597cee9c51bbee83'; To = $RequiredOuterChildPin },
            @{ From = '8a4904b3ff622d7ffda1e8cb01a509d2db430904'; To = $RequiredOpenFangPin },
            @{ From = 'a8c8d9f172a768850ad4cf999c6ebbb68bc6f015'; To = $RequiredVoicePin }
        )) {
            $content = $content.Replace($replacement.From, $replacement.To)
        }
        Set-Content -LiteralPath $fixtureScript -Value $content -NoNewline
        return $fixtureScript
    }

    function Invoke-GoldenPathPreflight {
        param(
            [Parameter(Mandatory)]
            [string]$RepositoryRoot,

            [Parameter(Mandatory)]
            [pscustomobject]$Pins,

            [string]$RequiredOuterChildPin = $Pins.OuterChildPin,

            [string]$RequiredOpenFangPin = $Pins.OpenFangPin,

            [string]$RequiredVoicePin = $Pins.VoicePin
        )

        $fixtureScript = New-GoldenPathPreflightScript -FixtureRoot $RepositoryRoot -Pins $Pins `
            -RequiredOuterChildPin $RequiredOuterChildPin -RequiredOpenFangPin $RequiredOpenFangPin `
            -RequiredVoicePin $RequiredVoicePin
        return Invoke-ReadinessPreflight -RepositoryRoot $RepositoryRoot -PreflightScript $fixtureScript
    }
}

Describe 'Proxmox operations runbook bundle' {
    BeforeAll {
        $script:RunbookRepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $script:OperationsRunbooks = @(
            'docs/runbooks/proxmox-reboot.md',
            'docs/runbooks/proxmox-backup-restore.md',
            'docs/runbooks/proxmox-cutover-rollback.md'
        )

        function Test-RunbookRequiredPhrases {
            param(
                [Parameter(Mandatory)]
                [string]$Content,

                [Parameter(Mandatory)]
                [string[]]$RequiredPhrases
            )

            return @($RequiredPhrases | Where-Object {
                    $Content -notmatch [regex]::Escape($_)
                }).Count -eq 0
        }

        function Test-CommonStaticRunbookBoundaries {
            param([Parameter(Mandatory)][string]$Content)

            return Test-RunbookRequiredPhrases -Content $Content -RequiredPhrases @(
                '## Scope and boundaries',
                'deployment_proven=false',
                'golden_path_proven=false',
                'does not perform or prove a runtime operation'
            )
        }

        function Test-RebootRunbookSemantics {
            param([Parameter(Mandatory)][string]$Content)

            return Test-RunbookRequiredPhrases -Content $Content -RequiredPhrases @(
                'request-specific authority',
                'current inventory',
                'backup or snapshot reference',
                'maintenance window',
                'stop criteria',
                'Health and reachability evidence',
                'operational verification',
                'independent readback',
                'restart escalation boundary'
            )
        }

        function Test-BackupRestoreRunbookSemantics {
            param([Parameter(Mandatory)][string]$Content)

            return Test-RunbookRequiredPhrases -Content $Content -RequiredPhrases @(
                'Static inventory',
                'PostgreSQL',
                'MongoDB',
                'Neo4j',
                'volumes',
                'versioned configuration',
                'backup reference',
                'timestamp',
                'checksum',
                'retention decision',
                'separate high-risk action with its own authority',
                'Restore probe',
                'data integrity',
                'independent readback',
                'fail closed',
                'unknown origin'
            )
        }

        function Test-CutoverRollbackRunbookSemantics {
            param([Parameter(Mandatory)][string]$Content)

            return Test-RunbookRequiredPhrases -Content $Content -RequiredPhrases @(
                'source boundary',
                'target boundary',
                'consumer inventory',
                'change freeze',
                'static readiness',
                'migration or audit result',
                'maintenance window',
                'No direct database fallback',
                'No silent dual-write',
                'independent readback',
                'consumer divergence',
                'Rollback triggers',
                'decision owner',
                'preserve the prior data basis',
                'Transport or health success is not cutover success'
            )
        }
    }

    It 'keeps all three runbooks versioned with common static-operation boundaries' {
        foreach ($relativePath in $script:OperationsRunbooks) {
            $absolutePath = Join-Path $script:RunbookRepositoryRoot $relativePath
            Test-Path -LiteralPath $absolutePath | Should -BeTrue
            (& git -C $script:RunbookRepositoryRoot ls-files --error-unmatch -- $relativePath 2>$null) |
                Should -Be $relativePath
            $LASTEXITCODE | Should -Be 0
            $status = & git -C $script:RunbookRepositoryRoot status --porcelain -- $relativePath
            $LASTEXITCODE | Should -Be 0
            @($status | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count | Should -Be 0

            $content = Get-Content -LiteralPath $absolutePath -Raw
            (Test-CommonStaticRunbookBoundaries -Content $content) | Should -BeTrue
        }

        $commonMutated = (Get-Content -LiteralPath (Join-Path $script:RunbookRepositoryRoot $script:OperationsRunbooks[0]) -Raw).
            Replace('`deployment_proven=false`', '')
        (Test-CommonStaticRunbookBoundaries -Content $commonMutated) | Should -BeFalse
    }

    It 'requires reboot authority, prerequisites, stop criteria, evidence separation, and restart escalation' {
        $content = Get-Content -LiteralPath (Join-Path $script:RunbookRepositoryRoot $script:OperationsRunbooks[0]) -Raw

        $mutated = $content.Replace('request-specific authority', 'ordinary authority')
        (Test-RebootRunbookSemantics -Content $content) | Should -BeTrue
        (Test-RebootRunbookSemantics -Content $mutated) | Should -BeFalse
    }

    It 'separates backup, high-risk restore, integrity, independent readback, and fail-closed conditions' {
        $content = Get-Content -LiteralPath (Join-Path $script:RunbookRepositoryRoot $script:OperationsRunbooks[1]) -Raw

        $mutated = $content.Replace('checksum', 'integrity marker')
        (Test-BackupRestoreRunbookSemantics -Content $content) | Should -BeTrue
        (Test-BackupRestoreRunbookSemantics -Content $mutated) | Should -BeFalse
    }

    It 'requires consumer and divergence gates, forbids fallbacks and dual writes, and preserves rollback control' {
        $content = Get-Content -LiteralPath (Join-Path $script:RunbookRepositoryRoot $script:OperationsRunbooks[2]) -Raw

        $mutated = $content.Replace('No silent dual-write', 'Dual-write allowed')
        (Test-CutoverRollbackRunbookSemantics -Content $content) | Should -BeTrue
        (Test-CutoverRollbackRunbookSemantics -Content $mutated) | Should -BeFalse
    }
}

Describe 'deployment readiness preflight' {
    It 'aligns authority-chain pin constants with committed and staged static facts' {
        $repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $expectedOuterChildPin = '82127e44944495e5cb47d22e597cee9c51bbee83'
        $expectedOpenFangPin = '8a4904b3ff622d7ffda1e8cb01a509d2db430904'
        $expectedSharedPin = 'fe9c31d257c551568794c44098bf75e92f327e7f'
        $expectedVoicePin = 'a8c8d9f172a768850ad4cf999c6ebbb68bc6f015'

        $expectedCommittedGitlink = "160000 commit $expectedOuterChildPin`t" + 'vibemind-os'
        $expectedStagedGitlink = "160000 $expectedOuterChildPin 0`t" + 'vibemind-os'
        (& git -C $repositoryRoot ls-tree HEAD vibemind-os).Trim() |
            Should -Be $expectedCommittedGitlink
        (& git -C $repositoryRoot ls-files --stage -- vibemind-os).Trim() |
            Should -Be $expectedStagedGitlink

        foreach ($specification in @(
            @{ Path = 'repo-manifest.yaml'; Pin = $expectedOpenFangPin },
            @{ Path = 'repo-manifest.yaml'; Pin = $expectedSharedPin },
            @{ Path = 'repo-manifest.yaml'; Pin = $expectedVoicePin }
        )) {
            (& git -C $repositoryRoot show "HEAD:$($specification.Path)" | Out-String) |
                Should -Match ([regex]::Escape($specification.Pin))
            (& git -C $repositoryRoot show ":$($specification.Path)" | Out-String) |
                Should -Match ([regex]::Escape($specification.Pin))
        }

        $preflightContent = Get-Content -LiteralPath $script:PreflightScript -Raw
        $preflightContent | Should -Match ([regex]::Escape("`$RequiredOuterChildPin = '$expectedOuterChildPin'"))
        $preflightContent | Should -Match ([regex]::Escape("`$RequiredOpenFangPin = '$expectedOpenFangPin'"))
        $preflightContent | Should -Match ([regex]::Escape("`$RequiredVoicePin = '$expectedVoicePin'"))
    }

    It 'does not retain superseded authority-chain pins' {
        $preflightContent = Get-Content -LiteralPath $script:PreflightScript -Raw

        $preflightContent | Should -Not -Match '407d515280b97ddfb7cedfe820cc1d938a50f3c6'
        $preflightContent | Should -Not -Match '26003b952d65359f116b14eba55695dc74d2b528'
        $preflightContent | Should -Not -Match 'fac8e429f5adfa50ac59dce2360c481290148cad'
        $preflightContent | Should -Not -Match '87596f0347aaa244353fbbf2dde79f05b29c5070'
        $preflightContent | Should -Not -Match '36dc5260e3408b64ad2eb26958549d1faedf78e1'
        $preflightContent | Should -Not -Match '89ba6176a40d190840dd36360a81dfdb3de3b97c'
        $preflightContent | Should -Not -Match '4bb89b22c287f84f6bb4f5ac6d40612531a33651'
        $preflightContent | Should -Not -Match '9ee1cc42401185824a4f4c624c33a8bde1dc92b8'
        $preflightContent | Should -Not -Match '33be359cb30574b5b62c14686f9459ec11fcc184'
        $preflightContent | Should -Not -Match '731288b4e36ac172dfb902e22627c6f937760a3e'
        $preflightContent | Should -Not -Match '75067d8c6b375fb70fe677daf78918164caaff41'
        $preflightContent | Should -Not -Match '2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899'
    }

    It 'writes a redacted static report without requiring Docker Engine' {
        $fixture = Join-Path $TestDrive 'static-ready'
        New-ReadinessFixture -Path $fixture

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.Report.schema_version | Should -Be 'vibemind.deployment-readiness.v1'
        $result.Report.mode | Should -Be 'static'
        $result.Report.deployment_proven | Should -BeFalse
        $result.Report.golden_path_proven | Should -BeFalse
        ($result.Report.checks | Where-Object id -eq 'static.phase2-compose').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.openfang-pinned-config').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.openfang-pinned-registry').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-reboot-artifact').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-backup-restore-artifact').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-cutover-rollback-artifact').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'local.docker-engine').status | Should -Be 'unverified'
        ($result.Report.checks | Where-Object id -eq 'static.submodule-readiness').status | Should -Be 'verified'
        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-predeploy').status | Should -Be 'blocked'
    }

    It 'fails closed when a required static manifest is absent' {
        $fixture = Join-Path $TestDrive 'missing-manifest'
        New-ReadinessFixture -Path $fixture
        Remove-Item -LiteralPath (Join-Path $fixture 'infra\proxmox\phase2a-docker-compose.yml')

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.phase2-compose').status | Should -Be 'blocked'
    }

    It 'blocks a tracked Proxmox compose artifact that declares a model runtime' {
        $fixture = Join-Path $TestDrive 'proxmox-model-runtime'
        New-ReadinessFixture -Path $fixture
        @'
services:
  local-model:
    image: ollama/ollama:latest
    command: ["ollama", "serve"]
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\phase2b-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/phase2b-docker-compose.yml
        & git -C $fixture commit -m 'test: add forbidden Proxmox model runtime' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'blocks a model server hidden in a multi-line compose command' {
        $fixture = Join-Path $TestDrive 'proxmox-split-model-command'
        New-ReadinessFixture -Path $fixture
        @'
services:
  opaque-worker:
    image: example.invalid/vibemind/worker:latest
    command:
      - python
      - -m
      - vllm.entrypoints.openai.api_server
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\phase2b-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/phase2b-docker-compose.yml
        & git -C $fixture commit -m 'test: hide forbidden model runtime in command list' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    Context 'Proxmox compose discovery' -Tag 'ComposeDiscovery' {
    It 'blocks every forbidden model-runtime signal in an additional tracked Proxmox compose artifact' {
        $fixture = Join-Path $TestDrive 'proxmox-added-model-runtime-signals'
        New-ReadinessFixture -Path $fixture
        @'
services:
  model-server:
    image: ollama/ollama:latest
    command: ["ollama", "serve"]
    environment:
      - HF_HOME=/models/cache
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add forbidden compose extension' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'allows a committed benign additional Proxmox compose artifact with a remote model identifier' {
        $fixture = Join-Path $TestDrive 'proxmox-added-benign-compose'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
    environment:
      - EMBEDDING_MODEL=text-embedding-3-small
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add benign compose extension' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'verified'
    }

    It 'blocks a model-weight cache in an additional tracked Proxmox compose artifact' {
        $fixture = Join-Path $TestDrive 'proxmox-added-model-cache'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
    environment:
      - HF_HOME=/models/cache
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add forbidden compose cache' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'blocks an accelerator assignment in an additional tracked Proxmox compose artifact' {
        $fixture = Join-Path $TestDrive 'proxmox-added-accelerator'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
    gpus: all
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add forbidden compose accelerator' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'blocks a block-list accelerator capability in an additional tracked Proxmox compose artifact' {
        $fixture = Join-Path $TestDrive 'proxmox-added-accelerator-capability-list'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
    deploy:
      resources:
        reservations:
          devices:
            - capabilities:
                - gpu
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add forbidden accelerator capability list' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'fails closed when an additional tracked Proxmox compose artifact has no HEAD version' {
        $fixture = Join-Path $TestDrive 'proxmox-index-only-compose'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'fails closed when an additional committed Proxmox compose artifact is staged for deletion' {
        $fixture = Join-Path $TestDrive 'proxmox-staged-compose-deletion'
        New-ReadinessFixture -Path $fixture
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add compose extension before staged deletion' | Out-Null
        & git -C $fixture rm infra/proxmox/extension-docker-compose.yml | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'fails closed when a committed model compose artifact is staged for rename to a benign artifact' {
        $fixture = Join-Path $TestDrive 'proxmox-staged-compose-rename'
        New-ReadinessFixture -Path $fixture
        @'
services:
  local-model:
    image: ollama/ollama:latest
    command: ["ollama", "serve"]
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\extension-docker-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/extension-docker-compose.yml
        & git -C $fixture commit -m 'test: add model compose extension before staged rename' | Out-Null
        & git -C $fixture mv infra/proxmox/extension-docker-compose.yml infra/proxmox/renamed-compose.yml
        @'
services:
  remote-provider-client:
    image: example.invalid/vibemind/remote-provider-client:latest
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\renamed-compose.yml') -NoNewline
        & git -C $fixture add infra/proxmox/renamed-compose.yml

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'does not treat an untracked Proxmox compose artifact as versioned policy input' {
        $fixture = Join-Path $TestDrive 'proxmox-untracked-compose'
        New-ReadinessFixture -Path $fixture
        @'
services:
  local-model:
    image: ollama/ollama:latest
    command: ["ollama", "serve"]
'@ | Set-Content -LiteralPath (Join-Path $fixture 'infra\proxmox\untracked-docker-compose.yml') -NoNewline

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'verified'
    }
    }

    It 'blocks a weakened Proxmox no-model contract' {
        $fixture = Join-Path $TestDrive 'weakened-proxmox-model-contract'
        New-ReadinessFixture -Path $fixture
        $contractPath = Join-Path $fixture 'docs\contracts\proxmox-no-model-runtime-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('No model may execute', 'Models may execute') |
            Set-Content -LiteralPath $contractPath -NoNewline
        & git -C $fixture add docs/contracts/proxmox-no-model-runtime-v1.md
        & git -C $fixture commit -m 'test: weaken Proxmox model policy' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-no-model-runtime').status | Should -Be 'blocked'
    }

    It 'fails closed when the pinned OpenFang registry is not readable' {
        $fixture = Join-Path $TestDrive 'missing-openfang-registry'
        New-ReadinessFixture -Path $fixture
        Remove-Item -LiteralPath (Join-Path $fixture 'vibemind-os\config\space_agent_registry.yml')

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.openfang-pinned-registry').status | Should -Be 'blocked'
    }

    It 'fails closed when an OpenFang file is checked out off the tracked Gitlink pin' {
        $fixture = Join-Path $TestDrive 'openfang-off-pin'
        New-ReadinessFixture -Path $fixture
        $submodule = Join-Path $fixture 'vibemind-os'
        Set-Content -LiteralPath (Join-Path $submodule 'off-pin.txt') -Value 'different pin' -NoNewline
        & git -C $submodule add off-pin.txt
        & git -C $submodule commit -m 'test: move submodule past pinned revision' | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.openfang-pinned-config').status | Should -Be 'blocked'
    }

    It 'fails closed when a required rollback artifact is not versioned' {
        $fixture = Join-Path $TestDrive 'untracked-rollback-artifact'
        New-ReadinessFixture -Path $fixture
        & git -C $fixture rm --cached docs/runbooks/proxmox-cutover-rollback.md | Out-Null

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.proxmox-cutover-rollback-artifact').status | Should -Be 'blocked'
    }

    It 'keeps each missing Proxmox runbook blocked as a separate prerequisite' {
        foreach ($artifact in @(
            @{ File = 'proxmox-reboot.md'; Id = 'static.proxmox-reboot-artifact' },
            @{ File = 'proxmox-backup-restore.md'; Id = 'static.proxmox-backup-restore-artifact' },
            @{ File = 'proxmox-cutover-rollback.md'; Id = 'static.proxmox-cutover-rollback-artifact' }
        )) {
            $fixture = Join-Path $TestDrive "missing-proxmox-runbooks-$($artifact.Id)"
            New-ReadinessFixture -Path $fixture
            Remove-Item -LiteralPath (Join-Path $fixture (Join-Path 'docs\runbooks' $artifact.File))

            $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

            $result.ExitCode | Should -Be 1
            ($result.Report.checks | Where-Object id -eq $artifact.Id).status | Should -Be 'blocked'
        }
    }

    It 'keeps supplied runtime targets out of the evidence report' {
        $fixture = Join-Path $TestDrive 'redaction'
        New-ReadinessFixture -Path $fixture
        $marker = 'not-for-evidence.example.invalid'

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture -ProxmoxUri "https://$marker`:8006/"

        $result.ExitCode | Should -Be 1
        ($result.Report | ConvertTo-Json -Depth 16) | Should -Not -Match $marker
        ($result.Report.checks | Where-Object id -eq 'runtime.proxmox-target').status | Should -Be 'verified'
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-predeploy').status | Should -Be 'blocked'
    }

    It 'fails closed when opt-in live probes do not have every target configured' {
        $fixture = Join-Path $TestDrive 'live-missing-targets'
        New-ReadinessFixture -Path $fixture

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture -LiveProbes

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'live.proxmox-reachability').status | Should -Be 'blocked'
        ($result.Report.checks | Where-Object id -eq 'live.supabase-reachability').status | Should -Be 'blocked'
        ($result.Report.checks | Where-Object id -eq 'live.qdrant-reachability').status | Should -Be 'blocked'
    }

    It 'rejects external output paths before they can be created or overwritten' {
        $fixture = Join-Path $TestDrive 'contained-output'
        New-ReadinessFixture -Path $fixture
        $externalDirectory = Join-Path $TestDrive 'external-output'
        New-Item -ItemType Directory -Force -Path $externalDirectory | Out-Null
        $existingOutput = Join-Path $externalDirectory 'existing-evidence.json'
        $missingOutput = Join-Path $externalDirectory 'missing-evidence.json'
        $sentinel = 'do-not-overwrite'
        Set-Content -LiteralPath $existingOutput -Value $sentinel -NoNewline

        foreach ($outputPath in @($existingOutput, $missingOutput)) {
            & $script:PowerShell -NoProfile -File $script:PreflightScript `
                -RepositoryRoot $fixture -OutputPath $outputPath 2>$null | Out-Null
            $LASTEXITCODE | Should -Be 1
        }

        Get-Content -LiteralPath $existingOutput -Raw | Should -Be $sentinel
        Test-Path -LiteralPath $missingOutput | Should -BeFalse
    }

    It 'fails closed when the manifest expected pin differs from the tracked Gitlink' {
        $fixture = Join-Path $TestDrive 'manifest-gitlink-mismatch'
        New-ReadinessFixture -Path $fixture
        $manifestPath = Join-Path $fixture 'repo-manifest.yaml'
        (Get-Content -LiteralPath $manifestPath -Raw).Replace(
            (& git -C $fixture rev-parse HEAD:vibemind-os).Trim(),
            '0000000000000000000000000000000000000000'
        ) | Set-Content -LiteralPath $manifestPath -NoNewline

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.submodule-readiness').status | Should -Be 'blocked'
    }

    It 'fails closed when the submodule-readiness validator is unavailable' {
        $fixture = Join-Path $TestDrive 'validator-unavailable'
        New-ReadinessFixture -Path $fixture
        $unavailablePython = Join-Path $TestDrive 'missing-python.cmd'

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture -PythonCommand $unavailablePython

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.submodule-readiness').status | Should -Be 'blocked'
    }

    It 'fails closed when the submodule-readiness validator returns malformed output' {
        $fixture = Join-Path $TestDrive 'validator-malformed'
        New-ReadinessFixture -Path $fixture
        $malformedPython = Join-Path $TestDrive 'malformed-python.cmd'
        Set-Content -LiteralPath $malformedPython -Value '@echo not-json' -NoNewline

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture -PythonCommand $malformedPython

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.submodule-readiness').status | Should -Be 'blocked'
    }

    It 'runs the submodule-readiness validator from RepositoryRoot rather than the caller CWD' {
        $fixture = Join-Path $TestDrive 'validator-repository-root'
        New-ReadinessFixture -Path $fixture
        $repositoryModule = Join-Path $fixture 'tools\v1_governance'
        $caller = Join-Path $TestDrive 'validator-caller'
        $callerModule = Join-Path $caller 'tools\v1_governance'
        New-Item -ItemType Directory -Force -Path $repositoryModule, $callerModule | Out-Null
        foreach ($module in @($repositoryModule, $callerModule)) {
            Set-Content -LiteralPath (Join-Path (Split-Path -Parent $module) '__init__.py') -Value '' -NoNewline
            Set-Content -LiteralPath (Join-Path $module '__init__.py') -Value '' -NoNewline
        }
        Set-Content -LiteralPath (Join-Path $repositoryModule '__main__.py') -Value @'
import json
print(json.dumps({"ready": True, "findings": []}))
'@ -NoNewline
        Set-Content -LiteralPath (Join-Path $callerModule '__main__.py') -Value @'
import json
print(json.dumps({"ready": False, "findings": [{"code": "caller-decoy"}]}))
'@ -NoNewline

        $result = Invoke-ReadinessPreflight -RepositoryRoot $fixture -CallerDirectory $caller

        ($result.Report.checks | Where-Object id -eq 'static.submodule-readiness').status | Should -Be 'verified'
    }

    It 'verifies every golden path detail and aggregate for a complete controlled chain' {
        $fixture = Join-Path $TestDrive 'golden-path-complete'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        foreach ($checkId in @(
            'static.golden-path-outer-child-pin',
            'static.golden-path-child-openfang-pin',
            'static.golden-path-child-voice-pin',
            'static.golden-path-contract-chain',
            'static.golden-path-approval-cost-authority',
            'static.golden-path-evidence-authority',
            'static.proxmox-no-model-runtime',
            'static.golden-path-predeploy'
        )) {
            ($result.Report.checks | Where-Object id -eq $checkId).status | Should -Be 'verified'
        }
        $result.ExitCode | Should -Be 0
    }

    It 'blocks the golden path when the outer child pin is stale' {
        $fixture = Join-Path $TestDrive 'golden-path-stale-outer-child'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins -RequiredOuterChildPin '26003b952d65359f116b14eba55695dc74d2b528'

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-outer-child-pin').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the manifest and Gitlink disagree' {
        $fixture = Join-Path $TestDrive 'golden-path-manifest-mismatch'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $manifestPath = Join-Path $fixture 'repo-manifest.yaml'
        (Get-Content -LiteralPath $manifestPath -Raw).Replace($pins.OuterChildPin, ('0' * 40)) |
            Set-Content -LiteralPath $manifestPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-outer-child-pin').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the child OpenFang pin is wrong' {
        $fixture = Join-Path $TestDrive 'golden-path-wrong-openfang'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins -RequiredOpenFangPin 'fac8e429f5adfa50ac59dce2360c481290148cad'

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-child-openfang-pin').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the child Voice pin is wrong' {
        $fixture = Join-Path $TestDrive 'golden-path-wrong-voice'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins -RequiredVoicePin ('0' * 40)

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-child-voice-pin').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when its versioned contract chain is missing' {
        $fixture = Join-Path $TestDrive 'golden-path-missing-contract-chain'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        Remove-Item -LiteralPath (Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md')

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-contract-chain').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when an approval identifier owner is not OpenFang' {
        $fixture = Join-Path $TestDrive 'golden-path-wrong-approval-owner'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $contractPath = Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('| `approval_id` | OpenFang |', '| `approval_id` | Brain |') |
            Set-Content -LiteralPath $contractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when a cost identifier owner is not OpenFang' {
        $fixture = Join-Path $TestDrive 'golden-path-wrong-cost-owner'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $contractPath = Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('| `cost_id` | OpenFang |', '| `cost_id` | Brain |') |
            Set-Content -LiteralPath $contractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the Space execution contract assigns OpenFang responsibilities to another owner' {
        $fixture = Join-Path $TestDrive 'golden-path-wrong-space-contract-owner'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $spaceContractPath = Join-Path $fixture 'docs\contracts\space-execution-contract-v1.md'
        (Get-Content -LiteralPath $spaceContractPath -Raw).Replace('| OpenFang | execution, permissions, approvals, providers, and costs |', '| Brain | execution, permissions, approvals, providers, and costs |') |
            Set-Content -LiteralPath $spaceContractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the Space execution contract omits approvals and costs from OpenFang responsibilities' {
        $fixture = Join-Path $TestDrive 'golden-path-missing-space-contract-approval-costs'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $spaceContractPath = Join-Path $fixture 'docs\contracts\space-execution-contract-v1.md'
        (Get-Content -LiteralPath $spaceContractPath -Raw).Replace('execution, permissions, approvals, providers, and costs', 'execution, permissions, and providers') |
            Set-Content -LiteralPath $spaceContractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when the authority matrix header is absent' {
        $fixture = Join-Path $TestDrive 'golden-path-missing-authority-header'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $contractPath = Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('What it does not prove', 'Unproven consequence') |
            Set-Content -LiteralPath $contractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when an authority matrix non-proof is weakened' {
        $fixture = Join-Path $TestDrive 'golden-path-weakened-authority-non-proof'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $contractPath = Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('that an external action occurred', 'that a policy record exists') |
            Set-Content -LiteralPath $contractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-approval-cost-authority').status | Should -Be 'blocked'
    }

    It 'blocks the golden path when evidence authority accepts a weak live equivalent' {
        $fixture = Join-Path $TestDrive 'golden-path-weak-evidence'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        $contractPath = Join-Path $fixture 'docs\contracts\brain-openfang-space-reference-path-v1.md'
        (Get-Content -LiteralPath $contractPath -Raw).Replace('Truth/Evidence is independent of the actor making the claim', 'Receipt evidence is sufficient') |
            Set-Content -LiteralPath $contractPath -NoNewline

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-evidence-authority').status | Should -Be 'blocked'
    }

    It 'keeps the golden path verified after master advances from the reviewed baseline' {
        $fixture = Join-Path $TestDrive 'golden-path-advanced-master'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        Set-Content -LiteralPath (Join-Path $fixture 'gate-merge-marker.txt') -Value 'simulated merge' -NoNewline
        & git -C $fixture add gate-merge-marker.txt
        & git -C $fixture commit -m 'test: simulate merged predeploy gate' | Out-Null
        & git -C $fixture update-ref refs/remotes/origin/master HEAD

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 0
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-outer-child-pin').status | Should -Be 'verified'
    }

    It 'blocks an authoritative master that is unrelated to the reviewed baseline' {
        $fixture = Join-Path $TestDrive 'golden-path-unrelated-master'
        $pins = New-ReadinessFixture -Path $fixture -GoldenPath -PassThru
        & git -C $fixture checkout --orphan unrelated-master | Out-Null
        & git -C $fixture commit --allow-empty -m 'test: unrelated authoritative master' | Out-Null
        & git -C $fixture update-ref refs/remotes/origin/master HEAD

        $result = Invoke-GoldenPathPreflight -RepositoryRoot $fixture -Pins $pins

        $result.ExitCode | Should -Be 1
        ($result.Report.checks | Where-Object id -eq 'static.golden-path-outer-child-pin').status | Should -Be 'blocked'
    }

    It 'rejects public authority override parameters' {
        $fixture = Join-Path $TestDrive 'public-authority-override'
        New-ReadinessFixture -Path $fixture
        $reportPath = Join-Path $fixture 'results\deployment-readiness.json'

        $output = & $script:PowerShell -NoProfile -File $script:PreflightScript `
            -RepositoryRoot $fixture -OutputPath $reportPath -ExpectedBasePin ('0' * 40) 2>&1 | Out-String

        $output | Should -Match "A parameter cannot be found that matches parameter name 'ExpectedBasePin'"
    }
}
