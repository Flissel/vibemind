BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $stackPath = Join-Path $repoRoot "infra\swarm\vibemind-stack.yml"
    $secretInitializerPath = Join-Path $repoRoot "scripts\swarm_secrets_init.ps1"
    $childConfigPath = Join-Path $repoRoot "vibemind-os\llm_config.yml.example"
    $manifestPath = Join-Path $repoRoot "repo-manifest.yaml"
    $stack = Get-Content -LiteralPath $stackPath -Raw -Encoding utf8
    $secretInitializer = Get-Content -LiteralPath $secretInitializerPath -Raw -Encoding utf8
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8
    Test-Path -LiteralPath $childConfigPath | Should -BeTrue
    $childConfig = Get-Content -LiteralPath $childConfigPath -Raw -Encoding utf8

    $manifestEntry = [regex]::Match(
        $manifest,
        '(?ms)^  - id: vibemind-os\r?\n(?<body>.*?)(?=^  - id:|\z)'
    ).Groups['body'].Value
    $manifestPin = [regex]::Match(
        $manifestEntry,
        '(?m)^    expected_gitlink_pin: (?<pin>[0-9a-f]{40})\r?$'
    ).Groups['pin'].Value
    $gitlinkTree = & git -C $repoRoot ls-tree HEAD vibemind-os
    $trackedGitlinkPin = [regex]::Match(
        $gitlinkTree,
        '^160000 commit (?<pin>[0-9a-f]{40})\tvibemind-os$'
    ).Groups['pin'].Value
    $manifestRecords = @(
        [regex]::Matches($manifest, '(?ms)^  - id: (?<id>[^\r\n]+)\r?\n(?<body>.*?)(?=^  - id:|\z)') |
            ForEach-Object {
                $body = $_.Groups['body'].Value
                [pscustomobject]@{
                    Id = $_.Groups['id'].Value
                    Parent = [regex]::Match($body, '(?m)^    parent: (?<value>[^\r\n]+)\r?$').Groups['value'].Value
                    Path = [regex]::Match($body, '(?m)^    path: (?<value>[^\r\n]+)\r?$').Groups['value'].Value
                    ExpectedPin = [regex]::Match($body, '(?m)^    expected_gitlink_pin: (?<value>[^\r\n]+)\r?$').Groups['value'].Value
                    EvidenceParentPin = [regex]::Match($body, '(?m)parent_pin: (?<value>[^,}\r\n]+)').Groups['value'].Value
                }
            }
    )

    # A content revision must use a new Swarm config object name and hash entry.
    $immutableConfigDigests = [ordered]@{
        embedding_service_llm_config_v1 = "14a6cbb517f737c833e8cae173563dea02ccee39539efeb83c87cd588a3f9995"
    }
    $normalizedSha256 = {
        param([Parameter(Mandatory)][string]$Content)

        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $normalized = $Content -replace "`r`n", "`n"
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
            return [System.BitConverter]::ToString($sha256.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $sha256.Dispose()
        }
    }

    $embeddingMatch = [regex]::Match(
        $stack,
        '(?ms)^  embedding-service:\r?\n(?<body>.*?)(?=^  # === B-next)'
    )
    $embeddingMatch.Success | Should -BeTrue
    $embeddingService = $embeddingMatch.Value
}

