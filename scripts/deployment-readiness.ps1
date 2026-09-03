[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),

    [string]$OutputPath,

    [switch]$LiveProbes,

    [string]$ProxmoxUri,

    [string]$SupabaseUri,

    [string]$QdrantUri,

    [ValidateNotNullOrEmpty()]
    [string]$PythonCommand = 'python',

    [ValidateRange(100, 30000)]
    [int]$TimeoutMilliseconds = 1500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RequiredBaselineAncestor = '1a78d9e42fc90b0463185d7af5442d75a6894a52'
$RequiredPredecessorAncestors = @(
    '62b50ce1336ce88fd162c79a66b8ede3b3b43144',
    '99d41a795ac7538fb32927664a301d318d62e725'
)
$RequiredOuterChildPin = '82127e44944495e5cb47d22e597cee9c51bbee83'
$RequiredOpenFangPin = '8a4904b3ff622d7ffda1e8cb01a509d2db430904'
$RequiredVoicePin = 'a8c8d9f172a768850ad4cf999c6ebbb68bc6f015'

function New-ReadinessCheck {
    param(
        [Parameter(Mandatory)]
        [string]$Id,

        [Parameter(Mandatory)]
        [ValidateSet('verified', 'blocked', 'unverified')]
        [string]$Status,

        [Parameter(Mandatory)]
        [string]$Scope,

        [Parameter(Mandatory)]
        [string]$Detail
    )

    [pscustomobject][ordered]@{
        id = $Id
        status = $Status
        scope = $Scope
        detail = $Detail
    }
}

function Test-HttpTargetConfiguration {
    param(
        [AllowEmptyString()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    [uri]$parsed = $null
    if (-not [uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$parsed)) {
        return $null
    }

    if ($parsed.Scheme -notin @('http', 'https') -or -not [string]::IsNullOrEmpty($parsed.UserInfo)) {
        return $null
    }

    return $parsed
}

function Test-TcpReachability {
    param(
        [Parameter(Mandatory)]
        [uri]$Uri,

        [Parameter(Mandatory)]
        [int]$TimeoutMilliseconds
    )

    $port = if ($Uri.IsDefaultPort) {
        if ($Uri.Scheme -eq 'https') { 443 } else { 80 }
    } else {
        $Uri.Port
    }

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync($Uri.Host, $port)
        return $connection.Wait($TimeoutMilliseconds) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Resolve-ContainedOutputPath {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$CandidateOutputPath
    )

    $candidate = if ([System.IO.Path]::IsPathRooted($CandidateOutputPath)) {
        $CandidateOutputPath
    } else {
        Join-Path $ResolvedRepositoryRoot $CandidateOutputPath
    }
    $resolvedOutput = if (Test-Path -LiteralPath $candidate) {
        (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
    } else {
        [System.IO.Path]::GetFullPath($candidate)
    }
    $rootWithSeparator = $ResolvedRepositoryRoot.TrimEnd([char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )) + [System.IO.Path]::DirectorySeparatorChar

    if (-not $resolvedOutput.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'OutputPath must resolve inside RepositoryRoot.'
    }

    return $resolvedOutput
}

function Test-ManifestGitlinkAlignment {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $manifestPath = Join-Path $ResolvedRepositoryRoot 'repo-manifest.yaml'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $false
    }

    try {
        $manifestEntries = [System.Collections.Generic.List[hashtable]]::new()
        $entry = $null
        foreach ($line in Get-Content -LiteralPath $manifestPath -ErrorAction Stop) {
            if ($line -match '^  - id:\s*(?<value>[^#\s]+)\s*$') {
                if ($null -ne $entry) {
                    $manifestEntries.Add($entry)
                }
                $entry = @{ id = $Matches.value }
                continue
            }
            if ($null -eq $entry) {
                continue
            }
            if ($line -match '^    (?<key>parent|path|expected_gitlink_pin):\s*(?<value>[^#\s]+)\s*$') {
                $entry[$Matches.key] = $Matches.value
            }
        }
        if ($null -ne $entry) {
            $manifestEntries.Add($entry)
        }

        $expectedPins = @{}
        foreach ($manifestEntry in $manifestEntries) {
            if ($manifestEntry.parent -eq 'vibemind-v1' -and
                $manifestEntry.ContainsKey('path') -and
                $manifestEntry.ContainsKey('expected_gitlink_pin') -and
                $manifestEntry.expected_gitlink_pin -match '^[0-9a-f]{40}$') {
                $expectedPins[$manifestEntry.path] = $manifestEntry.expected_gitlink_pin
            }
        }

        $gitlinkOutput = & git -C $ResolvedRepositoryRoot ls-files --stage 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        $trackedGitlinks = @{}
        foreach ($gitlinkLine in $gitlinkOutput) {
            if ($gitlinkLine -match '^160000 (?<pin>[0-9a-f]{40}) 0\t(?<path>.+)$') {
                $trackedGitlinks[$Matches.path] = $Matches.pin
            }
        }

        foreach ($path in $expectedPins.Keys) {
            if (-not $trackedGitlinks.ContainsKey($path) -or $trackedGitlinks[$path] -ne $expectedPins[$path]) {
                return $false
            }
        }
        foreach ($path in $trackedGitlinks.Keys) {
            if (-not $expectedPins.ContainsKey($path)) {
                return $false
            }
        }
        return $true
    } catch {
        return $false
    }
}

function Test-OfflineSubmoduleReadiness {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$PythonCommand
    )

    if ($null -eq (Get-Command -Name $PythonCommand -ErrorAction SilentlyContinue)) {
        return $null
    }

    $locationPushed = $false
    try {
        Push-Location -LiteralPath $ResolvedRepositoryRoot
        $locationPushed = $true
        $validatorOutput = & $PythonCommand -m tools.v1_governance submodules readiness --repo $ResolvedRepositoryRoot --format json 2>$null | Out-String
        $validatorExitCode = $LASTEXITCODE
        $validatorResult = $validatorOutput | ConvertFrom-Json -ErrorAction Stop
        if ($null -eq $validatorResult -or
            $null -eq $validatorResult.PSObject.Properties['ready'] -or
            $null -eq $validatorResult.PSObject.Properties['findings'] -or
            $validatorResult.ready -isnot [bool] -or
            $validatorResult.findings -isnot [System.Array]) {
            return $null
        }
        foreach ($finding in @($validatorResult.findings)) {
            if ($null -eq $finding -or
                $null -eq $finding.PSObject.Properties['code'] -or
                $null -eq $finding.PSObject.Properties['path'] -or
                $finding.code -isnot [string] -or
                $finding.path -isnot [string]) {
                return $null
            }
        }
        if (($validatorResult.ready -and $validatorResult.findings.Count -ne 0) -or
            (-not $validatorResult.ready -and $validatorResult.findings.Count -eq 0)) {
            return $null
        }
        if (($validatorResult.ready -and $validatorExitCode -ne 0) -or
            (-not $validatorResult.ready -and $validatorExitCode -notin @(0, 2))) {
            return $null
        }
        return [bool]$validatorResult.ready
    } catch {
        return $null
    } finally {
        if ($locationPushed) {
            Pop-Location
        }
    }
}

function Test-ReadableFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }

    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
        $stream.Dispose()
        return $true
    } catch {
        return $false
    }
}

