# Design-Spec: aisalesorgcore ↔ VibeMind-Stack-Integration

**Datum:** 2026-07-11 · **Status:** Design (Review offen)
**Scope:** Anbindung des externen AutoGen-Multi-Agent-Sales-Teams `Flissel/aisalesorgcore` (privat, Branch `claude/repo-overview-m3tu6h`) an reale VibeMind-Infrastruktur — CRM, Kommunikationskanäle, Recherche, persistentes Memory. Kein Umbau von `aisalesorgcore` selbst, kein Eingriff in `vibemind-stack.yml`.

**Nicht-Ziel:** Neue externe SaaS-Verträge (Clearbit/Apollo/Twilio/Calendly/ZeroBounce/Sales-Navigator-Scraper) — nur einsetzen, wo intern nichts Gleichwertiges existiert und der User es ausdrücklich will.

---

## 1. Ausgangslage (verifiziert)

`aisalesorgcore` ist ein AutoGen-Swarm-generiertes Repo: 42 Agenten, Lead `ChiefSalesOfficerAgent`, 9 unabhängig lauffähige Sub-Teams (`intel`, `qualification`, `research`, `callintel`, `outreach`, `bdr`, `content`, `workspace`, `revops`). `master`-Branch ist veraltet (nur 4 Sub-Teams) — **Basis ist der Branch `claude/repo-overview-m3tu6h`** (vollständig, dokumentiert in `ARCHITECTURE.md`, validiert via `src/validate.py`).

Von den ~24 Domain-Tools sind nur diese **echt** (mit Key): `send_email` (Resend), `send_slack_message` (Slack), `check_email_deliverability` (ZeroBounce), `search_competitors` (SerpAPI), `claude_code` (echte CLI), `score_lead` (Algorithmus, kein API-Call nötig). Alles andere — `crm_*`, `enrich_contact`, `fetch_linkedin_profile`, `analyze_intent_signals`, `query_data_warehouse`, `schedule_meeting`, `create_video_message`, `send_sms`, `analyze_call_transcript` — ist deterministischer Mock (Hash-basiert).

**Entscheidende Mechanik aus `src/main.py`** (bestimmt die ganze Integrationsform):
```python
mcp_tools = await _discover_mcp_tools()   # GET {GATEWAY}/tools/list einmal pro Prozessstart
all_tools = tools + mcp_tools             # additiv — MCP-Tools ergänzen, überschreiben NICHT
```
MCP-Gateway-Tools werden jedem der 13 Core-Agenten UND jedem der 9 Sub-Teams unabhängig hinzugefügt (jedes Sub-Team ist ein eigener `python main.py`-Subprozess, der beim Start selbst erneut `/tools/list` abfragt; Env-Vars vererben sich an den Subprozess). **Einmal Gateway konfigurieren → automatisch überall verfügbar**, ohne jede `agent.yml` einzeln anzufassen.

`docker-compose.yml` im Branch hat bereits `extra_hosts: host.docker.internal:host-gateway` — vorbereitet für genau dieses Pattern.

---

## 2. Deployment-Topologie: Docker MCP Toolkit (bestätigt, kein Umbau)

`aisalesorgcore`s eigener Code kommentiert das Gateway-Tool wörtlich als **„Call MCP tool via Docker MCP Gateway"** (`POST /tools/call`, `GET /tools/list`, Bearer-Auth) — exaktes Protokoll von Docker Desktops **MCP Toolkit** (`docker mcp gateway run`). Die CLI ist auf der Zielmaschine bereits installiert, aktuell ungenutzt — kein Konflikt mit dem bestehenden OpenFang-Hub (`:4200/mcp`, andere Konsumenten).

Bestätigt durch Schwester-Repo `aiagentorganisation-gitops`, dessen README das exakte Rezept dokumentiert:
```bash
docker mcp gateway run --port 8808 --transport sse --servers vibemind-sales-tools
# .env: MCP_GATEWAY_URL=http://host.docker.internal:8808
```

`aisalesorgcore` bleibt **standalone** (eigenes Repo/Container, kein Netzwerk-Merge mit dem Swarm-Stack). Ein neuer, selbstgebauter MCP-Server läuft auf dem Host und wird über Docker MCP Toolkit katalogisiert.

---

## 3. Neue Komponente: MCP-Server „vibemind-sales-tools"

Ein neuer, schlanker Python-Stdio-MCP-Server (Ort: `spaces/sales/mcp-tools/`, analog zu `scripts/mcp_server_rowboat_ui.py`), läuft auf dem Host, wird von Docker MCP Toolkit katalogisiert. Er ist reiner Adapter — enthält selbst möglichst wenig Fachlogik, sondern verdrahtet drei bestehende Subsysteme:

```
aisalesorgcore (Docker, standalone)
      │  MCP_GATEWAY_URL=http://host.docker.internal:8808
      ▼
Docker MCP Toolkit Gateway (Host, :8808)
      │  katalogisiert
      ▼
vibemind-sales-tools (Host, stdio MCP-Server)
      ├──► Supabase `sales.*` Schema (CRM — direktes SQL)
      ├──► OpenFang REST API :4200 (Versand + Recherche — Agent-Turns)
      └──► Rowboat-Vault + Mongo (Memory — write/read)
```

### 3.1 Tool-Katalog

| MCP-Tool | Zweck | Backend |
|---|---|---|
| `sales_crm_search` | Kontakt/Deal-Suche | Supabase `sales.*` |
| `sales_crm_create_contact` | Kontakt anlegen (Upsert auf Email) | Supabase `sales.*` |
| `sales_crm_log_activity` | Aktivität protokollieren | Supabase `sales.*` |
| `sales_crm_update_deal` | Deal/Stage/Value updaten | Supabase `sales.*` |
| `sales_send_message` | Nachricht auf beliebigem Kanal | OpenFang `channel_send` (via neuem `sales-sender`-Agent) |
| `sales_schedule_meeting` | Terminvorschlag mit `.ics` | intern: baut `.ics`, ruft `sales_send_message` (Kanal `email`) |
| `sales_research` | Firma/Person recherchieren | OpenFang `researcher-hand` (freie Suche, kein Key) |
| `rowboat_publish_person` | Kontakt ins Vault schreiben | Rowboat `People/` + Mongo |
| `rowboat_publish_organization` | Firma ins Vault schreiben | Rowboat `Organizations/` + Mongo |
| `rowboat_search_context` | Vorwissen abfragen (Read-Path) | Rowboat Chat-API `:3100` |

**Bewusst NICHT gebaut** (Begründung in Abschnitt 6): `check_email_deliverability`-Ersatz mit ZeroBounce-Güte, echtes `fetch_linkedin_profile` für Fremdprofile, `create_video_message`, `analyze_call_transcript`.

---

## 4. Supabase-Schema: neues `sales`-Schema

Das bestehende `marketing.*`-Schema (`spaces/marketing/db/001_marketing_schema.sql`) ist auf **Bulk-E-Mail-Kampagnen** ausgelegt (`accounts`/`emails`/`campaigns`/`campaign_sends`) — kein Deal/Pipeline-Stage/BANT-Konzept. Empfehlung (**Bestätigung durch User noch offen**, siehe Abschnitt 9): eigenes Schema, analog zu `marketing`s Aufbau:

```sql
CREATE SCHEMA IF NOT EXISTS sales;

CREATE TABLE sales.contacts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text UNIQUE NOT NULL,
    name          text,
    company       text,
    title         text,
    phone         text,
    linkedin_url  text,
    icp_score     integer,
    icp_breakdown jsonb DEFAULT '{}'::jsonb,
    bant_stage    text,                       -- 'raw'|'mql'|'sal'|'sql'
    source        text DEFAULT 'aisalesorgcore',
    created_at    timestamptz DEFAULT now(),
    updated_at    timestamptz DEFAULT now()
);

CREATE TABLE sales.deals (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id    uuid REFERENCES sales.contacts(id) ON DELETE CASCADE,
    stage         text DEFAULT 'raw',
    value         numeric DEFAULT 0,
    notes         text,
    created_at    timestamptz DEFAULT now(),
    updated_at    timestamptz DEFAULT now()
);

CREATE TABLE sales.activities (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id    uuid REFERENCES sales.contacts(id) ON DELETE CASCADE,
    activity_type text NOT NULL,               -- 'email'|'whatsapp'|'call'|'meeting'
    notes         text,
    created_at    timestamptz DEFAULT now()
);
```

FK-losen Bezug zu `marketing.emails` bewusst vermieden (getrennte Konzepte) — Verknüpfung nur informell über die `email`-Spalte, falls ein Sales-Kontakt später auch in eine Marketing-Kampagne wandert.

---

## 5. Kommunikation: OpenFang `channel_send` statt Einzellösungen

**Verifiziert:** `vibemind-os/openfang/crates/openfang-channels/` enthält 41 echte Channel-Adapter (WhatsApp, Email, Slack, Telegram, Discord, ...) mit realen `async fn send()`-Implementierungen gegen die jeweiligen Provider-APIs. Zusammengeführt über das Runtime-Tool **`channel_send`** (`openfang-runtime/src/tool_runner.rs:1042`), Signatur `{channel, recipient, subject?, message?, image_url?, file_url?, ...}` — dispatcht an den echten, in `~/.openfang/config.toml` konfigurierten Adapter.

