<#
.SYNOPSIS
    Idempotent re-apply of VibeMind's openclaw patches after any install/update.

.DESCRIPTION
    `npm install -g openclaw@...` overwrites the whole dist/ tree, wiping any
    local edits. This script re-applies VibeMind's patches so they survive
    every update. Safe to run repeatedly — each patch checks whether it is
    already applied before touching anything.

    Patches applied:
      1. qr-terminal: terminal half-block QR codes scan poorly (line-height
         distorts the aspect ratio). We (a) keep the terminal render
         square (small:false) and (b) ALSO dump a real PNG to the Desktop
         and open it — that scans reliably regardless of terminal font/size.

    The target file name carries a content hash (qr-terminal-XXXX.js) that
    changes per openclaw build, so we glob `dist/qr-terminal-*.js` instead of
    hard-coding the hash.

    Exit code: always 0 (best-effort — must never block a stack start).

.NOTES
    Called by:
      - scripts/openclaw_update.ps1 (right after npm install)
      - scripts/vibemind-start.ps1 (every stack start, as a safety net)
    Standalone:  pwsh -File scripts/openclaw_apply_patches.ps1
#>
param(
    [string]$NpmRoot = (npm root -g 2>$null)
)

$ErrorActionPreference = "Continue"

function Write-PatchLog([string]$msg, [string]$color = "Gray") {
    Write-Host "  [openclaw-patch] $msg" -ForegroundColor $color
}

if (-not $NpmRoot) {
    $NpmRoot = Join-Path $env:APPDATA "npm\node_modules"
}
$distDir = Join-Path $NpmRoot "openclaw\dist"

if (-not (Test-Path $distDir)) {
    Write-PatchLog "openclaw dist not found at $distDir — openclaw not installed? skipping." "Yellow"
    exit 0
}

# ── Patch 1: qr-terminal PNG dump + square terminal render ──────────────
$qrFiles = @(Get-ChildItem -Path $distDir -Filter "qr-terminal-*.js" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike "*.bak*" })

if ($qrFiles.Count -eq 0) {
    Write-PatchLog "no qr-terminal-*.js in dist — openclaw structure changed? skipping QR patch." "Yellow"
} else {
    foreach ($qf in $qrFiles) {
        $content = Get-Content -Raw -Path $qf.FullName -Encoding utf8

        # Already patched? (our marker comment)
        if ($content -match "VibeMind patch") {
            Write-PatchLog "qr-terminal already patched: $($qf.Name)"
            continue
        }

        # Must contain the function we expect to patch.
        if ($content -notmatch "async function renderQrTerminal") {
            Write-PatchLog "qr-terminal has no renderQrTerminal — unexpected shape, skipping $($qf.Name)" "Yellow"
            continue
        }

        # Backup once.
        $bak = "$($qf.FullName).bak-pre-vibemind-patch"
        if (-not (Test-Path $bak)) {
            Copy-Item -Path $qf.FullName -Destination $bak -Force
        }

        # The patched renderQrTerminal body. We replace the whole function
        # definition. Source shape (openclaw 2026.5.x):
        #   async function renderQrTerminal(input, opts = {}) {
        #       return await (await loadQrCodeRuntime()).toString(normalizeQrText(input), {
        #           small: opts.small ?? false,   (or ?? true if a prior edit ran)
        #           type: "terminal"
        #       });
        #   }
        $patched = @'
// VibeMind patch (2026-06): terminal half-block QR codes scan poorly.
// Dump a real PNG to the Desktop and open it, in addition to the terminal
// render. Best-effort: any failure here must never break the login flow.
async function _vibemindDumpQrPng(text) {
	try {
		const os = await import("node:os");
		const path = await import("node:path");
		const cp = await import("node:child_process");
		const rt = await loadQrCodeRuntime();
		const out = path.join(os.homedir(), "Desktop", "openclaw-qr.png");
		await rt.toFile(out, text, { type: "png", scale: 8, margin: 2 });
		try { cp.spawn("cmd", ["/c", "start", "", out], { detached: true, stdio: "ignore" }).unref(); } catch {}
		process.stdout.write(`\n[openclaw] Scannbarer QR als Bild: ${out}\n`);
	} catch {}
}
async function renderQrTerminal(input, opts = {}) {
	const text = normalizeQrText(input);
	_vibemindDumpQrPng(text);
	return await (await loadQrCodeRuntime()).toString(text, {
		small: opts.small ?? false,
		type: "terminal"
	});
}
'@

        # Replace from `async function renderQrTerminal` up to the closing
        # brace of that function (the line `}` immediately before `//#endregion`).
        $pattern = '(?s)async function renderQrTerminal\(input, opts = \{\}\) \{.*?\n\}'
        if ($content -match $pattern) {
            $new = [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $patched }, 1)
            Set-Content -Path $qf.FullName -Value $new -Encoding utf8 -NoNewline
            Write-PatchLog "qr-terminal patched: $($qf.Name)" "Green"
        } else {
            Write-PatchLog "qr-terminal regex did not match in $($qf.Name) — leaving untouched" "Yellow"
        }
    }
}

Write-PatchLog "done." "Cyan"
exit 0