Describe "Embedding service OpenFang runtime wiring" {
    It "uses only the canonical OpenFang endpoint and secret-file contract" {
        $embeddingService | Should -Match '(?m)^      - OPENFANG_URL=http://host\.docker\.internal:4200$'
        $embeddingService | Should -Match '(?m)^      - OPENFANG_API_KEY_FILE=/run/secrets/openfang_api_key$'
        $embeddingService | Should -Match '(?m)^    extra_hosts:\r?$'
        $embeddingService | Should -Match '(?m)^      - "host\.docker\.internal:host-gateway"$'
        $embeddingService | Should -Match '(?m)^    secrets:\r?\n      - openfang_api_key$'
        $embeddingService | Should -Not -Match '(?m)^      - EMBEDDING_MODEL='
        $embeddingService | Should -Not -Match '(?m)^      - openai_api_key$'
    }

    It "mounts the immutable canonical LLM configuration at the shared lookup path" {
        $embeddingService | Should -Match '(?ms)^    configs:\r?\n      - source: embedding_service_llm_config_v1\r?\n        target: /config/llm_config\.yml\r?\n        mode: 0444$'
        $stack | Should -Match '(?ms)^  embedding_service_llm_config_v1:\r?\n    file: ../../vibemind-os/llm_config\.yml\.example$'

        $mountedSource = [regex]::Match(
            $embeddingService,
            '(?m)^      - source: (?<name>embedding_service_llm_config_v\d+)$'
        ).Groups['name'].Value
        $immutableConfigDigests.Contains($mountedSource) | Should -BeTrue
        (& $normalizedSha256 $childConfig) | Should -Be $immutableConfigDigests[$mountedSource]
        $manifestPin | Should -Be $trackedGitlinkPin
    }

    It "pins the mounted child config to canonical OpenFang and the fungus embedding contract" {
        $providerBlock = [regex]::Match(
            $childConfig,
            '(?ms)^providers:\r?\n(?<body>.*?)(?=^default:)'
        ).Groups['body'].Value
        $openfangBlock = [regex]::Match(
            $providerBlock,
            '(?ms)^  openfang:\r?\n(?<body>.*?)(?=^  (?:[a-z_]+:|#)|\z)'
        ).Groups['body'].Value
        $fungusEmbeddingBlock = [regex]::Match(
            $childConfig,
            '(?ms)^  fungus_search:\r?\n(?<body>.*?)(?=^  (?:[a-z_]+:|#)|\z)'
        ).Groups['body'].Value

        $openfangBlock | Should -Match '(?m)^    type: openai\r?$'
        $openfangBlock | Should -Match '(?m)^    base_url: \$\{OPENFANG_URL\}/v1\r?$'
        $openfangBlock | Should -Match '(?m)^    key_ref: openfang\r?$'
        $openfangBlock | Should -Match '(?m)^    fail_closed: true\r?$'
        $openfangBlock | Should -Match '(?m)^    max_retries: 3\r?$'
        $openfangBlock | Should -Match '(?m)^    timeout_seconds: 30\r?$'
        $providerBlock | Should -Not -Match '(?m)^  (?:openrouter|anthropic|google|ollama):'
        $providerBlock | Should -Match '(?m)^  openai:'

        $fungusEmbeddingBlock | Should -Match '(?m)^    driver: openai\r?$'
        $fungusEmbeddingBlock | Should -Match '(?m)^    provider: openfang\r?$'
        $fungusEmbeddingBlock | Should -Match '(?m)^    model: text-embedding-3-large\r?$'
        $fungusEmbeddingBlock | Should -Match '(?m)^    dim: 3072\r?$'
        $childConfig | Should -Match '(?m)^  voice_realtime:\s+\{ provider: openai,\s+model: gpt-4o-realtime-preview,'
    }

    It "aligns recursive manifest pins with the current child trees" {
        $vibemindOsRecords = @($manifestRecords | Where-Object Parent -eq 'vibemind-os')
        $vibemindOsRecords.Count | Should -Be 14

        foreach ($record in $vibemindOsRecords) {
            $record.EvidenceParentPin | Should -Be $trackedGitlinkPin
            if ($record.ExpectedPin -ne 'absent') {
                $childTree = & git -C (Join-Path $repoRoot 'vibemind-os') ls-tree HEAD -- $record.Path
                $childPin = [regex]::Match(
                    $childTree,
                    '^160000 commit (?<pin>[0-9a-f]{40})\t'
                ).Groups['pin'].Value
                $record.ExpectedPin | Should -Be $childPin
            }
        }

        $voiceRecord = @($vibemindOsRecords | Where-Object Id -eq 'voice')
        $voiceRecord.Count | Should -Be 1
        $voiceRecords = @($manifestRecords | Where-Object Parent -eq 'voice')
        $voiceRecords.Count | Should -Be 5
        foreach ($record in $voiceRecords) {
            $record.EvidenceParentPin | Should -Be $voiceRecord[0].ExpectedPin
        }
    }

    It "declares and provisions the OpenFang secret without removing the global OpenAI secret" {
        $stack | Should -Match '(?ms)^  openfang_api_key:\r?\n    external: true$'
        $stack | Should -Match '(?ms)^  openai_api_key:\r?\n    external: true$'
        $secretInitializer | Should -Match 'OPENFANG_API_KEY\s*=\s*"openfang_api_key"'
    }
}