function Test-ReadablePinnedSubmoduleFile {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$SubmodulePath,

        [Parameter(Mandatory)]
        [string]$RelativeFile
    )

    $submoduleRoot = Join-Path $ResolvedRepositoryRoot $SubmodulePath
    if (-not (Test-Path -LiteralPath $submoduleRoot -PathType Container)) {
        return $false
    }

    try {
        $insideWorkTree = (& git -C $submoduleRoot rev-parse --is-inside-work-tree 2>$null | Select-Object -First 1).Trim()
        if ($insideWorkTree -ne 'true') {
            return $false
        }
        $submoduleStatus = (& git -C $ResolvedRepositoryRoot status --porcelain --ignore-submodules=none -- $SubmodulePath 2>$null | Out-String).Trim()
        if (-not [string]::IsNullOrWhiteSpace($submoduleStatus)) {
            return $false
        }

        $filePath = Join-Path $submoduleRoot $RelativeFile
        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            return $false
        }
        $stream = [System.IO.File]::OpenRead($filePath)
        $stream.Dispose()
        return $true
    } catch {
        return $false
    }
}

function Test-ReadableVersionedArtifact {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$RelativePath
    )

    $artifactPath = Join-Path $ResolvedRepositoryRoot $RelativePath
    if (-not (Test-ReadableFile -Path $artifactPath)) {
        return $false
    }

    try {
        & git -C $ResolvedRepositoryRoot ls-files --error-unmatch -- $RelativePath 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        & git -C $ResolvedRepositoryRoot cat-file -e "HEAD`:$RelativePath" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        & git -C $ResolvedRepositoryRoot diff --quiet -- $RelativePath 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        & git -C $ResolvedRepositoryRoot diff --cached --quiet -- $RelativePath 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-VersionedArtifactContent {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$RelativePath
    )

    if (-not (Test-ReadableVersionedArtifact -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath $RelativePath)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath (Join-Path $ResolvedRepositoryRoot $RelativePath) -Raw -ErrorAction Stop
    } catch {
        return $null
    }
}