Kein generischer REST-Endpoint dafür — nur als Agent-Tool aufrufbar (`POST /api/agents/{id}/message`). VibeMind hat dafür bereits das Muster etabliert: `marketing-sender`-Agent (`vibemind-os/openfang/agents/marketing-sender/agent.toml`) — ein enger, deterministischer (temperature=0) Agent, dessen **einziges** Tool `channel_send` ist.

**→ Neuer Agent `sales-sender`** (gleiches Muster, eigener Namespace, damit Marketing- und Sales-Versand getrennt bleiben und getrennt auditierbar sind). `vibemind-sales-tools`' `sales_send_message` ruft `POST /api/agents/sales-sender/message`.

Das ersetzt zwei ursprünglich geplante Einzellösungen ersatzlos:
- Kein eigenes SMTP-Modul gegen Mailcow nötig (der bestehende `_send_paranoid.py`-Stack ist ohnehin hart auf `@vibemind.space` gesperrt und für Sales-Prospects ungeeignet — `channel_send`s Email-Adapter hat diese Einschränkung nicht).
- Kein `docker exec ... openclaw agent --channel whatsapp` nötig — WhatsApp läuft über denselben `channel_send`-Adapter, sofern in `config.toml` konfiguriert.

**Voraussetzung:** Email- und WhatsApp-Adapter müssen in `~/.openfang/config.toml` mit echten Credentials hinterlegt sein (heute ungeklärt, ob das für WhatsApp bereits der Fall ist — openclaw hat eine laufende QR-Session, aber das ist ein separates System von OpenFangs eigenem WhatsApp-Adapter; **muss vor Implementierung geprüft werden**, siehe Abschnitt 9).

**`sales_schedule_meeting`** baut eine `.ics`-Datei und ruft intern `sales_send_message(channel="email", ...)` mit Anhang — kein Calendly/Cal.com nötig, aber auch keine echte Verfügbarkeitsprüfung (reiner Terminvorschlag per Mail).

---

## 6. Recherche: OpenFang `researcher-hand` statt bezahlter Enrichment-APIs

**Verifiziert:** `researcher-hand` (`vibemind-os/openfang/crates/openfang-hands/bundled/researcher/HAND.toml`) ist ein echter, beliebig promptbarer Agent (`web_fetch`, `web_search`, kein Login/Browser-Klicken). `web_search` kaskadiert Tavily → Brave → Perplexity → **DuckDuckGo HTML (kostenlos, kein Key)** — funktioniert also auch ganz ohne bezahlte Keys. Aufruf: `GET /api/hands` (agent_id auflösen) → `POST /api/agents/{id}/message` mit frei formuliertem Rechercheauftrag, synchron mit langem Timeout (Hand-Loop: `max_iterations=25`).

**`sales_research(company_or_person, question)`** nutzt das für: `enrich_contact` (Firmografika), `analyze_intent_signals` (Kaufsignale), `search_competitors` (ersetzt SerpAPI-Bedarf ersatzlos — kostenlos über denselben Kanal).

**Bewusst limitiert:** LinkedIn-Profile/Sales-Navigator bleiben außen vor — JS-lastige/Login-gated Seiten scheitern laut Hand-Prompt selbst (CAPTCHA). Für `fetch_linkedin_profile` bleibt daher **Mock** (kein 3rd-Party-Scraper, der gegen LinkedIns ToS verstößt). Die vom User erwähnte eigene OAuth-Anbindung deckt nur das **eigene** Profil/Netzwerk ab (LinkedIn-API-Policy) — als kleines Zusatz-Tool `linkedin_check_own_network` (v1.5, kein Blocker) denkbar, aber kein Ersatz für Prospect-Lookups.

Die früher erwogene „Vector-DB mit Personas" existiert **nicht** (verifiziert, keine Qdrant-Collection dieser Art im Repo) — kein Enrichment-Baustein darauf.

---

## 7. Rowboat: persistentes Cross-Run-Memory

AutoGen-Swarm-Runs sind zustandslos — nach `docker compose run` ist alles Wissen weg außer den Dateien in `output/`. Rowboat-Vault (`~/.rowboat/knowledge/`) hat bereits `People/`, `Organizations/`, `Projects/` — **`People`/`Organizations` werden vom bestehenden Cleanup (`cleanup_orphaned_project_dirs`) nie gescannt**, also sicher vor versehentlichem Löschen durch den Bubble-Sync-Mechanismus.

