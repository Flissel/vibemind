# ADR-0013 — MCP als einziger externer Erweiterungsvertrag

**Status:** Vorgeschlagen · **Kategorie:** B (übernehmen und erweitern) · **Phase:** 3
**Betrifft:** Integrationen, Erweiterbarkeit, Sicherheit

---

## Goal

> Externe Fähigkeiten kommen über **einen** Vertrag nach VibeMind — MCP —
> mit Namespaces, Risikoklassifikation pro Tool, Health-Überwachung und Isolation.
> VibeMind bietet seine eigenen Fähigkeiten ebenfalls per MCP an.

**Messbar erreicht, wenn:** Ein neuer Dienst wird ohne Code-Änderung angebunden;
ein ausgefallener MCP-Server bricht keine Session; VibeMind ist von außen als
MCP-Server ansprechbar.

---

## Kontext

OpenWorkers MCP-Client (`coworker/mcp/`, ~600 LOC) löst die schwierigen Teile gut:

- **Async-Lifecycle korrekt:** Jeder Server läuft in einer **dedizierten
  asyncio-Task**, die Transport und `ClientSession` öffnet, offen hält und **in derselben
  Task** schließt — weil die anyio-Cancel-Scopes des SDK das verlangen. Kein
  `nest_asyncio`, kein zweiter Event-Loop (`mcp/client.py:1-11`). Das ist die Falle,
  in die viele MCP-Integrationen tappen.
- **Kein Browser-Hijack:** `ensure(server, interactive=False)` als Default; ein Server,
  der Re-Autorisierung verlangt, wirft `InteractiveAuthRequired`, statt ungefragt den
  Browser zu öffnen (`client.py:44-51`).
- **Konfiguration ohne Code:** `POST /v1/mcp`, mit `include_tools`/`exclude_tools`.

**Die Lücken:**

| Lücke | Beleg |
|---|---|
| Nur Tools — keine Resources, Prompts, Sampling | `client.py:130` (`list_tools` only) |
| Ein Risk-Level **pro Server**, nicht pro Tool | `mcp/tools.py:82-88` — pauschal `medium` |
| Namensabschnitt bei 64 Zeichen → Kollisionsrisiko | `mcp/tools.py:26-31` + stilles Überschreiben in `registry.py:45-46` |
| Kein Health-Check, kein Reconnect | `client.py:138-140` entfernt die Verbindung, der nächste Aufruf scheitert |
| Keine Isolation | stdio-Server ist ein Kindprozess mit vollen Nutzerrechten → kann `secrets.json` lesen |
| **Kein Server-Modus** | OpenWorker kann seine Fähigkeiten nicht anbieten |
| `/v1/mcp` ist faktisch RCE | beliebige `command`/`args`, nur durch das Sidecar-Token geschützt |