function Get-VersionedProxmoxComposeArtifacts {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    try {
        $headArtifacts = @(& git -C $ResolvedRepositoryRoot ls-tree -r --name-only HEAD -- infra/proxmox 2>$null)
        if ($LASTEXITCODE -ne 0) {
            return $null
        }

        $indexArtifacts = @(& git -C $ResolvedRepositoryRoot ls-files --full-name -- infra/proxmox 2>$null)
        if ($LASTEXITCODE -ne 0) {
            return $null
        }

        $artifacts = @($headArtifacts + $indexArtifacts | Where-Object {
            $_ -is [string] -and $_ -match '^infra/proxmox/[^/]+-docker-compose\.yml$'
        } | Sort-Object -Unique)
        if ($artifacts.Count -eq 0) {
            return $null
        }

        foreach ($artifact in $artifacts) {
            if ($artifact -isnot [string] -or $artifact -notmatch '^infra/proxmox/[^/]+-docker-compose\.yml$') {
                return $null
            }
        }

        return @($artifacts | Sort-Object -Unique)
    } catch {
        return $null
    }
}

function Test-GitAncestor {
    param(
        [Parameter(Mandatory)]
        [string]$RepositoryRoot,

        [Parameter(Mandatory)]
        [string]$Ancestor,

        [Parameter(Mandatory)]
        [string]$Descendant
    )

    try {
        & git -C $RepositoryRoot merge-base --is-ancestor $Ancestor $Descendant 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-GoldenPathOuterChildPin {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    try {
        $originMaster = (& git -C $ResolvedRepositoryRoot rev-parse origin/master 2>$null | Select-Object -First 1).Trim()
        $head = (& git -C $ResolvedRepositoryRoot rev-parse HEAD 2>$null | Select-Object -First 1).Trim()
        $gitlink = (& git -C $ResolvedRepositoryRoot ls-tree HEAD vibemind-os 2>$null | Select-Object -First 1).Trim()
        if ($head -ne $originMaster -or
            $gitlink -ne ('160000 commit ' + $RequiredOuterChildPin + [char]9 + 'vibemind-os') -or
            -not (Test-GitAncestor -RepositoryRoot $ResolvedRepositoryRoot -Ancestor $RequiredBaselineAncestor -Descendant $originMaster)) {
            return $false
        }
        foreach ($ancestor in $RequiredPredecessorAncestors) {
            if (-not (Test-GitAncestor -RepositoryRoot $ResolvedRepositoryRoot -Ancestor $ancestor -Descendant $originMaster)) {
                return $false
            }
        }
        return Test-ManifestGitlinkAlignment -ResolvedRepositoryRoot $ResolvedRepositoryRoot
    } catch {
        return $false
    }
}

function Test-GoldenPathChildGitlinkPin {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot,

        [Parameter(Mandatory)]
        [string]$NestedPath,

        [Parameter(Mandatory)]
        [string]$RequiredNestedPin
    )

    $childRoot = Join-Path $ResolvedRepositoryRoot 'vibemind-os'
    try {
        if ((& git -C $childRoot rev-parse --is-inside-work-tree 2>$null | Select-Object -First 1).Trim() -ne 'true') {
            return $false
        }
        if ((& git -C $childRoot rev-parse HEAD 2>$null | Select-Object -First 1).Trim() -ne $RequiredOuterChildPin) {
            return $false
        }
        if (-not [string]::IsNullOrWhiteSpace((& git -C $ResolvedRepositoryRoot status --porcelain --ignore-submodules=none -- vibemind-os 2>$null | Out-String).Trim())) {
            return $false
        }
        & git -C $childRoot cat-file -e "$RequiredOuterChildPin^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        $entry = (& git -C $childRoot ls-tree $RequiredOuterChildPin $NestedPath 2>$null | Select-Object -First 1).Trim()
        return $entry -eq ('160000 commit ' + $RequiredNestedPin + [char]9 + $NestedPath)
    } catch {
        return $false
    }
}

function Test-GoldenPathLedgerPins {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $content = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/governance/cockpit-reconciliation-ledger-v1.json'
    if ($null -eq $content) {
        return $false
    }
    try {
        $ledger = $content | ConvertFrom-Json -ErrorAction Stop
        $chain = @($ledger.entries | Where-Object { $_.kind -eq 'historical-gitlink-chain' } | Where-Object {
            @($_.links | Where-Object { $_.path -eq 'vibemind-os' -and $_.target_commit -eq $RequiredOuterChildPin }).Count -eq 1
        }) | Select-Object -Last 1
        if ($null -eq $chain) {
            return $false
        }
        return @($chain.links | Where-Object { $_.path -eq 'openfang' -and $_.target_commit -eq $RequiredOpenFangPin }).Count -eq 1 -and
            @($chain.links | Where-Object { $_.path -eq 'voice' -and $_.target_commit -eq $RequiredVoicePin }).Count -eq 1
    } catch {
        return $false
    }
}

function Test-GoldenPathContractChain {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $referencePath = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/brain-openfang-space-reference-path-v1.md'
    $orchestration = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/superpowers/specs/2026-07-30-v1-space-orchestration-design.md'
    $lifecycleSchema = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'shared/contracts/brain/v1/brain-plan-lifecycle-v1.schema.json'
    $handoffSchema = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'shared/contracts/brain/v1/brain-openfang-handoff-v1.schema.json'
    if ($null -in @($referencePath, $orchestration, $lifecycleSchema, $handoffSchema)) {
        return $false
    }

    return $referencePath -match 'Brain is the control plane' -and
        $referencePath -match 'OpenFang is the execution engine' -and
        $referencePath -match 'No direct fallback is permitted' -and
        $referencePath -match 'Space-Agent' -and
        $referencePath -match 'MCP/Service adapter' -and
        $referencePath -match 'independent Truth/Evidence' -and
        $orchestration -match 'Brain zu OpenFang und von dort zum zuständigen Space-Agenten und der bestehenden Application' -and
        $lifecycleSchema -match 'execution_deferred' -and
        $handoffSchema -match '"execution_boundary"\s*:\s*\{\s*"const"\s*:\s*"openfang"'
}

function Test-GoldenPathApprovalCostAuthority {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $referencePath = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/brain-openfang-space-reference-path-v1.md'
    $spaceContract = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/space-execution-contract-v1.md'
    $handoffSchema = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'shared/contracts/brain/v1/brain-openfang-handoff-v1.schema.json'
    if ($null -in @($referencePath, $spaceContract, $handoffSchema)) {
        return $false
    }

    return $referencePath -match 'OpenFang accepts a separately admissible handoff, creates or correlates `approval_id` and `cost_id`' -and
        $referencePath -match '\|\s*Identifier\s*\|\s*Owner at creation\s*\|\s*What it correlates\s*\|\s*What it does not prove\s*\|' -and
        $referencePath -match '\|\s*`approval_id`\s*\|\s*OpenFang\s*\|\s*[^|\r\n]+\|\s*that an external action occurred\s*\|' -and
        $referencePath -match '\|\s*`cost_id`\s*\|\s*OpenFang\s*\|\s*[^|\r\n]+\|\s*cost settlement or provider billing\s*\|' -and
        $spaceContract -match '\|\s*OpenFang\s*\|\s*execution\s*,\s*permissions\s*,\s*approvals\s*,\s*providers\s*,\s*and\s*costs\s*\|\s*shared\s+contract\s+ownership\s*\|' -and
        $handoffSchema -match '"execution_boundary"\s*:\s*\{\s*"const"\s*:\s*"openfang"' -and
        $handoffSchema -match '"approval_ref"' -and $handoffSchema -match '"cost_ref"'
}

function Test-GoldenPathEvidenceAuthority {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $referencePath = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/brain-openfang-space-reference-path-v1.md'
    $evidenceGovernance = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/observability-evidence-governance-v2.md'
    if ($null -in @($referencePath, $evidenceGovernance)) {
        return $false
    }

    return $referencePath -match 'Truth/Evidence is independent of the actor making the claim' -and
        $referencePath -match 'transport or tool success alone is insufficient' -and
        $evidenceGovernance -match 'Transport success is not `verified_live`' -and
        $evidenceGovernance -match 'An HTTP 2xx response is not `verified_live`' -and
        $evidenceGovernance -match 'Registry matches are not `verified_live`'
}

function Test-ProxmoxNoModelRuntime {
    param(
        [Parameter(Mandatory)]
        [string]$ResolvedRepositoryRoot
    )

    $contract = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath 'docs/contracts/proxmox-no-model-runtime-v1.md'
    if ($null -eq $contract) {
        return $false
    }

    $normalizedContract = [regex]::Replace($contract, '\s+', ' ').Trim()
    $requiredContractStatements = @(
        'No model may execute on the Proxmox host or in any VM, container, service, worker, or job scheduled on it.',
        'This prohibition covers LLM, embedding, reranking, OCR and vision, speech recognition, TTS, lip-sync, image, video, and any other model inference.',
        'Model weights, model caches, accelerators assigned for inference, and model-serving runtimes are forbidden inside the Proxmox boundary.',
        'route every model request to an approved provider outside the Proxmox boundary',
        'Provider model identifiers such as `EMBEDDING_MODEL` are configuration only and never authorize local weights or inference.'
    )
    foreach ($statement in $requiredContractStatements) {
        if ($normalizedContract -notmatch [regex]::Escape($statement)) {
            return $false
        }
    }

    $requiredComposeArtifacts = @(
        'infra/proxmox/phase1-docker-compose.yml',
        'infra/proxmox/phase2a-docker-compose.yml',
        'infra/proxmox/phase2b-docker-compose.yml'
    )
    $composeArtifacts = Get-VersionedProxmoxComposeArtifacts -ResolvedRepositoryRoot $ResolvedRepositoryRoot
    if ($null -eq $composeArtifacts) {
        return $false
    }
    foreach ($requiredArtifact in $requiredComposeArtifacts) {
        if ($requiredArtifact -notin $composeArtifacts) {
            return $false
        }
    }
    $forbiddenPatterns = @(
        '(?im)^\s{2}[^#\r\n]*(?:ollama|vllm|llama(?:cpp|\.cpp)?|localai|text-generation-inference|tritonserver|model-server|inference-server|embedding-service|embedder|whisper|tts|stt|lip-?sync|vision-model)[^:\r\n]*:\s*$',
        '(?im)^\s*image:\s*[^\r\n]*(?:ollama|vllm|llama|localai|text-generation-inference|tritonserver|tensorflow/serving|huggingface/(?:text-generation-inference|transformers)|whisper|coqui|piper)',
        '(?im)^\s*(?:command|entrypoint):[^\r\n]*(?:ollama\s+serve|vllm|llama-server|text-generation-launcher|tritonserver)',
        '(?ims)^\s*(?:command|entrypoint):\s*(?:(?:\r?\n)\s*-[^\r\n]*){0,11}(?:\r?\n)\s*-[^\r\n]*(?:ollama|vllm|llama-server|text-generation-launcher|tritonserver)',
        '(?im)^\s*-\s*(?:HF_HOME|TRANSFORMERS_CACHE|OLLAMA_MODELS|MODEL_WEIGHTS_PATH)\s*=',
        '(?im)^\s*(?:HF_HOME|TRANSFORMERS_CACHE|OLLAMA_MODELS|MODEL_WEIGHTS_PATH)\s*:',
        '(?im)(?:/root/\.ollama|/models(?:/|$)|/\.cache/huggingface)',
        '(?im)^\s*gpus\s*:',
        '(?im)^\s*(?:NVIDIA_VISIBLE_DEVICES|CUDA_VISIBLE_DEVICES|ROCR_VISIBLE_DEVICES)\s*:',
        '(?im)^\s*-\s*(?:NVIDIA_VISIBLE_DEVICES|CUDA_VISIBLE_DEVICES|ROCR_VISIBLE_DEVICES)\s*=',
        '(?im)^[\t ]*(?:-[\t ]*)?capabilities:\s*\[[^\]\r\n]*(?:gpu|tpu|npu)',
        '(?ims)^[\t ]*(?:-[\t ]*)?capabilities:[\t ]*(?:(?:\r?\n)[\t ]*-[^\r\n]*){0,11}(?:\r?\n)[\t ]*-[\t ]*(?:gpu|tpu|npu)\b'
    )

    foreach ($relativePath in $composeArtifacts) {
        $content = Get-VersionedArtifactContent -ResolvedRepositoryRoot $ResolvedRepositoryRoot -RelativePath $relativePath
        if ($null -eq $content) {
            return $false
        }
        foreach ($pattern in $forbiddenPatterns) {
            if ($content -match $pattern) {
                return $false
            }
        }
    }

    return $true
}

$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $RepositoryRoot 'results\deployment-readiness.json'
}
$OutputPath = Resolve-ContainedOutputPath -ResolvedRepositoryRoot $RepositoryRoot -CandidateOutputPath $OutputPath

