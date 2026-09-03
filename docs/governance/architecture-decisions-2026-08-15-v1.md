# V1 Architekturentscheidungen — 2026-08-15 (Entscheidungsrunde 2, Block n8n)

**Status:** entschieden, umsetzungspendent
**Referenz:** `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-15T11:38:00Z`
**Anlass:** Das Cockpit `cockpit-n8n` hat seinen Repo-first-Audit am 2026-08-14 abgeschlossen und drei Gates an den User eskaliert (Queue Abschnitt 3.1d, User-Entscheidungsrunde 2). Dieses Dokument setzt die E-Nummerierung aus `architecture-decisions-2026-08-13-v1.md` fort (dort E1–E5) und hält den n8n-Block als E6–E8 fest.

Dieses Dokument ändert selbst **keinen** Vertrag und keine Laufzeit: Registry-, Katalog-, Compose- und Routing-Änderungen erfolgen ausschließlich in den abgeleiteten, separat geprüften Tasks. Bis zu deren Merge gilt der dokumentierte Ist-Zustand.

## Ausgangslage (Orchestrator-Evidence, repo-first vor der Vorlage erhoben)

| Befund | Beleg |
|---|---|
| Port `15678:5678` ist **ohne IP-Präfix** veröffentlicht, bindet also alle Interfaces | `infra/swarm/vibemind-stack.yml:666`, `infra/proxmox/phase2a-docker-compose.yml:78` |
| Alle bekannten Nutzer greifen über die Loopback-Adresse zu | `spaces/marketing/docs/GO_LIVE.md:46-48`, `:52`, `spaces/marketing/db/038_channel_aware_webhook_routing.sql:122` |
| Der Webhook-Worker läuft auf dem Windows-Host außerhalb des Docker-Netzes und braucht deshalb einen host-veröffentlichten Port | `spaces/marketing/docs/GO_LIVE.md:52` |
| `docs/SPACES.md` deklariert n8n als aktiven Space mit Agent `brain-n8n`, Prefix `n8n.`, acht Events und einem `space-n8n` Swarm-Profil | `docs/SPACES.md:29`, `:157-173` |
| Ein Verzeichnis `spaces/n8n` existiert **weder** im Superproject **noch** in `vibemind-os` (dort liegen zwölf andere Spaces) | Verzeichnis-Listing beider Repos |
| Die Registry bindet die acht `n8n.*`-Events **direkt auf MCP-Tools** (`n8n_generate_workflow`, `n8n_list_workflows`, `n8n_health_check`, `n8n_update_partial_workflow`, `n8n_delete_workflow`, `n8n_test_workflow`, `n8n_get_workflow`) mit `mcp_servers: [vibemind-db, n8n]` | `vibemind-os/config/space_agent_registry.yml:241-259` |
| Marketing ruft n8n direkt über HTTP an — drei aktive Webhook-Subscriptions, per DB-Migration geschriebene URLs, eigener API-Key | `spaces/marketing/docs/GO_LIVE.md:42-48`, `spaces/marketing/db/038_channel_aware_webhook_routing.sql:17`, `infra/swarm/profiles/marketing-mailcow.md:392` |

## E6 — Port-Bindung: Loopback

**Frage:** Soll Port 15678 aus dem Netz erreichbar sein?

**Entscheidung (User):** Die Veröffentlichung wird auf die Loopback-Adresse eingeschränkt (`127.0.0.1:15678:5678`).

**Begründung:** Der Port ist heute faktisch netzweit offen, obwohl kein bekannter Nutzer ihn so braucht — Marketing-Webhooks, OAuth-Redirects und die Health-Probe adressieren durchweg `127.0.0.1`. Die Loopback-Bindung entfernt die Angriffsfläche, ohne einen einzigen belegten Konsumenten zu brechen; insbesondere bleibt der host-basierte Webhook-Worker funktionsfähig, weil der Port weiterhin auf dem Host veröffentlicht wird.

**Auflage:** Die Repository-Änderung an den Compose-Dateien ist Gegenstand des abgeleiteten Tasks. Das **Anwenden** (Redeploy/Neustart auf dem Proxmox-Host) bleibt eine Live-Aktion des Users und ist von dieser Entscheidung **nicht** gedeckt. Vor dem Redeploy ist zu prüfen, ob ein Konsument außerhalb des Hosts existiert, der bisher unbemerkt über die offene Bindung zugreift.

## E7 — Space-Status: MCP-only, Deklaration korrigieren

**Frage:** `docs/SPACES.md` deklariert einen n8n-Space, es gibt aber keinen Space-Code. In welche Richtung wird die Diskrepanz aufgelöst?

**Entscheidung (User):** **MCP-only** — die Deklaration wird an die Realität angeglichen, nicht umgekehrt.

