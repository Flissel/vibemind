# 07 — Desktop Automation

---

## 7.1 Was existiert

Trotz der Selbstbeschreibung „lives on your desktop" und „works across your desktop"
(README:9, :28) gibt es in OpenWorker **keine** Desktop-Automation im Sinne von
Bildschirmsteuerung. Es gibt drei Dinge:

| Ebene | Umfang | Datei |
|---|---|---|
| **Dateisystem** | Lesen/Schreiben, pfad-gescoped auf Roots | `tools/files.py`, aisuite-Toolkit |
| **Shell** | Persistente bash/PowerShell mit vollen User-Rechten | `tools/shell.py` |
| **Browser** | 11 Playwright-Tools, sichtbares Chromium | `connectors/browser_automation.py` |

**Was fehlt:** Maus, Tastatur, Screenshot des *Desktops* (nur der Browserseite),
Fensterverwaltung, Accessibility-Baum, OCR, native App-Steuerung, Zwischenablage,
Koordinaten-Klicks.

Die Shell ist die einzige „Desktop"-Fähigkeit — und über sie kann man natürlich alles
tun (`osascript`, `powershell`, `xdotool`), aber ohne Wahrnehmung: der Agent sieht
nicht, was auf dem Bildschirm passiert.

---

## 7.2 Die Browser-Tools im Detail

`connectors/browser_automation.py` (577 LOC), 11 Tools:

| Tool | Art | Approval |
|---|---|---|
| `browser_open_url` | Navigation | ✅ |
| `browser_snapshot` | Wahrnehmung — Text + Controls + Selector-Hinweise | ✅ (laut Schema; siehe §36-Anmerkung) |
| `browser_get_text` | Wahrnehmung — nur Text | ✅ |
| `browser_click`, `browser_type`, `browser_select` | Aktion | ✅ |
| `browser_upload_file` | Aktion | ✅ |
| `browser_wait` | Steuerung | ✅ |
| `browser_screenshot` | Wahrnehmung (Datei) | ✅ |
| `browser_close` | Lifecycle | ✅ |
| `browser_read_url` | Statisches Fetch (kein Browser) | read |

### Der Wahrnehmungsmechanismus

`_SNAPSHOT_JS` (`browser_automation.py:270-311`) — ein injiziertes Skript, das:
- alle sichtbaren `a, button, input, textarea, select, [role=button], [contenteditable]`
  sammelt (max. 120),
- pro Element `tag, type, id, name, role, aria-label, label, placeholder, text (200 Zeichen),
  href` **und einen `selectorHint`** liefert,
- plus `document.body.innerText` (gekappt).

Der `selectorHint` ist die eigentliche Idee: `#id` wenn vorhanden, sonst `[name="…"]`.
Der Agent bekommt also nicht nur „was steht da", sondern „**wie klicke ich es an**".

Der Locator (`_target_locator`, `:245-256`) akzeptiert drei Formen mit Fallback:
`text=…` → `get_by_text`, `role=button:Name` → `get_by_role`, sonst CSS-Selector,
und bei Fehlschlag Textsuche. Pragmatisch und robust.

**Das ist ein DOM-basierter Ansatz — kein Vision-Ansatz.** Das ist die zentrale
Designentscheidung und sie ist für *Web*-Automation die richtige: DOM ist billiger,
deterministischer und zuverlässiger als Pixel. Aber sie schließt alles Nicht-Web aus.

### Die drei Defekte

**(1) Modul-Singleton.** `_BROWSER = _BrowserController()` (`:223`) — **eine**
Browser-Instanz für den gesamten Prozess. Alle Sessions teilen sich Seite, Cookies,
Login-Zustand. Zwei parallele Cowork-Sessions, die beide browsen, kollidieren.
Serialisiert über `ThreadPoolExecutor(max_workers=1)` (`:70-72`) — das verhindert
Korruption, macht Sessions aber gegenseitig blockierend. **Architekturfehler.**

**(2) `headless=False`, fest verdrahtet** (`:125`). Der Browser springt sichtbar auf.
Für ein „Cowork"-Erlebnis gewollt, für unbeaufsichtigte Automations störend — und es
gibt keinen Schalter.