$checks = [System.Collections.Generic.List[object]]::new()
$requiredArtifacts = @(
    [pscustomobject]@{ Id = 'static.vibemind-config'; RelativePath = 'vibemind.config.json'; Type = 'Leaf'; Detail = 'repository configuration artifact is present' },
    [pscustomobject]@{ Id = 'static.phase1-compose'; RelativePath = 'infra/proxmox/phase1-docker-compose.yml'; Type = 'Leaf'; Detail = 'Proxmox phase 1 compose artifact is present' },
    [pscustomobject]@{ Id = 'static.phase1-config-manifest'; RelativePath = 'infra/proxmox/phase1-configs-manifest.json'; Type = 'Leaf'; Detail = 'Proxmox phase 1 config manifest is present' },
    [pscustomobject]@{ Id = 'static.phase2-compose'; RelativePath = 'infra/proxmox/phase2a-docker-compose.yml'; Type = 'Leaf'; Detail = 'Proxmox phase 2 compose artifact is present' },
    [pscustomobject]@{ Id = 'static.phase2-required-vars'; RelativePath = 'infra/proxmox/phase2-required-vars.txt'; Type = 'Leaf'; Detail = 'Proxmox phase 2 required-variable manifest is present' },
    [pscustomobject]@{ Id = 'static.vibemind-os-boundary'; RelativePath = 'vibemind-os'; Type = 'Container'; Detail = 'runtime submodule boundary is present' }
)
$pinnedOpenFangFiles = @(
    [pscustomobject]@{ Id = 'static.openfang-pinned-config'; RelativePath = 'llm_config.yml.example'; Detail = 'pinned OpenFang configuration is readable' },
    [pscustomobject]@{ Id = 'static.openfang-pinned-registry'; RelativePath = 'config/space_agent_registry.yml'; Detail = 'pinned OpenFang registry is readable' }
)
$versionedOperationalArtifacts = @(
    [pscustomobject]@{ Id = 'static.proxmox-reboot-artifact'; RelativePath = 'docs/runbooks/proxmox-reboot.md'; Detail = 'versioned Proxmox reboot artifact is readable' },
    [pscustomobject]@{ Id = 'static.proxmox-backup-restore-artifact'; RelativePath = 'docs/runbooks/proxmox-backup-restore.md'; Detail = 'versioned Proxmox backup-restore artifact is readable' },
    [pscustomobject]@{ Id = 'static.proxmox-cutover-rollback-artifact'; RelativePath = 'docs/runbooks/proxmox-cutover-rollback.md'; Detail = 'versioned Proxmox cutover-rollback artifact is readable' }
)

