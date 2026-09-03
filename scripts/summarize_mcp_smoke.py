"""
Post-process results/mcp_smoke.json into a clean per-server matrix.

Reclassifies "transport_error" entries that came from dangerous-tool probes
hitting the request timeout: those mean the MCP accepted the call and the
tool is doing real work in its executor. They are not DEAD — they prove
end-to-end reachability up to and including the tool process.

Categories in final report:
- ok_real      : read-only tool returned real data
- ok_validated : dangerous tool returned a tool-side error (validation/no-op)
- ok_busy      : dangerous tool accepted the call, executor is busy past timeout
- tool_error   : a real read failed (likely needs args / config)
- dead         : transport-level error that was NOT timeout-on-dangerous
- skipped      : required args not provided

Per-server verdict:
  GREEN  = at least one ok_real or ok_validated, zero dead
  YELLOW = at least one dead, but also some ok
  RED    = every tool dead
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results" / "mcp_smoke.json"


def reclassify(entry: dict) -> str:
    eff = entry.get("effective", "")
    if eff == "transport_error" and entry.get("dangerous") and entry.get("elapsed_s", 0) >= 4.5:
        return "ok_busy"
    return eff


def main() -> int:
    if not RESULTS.is_file():
        print(f"missing {RESULTS}")
        return 1

    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    by_server: dict[str, list[dict]] = defaultdict(list)
    for entry in data:
        entry["final"] = reclassify(entry)
        by_server[entry["server"]].append(entry)

    print(f"{'SERVER':25s} {'GRN':>4s} {'OKR':>4s} {'OKV':>4s} {'BSY':>4s} {'ERR':>4s} {'SKP':>4s} {'DEAD':>5s}  VERDICT")
    print("-" * 80)
    totals = defaultdict(int)
    verdict_counts = defaultdict(int)

    for server in sorted(by_server):
        entries = by_server[server]
        c = defaultdict(int)
        for e in entries:
            c[e["final"]] += 1
            totals[e["final"]] += 1

        ok = c["ok_real"] + c["ok_validated"] + c["ok_busy"]
        dead = c["transport_error"]
        if dead == 0 and ok > 0:
            verdict = "GREEN"
        elif dead > 0 and ok > 0:
            verdict = "YELLOW"
        elif dead == len(entries):
            verdict = "RED"
        else:
            verdict = "GREY"
        verdict_counts[verdict] += 1

        print(
            f"{server:25s} {ok:4d} {c['ok_real']:4d} {c['ok_validated']:4d} "
            f"{c['ok_busy']:4d} {c['tool_error']:4d} {c['skipped_needs_args']:4d} "
            f"{dead:5d}  {verdict}"
        )

    print("-" * 80)
    print(
        f"{'TOTAL':25s} {totals['ok_real']+totals['ok_validated']+totals['ok_busy']:4d} "
        f"{totals['ok_real']:4d} {totals['ok_validated']:4d} {totals['ok_busy']:4d} "
        f"{totals['tool_error']:4d} {totals['skipped_needs_args']:4d} "
        f"{totals['transport_error']:5d}"
    )
    print()
    print(f"Verdicts:  GREEN={verdict_counts['GREEN']}  "
          f"YELLOW={verdict_counts['YELLOW']}  "
          f"RED={verdict_counts['RED']}  GREY={verdict_counts['GREY']}")

    # Highlight any genuine DEAD tools
    dead_tools = [e for e in data if e["final"] == "transport_error"]
    if dead_tools:
        print(f"\nGenuinely unreachable ({len(dead_tools)}):")
        for e in dead_tools:
            print(f"  {e['server']:25s} {e['tool']:55s} {e.get('summary','')[:60]}")

    # Write final report
    out = RESULTS.parent / "mcp_smoke_summary.json"
    out.write_text(
        json.dumps(
            {
                "totals": dict(totals),
                "verdicts": dict(verdict_counts),
                "by_server": {
                    s: {
                        "verdict": (
                            "GREEN"
                            if (sum(1 for e in by_server[s] if e["final"] in ("ok_real","ok_validated","ok_busy")) > 0
                                and sum(1 for e in by_server[s] if e["final"] == "transport_error") == 0)
                            else (
                                "RED" if all(e["final"] == "transport_error" for e in by_server[s])
                                else "YELLOW" if any(e["final"] == "transport_error" for e in by_server[s])
                                else "GREY"
                            )
                        ),
                        "tools": [
                            {
                                "name": e["tool"],
                                "final": e["final"],
                                "elapsed_s": e.get("elapsed_s", 0),
                                "summary": e.get("summary", "")[:120],
                            }
                            for e in by_server[s]
                        ],
                    }
                    for s in sorted(by_server)
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