VibeMind hat bereits eigene MCP-Server (`mcp/docker/`, `tools/mcp_sync/`, laut
`STARTUP_PROFILES.md` „MCP-Server (7)") — die Federation ist die natürliche Konsequenz.

---

## Entscheidung

**Client-Muster übernehmen, um Federation, Sicherheit und Server-Modus erweitern.**

| Aspekt | Entscheidung |
|---|---|
| **Namespaces** | `mcp:<server>/<tool>`, hierarchisch. Kollision = **Fehler**. Bei Längenüberschreitung Hash statt Abschnitt ([ADR-0007](ADR-0007-tool-registry-namespaces.md)) |
| **Risk pro Tool** | Heuristik (`get_*`/`list_*`/`search_*` → READ; `create_*`/`send_*`/`delete_*` → EXTERNAL/DESTRUCTIVE) **plus** manuelle Overrides. Fallback: `EXTERNAL` (fail-closed, [ADR-0002](ADR-0002-risk-klassifikation.md)) |
| **Isolation** | Jeder stdio-Server in einem eigenen Container mit eigenem Nutzer, ohne Zugriff auf VibeMind-Secrets. HTTP-Server ohnehin extern |
| **Health + Reconnect** | Periodischer Ping, exponentielles Backoff, Circuit Breaker. Ein toter Server macht seine Tools unsichtbar, statt Aufrufe fehlschlagen zu lassen |
| **Voller Protokollumfang** | Resources (als Kontextquellen), Prompts (als Skill-Bausteine), Sampling (kontrolliert — ein MCP-Server, der Modellaufrufe anfordert, geht durch Budget und Policy) |
| **Server-Modus** ⭐ | VibeMind bietet seine Fähigkeiten per MCP an: `vibemind:plan`, `vibemind:recall`, `vibemind:approve`. Damit können Claude Code, Cursor und andere Hosts VibeMind-Fähigkeiten nutzen |
| **Registrierung absichern** | `POST /mcp/servers` ist eine `DESTRUCTIVE`-Aktion mit Genehmigungspflicht — nicht nur tokengeschützt |

---

## Begründung

- **MCP ist der Konsens des Felds.** Alle zehn verglichenen Systeme setzen darauf
  ([15.3](../15-architekturvergleich.md#153-tool-system)). Goose geht am weitesten:
  **alles** ist eine MCP-Extension, es gibt keinen eingebauten Connector-Katalog. Das ist
  die Architektur, die VibeMind anstreben sollte.
- **Es macht den Verzicht auf OpenWorkers 33 Connectoren tragbar.** Ohne MCP müsste
  VibeMind SaaS-Integrationen selbst pflegen — der Aufwand, den OpenWorker mit 4.892 LOC
  in einer Datei bezahlt ([02](../02-repositorystruktur.md#coworkerconnectors--der-problembereich)).
- **Der Async-Lifecycle ist nicht trivial** und in OpenWorker korrekt gelöst — das ist
  der wertvollste übernehmbare Teil.
- **Der Server-Modus dreht die Richtung um:** VibeMind wird von einem Konsumenten zu
  einem Anbieter von Fähigkeiten. Das ist strategisch wertvoll und in keinem
  Vergleichssystem vorhanden.

---

## Konsequenzen

**Positiv**
- Neue Integrationen ohne Code.
- Ein Sicherheitsmodell für alle externen Tools.
- Kein eigener Connector-Wartungsaufwand.
- VibeMind-Fähigkeiten von außen nutzbar.

**Negativ / Kosten**
- **MCP-Server sind Fremdcode.** Isolation ist Pflicht, nicht Kür — und sie kostet
  (Container pro Server, Startzeit, Speicher).
- **Qualität variiert stark.** Schlechte Tool-Beschreibungen führen direkt zu
  Fehlrouting — genau das Problem, das `intent_validation/00_MASTER.md` bei
  `bubble_evaluate` dokumentiert. Gegenmaßnahme: Beschreibungen dürfen lokal
  überschrieben werden.
- **Protokollreife**: Resources und Sampling sind weniger verbreitet als Tools;
  Server-Unterstützung ist uneinheitlich.
- Sampling ist ein potenzieller Kostenkanal — muss zwingend durch Budget und Policy.

**Risiko**
- **Bösartiger MCP-Server.** Wahrscheinlichkeit niedrig (kuratierte Auswahl), Wirkung
  hoch. Gegenmaßnahmen: Isolation, fail-closed-Risikoklassen, Egress-Allowlist,
  Genehmigungspflicht bei Registrierung, Audit jedes Aufrufs.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **OpenWorkers Connectoren portieren** | Verworfen: 4.892 LOC Monolith, geschlossen, 33 SaaS-APIs zu pflegen. Der Aufwand steht in keinem Verhältnis |
| **n8n für alle Integrationen** | n8n bleibt für **deterministische** Abläufe. Für ad-hoc Tool-Aufrufe eines Agenten ist es zu schwerfällig (ein Workflow pro Aktion). **Beides, klar abgegrenzt** ([ADR-0011](ADR-0011-planner-neuentwicklung.md)) |
| **Eigenes Plugin-Protokoll** | Verworfen: MCP ist etabliert, das Ökosystem existiert bereits |
| **OpenAPI-Tools statt MCP** | Gut für reine REST-APIs, aber ohne Lifecycle, ohne Resources/Prompts, ohne stdio-Server. **Als Ergänzung sinnvoll** (OpenAPI → Tool-Generator), nicht als Ersatz |
| **Keine Isolation** (OpenWorker-Status) | Verworfen: Fremdcode mit Zugriff auf Secrets ist nicht vertretbar |