if (Test-Path -LiteralPath $RepositoryRoot -PathType Container) {
    $checks.Add((New-ReadinessCheck -Id 'static.repository-root' -Status 'verified' -Scope 'static' -Detail 'repository root is accessible'))
    foreach ($artifact in $requiredArtifacts) {
        $path = Join-Path $RepositoryRoot $artifact.RelativePath
        $present = Test-Path -LiteralPath $path -PathType $artifact.Type
        $status = if ($present) { 'verified' } else { 'blocked' }
        $detail = if ($present) { $artifact.Detail } else { 'required deployment artifact is absent' }
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status $status -Scope 'static' -Detail $detail))
    }
    foreach ($artifact in $pinnedOpenFangFiles) {
        $readable = if ($artifact.Id -eq 'static.openfang-pinned-config') {
            Test-ReadablePinnedSubmoduleFile -ResolvedRepositoryRoot $RepositoryRoot -SubmodulePath 'vibemind-os' -RelativeFile 'llm_config.yml.example'
        } else {
            Test-ReadablePinnedSubmoduleFile -ResolvedRepositoryRoot $RepositoryRoot -SubmodulePath 'vibemind-os' -RelativeFile 'config/space_agent_registry.yml'
        }
        $status = if ($readable) { 'verified' } else { 'blocked' }
        $detail = if ($readable) { $artifact.Detail } else { 'required pinned OpenFang artifact is unavailable, off-pin, modified, or unreadable' }
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status $status -Scope 'static' -Detail $detail))
    }
    foreach ($artifact in $versionedOperationalArtifacts) {
        $relativePath = [string]$artifact.RelativePath
        $readable = Test-ReadableVersionedArtifact -ResolvedRepositoryRoot $RepositoryRoot -RelativePath $relativePath
        $status = if ($readable) { 'verified' } else { 'blocked' }
        $detail = if ($readable) { $artifact.Detail } else { 'required versioned operational artifact is absent, modified, or unreadable' }
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status $status -Scope 'static' -Detail $detail))
    }

    $manifestGitlinksAligned = Test-ManifestGitlinkAlignment -ResolvedRepositoryRoot $RepositoryRoot
    $submoduleReady = Test-OfflineSubmoduleReadiness -ResolvedRepositoryRoot $RepositoryRoot -PythonCommand $PythonCommand
    if (-not $manifestGitlinksAligned) {
        $checks.Add((New-ReadinessCheck -Id 'static.submodule-readiness' -Status 'blocked' -Scope 'static' -Detail 'manifest and tracked Gitlink pins are not aligned'))
    } elseif ($null -eq $submoduleReady) {
        $checks.Add((New-ReadinessCheck -Id 'static.submodule-readiness' -Status 'blocked' -Scope 'static' -Detail 'offline submodule-readiness validator is unavailable or returned invalid output'))
    } elseif (-not $submoduleReady) {
        $checks.Add((New-ReadinessCheck -Id 'static.submodule-readiness' -Status 'blocked' -Scope 'static' -Detail 'offline submodule-readiness validator reported blocked findings'))
    } else {
        $checks.Add((New-ReadinessCheck -Id 'static.submodule-readiness' -Status 'verified' -Scope 'static' -Detail 'manifest Gitlinks and offline submodule readiness are verified'))
    }
} else {
    $checks.Add((New-ReadinessCheck -Id 'static.repository-root' -Status 'blocked' -Scope 'static' -Detail 'repository root is absent'))
    foreach ($artifact in $requiredArtifacts) {
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status 'blocked' -Scope 'static' -Detail 'repository root is unavailable'))
    }
    foreach ($artifact in $pinnedOpenFangFiles) {
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status 'blocked' -Scope 'static' -Detail 'repository root is unavailable'))
    }
    foreach ($artifact in $versionedOperationalArtifacts) {
        $checks.Add((New-ReadinessCheck -Id $artifact.Id -Status 'blocked' -Scope 'static' -Detail 'repository root is unavailable'))
    }
    $checks.Add((New-ReadinessCheck -Id 'static.submodule-readiness' -Status 'blocked' -Scope 'static' -Detail 'repository root is unavailable'))
}

