# 12 — Erweiterbarkeit

Bewertet wird jeweils: **Aufwand · notwendige Code-Änderungen · ob es ohne Fork geht.**

---

## 12.1 Neues Modell

**Aufwand: XS bis S. Ohne Fork: ja (für vorhandene Provider).**

Drei Fälle:

| Fall | Aufwand | Weg |
|---|---|---|
| Neues Modell bei vorhandenem Provider | **XS** | UI: „Add model" → String eintragen (`manager.add_model`). README: „Adding any model string works at your own risk." |
| Modell mit anderen Fähigkeiten (Vision/PDF) | **XS** | Eintrag in `providers/capabilities.py` / `matrix.py` |
| **Neuer Provider** | **S** | `ProviderClient`-Subklasse + `ProviderDescriptor` in `providers/registry.py` + Logo in der GUI |

Der `ProviderRouter` braucht **keine** Änderung — er dispatcht generisch über
`get_descriptor(prefix)` (`router.py:48-56`). Das ist gut gebaut: Die letzten
Commits der Historie (`Add AWS Bedrock provider`, `Add Google Vertex AI provider`,
`Add OpenRouter…`, `Add Meta Model API provider`) zeigen, dass der Pfad in der Praxis
funktioniert.

**Grenzen:**
- Ollama-Modelle werden per Prozess-Probing entdeckt (`manager._ollama_models`), nicht
  über ein generisches Discovery-Interface. Ein zweiter lokaler Runner (vLLM, LM Studio)
  bräuchte eigenen Code.
- Kein Modell-Routing nach Aufgabe (billig für Routine, teuer für Planung). Ein Modell
  pro Session, umschaltbar — aber nicht automatisch.

**Note: A-.**

---

## 12.2 Neuer Agent / neue Persona

**Aufwand: XS (Markdown) bis S (Code). Ohne Fork: ja.**

Eine Persona ist eine **Markdown-Datei mit YAML-Frontmatter**
(`personas/manifest.py`):

```yaml
---
id: research-analyst
name: Research Analyst
family: knowledge            # code | knowledge
tools: [files, search, shell, todo]     # Capability-IDs aus catalog.py
messaging: true
connectors: true
default_permission_mode: interactive
recommended_models: [...]
skills: [...]
mcp: [...]
recommends:
  - {kind: connector, ref: notion, reason: "…", tier: core}
---
<Markdown-Body = Systemprompt>
```

Installierbar über `POST /v1/personas/install` bzw. die Galerie
(`/v1/cloud/gallery`). Strikte Validierung: ungültige Manifeste werfen
`ManifestError` statt still zu degradieren (`manifest.py:5-6`) — für Fremd-Personas
genau richtig.

**Das ist ein sehr gutes Erweiterungsmodell** und für VibeMind direkt adaptierbar
([ADR-0009](adr/ADR-0009-skill-persona-format.md)).

**Grenzen:**
- `tools:` referenziert nur **kuratierte Capability-IDs** — eine Persona kann keine
  neuen Tools mitbringen (nur MCP-Server empfehlen).
- Personas sind **Session-Surfaces**, nicht komponierbare Rollen. Zwei Personas können
  nicht zusammenarbeiten.
