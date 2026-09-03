"""Manual live smoke test against the real Docker engine. Read-only.

Run: python -m docker.tests.smoke_live   (from the mcp/ directory)
"""

from docker import server


def main() -> None:
    checks = [
        ("version", lambda: server.version()),
        ("container_ls", lambda: server.container_ls(all=True)),
        ("image_ls", lambda: server.image_ls()),
        ("stack_ls", lambda: server.stack_ls()),
        ("service_ls", lambda: server.service_ls()),
        ("system_df", lambda: server.system_df()),
    ]
    failed = 0
    for name, fn in checks:
        res = fn()
        ok = res.get("ok")
        n = len(res["data"]) if isinstance(res.get("data"), list) else "-"
        print(f"[{'OK ' if ok else 'FAIL'}] {name:16} ok={ok} data_items={n}")
        if not ok:
            failed += 1
            print("        stderr:", res.get("stderr", "")[:200])
    print(f"\n{len(checks) - failed}/{len(checks)} read tools OK")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