$outerGitFactsVerified = Test-GoldenPathOuterChildPin -ResolvedRepositoryRoot $RepositoryRoot
$ledgerPinFactsVerified = Test-GoldenPathLedgerPins -ResolvedRepositoryRoot $RepositoryRoot
$outerChildPinVerified = $outerGitFactsVerified -and $ledgerPinFactsVerified
$outerChildPinDetail = if ($outerChildPinVerified) {
    'required outer base, ancestry, manifest/Gitlink, and reconciliation-ledger child pin facts are verified'
} elseif (-not $outerGitFactsVerified) {
    'required outer base, ancestry, or manifest/Gitlink child pin facts are missing, off-pin, contradictory, or unreadable'
} else {
    'required reconciliation-ledger child pin facts are missing, contradictory, or unreadable'
}
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-outer-child-pin' -Status $(if ($outerChildPinVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $outerChildPinDetail))

$openFangPinVerified = Test-GoldenPathChildGitlinkPin -ResolvedRepositoryRoot $RepositoryRoot -NestedPath 'openfang' -RequiredNestedPin $RequiredOpenFangPin
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-child-openfang-pin' -Status $(if ($openFangPinVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($openFangPinVerified) { 'materialized child Git tree verifies the expected OpenFang Gitlink' } else { 'materialized child Git tree is unavailable, off-pin, contradictory, or does not verify the expected OpenFang Gitlink' })))

