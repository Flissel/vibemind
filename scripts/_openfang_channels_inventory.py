"""Lightweight static-analysis of OpenFang channel modules.

For each .rs file in openfang-channels/src/, count:
  - file size (rough proxy for maturity)
  - presence of `pub async fn send_message` or similar outbound entry
  - presence of webhook/poll/listen indicators for inbound
  - OAuth-related symbols (Authorization, Bearer, client_id, oauth)
  - whether it's referenced from router.rs (= actually wired up)

This is a smoke-test, not a deep code review. Channels that LOOK production-ready
here still need a hands-on integration test.

Output: a Markdown table sortable by maturity.
"""
from __future__ import annotations
import re
from pathlib import Path

CHANNELS_DIR = Path(__file__).parent.parent / "vibemind-os" / "openfang" / "crates" / "openfang-channels" / "src"
OUT_PATH = Path(__file__).parent.parent / "vibemind-os" / "spaces" / "marketing" / "docs" / "openfang-channels-inventory.md"

# Files we skip (not channels)
SKIP = {"lib.rs", "router.rs", "types.rs", "bridge.rs", "formatter.rs"}

# Patterns to detect capability
OUTBOUND_PATTERNS = [
    r"async fn send_message",
    r"async fn send\b",
    r"async fn post\b",
    r"async fn deliver",
    r"fn outbound",
]
INBOUND_PATTERNS = [
    r"webhook",
    r"fn poll",
    r"async fn start_listener",
    r"async fn listen",
    r"async fn receive",
    r"InboundEvent",
]
OAUTH_PATTERNS = [
    r"oauth",
    r"OAuth",
    r"Bearer ",
    r"access_token",
    r"client_id",
    r"client_secret",
    r"refresh_token",
]
HTTP_PATTERNS = [
    r"reqwest::",
    r"hyper::",
    r"https://",
]


def has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def count_pub_async_fn(text: str) -> int:
    return len(re.findall(r"pub (?:async )?fn ", text))


def main():
    router_path = CHANNELS_DIR / "router.rs"
    router_text = router_path.read_text(encoding="utf-8", errors="replace") if router_path.exists() else ""
    lib_path = CHANNELS_DIR / "lib.rs"
    lib_text = lib_path.read_text(encoding="utf-8", errors="replace") if lib_path.exists() else ""

    rows = []
    for f in sorted(CHANNELS_DIR.glob("*.rs")):
        if f.name in SKIP:
            continue
        ch = f.stem  # bluesky, telegram, etc.
        text = f.read_text(encoding="utf-8", errors="replace")
        size = len(text)
        loc = text.count("\n")
        # Module reference in lib.rs?
        referenced_in_lib = bool(re.search(rf"\bmod {ch}\b|\bpub mod {ch}\b", lib_text))
        # Wired in router?
        wired_in_router = ch in router_text or ch.replace("_", "-") in router_text
        outbound = has_any(text, OUTBOUND_PATTERNS)
        inbound = has_any(text, INBOUND_PATTERNS)
        oauth = has_any(text, OAUTH_PATTERNS)
        http = has_any(text, HTTP_PATTERNS)
        pub_fns = count_pub_async_fn(text)
        # Maturity heuristic
        if size < 500:
            maturity = "stub"
        elif size < 3000:
            maturity = "early"
        elif outbound and (inbound or oauth):
            maturity = "ready"
        elif outbound:
            maturity = "outbound-only"
        else:
            maturity = "skeleton"
        rows.append({
            "channel": ch,
            "size": size,
            "loc": loc,
            "pub_fns": pub_fns,
            "outbound": "✓" if outbound else "·",
            "inbound": "✓" if inbound else "·",
            "oauth": "✓" if oauth else "·",
            "http": "✓" if http else "·",
            "lib_ref": "✓" if referenced_in_lib else "·",
            "router": "✓" if wired_in_router else "·",
            "maturity": maturity,
        })

    # Sort: ready first, then by size desc
    maturity_order = {"ready": 0, "outbound-only": 1, "skeleton": 2, "early": 3, "stub": 4}
    rows.sort(key=lambda r: (maturity_order[r["maturity"]], -r["size"]))

    # Render Markdown
    md = []
    md.append("# OpenFang Channels — Static Inventory")
    md.append("")
    md.append("Generated: 2026-05-26")
    md.append("Source: `vibemind-os/openfang/crates/openfang-channels/src/*.rs`")
    md.append("Method: regex-based static scan, **not** integration tested. A `ready` rating means")
    md.append("the file has outbound send + (inbound OR oauth) + non-trivial size — it's a smoke")
    md.append("signal, no guarantee the channel actually works end-to-end.")
    md.append("")
    md.append("## Summary")
    md.append("")
    from collections import Counter
    counts = Counter(r["maturity"] for r in rows)
    for k in ("ready", "outbound-only", "skeleton", "early", "stub"):
        if counts.get(k):
            md.append(f"- **{k}**: {counts[k]}")
    md.append(f"- **Total channel files**: {len(rows)}")
    md.append("")
    md.append("## Per-channel detail")
    md.append("")
    md.append("| Channel | Maturity | LOC | Pub fns | OUT | IN | OAuth | HTTP | lib mod | router |")
    md.append("|---|---|---:|---:|:-:|:-:|:-:|:-:|:-:|:-:|")
    for r in rows:
        md.append(
            f"| {r['channel']} | {r['maturity']} | {r['loc']} | {r['pub_fns']} | "
            f"{r['outbound']} | {r['inbound']} | {r['oauth']} | {r['http']} | "
            f"{r['lib_ref']} | {r['router']} |"
        )

    md.append("")
    md.append("## Top-8 for Marketing-Ops Phase 1")
    md.append("")
    md.append("From the Marketing-Ops plan, we'd want: email, telegram, discord, slack,")
    md.append("linkedin, mastodon, bluesky, webhook. Status per the inventory above:")
    md.append("")
    md.append("| Channel | Maturity | Comment |")
    md.append("|---|---|---|")
    target = ["email", "telegram", "discord", "slack", "linkedin", "mastodon", "bluesky", "webhook"]
    by_name = {r["channel"]: r for r in rows}
    for t in target:
        r = by_name.get(t)
        if r:
            md.append(f"| {t} | {r['maturity']} | {r['loc']} LOC, {r['pub_fns']} pub fns |")
        else:
            md.append(f"| {t} | MISSING | not present in src/ |")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote: {OUT_PATH}")
    print()
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
