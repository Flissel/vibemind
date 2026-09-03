<#
.SYNOPSIS
    Single source of truth for building the LOCAL images the unified Swarm
    stack (infra/swarm/vibemind-stack.yml) deploys with `--resolve-image never`.
.DESCRIPTION
    The stack deploys local-only `:latest`/`:static` images and NEVER builds
    them (`docker stack deploy` cannot build). If an image is missing, the
    service is endlessly "Rejected: No such image" — a silent partial start.

    This script declares every such image with its build recipe and exposes
    Invoke-EnsureStackImages, which the launcher calls BEFORE `stack deploy`:
      1. Ensure build SOURCES exist (mirofish git submodule; rowboat app source
         — both can be absent in a fresh checkout).
      2. Detect which required images are missing locally.
      3. Build ONLY the missing ones (fast normal start: 0 builds when present;
         self-healing when an image was pruned).

    Tags are deliberately INCONSISTENT across services (davefelix-* vs
    vibemind-* vs :static) — historical. That's exactly why the recipe is an
    explicit per-image map here, not a project-prefix guess.

    Dot-source this file, then call Invoke-EnsureStackImages -Root <repoRoot>.
    Returns $true if all required images are present after the run, else $false.
#>

# ── Image recipes ────────────────────────────────────────────────────
# Each recipe is one required stack image. Two build kinds:
#   "compose": docker compose -p <Project> -f <File> build <Service>
#              → produces tag  <Project>-<Service>:latest
#   "build":   docker build -t <Tag> -f <Dockerfile> <Context>
#              → produces the exact <Tag> (use for the divergent tags)
# Paths are relative to repo root; resolved to absolute at call time.
function Get-StackImageRecipes {
    @(
        # --- Mirofish (compose; needs git submodule source) ---
        @{ Tag = "vibemind-mirofish-mirofish:latest"
           Kind = "compose"; Project = "vibemind-mirofish"; Service = "mirofish"
           File = "vibemind-os/voice/docker-compose.mirofish.yml"
           Env  = @{ MIROFISH_HOST_PORT = "5101" } }

        # --- n8n (compose) ---
        @{ Tag = "vibemind-n8n:latest"
           Kind = "compose"; Project = "vibemind"; Service = "n8n"
           File = "vibemind-os/voice/docker-compose.n8n.yml" }

        # --- Rowboat: UI/API + jobs + rag, all from apps/rowboat (compose) ---
        # rowboat-agents is intentionally NOT built (replicas:0 in the stack —
        # upstream removed the source). Re-add a recipe here if it's restored.
        @{ Tag = "vibemind-rowboat-rowboat:latest"
           Kind = "compose"; Project = "vibemind-rowboat"; Service = "rowboat"
           File = "vibemind-os/spaces/rowboat/rowboat/docker-compose.yml" }
        @{ Tag = "vibemind-rowboat-jobs-worker:latest"
           Kind = "compose"; Project = "vibemind-rowboat"; Service = "jobs-worker"
           File = "vibemind-os/spaces/rowboat/rowboat/docker-compose.yml" }
        @{ Tag = "vibemind-rowboat-rag-worker:latest"
           Kind = "compose"; Project = "vibemind-rowboat"; Service = "rag-worker"
           File = "vibemind-os/spaces/rowboat/rowboat/docker-compose.yml" }

        # --- Coding-engine (explicit docker build — divergent tags) ---
        @{ Tag = "davefelix-coding-engine-api:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/coding-engine/infra/docker/Dockerfile.api"
           Context = "vibemind-os/coding-engine" }
        @{ Tag = "vibemind-coding-worker:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/coding-engine/infra/docker/Dockerfile.worker"
           Context = "vibemind-os/coding-engine" }
        @{ Tag = "davefelix-coding-engine-openclaude-service:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/openclaude/Dockerfile"
           Context = "vibemind-os/openclaude" }
        # Static nginx SPA on :80 (NOT the repo's default Vite dev Dockerfile).
        @{ Tag = "vibemind-coding-frontend:static"
           Kind = "build"
           Dockerfile = "vibemind-os/coding-engine/web-app/front/Dockerfile.static"
           Context = "vibemind-os/coding-engine/web-app/front" }

        # --- Embedding service (explicit docker build) ---
        @{ Tag = "vibemind-embedding-service:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/embedding-service/Dockerfile"
           Context = "vibemind-os/embedding-service" }

        # --- Brain core (explicit docker build). Context is the vibemind-os
        #     ROOT: the Dockerfile COPYs both shared/ and brain/the_brain/.
        #     Used unchanged by brain-core/-api/-loops/-autotrain-drain and
        #     the opt-in learner/inference services. ---
        @{ Tag = "vibemind-brain-core:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/brain/the_brain/Dockerfile"
           Context = "vibemind-os" }
    )
}

