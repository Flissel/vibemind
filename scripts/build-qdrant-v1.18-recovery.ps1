param(
    [string]$AssetPath = "",
    [string]$ImageTag = "vibemind-qdrant:v1.18.0-recovery",
    [switch]$LibraryMode
)

$ErrorActionPreference = "Stop"

function Get-QdrantRecoveryMetadata {
    [pscustomobject]@{
        Version = "v1.18.0"
        AssetName = "qdrant-x86_64-unknown-linux-musl.tar.gz"
        AssetBytes = 32330331L
        AssetSha256 = "76C38C3859682776D2BEF61BF6C23B593B7C06682578F7C9FF9EAC79C87A4268"
        AssetUrl = "https://github.com/qdrant/qdrant/releases/download/v1.18.0/qdrant-x86_64-unknown-linux-musl.tar.gz"
        BaseImage = "qdrant/qdrant:v1.12.6@sha256:89d9d35757eb57c62973c193c96b5b50ca73bbaff7fa282ef81f7fd155a3747d"
        DefaultImageTag = "vibemind-qdrant:v1.18.0-recovery"
    }
}

function Test-QdrantReleaseAsset {
    param([Parameter(Mandatory)][string]$Path)

    $metadata = Get-QdrantRecoveryMetadata
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Qdrant release asset does not exist: $Path"
    }

    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $metadata.AssetBytes) {
        throw "Qdrant release asset size mismatch: $($item.Length) != $($metadata.AssetBytes)"
    }

    $hash = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
    if ($hash -ne $metadata.AssetSha256) {
        throw "Qdrant release asset SHA256 mismatch: $hash"
    }

    return $item
}

function Invoke-QdrantRecoveryBuild {
    param(
        [Parameter(Mandatory)][string]$VerifiedAssetPath,
        [string]$Tag = "vibemind-qdrant:v1.18.0-recovery"
    )

    $asset = Test-QdrantReleaseAsset -Path $VerifiedAssetPath
    $metadata = Get-QdrantRecoveryMetadata
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $recoveryRoot = Join-Path $repoRoot "logs\recovery"
    $buildRoot = Join-Path $recoveryRoot "qdrant-v1.18.0-build"
    $dockerfile = Join-Path $repoRoot "infra\qdrant-recovery\Dockerfile"

    if (Test-Path -LiteralPath $buildRoot) {
        $resolvedBuildRoot = (Resolve-Path -LiteralPath $buildRoot).Path
        $resolvedRecoveryRoot = (Resolve-Path -LiteralPath $recoveryRoot).Path
        if (-not $resolvedBuildRoot.StartsWith(
            $resolvedRecoveryRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to clear build directory outside recovery root: $resolvedBuildRoot"
        }
        Remove-Item -LiteralPath $resolvedBuildRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

    & tar.exe -xzf $asset.FullName -C $buildRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to extract Qdrant release asset (tar exit $LASTEXITCODE)"
    }

    $binaryCandidates = @(
        Get-ChildItem -LiteralPath $buildRoot -Recurse -File -Filter "qdrant"
    )
    if ($binaryCandidates.Count -ne 1) {
        throw "Expected exactly one qdrant binary, found $($binaryCandidates.Count)"
    }
    $contextBinary = Join-Path $buildRoot "qdrant"
    if ($binaryCandidates[0].FullName -ne $contextBinary) {
        Copy-Item -LiteralPath $binaryCandidates[0].FullName -Destination $contextBinary -Force
    }

    & docker.exe build `
        --pull=false `
        --build-arg "BASE_IMAGE=$($metadata.BaseImage)" `
        --tag $Tag `
        --file $dockerfile `
        $buildRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Qdrant recovery image build failed (docker exit $LASTEXITCODE)"
    }

    $versionOutput = & docker.exe run --rm --entrypoint /qdrant/qdrant $Tag --version
    if ($LASTEXITCODE -ne 0 -or ($versionOutput -join " ") -notmatch "1\.18\.0") {
        throw "Qdrant recovery image version check failed: $($versionOutput -join ' ')"
    }

    $imageId = & docker.exe image inspect $Tag --format "{{.Id}}"
    [pscustomobject]@{
        Image = $Tag
        ImageId = ($imageId | Select-Object -First 1)
        VersionOutput = ($versionOutput -join " ").Trim()
        AssetSha256 = $metadata.AssetSha256
        BaseImage = $metadata.BaseImage
        BuildContext = $buildRoot
    }
}

if (-not $LibraryMode) {
    if (-not $AssetPath) {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        $AssetPath = Join-Path $repoRoot "backups\qdrant\qdrant-x86_64-unknown-linux-musl-v1.18.0.tar.gz"
    }
    Invoke-QdrantRecoveryBuild -VerifiedAssetPath $AssetPath -Tag $ImageTag
}
