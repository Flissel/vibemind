# Supabase Swarm-Stack-Integration

Konfigurationen und Daten-Snapshots für die Migration von Supabase aus dem
externen `supabase`-CLI-Stack in den Vibemind-Docker-Swarm-Stack.

Plan: `~/.claude/plans/k-nnnen-wir-adative-skills-splendid-mochi.md`
(2026-05-20). Schritt-für-Schritt-Verzeichnis-Aufbau in 5 Commits.

## Verzeichnis-Layout

```
infra/swarm/supabase/
├── README.md                       — diese Datei
├── .gitignore                      — schließt temporäre Dump-Artefakte aus
├── kong.yml                        — Kong declarative config (Commit 2)
├── postgresql.custom.conf          — Postgres-Overrides (Commit 2; aktuell leer)
└── initdb/
    ├── 00-bootstrap.sql            — Roles, Schemas, Extensions, _supabase DB
    ├── 01-restore.sql              — pg_dump der `postgres` DB (Schema + Daten)
    └── 02-restore-internal.sql     — pg_dump der `_supabase` DB (Analytics)
```

## Initdb-Pipeline

Wenn `supabase-db` mit leerem Volume startet, führt Postgres alle
`*.sql`-Dateien unter `/docker-entrypoint-initdb.d/` in alphabetischer
Reihenfolge aus. Reihenfolge per Datei-Namen erzwungen:

1. **`00-bootstrap.sql`** — Extracted aus dem Original-CLI-Container-Heredoc
   (`docker inspect supabase_db_supabase --format '{{index .Args 1}}'`).
   Erzeugt: Roles (`authenticator`, `supabase_auth_admin`, `supabase_storage_admin`, …),
   pgsodium/pgvault/pg_net Extensions, `_realtime` und `supabase_functions`
   Schemas, JWT-Config-DB-Settings, `_supabase` DB-Create am Ende.
2. **`01-restore.sql`** — pg_dump der Production-`postgres` DB inklusive
   aller Tabellen, Daten, Indizes, Constraints, Triggers, Functions.
   **Achtung**: `--exclude-table-data=public.face_target_blobs` —
   FaceSwap-Bildblobs (58 MB Base64) sind ausgeschlossen, das Schema
   bleibt. Die Tabelle wird im neuen Container leer sein; FaceSwap-
   Pipeline muss neu populieren falls genutzt.
3. **`02-restore-internal.sql`** — pg_dump der `_supabase` DB (Logflare-
   Analytics-Backend). Klein (~177 kB).

## Refresh des Snapshots

Vor jedem Cutover (Commit 4) muss `01-restore.sql` aktualisiert werden,
damit zwischenzeitliche Schreibvorgänge erhalten bleiben:

```powershell
docker exec supabase_db_supabase pg_dump -U postgres -d postgres `
  -F p --clean --if-exists --no-owner --no-privileges `
  --exclude-table-data=public.face_target_blobs `
  > infra/swarm/supabase/initdb/01-restore.sql

docker exec supabase_db_supabase pg_dump -U postgres -d _supabase `
  -F p --clean --if-exists --no-owner --no-privileges `
  > infra/swarm/supabase/initdb/02-restore-internal.sql
```

## Disaster-Recovery — Restore aus Volume-Backup

Wenn der Stack mal komplett platt ist und `supabase_db` Volume verloren
geht: Backup-Volume mounten, `docker stack deploy` läuft initdb gegen
das leere Volume, lädt die committed Snapshots. Daten sind auf
Snapshot-Stand zurück (alles seit letztem Refresh verloren).

Für stündliche Snapshots empfiehlt sich ein periodisch ausgeführter
`docker exec ... pg_dump` als Cronjob/Scheduled Task — aber das ist
eine **separate** Story (vgl. `tasks/gaps.md`).

## Rollback zur CLI-Variante

Der Cutover-Pfad behält das alte CLI-Volume `supabase_db_supabase`
unverändert. Falls die Migration fehlschlägt:

```powershell
docker stack rm vibemind         # Entfernt auch die neuen Supabase-Services
cd vibemind-os/supabase
supabase start                   # Bringt das alte Volume zurück
```

Brain muss dann wieder mit dem alten Stack-File gegen
`host.docker.internal:54321` laufen (URL ist gleich, Routing ist
nahtlos).