**Präzisierung durch den Registry-Befund:** Die Auflösung ist enger, als die Frage vermuten ließ. Die acht `n8n.*`-Events sind in `space_agent_registry.yml` bereits **direkt auf MCP-Tools gebunden**; es existiert keine Zwischenschicht, die fehlen würde. n8n ist damit strukturell schon heute eine registry-geroutete Werkzeug-Oberfläche ohne eigene Applikation. Die Korrektur betrifft folglich **nicht** die acht Events — die bleiben die kanonische Oberfläche —, sondern die Behauptungen in `docs/SPACES.md`, es gebe einen eigenen Space mit eigener Applikation und einem `space-n8n` Swarm-Profil. Der abgeleitete Task stellt fest und dokumentiert: n8n hat **keine eigene Space-Applikation, keine eigene Datenhoheit und kein eigenes Space-Verzeichnis**; Integrationscode und Compose-Definitionen gehören der `voice`-Komponente.

**Konsequenz:** Kein Restore-Aufwand, keine Event-Entfernung, keine Breaking-Contract-Änderung. Der Task ist Dokumentations- und Katalogpflege mit Testabgleich.

## E8 — Marketing-Grenze: über den kanonischen n8n-Pfad

**Frage:** Marketing greift direkt auf n8n zu, am deklarierten n8n-Pfad vorbei. Dokumentieren, technisch trennen oder umleiten?

**Entscheidung (User):** **Umleiten** — Marketing-Zugriffe auf n8n laufen künftig über den kanonischen n8n-Pfad statt über direkte HTTP-Aufrufe.

**Auflösung der scheinbaren Spannung zu E7:** Beide Entscheidungen zusammen ergeben nur dann Sinn, wenn „über den n8n-Space routen" den **Registry-Event-Pfad** meint, nicht eine wiederherzustellende Space-Applikation. Genau so liest der Orchestrator sie: Marketing ruft n8n nicht mehr direkt per HTTP an, sondern geht `Brain → OpenFang → brain-n8n-Events → n8n-MCP`. E7 entfernt die Fiktion einer eigenen Applikation; E8 macht die verbleibende, registry-definierte Oberfläche zum verbindlichen Zugangsweg. Sollte diese Lesart nicht der Absicht entsprechen, ist E8 vor Umsetzungsbeginn zu korrigieren — bis dahin gilt sie.

**Verbindliche Stufung:** Die Umleitung berührt drei aktive Webhook-Ketten, eine DB-Migration mit hinterlegten URLs und einen eigenen API-Key. Sie wird deshalb **zweistufig** umgesetzt:

1. **Stufe 1 (Routine, `code`):** Vollständiges Inventar aller direkten n8n-Zugriffe aus Marketing (Webhook-Subscriptions, DB-Einträge, API-Key-Nutzung, OAuth-Redirects), Abbildung jedes einzelnen auf das entsprechende `n8n.*`-Event beziehungsweise Feststellung, wo kein Event existiert, plus Migrationsplan mit Reihenfolge und Rückfallweg. Keine Verhaltensänderung.
2. **Stufe 2 (user-gated):** Die eigentliche Umstellung. Sie berührt Secrets und laufende Automationen und braucht eine eigene, request-spezifische Freigabe — insbesondere, weil Marketing-Flows bis zum Abschluss der Migration brechen können.

**Ungeklärt und explizit offen:** Die Webhook-Richtung ist keine Ausgabe, sondern ein **Eingang** — n8n ruft Marketing-Workflows auf, nicht umgekehrt. Ob und wie eingehende Trigger über den kanonischen Pfad laufen sollen, ist von den acht Events nicht abgedeckt und wird in Stufe 1 als Befund vorgelegt, nicht eigenmächtig entschieden.

## Abgeleitete Tasks

| Task | Entscheidung | Parent-Cockpit | Risiko | Stufe |
|---|---|---|---|---|
| `task-deployment-0017-n8n-loopback-binding-v1` | E6 | `cockpit-n8n` | `deployment` (Compose-Konfiguration; Redeploy bleibt User-Aktion) | 9 |
| `task-n8n-0001-space-declaration-correction-v1` | E7 | `cockpit-n8n` | `code` (Doku, Katalog, Tests) | 2 |
| `task-marketing-0001-n8n-access-inventory-v1` | E8 Stufe 1 | `cockpit-marketing` | `code` (Inventar und Migrationsplan, keine Verhaltensänderung) | 2 |
| E8 Stufe 2 (Umstellung) | E8 | `cockpit-marketing` | user-gated: Secrets plus laufende Automationen | offen |

Die ersten drei Tasks admittiert der Orchestrator; E6 stützt sich dabei auf die oben referenzierte User-Entscheidung als request-spezifische Autorität für die Repository-Änderung, nicht für das Deployment selbst. E8 Stufe 2 entsteht erst nach Vorlage des Inventars.
