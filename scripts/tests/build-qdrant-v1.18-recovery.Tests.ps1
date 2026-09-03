Describe "Qdrant v1.18 recovery build" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $scriptPath = Join-Path $repoRoot "scripts\build-qdrant-v1.18-recovery.ps1"
        $dockerfilePath = Join-Path $repoRoot "infra\qdrant-recovery\Dockerfile"
        . $scriptPath -LibraryMode
    }

    It "pins the official release asset and compatible cached base" {
        $metadata = Get-QdrantRecoveryMetadata

        $metadata.Version | Should -Be "v1.18.0"
        $metadata.AssetBytes | Should -Be 32330331
        $metadata.AssetSha256 | Should -Be "76C38C3859682776D2BEF61BF6C23B593B7C06682578F7C9FF9EAC79C87A4268"
        $metadata.BaseImage | Should -Be "qdrant/qdrant:v1.12.6@sha256:89d9d35757eb57c62973c193c96b5b50ca73bbaff7fa282ef81f7fd155a3747d"
    }

    It "fails closed for a missing asset" {
        { Test-QdrantReleaseAsset -Path (Join-Path $TestDrive "missing.tar.gz") } |
            Should -Throw "*does not exist*"
    }

    It "fails closed for an asset with the wrong size or digest" {
        $badAsset = Join-Path $TestDrive "bad.tar.gz"
        Set-Content -LiteralPath $badAsset -Value "not qdrant" -NoNewline

        { Test-QdrantReleaseAsset -Path $badAsset } |
            Should -Throw "*size mismatch*"
    }

    It "uses the pinned base image and recovery version label" {
        $dockerfile = Get-Content -Raw -LiteralPath $dockerfilePath

        $dockerfile | Should -Match 'ARG BASE_IMAGE'
        $dockerfile | Should -Match ([regex]::Escape('ARG BASE_IMAGE=qdrant/qdrant:v1.12.6@sha256:89d9d35757eb57c62973c193c96b5b50ca73bbaff7fa282ef81f7fd155a3747d'))
        $dockerfile | Should -Match 'FROM \$\{BASE_IMAGE\}'
        $dockerfile | Should -Match 'org.opencontainers.image.version="v1.18.0-recovery"'
        $dockerfile | Should -Match 'COPY qdrant /qdrant/qdrant'
    }
}