function Test-ImageExists {
    param([string]$Tag)
    $found = docker image inspect $Tag 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-BuildSources {
    <#
        Make sure build CONTEXTS that can be absent in a fresh checkout exist:
          * mirofish — a git submodule (clone if the Dockerfile is missing).
          * rowboat apps/rowboat — upstream app source (warn if absent; it is
            fetched out-of-band, no canonical submodule in this repo).
        Best-effort; returns nothing. Missing-source images simply fail the
        later build and are reported by the caller.
    #>
    param([string]$Root)

    # mirofish submodule
    $mfDir = Join-Path $Root "vibemind-os/spaces/mirofish/mirofish"
    $mfDockerfile = Join-Path $mfDir "Dockerfile"
    if (-not (Test-Path $mfDockerfile)) {
        Write-Host "  [BUILD] mirofish source missing — cloning submodule..." -ForegroundColor Cyan
        $url = "https://github.com/Flissel/MiroFish.git"
        $branch = "backup-local-2026-04-12"
        # Prefer submodule init; fall back to a direct branch clone (the gitlink
        # isn't committed at the nested level in some checkouts).
        Push-Location (Join-Path $Root "vibemind-os")
        try { git submodule update --init "spaces/mirofish/mirofish" 2>&1 | Out-Null } catch {}
        Pop-Location
        if (-not (Test-Path $mfDockerfile)) {
            if (Test-Path $mfDir) { Remove-Item -Recurse -Force $mfDir -ErrorAction SilentlyContinue }
            git clone --branch $branch --depth 1 $url $mfDir 2>&1 | Out-Null
        }
        if (Test-Path $mfDockerfile) {
            Write-Host "    mirofish source ready." -ForegroundColor Green
        } else {
            Write-Host "    [WARN] mirofish source still missing — its image will not build." -ForegroundColor Yellow
        }
    }

    # rowboat app source
    $rbDockerfile = Join-Path $Root "vibemind-os/spaces/rowboat/rowboat/apps/rowboat/Dockerfile"
    if (-not (Test-Path $rbDockerfile)) {
        Write-Host "  [WARN] rowboat app source missing (apps/rowboat/Dockerfile)." -ForegroundColor Yellow
        Write-Host "         Fetch it from rowboatlabs/rowboat (commit bc929b6c) into" -ForegroundColor DarkYellow
        Write-Host "         vibemind-os/spaces/rowboat/rowboat/apps/rowboat/ then re-run." -ForegroundColor DarkYellow
    }
}

function Invoke-BuildRecipe {
    param([hashtable]$Recipe, [string]$Root)
    $tag = $Recipe.Tag
    if ($Recipe.Kind -eq "compose") {
        $file = Join-Path $Root $Recipe.File
        if (-not (Test-Path $file)) {
            Write-Host "    [WARN] compose file missing for $tag : $file" -ForegroundColor Yellow
            return $false
        }
        # Per-recipe env (e.g. MIROFISH_HOST_PORT) into process env for this build.
        $saved = @{}
        if ($Recipe.Env) {
            foreach ($k in $Recipe.Env.Keys) {
                $saved[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
                [Environment]::SetEnvironmentVariable($k, [string]$Recipe.Env[$k], "Process")
            }
        }
        Write-Host "    Building $tag (compose $($Recipe.Project)/$($Recipe.Service))..." -ForegroundColor Gray
        docker compose -p $Recipe.Project -f $file build $Recipe.Service 2>&1 |
            Where-Object { $_ -match 'ERROR|error|failed|Built' } |
            Select-Object -Last 3 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
        $ok = ($LASTEXITCODE -eq 0)
        if ($Recipe.Env) {
            foreach ($k in $Recipe.Env.Keys) {
                [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process")
            }
        }
    }
    else {
        # Kind = "build": explicit -t tag
        $df  = Join-Path $Root $Recipe.Dockerfile
        $ctx = Join-Path $Root $Recipe.Context
        if (-not (Test-Path $df) -or -not (Test-Path $ctx)) {
            Write-Host "    [WARN] source missing for $tag (dockerfile/context absent) — skipping" -ForegroundColor Yellow
            return $false
        }
        Write-Host "    Building $tag (docker build)..." -ForegroundColor Gray
        docker build -t $tag -f $df $ctx 2>&1 |
            Where-Object { $_ -match 'ERROR|error|failed|writing image|naming to' } |
            Select-Object -Last 3 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
        $ok = ($LASTEXITCODE -eq 0)
    }
    if ($ok -and (Test-ImageExists $tag)) {
        Write-Host "    [OK] $tag" -ForegroundColor Green
        return $true
    }
    Write-Host "    [FAIL] $tag did not build" -ForegroundColor Red
    return $false
}

function Invoke-EnsureStackImages {
    <#
    .SYNOPSIS
        Ensure every required local stack image exists; build the missing ones.
    .PARAMETER Root
        Repo root (where infra/ and vibemind-os/ live).
    .PARAMETER Force
        Rebuild ALL recipes even if the image already exists (for updates).
    .OUTPUTS
        [bool] $true if every required image is present afterwards.
    #>
    param([Parameter(Mandatory)][string]$Root, [switch]$Force)

    $recipes = Get-StackImageRecipes
    $missing = if ($Force) { $recipes } else { $recipes | Where-Object { -not (Test-ImageExists $_.Tag) } }

    if ($missing.Count -eq 0) {
        Write-Host "  [BUILD] All $($recipes.Count) stack images present — nothing to build." -ForegroundColor Green
        return $true
    }

    Write-Host "  [BUILD] $($missing.Count)/$($recipes.Count) stack image(s) missing — building..." -ForegroundColor Cyan
    Ensure-BuildSources -Root $Root

    $failed = @()
    foreach ($r in $missing) {
        if (-not (Invoke-BuildRecipe -Recipe $r -Root $Root)) { $failed += $r.Tag }
    }

    if ($failed.Count -gt 0) {
        Write-Host "  [BUILD] $($failed.Count) image(s) FAILED to build:" -ForegroundColor Red
        $failed | ForEach-Object { Write-Host "          - $_" -ForegroundColor Red }
        Write-Host "  [BUILD] The matching stack services will stay 'No such image' (0/1)." -ForegroundColor Yellow
        return $false
    }
    Write-Host "  [BUILD] All missing images built." -ForegroundColor Green
    return $true
}