$voicePinVerified = Test-GoldenPathChildGitlinkPin -ResolvedRepositoryRoot $RepositoryRoot -NestedPath 'voice' -RequiredNestedPin $RequiredVoicePin
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-child-voice-pin' -Status $(if ($voicePinVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($voicePinVerified) { 'materialized child Git tree verifies the expected Voice Gitlink' } else { 'materialized child Git tree is unavailable, off-pin, contradictory, or does not verify the expected Voice Gitlink' })))

$contractChainVerified = Test-GoldenPathContractChain -ResolvedRepositoryRoot $RepositoryRoot
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-contract-chain' -Status $(if ($contractChainVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($contractChainVerified) { 'versioned contracts preserve the Brain to OpenFang to Space or deterministic adapter to Application to independent truth chain without a fallback' } else { 'versioned contract chain is missing, unordered, contradictory, modified, or unreadable' })))

$approvalCostAuthorityVerified = Test-GoldenPathApprovalCostAuthority -ResolvedRepositoryRoot $RepositoryRoot
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-approval-cost-authority' -Status $(if ($approvalCostAuthorityVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($approvalCostAuthorityVerified) { 'versioned contracts assign execution, approval, and cost references to OpenFang without treating references as approval, execution, or booking proof' } else { 'versioned approval or cost authority is missing, contradictory, modified, unreadable, or outside OpenFang' })))

