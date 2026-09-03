"""Extract named services from infra/swarm/vibemind-stack.yml into a plain
(non-Swarm) docker-compose.yml for a remote host, stripping Swarm-only keys
and applying the cross-machine env var overrides needed for that host.

Usage: python extract_compose.py <phase1|phase2> > output.yml
"""
import os
import sys
import yaml

SOURCE = "infra/swarm/vibemind-stack.yml"
SOURCE_DIR = os.path.dirname(SOURCE)

PHASE1_SERVICES = ["loki", "grafana-vibemind", "coding-gitea", "gitea-postgres"]
PHASE2_SERVICES = [
    "rowboat-mongo", "rowboat-redis", "rowboat", "rowboat-agents",
    "rowboat-jobs-worker", "rowboat-rag-worker", "neo4j-mirofish", "n8n",
    "supabase-db", "supabase-auth", "supabase-rest", "supabase-realtime",
    "supabase-storage", "supabase-pg-meta", "supabase-analytics",
    "supabase-kong", "supabase-studio", "supabase-inbucket",
]
PHASE2B_SERVICES = [
    "supabase-db", "supabase-auth", "supabase-rest", "supabase-realtime",
    "supabase-storage", "supabase-pg-meta", "supabase-analytics",
    "supabase-kong", "supabase-studio", "supabase-inbucket",
]

# Env var rewrites keyed by service name: {old_value: new_value}
# Applied to BOTH list-style (`- KEY=value`) and dict-style (`KEY: value`)
# `environment:` blocks -- Phase 2b's supabase-* services use dict style.
ENV_REWRITES = {
    "grafana-vibemind": {
        "GF_SECURITY_ADMIN_PASSWORD=vibemind-dev": "GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}",
    },
    "coding-gitea": {
        "GITEA__server__ROOT_URL=http://localhost:3002/": "GITEA__server__ROOT_URL=http://192.168.178.65:3002/",
        "GITEA__database__PASSWD=gitea": "GITEA__database__PASSWD=${GITEA_POSTGRES_PASSWORD}",
    },
    "gitea-postgres": {
        "POSTGRES_PASSWORD=gitea": "POSTGRES_PASSWORD=${GITEA_POSTGRES_PASSWORD}",
    },
    "rowboat": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-agents": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-jobs-worker": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-rag-worker": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    # Phase 2b: same demo secrets as the local deploy for now (functional
    # parity first) -- only rewrite the host-facing URLs that were
    # 127.0.0.1-scoped locally. Secret rotation is a deliberate follow-up
    # (kong.yml embeds the demo JWT 8x in Lua request-transformer templates
    # -- rotating it needs its own careful pass, not bundled with this move).
    "supabase-auth": {
        "API_EXTERNAL_URL": "http://192.168.178.65:54321",
        # GoTrue's pop/pgx driver doesn't inherit the role-level
        # `ALTER ROLE supabase_auth_admin SET search_path=auth` default on a
        # truly fresh DB (confirmed via psql: rolconfig IS set correctly,
        # GoTrue's own connection still errors "no schema has been selected
        # to create in"). Neither a bare `?search_path=` query param nor a
        # `?options=-c search_path%3D...` DSN param were honored -- trying
        # PGOPTIONS as a plain env var next (libpq reads it directly,
        # independent of DSN parsing).
        "GOTRUE_DB_DATABASE_URL": "postgresql://supabase_auth_admin:postgres@supabase-db:5432/postgres",
        "PGOPTIONS": "-c search_path=auth",
    },
    "supabase-studio": {"SUPABASE_PUBLIC_URL": "http://192.168.178.65:54321"},
    "supabase-storage": {
        "DATABASE_URL": "postgresql://supabase_storage_admin:postgres@supabase-db:5432/postgres?search_path=storage,public,extensions",
    },
}

STRIP_KEYS = ["deploy", "secrets", "extra_hosts", "healthcheck"]

# Postgres's docker-entrypoint runs /docker-entrypoint-initdb.d/* in plain
# alphabetical order, and the Supabase postgres image's own role-creation
# script (migrate.sh) lives in that same directory. "00-"/"01-"/"02-" sort
# BEFORE "migrate.sh" ('0' < 'm'), so on a truly fresh volume our scripts'
# `ALTER USER postgres ...` runs before migrate.sh has created that role.
# The shared source filenames stay as-is (matches the currently-deployed
# local stack); only the container-side mount TARGET is renamed here so it
# sorts after migrate.sh, VM-deploy-only.
TARGET_OVERRIDES = {
    "/docker-entrypoint-initdb.d/00-bootstrap.sql": "/docker-entrypoint-initdb.d/z0-bootstrap.sql",
    "/docker-entrypoint-initdb.d/01-restore.sql": "/docker-entrypoint-initdb.d/z1-restore.sql",
    "/docker-entrypoint-initdb.d/02-restore-internal.sql": "/docker-entrypoint-initdb.d/z2-restore-internal.sql",
}


def main():
    phase = sys.argv[1]
    names = {"phase1": PHASE1_SERVICES, "phase2b": PHASE2B_SERVICES}.get(phase, PHASE2_SERVICES)

    with open(SOURCE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    out_services = {}
    out_volumes = {}
    all_services = data["services"]
    all_configs = data.get("configs", {})
    config_files_needed = []  # (local_path, remote_relative_name) pairs to scp over

    for name in names:
        cfg = dict(all_services[name])
        configs = cfg.pop("configs", [])
        for key in STRIP_KEYS:
            cfg.pop(key, None)
        cfg["restart"] = "unless-stopped"
        cfg.pop("networks", None)

        # Swarm `configs:` -> plain bind-mount volumes, staged under ./configs/
        bind_mounts = list(cfg.get("volumes", []) or [])
        for c in configs:
            source_name = c["source"]
            raw_path = all_configs[source_name]["file"]
            local_path = os.path.normpath(os.path.join(SOURCE_DIR, raw_path))
            staged_name = source_name + os.path.splitext(raw_path)[1]
            config_files_needed.append((local_path.replace("\\", "/"), staged_name))
            target = TARGET_OVERRIDES.get(c["target"], c["target"])
            bind_mounts.append(f"./configs/{staged_name}:{target}:ro")
        if bind_mounts:
            cfg["volumes"] = bind_mounts

        rewrites = ENV_REWRITES.get(name, {})
        if rewrites and isinstance(cfg.get("environment"), list):
            # List-style `- KEY=value` entries: rewrite keyed by full "KEY=value".
            new_env = []
            for entry in cfg["environment"]:
                new_env.append(rewrites.get(entry, entry))
            cfg["environment"] = new_env
        elif rewrites and isinstance(cfg.get("environment"), dict):
            # Dict-style `KEY: value` entries: rewrite keyed by KEY alone.
            # Adds the key if absent (e.g. PGOPTIONS) rather than requiring
            # it to already exist in the source service block.
            for key, new_value in rewrites.items():
                cfg["environment"][key] = new_value

        out_services[name] = cfg

        for vol in cfg.get("volumes", []):
            if ":" in vol and not vol.startswith("/"):
                vol_name = vol.split(":")[0]
                if vol_name in data.get("volumes", {}):
                    out_volumes[vol_name] = {}

    result = {"services": out_services}
    if out_volumes:
        result["volumes"] = out_volumes

    print(yaml.dump(result, sort_keys=False, default_flow_style=False))

    if config_files_needed:
        import json
        manifest_path = f"infra/proxmox/{phase}-configs-manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(config_files_needed, f, indent=2)
        print(f"# {len(config_files_needed)} config file(s) to stage -> see {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