- **Write-Path** (nach jedem Lead-Run): `rowboat_publish_person`/`rowboat_publish_organization` schreiben Markdown-Datei + Mongo-`sources`-Eintrag (rag-worker embedded automatisch) — Implementierung reuse von `vibemind-os/voice/python/publishing/rowboat_mongo_publisher.py`'s Pattern (Schema-Semaphore + Filesystem-Fallback).
- **Read-Path** (vor Kickoff): `rowboat_search_context("Acme Corp")` — HTTP `POST :3100/api/v1/{projectId}/chat` (gleiches Pattern wie `spaces/marketing/tools/rowboat_client.py`) — gibt vorhandenes Wissen über Firma/Person zurück, bevor der CSO-Agent startet.
- **Nicht in Rowboat:** keine sensiblen Rohdaten (Telefonnummern etc.) unstrukturiert reinschreiben — nur das, was ohnehin für Sales-Zusammenarbeit sinnvoll ist (Firmenkontext, Gesprächsnotizen), analog zur bestehenden Regel „sensible Daten nicht in Rowboat-KB".

---

## 8. `aisalesorgcore`-seitige Anpassungen

Keine Patches an `tools.py` (bleibt 1:1 upstream-pullbar). Zwei kleine, textuelle Diffs:

1. **`.env`**: `MCP_GATEWAY_URL=http://host.docker.internal:8808` (+ ggf. `MCP_GATEWAY_AUTH_TOKEN`).
2. **System-Message-Zusatz** (ein Absatz) in `ChiefSalesOfficerAgent`, `QualificationManager`, `SystemsAndDataManager`, `DataWarehouseLead`, `ChannelOutreachManager`: *„Tools mit Prefix `mcp_sales_`/`mcp_rowboat_` sind echte Integrationen — IMMER bevorzugen gegenüber `crm_*`/`enrich_contact`/`query_data_warehouse`, die nur lokale Simulations-Fallbacks sind."*

Kein Fork nötig — Diff bleibt klein genug, um bei Upstream-Updates manuell neu anzuwenden.

---

## 9. Offene Entscheidungen für den User

1. **Supabase-Schema-Name bestätigen** — Vorschlag `sales` (Abschnitt 4) vs. Erweiterung von `marketing.*`. Bisher zweimal nicht direkt beantwortet.
2. **OpenFang `config.toml`**: Sind Email- und WhatsApp-Adapter dort schon mit echten Credentials hinterlegt, oder muss das vor Implementierung nachgezogen werden? (Unklar aus der Recherche — openclaws WhatsApp-Session ist ein separates System.)
3. **Docker Desktop aktuell nicht gestartet** — muss vor dem ersten Test laufen (`docker mcp gateway run ...`).
4. Reihenfolge der v1.5-Erweiterungen (Video-Message-Pipeline, Call-Transcript-Read, LinkedIn-Own-Network) — später, kein Blocker für v1.

---

## 10. Scope

**v1 (dieser Spec):** Supabase `sales.*` CRM · `sales-sender`-Agent (Email+WhatsApp via `channel_send`) · `sales_schedule_meeting` (.ics) · `sales_research` (researcher-hand) · Rowboat-Write/Read-Path.

**v1.5 (später, kein Blocker):** Video-Message über `spaces/video`-Pipeline · `analyze_call_transcript` gegen SQLite `conversation_history` · `linkedin_check_own_network`.

**Entfällt (bewusst kein Aufwand):** Instagram-Versand (laut eigener Marketing-Spec verworfen, 40h+ für DIY-Bot), Persona-Vector-Suche (existiert nicht), `fetch_linkedin_profile` für Fremdprofile (ToS-Risiko), ZeroBounce-Qualität bei Deliverability (leichter MX-Check als Kompromiss).

---

## 11. Testplan

1. `python src/validate.py` in `aisalesorgcore` (unverändert, da `domain_tools:`-Listen nicht angefasst werden).
2. Manueller End-to-End-Lauf: `docker compose run --rm app python main.py "Neuer Lead: <Testperson>"` → prüfen: Zeile in `sales.contacts` erscheint, Markdown-Datei in `~/.rowboat/knowledge/People/` erscheint, `sales-sender` verschickt eine echte Test-Mail/WhatsApp (mit expliziter Freigabe, kein automatischer Versand an echte Fremdadressen ohne Test-Flag).
3. Gateway-Ausfall-Test: `MCP_GATEWAY_URL` absichtlich falsch setzen → Agenten müssen auf Mock-Verhalten zurückfallen (bestehendes `[WARN] Tool '...' not in tools.py` bzw. Timeout-Handling), dürfen nicht crashen.