- **Der Kern-Vorbehalt:** Persona-Installation ist Ausführung fremder Prompts mit dem
  vollen Toolset ihrer Familie. Es gibt einen Consent-Screen (über `Capability.risk`),
  aber `Skill.allowed_tools` wird **nicht durchgesetzt**
  ([08 R-07](08-security-risikoanalyse.md#r-07)).

**Note: A- (Modell) / C (Sicherheit der Drittinstallation).**

---

## 12.3 Neuer Connector

**Aufwand: L. Ohne Fork: NEIN.**

Erforderlich:

1. `ConnectorDescriptor` in `descriptors.py` (Auth-Methode, Felder, Anleitung, `validate`)
2. n × `ConnectorToolDef` in `tool_defs.py` (Name, Label, `kind`, `target_arg`)
3. Implementierung in `integration_tools.py` (der 4.892-LOC-Monolith)
4. ggf. Adapter für eingehende Nachrichten (`connectors/adapters.py`)
5. ggf. Eintrag in `cloud.PROVIDER_FOR_CONNECTOR` für Managed OAuth
6. GUI: Icon, Visuals, ggf. eigene Detail-Komponente
7. Tests

**Und das geht nur upstream.** Der Katalog ist explizit geschlossen
(`catalog.py:11-13`), es gibt keinen Plugin-Loader, keinen Entry-Point-Mechanismus,
kein dynamisches Laden. Die README bestätigt die Haltung: „we may not approve PRs that
add features that are already under-development or deviates from our vision."

**Bewertung:** Als *Sicherheitsmodell* (Kuratierung statt offener Marktplatz)
verteidigbar. Als *Erweiterbarkeit* das schlechteste Ergebnis im Repo.

**Note: D.**

---

## 12.4 Neuer MCP-Server

**Aufwand: XS. Ohne Fork: ja. Ohne Code: ja.**

```
POST /v1/mcp  {name, transport: "stdio"|"http", command|url, args, env, headers,
               include_tools, exclude_tools, requires_approval}
```

Oder über die UI. Tools erscheinen sofort als `mcp__<server>__<tool>`.
OAuth für HTTP-Server wird unterstützt (`mcp/oauth.py`), mit dem korrekten
Nicht-Hijack-Default ([08](08-security-risikoanalyse.md#e-mcp-oauth-ohne-browser-hijack)).
`include_tools`/`exclude_tools` erlauben Feingranularität pro Server.

**Das ist der Erweiterungspfad des Systems** — und der Grund, warum der geschlossene
Connector-Katalog überhaupt vertretbar ist.

**Grenzen:**
- Nur Tools (keine Resources/Prompts/Sampling).
- Ein Risk-Level pro Server statt pro Tool.
- Namenskollision bei >64-Zeichen-Namen möglich, mit stillem Überschreiben
  ([04](04-tool-system.md#41-registrierung-eine-flache-map-drei-wege-hinein)).
- Kein Health-Monitoring, kein Auto-Reconnect.
- **Keine MCP-Federation** — kein Server-of-Servers, keine Namespace-Hierarchie,
  keine geteilten MCP-Registries.
- **OpenWorker ist kein MCP-Server** — es kann seine Fähigkeiten nicht anbieten.
  Für VibeMind, das MCP als Integrationsschicht nutzt, wäre genau das interessant
  gewesen.

**Note: A- (Client) / — (Server: existiert nicht).**

---

## 12.5 Neuer Speicher (Memory-Backend)

**Aufwand: S für einen gleichwertigen Store, L für Semantik. Ohne Fork: nein.**

`MemoryStore`-ABC (`memory/base.py:33-61`) ist da, aber:
- er wird **nicht** konfigurierbar ausgewählt — `manager` instanziiert
  `SQLiteMemoryStore` direkt,
- der Vertrag hat kein `search()` ([06](06-memory.md#63-der-memorystore-vertrag)),
- der Abrufpfad im Prompt-Builder ist hart auf `list()` verdrahtet (`agent.py:255-260`).

Ein Qdrant-Backend braucht also: Vertragserweiterung + Änderung im Prompt-Builder +
Konfigurationspfad. Das ist ein Fork.

**Note: C.**

---

## 12.6 Neue UI / neue Surface

**Aufwand: M (Client gegen die API) bis XL (echte zweite Surface).**

**Was leicht ist:** Die API ist vollständig und gut dokumentiert durch den Code —
REST + WS + sogar ein OpenAI-kompatibles `/v1/chat/completions`
(`app.py:651`). Ein eigener Client (CLI, Mobile, IDE-Plugin) kann direkt andocken.
Der Beweis: Es gibt bereits **vier** Surfaces (GUI, TUI, CLI, Messaging-Gateway).

**Was schwer ist:** Es gibt **keine** geteilte Client-Logikschicht. `api.ts` ist
TypeScript-spezifisch, `App.tsx` ist nicht wiederverwendbar. Eine zweite grafische
Surface schreibt die gesamte Zustandslogik neu.

**Was fehlt:** Kein Webhook-/Callback-Mechanismus für externe Systeme, keine
Server-Sent-Events als WS-Alternative, keine offene OpenAPI-Spezifikation als Artefakt
(FastAPI generiert sie zur Laufzeit, sie wird aber nicht veröffentlicht/versioniert).

**Note: B.**

---

## 12.7 Weitere Erweiterungsachsen

| Achse | Aufwand | Ohne Fork? |
|---|---|---|
| Neue **Risikoklasse** | S | nein |
| Neuer **Permission-Mode** | S | nein |
| Neuer **Executor** (Container/VM) | M — ABC existiert, Implementierung fehlt | nein |
| Neuer **Prompt-Typ** (5. Inbox-Kind) | M — Engine + Inbox + WS + GUI | nein |
| Neue **Capability** im Katalog | S | nein (bewusst) |
| Neuer **Skill** | **XS** — Ordner mit `SKILL.md` | **ja** |
| Neuer **Automation-Trigger** (event-basiert statt cron) | M — `Schedule` kennt nur `cron`/`once` | nein |
| Neue **Sprache** für STT | L — anderes Modell, andere Konstanten | nein |
| **Tool-Streaming** | M — neuer Event-Typ durch alle Schichten | nein |

---

## 12.8 Gesamtbild

```
   Erweiterbarkeit
   hoch │  MCP-Server ●        ● Skills
        │  Modelle ●    ● Personas
        │
        │              ● Surfaces/Clients
        │
        │        ● Memory-Backend    ● Executor
        │
   nied.│  ● Connectoren   ● Risikoklassen/Modi   ● Capabilities
        └────────────────────────────────────────────────────
          ohne Fork                             nur mit Fork
```

**Das Muster ist klar und konsistent:** OpenWorker ist **nach außen offen**
(MCP, Skills, Personas, Modelle, Clients) und **nach innen geschlossen**
(Connectoren, Capabilities, Risikomodell, Runtime).

Das ist eine **verteidigbare Produktstrategie** für ein kuratiertes Endanwenderprodukt:
Die Sicherheitsgarantien beruhen darauf, dass der Kern kontrolliert bleibt, und Breite
kommt über einen Kanal (MCP), dessen Risiko der User bewusst eingeht.

**Für VibeMind ist genau diese Strategie unpassend.** VibeMind *ist* das Innere —
Brain, OpenFang, OpenClaw, Automation_ui, n8n, 446 Intents über 19 Kategorien. Was
VibeMind braucht, ist die umgekehrte Offenheit: **erweiterbarer Kern, kuratierte
Außenkanten.**

Konkret heißt das für die Übernahme:

| Übernehmen | Weil |
|---|---|
| Persona-/Skill-Format (Markdown + YAML) | Beste Erweiterungsachse des Repos |
| MCP-Client-Anbindung als Datenkonfiguration | Kein Code für neue Server |
| Provider-Descriptor-Muster | Neuer Provider = eine Klasse + ein Descriptor |
| Capability-Bündel mit `requires`/`risk` | Gute Zwischenschicht zwischen Persona und Tools |

| Nicht übernehmen | Weil |
|---|---|
| Geschlossener Katalog | VibeMind braucht interne Erweiterbarkeit |
| Flache Registry ohne Namespaces | Skaliert nicht auf VibeMind-Größe |
| Fest verdrahtete Store-Auswahl | VibeMind nutzt Qdrant/Supabase/Redis parallel |

---

**Weiter:** [13 — Vergleich mit VibeMind](13-vergleich-vibemind.md)