**(3) Kein Persistent-Context.** `new_context()` ohne `storage_state` — jede
Browser-Session startet ohne Cookies. Der Agent muss sich bei jedem Neustart neu
einloggen (oder es geht gar nicht, weil MFA).

**(4) Widersprüchliche Approval-Semantik.** Alle Tools werden mit `approval=True`
aufgerufen, aber `_attach()` (`:50-59`) überschreibt das:
`approval = approval_for_tool(name, default=approval)` — mit dem Kommentar
„§36: the tool registry's read/write kind wins for registered tools — reads never gate".
Da `browser_snapshot`/`browser_get_text` in `tool_defs.py` als `kind="read"` deklariert
sind, laufen sie **ohne** Approval. Das ist konsistent gedacht, aber der Code liest sich
gegenteilig, und die Begründung (§36) ist im Repo **nicht auffindbar**.

---

## 7.3 Vergleich

| | **OpenWorker** | **Playwright (roh)** | **Claude Computer Use** | **OpenInterpreter** | **OpenHands** |
|---|---|---|---|---|---|
| **Wahrnehmung** | DOM-Snapshot + Controls + Selector-Hints | DOM/Accessibility, voller Zugriff | **Screenshots** (Vision) | Screenshot + OCR (`os`-Modus) | Browser-DOM + Terminal + Editor |
| **Reichweite** | Nur Browser | Nur Browser | **Ganzer Desktop** | Ganzer Desktop | Browser + Shell + Code |
| **Aktionen** | click/type/select/upload/wait | alles | Maus (Koordinaten), Tastatur, Screenshot | Maus, Tastatur, Code-Ausführung | Bash, Editor, Browser |
| **Isolation** | ❌ keine (User-Prozess) | — (Bibliothek) | ⚠️ VM/Container empfohlen | ❌ standardmäßig keine | ✅ **Docker-Sandbox by default** |
| **Zuverlässigkeit** | Hoch für Web (Selektoren) | Höchste | Mittel (Vision, Koordinaten) | Niedrig-Mittel | Hoch |
| **Kosten pro Schritt** | Niedrig (Text) | — | **Hoch** (Bild-Token) | Hoch | Niedrig-Mittel |
| **Nicht-Web-Apps** | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Session-Isolation** | ❌ Singleton | ✅ pro Context | je nach Host | ❌ | ✅ pro Runtime |
| **Multi-Session parallel** | ❌ | ✅ | je nach Host | ❌ | ✅ |
| **Persistente Logins** | ❌ | ✅ `storage_state` | ✅ (VM-Zustand) | ✅ | ✅ |
| **Approval-Gate** | ✅ pro Tool | — | je nach Host | ⚠️ y/n-Prompt | ⚠️ konfigurierbar |

### Einordnung

- **Gegenüber rohem Playwright** ist OpenWorkers Beitrag der **Snapshot-mit-Selector-Hints**
  und die **Approval-Integration**. Beides ist übernehmenswert; der Rest ist Playwright.
- **Gegenüber Computer Use** ist OpenWorker billiger und zuverlässiger im Web, aber
  blind außerhalb. Computer Use löst ein anderes Problem (beliebige GUIs) zu höheren
  Kosten und niedrigerer Zuverlässigkeit.
- **Gegenüber OpenHands** ist der auffälligste Unterschied die **Sandbox**: OpenHands
  führt standardmäßig in einem Docker-Runtime aus, OpenWorker im User-Prozess.
  Bei einem Produkt, das Shell + Dateien + 33 Connectoren + MCP kombiniert, ist das
  der gravierendere Nachteil.
- **Gegenüber OpenInterpreter** ist OpenWorker deutlich disziplinierter (Approval-Gate,
  Risikoklassen, Audit), aber weniger fähig am Desktop.

---

## 7.4 VibeMind-Kontext

VibeMind hat laut `infra/swarm/STARTUP_PROFILES.md` bereits **zwei** eigene Ebenen,
die über OpenWorker hinausgehen:

| VibeMind-Komponente | Status laut eigener Doku | Verhältnis zu OpenWorker |
|---|---|---|
| **Automation_ui** (`:8007`), „perception (19 Tools)" | ✅ implementiert; „eyeTerm gaze/dwell/calibrate **nicht** implementiert" | Deutlich weiter — Desktop-Wahrnehmung existiert |
| **OpenClaw** dual: Docker `:18789` headless / Native `:18793` **visible** | ✅ live | Löst genau das Problem, das OpenWorker mit `headless=False` hart verdrahtet hat |
| Routing `browser_automation` vs. `desktop_skill` | im Cap-Router (`capabilities.yaml`), Bug bereits gefixt (`b47caab`) | OpenWorker hat kein Routing-Konzept |

**Damit ist die Entscheidung klar:** OpenWorkers Browser-Layer ist gegenüber
VibeMinds OpenClaw + Automation_ui ein **Rückschritt** — weniger Reichweite, keine
Session-Isolation, keine Headless-Option, kein Routing.

**Was VibeMind trotzdem mitnehmen sollte:**

1. **Den Snapshot-mit-Selector-Hints** (`_SNAPSHOT_JS`). Das ist die kompakteste
   bekannte Repräsentation einer Seite für ein LLM: Text + interagierbare Elemente +
   wie man sie anspricht, in unter 40 Zeilen JS. Direkt portierbar nach OpenClaw.
2. **Das Approval-pro-Aktion-Muster** — jeder Klick, jede Eingabe, jeder Upload ist ein
   eigener Genehmigungspunkt, mit `kind`-basierter Ausnahme für Reads.
3. **Die `Executor`-ABC-Idee** aus `tools/shell.py:55` als Vorbild für einen
   `PerceptionBackend`-/`ActionBackend`-Vertrag: OpenWorker hat die Abstraktion für
   Sandboxing angelegt (und nie gefüllt) — VibeMind sollte sie füllen.

**Was VibeMind vermeiden muss:**

- Modul-Singletons für Ressourcen, die pro Session existieren müssen.
- Hart verdrahtete Headless-Entscheidungen.
- Browser ohne `storage_state` (Login-Persistenz).

---

## 7.5 Was in beiden Systemen fehlt

| Fähigkeit | OpenWorker | VibeMind (laut eigener Doku) |
|---|---|---|
| Sandbox/Container für Desktop-Aktionen | ❌ | ⚠️ OpenClaw hat Docker-Variante |
| Wiederholbare Aufzeichnung (Record & Replay) | ❌ | ❌ |
| Selbstheilende Selektoren | ❌ | unbekannt |
| Visuelle Regression / Verifikation nach Aktion | ❌ | ❌ |
| Undo/Kompensation nach fehlerhafter GUI-Aktion | ❌ | ❌ |
| Multi-Display / Fensterverwaltung | ❌ | teilweise (perception) |
| Barrierefreiheits-Baum statt Pixel | ❌ | unbekannt |

Der letzte Punkt ist strategisch: Accessibility-APIs (macOS AX, Windows UIA, AT-SPI)
liefern strukturierte, billige, zuverlässige Desktop-Wahrnehmung — das Äquivalent
zum DOM für native Apps. Weder OpenWorker noch (nach verfügbarer Doku) VibeMind nutzt
sie. Das ist die aussichtsreichste Lücke für VibeMind, wenn „Desktop Automation als
letzte Ausführungsebene" ernst gemeint ist.

---

## 7.6 Entscheidung

| Komponente | Entscheidung |
|---|---|
| `_SNAPSHOT_JS` (Wahrnehmungs-Repräsentation) | **Direkt übernehmen** → nach OpenClaw portieren |
| Approval-pro-Browser-Aktion | **Übernehmen** |
| `_target_locator` (dreiformige Selektorauflösung mit Fallback) | **Übernehmen** |
| `_BrowserController` (Singleton) | **Nicht übernehmen** — Session-scoped neu bauen |
| Playwright als Browser-Engine | **Nicht nötig** — OpenClaw existiert bereits |
| Desktop-Wahrnehmung | **Neu entwickeln** — Accessibility-Baum statt Pixel |

---

**Weiter:** [08 — Security & Risikoanalyse](08-security-risikoanalyse.md)