$evidenceAuthorityVerified = Test-GoldenPathEvidenceAuthority -ResolvedRepositoryRoot $RepositoryRoot
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-evidence-authority' -Status $(if ($evidenceAuthorityVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($evidenceAuthorityVerified) { 'versioned contracts require independent evidence and reject receipt, transport, HTTP, and registry-only live equivalence' } else { 'versioned independent evidence authority is missing, contradictory, modified, unreadable, or accepts a weak live equivalent' })))

$proxmoxNoModelRuntimeVerified = Test-ProxmoxNoModelRuntime -ResolvedRepositoryRoot $RepositoryRoot
$checks.Add((New-ReadinessCheck -Id 'static.proxmox-no-model-runtime' -Status $(if ($proxmoxNoModelRuntimeVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($proxmoxNoModelRuntimeVerified) { 'versioned Proxmox manifests contain no model runtime and the no-model contract is intact' } else { 'Proxmox no-model contract or compose policy is missing, modified, unreadable, or permits a model runtime' })))

$goldenPathDetailChecks = @($outerChildPinVerified, $openFangPinVerified, $voicePinVerified, $contractChainVerified, $approvalCostAuthorityVerified, $evidenceAuthorityVerified, $proxmoxNoModelRuntimeVerified)
$predeployVerified = @($goldenPathDetailChecks | Where-Object { $_ }).Count -eq 7
$checks.Add((New-ReadinessCheck -Id 'static.golden-path-predeploy' -Status $(if ($predeployVerified) { 'verified' } else { 'blocked' }) -Scope 'static' -Detail $(if ($predeployVerified) { 'all seven static Golden-Path detail checks are verified' } else { 'one or more static Golden-Path detail checks are blocked' })))

$checks.Add((New-ReadinessCheck -Id 'local.docker-engine' -Status 'unverified' -Scope 'local-runtime' -Detail 'not required or queried by the static preflight'))

$targetInputs = @(
    [pscustomobject]@{ Id = 'proxmox'; Value = $ProxmoxUri },
    [pscustomobject]@{ Id = 'supabase'; Value = $SupabaseUri },
    [pscustomobject]@{ Id = 'qdrant'; Value = $QdrantUri }
)
$configuredTargets = @{}
foreach ($target in $targetInputs) {
    $uri = Test-HttpTargetConfiguration -Value $target.Value
    if ([string]::IsNullOrWhiteSpace($target.Value)) {
        $checks.Add((New-ReadinessCheck -Id "runtime.$($target.Id)-target" -Status 'unverified' -Scope 'runtime-configuration' -Detail 'target was not supplied'))
    } elseif ($null -eq $uri) {
        $checks.Add((New-ReadinessCheck -Id "runtime.$($target.Id)-target" -Status 'blocked' -Scope 'runtime-configuration' -Detail 'target must be an absolute HTTP or HTTPS URI without credentials'))
    } else {
        $configuredTargets[$target.Id] = $uri
        $checks.Add((New-ReadinessCheck -Id "runtime.$($target.Id)-target" -Status 'verified' -Scope 'runtime-configuration' -Detail 'target is configured; its value is redacted from evidence'))
    }
}

if ($LiveProbes) {
    foreach ($target in $targetInputs) {
        $checkId = "live.$($target.Id)-reachability"
        if (-not $configuredTargets.ContainsKey($target.Id)) {
            $checks.Add((New-ReadinessCheck -Id $checkId -Status 'blocked' -Scope 'live-probe' -Detail 'live probe target is not safely configured'))
            continue
        }

        $reachable = Test-TcpReachability -Uri $configuredTargets[$target.Id] -TimeoutMilliseconds $TimeoutMilliseconds
        $status = if ($reachable) { 'verified' } else { 'blocked' }
        $detail = if ($reachable) { 'TCP reachability verified; service health is not proven' } else { 'TCP reachability was not verified' }
        $checks.Add((New-ReadinessCheck -Id $checkId -Status $status -Scope 'live-probe' -Detail $detail))
    }
}

$blocked = @($checks | Where-Object { $_.status -eq 'blocked' })
$report = [pscustomobject][ordered]@{
    schema_version = 'vibemind.deployment-readiness.v1'
    mode = if ($LiveProbes) { 'live-probes' } else { 'static' }
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    evidence_policy = 'redacted: runtime target values and all secret values are omitted'
    deployment_proven = $false
    golden_path_proven = $false
    conclusion = 'This preflight inventories prerequisites only. It does not deploy, alter runtime state, prove service health, or prove a Golden Path.'
    checks = $checks.ToArray()
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding utf8

Write-Output "Deployment readiness evidence written (blocked checks: $($blocked.Count))."
if ($blocked.Count -gt 0) {
    exit 1
}
