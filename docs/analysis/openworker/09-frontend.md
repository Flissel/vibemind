# 09 — Frontend

Stack: React 18.3 · Vite 5 · TypeScript 5.5 · Tailwind 3.4 · Tauri 2.11 ·
Vitest · Playwright. Keine State-Management-Bibliothek, kein Data-Fetching-Layer,
keine Komponentenbibliothek.

---

## 9.1 UX — was hier tatsächlich gut ist

Die UX-Arbeit ist die Stärke des Frontends, nicht die Technik.

### (a) Stream-Gating

`src/streamGate.ts` — 41 Zeilen, die ein reales Problem lösen: Ein Modell schreibt vor
Tool-Calls eine Narrationszeile („Checking what merged since yesterday's digest."). Ohne
Gating erscheint sie als schwebender Absatz, wird dann von Tool-Karten verdrängt und
wirkt wie eine abgebrochene Antwort.

| Modus | Bedingung | Darstellung |
|---|---|---|
| `hold` | Turn-Start, < 40 Wörter | nur Spinner |
| `quiet` | Mid-Turn, < 40 Wörter | Zeile im laufenden Turn-Block |
| `answer` | ≥ 40 Wörter **oder** Turn beendet | Antwort-Bubble |

Der Kommentar dokumentiert sogar die Revision: v2 deckte nur Turn-Start ab,
Mid-Turn-Narration flackerte weiter — der Fix ist eine Regel für *allen* Stream-Text.
Zusätzlich: Turns starten **eingeklappt**, die Kopfzeile ist der Puls
(„Running 12 steps… · checking the historical pages…"), Aufklappen ist opt-in.

**Für VibeMind hochrelevant** — dasselbe Problem tritt bei TTS in verschärfter Form auf
([05](05-voice-pipeline.md#55-was-für-vibemind-trotzdem-relevant-ist)).

### (b) Die vier Prompt-Typen als eigene Karten

`ApprovalCard`, `DirectoryRequestCard`, `PlanCard` + Inline-Frage. Jeder Prompt-Typ hat
eine eigene Darstellung mit eigener Entscheidungsmenge
(`once / always_tool / always_command / always_task / deny`). Kein generischer
„Confirm?"-Dialog. Das ist der Unterschied zwischen einem Approval-Modell, das
funktioniert, und einem, das der User wegklickt.

### (c) Artefakt-Links

Der Cowork-Prompt fordert das Literal `[Titel](artifact:<relativer-pfad>)` am Antwortende
(`agents/cowork.py:29-31`), die GUI rendert das als Ein-Klick-Öffner
(`/v1/sessions/{id}/artifacts/read` + `…/reveal`). Enges Prompt-UI-Zusammenspiel, das
das Produktversprechen („finished work, not just chat") einlöst.

### (d) Onboarding und Progressive Enthüllung

`Onboarding.tsx`, `FolderGate.tsx`, `WorkspaceTrustPrompt.tsx`, `SessionIntro.tsx` —
der Workspace-Trust-Dialog erscheint genau dann, wenn er relevant wird, nicht als
Vorab-Einstellung.

---

## 9.2 State Management — die technische Schwäche

**Kein Store.** `App.tsx` (1.732 LOC) enthält 78 `useState`/`useEffect`/`useRef`-Aufrufe
und ist der zentrale Zustandsknoten für: Sessions, Messages, Items, Streaming-Puffer,
Approvals, Inbox, Personas, Settings, Roots, Artefakte, Automations, Modelle,
Connectoren, Workspace-Trust, Onboarding, Suche, Rechte Leiste, Update-Banner.

**Konsequenzen:**

| Problem | Wirkung |
|---|---|
| Prop-Drilling | `Composer` bekommt ~20 Props, `Sidebar` (1.378 LOC) ähnlich |
| Re-Render-Breite | Jedes `ASSISTANT_DELTA` setzt State in `App.tsx` → Rerender des gesamten Baums. Bei schnellen Streams ist das messbar teuer. |
| Keine Cache-Invalidierung | Jede REST-Antwort wird manuell in State geschrieben; Konsistenz zwischen Views ist Handarbeit |
| Testbarkeit | Nur über E2E sinnvoll testbar — was erklärt, warum es 55 E2E-Specs und nur 8 Unit-Tests gibt |
| Optimistic Updates | Von Hand pro Aktion |

**Kein `react-query`/`swr`** heißt: kein Retry, kein Stale-While-Revalidate, kein
Deduplizieren paralleler Requests, kein Hintergrund-Refetch. Statt dessen manuelle
`useEffect`-Ketten und Custom-Events auf `window`
(`window.dispatchEvent(new Event("coworker:voice-input-changed"))`,
`PERSONAS_CHANGED`) als Ad-hoc-Event-Bus zwischen entkoppelten Komponenten. Das
funktioniert, ist aber ein Umgehungspfad um den fehlenden Store.

---

## 9.3 Komponentenstruktur

49 Komponenten in `src/components/`, davon 14 unter `components/connectors/`.

**Gut:** Kleine, fokussierte Komponenten (`Toggle`, `Dropdown`, `SelectMenu`, `Icon`,
`RootRow`, `SubscriptionsChip`). Ikonografie über `simple-icons` + eigene
`brandIcons.tsx`.

**Problematisch:** Für jeden großen Connector existiert eine handgeschriebene
Detail-Komponente (`SlackDetail` 626 LOC, `GithubDetail`, `GmailDetail`,
`CalendarDetail`, `HubSpotDetail`, `AccountsDetail`, `AvailableDetail`). Das Backend
hat mit `ConnectorDescriptor` ein **datengetriebenes** Modell — das Frontend
implementiert dieselbe Information ein zweites Mal von Hand. Bei 33 Connectoren ist das
der Punkt, an dem eine generische, descriptor-getriebene Detailansicht mit
Spezialfall-Slots richtig gewesen wäre.

**Typ-Drift:** `src/types.ts` und `src/api.ts` (1.864 LOC) sind handgepflegt. Es gibt
**keine** Typgenerierung aus dem FastAPI-OpenAPI-Schema — obwohl FastAPI es kostenlos
liefert. Jede Backend-Änderung kann still divergieren; **`tsc` läuft nicht in CI**
(`npm test` ist nur vitest), also fällt es nicht einmal beim Build auf.

---

## 9.4 IPC & Tauri-Integration

Zwei getrennte Kanäle, sauber abgegrenzt:

| Kanal | Wofür | Datei |
|---|---|---|
| HTTP/WS → `127.0.0.1:<port>` | Alles Fachliche | `api.ts` |
| Tauri `invoke` | Nur was das OS braucht: `pick_folder`, `get/set_autostart`, `get/set_keep_awake`, `start_window_drag`, Dictation-Commands | `tauri.ts`, `src-tauri/src/lib.rs` |

**Die Rust-Shell als Supervisor** (`src-tauri/src/lib.rs`):
- sucht einen freien Port (`free_port()`),
- erzeugt ein **In-Memory-Launch-Token** (`launch_token()`) — im Gegensatz zum
  Standalone-Server, der es nach `<state-dir>/sidecar-<port>.token` schreibt.
  Die Desktop-App schreibt es **nie auf Platte** (`README.md:87-90`). Guter Unterschied.
- startet das Server-Binary, leitet Logs in eine Datei,
- hält per `SetThreadExecutionState` (Windows) bzw. IOKit (macOS) den Rechner wach,
  wenn eine Automation läuft — plattformspezifisch mit `cfg`-Zweigen.

**Bewertung:** Die Trennung „Tauri macht nur OS-Dinge" ist genau richtig und macht die
GUI im Browser lauffähig (`npm run dev`) — bis auf Voice, das an `isTauri()` hängt
(`Composer.tsx:289`). Für VibeMind (Electron) ist der Tauri-Code irrelevant, das
**Muster** aber übernehmenswert: Fach-API über HTTP, OS-API über IPC, nichts vermischen.

Die Tauri-Capabilities (`src-tauri/capabilities/default.json`) sind vorhanden — die
Berechtigungen der Webview sind also explizit deklariert und nicht offen.

---

## 9.5 Performance

| Aspekt | Befund |
|---|---|
| Bundle | React + react-markdown + remark-gfm + **pdfjs-dist** + **xlsx** + simple-icons. `pdfjs` und `xlsx` sind schwer (~1 MB+ zusammen); es gibt kein sichtbares Code-Splitting/Lazy-Loading |
| Rerender | Zentraler State → breite Rerenders bei jedem Stream-Delta ([9.2](#92-state-management--die-technische-schwäche)) |
| Virtualisierung | **Keine.** `Transcript.tsx` rendert alle Items. Eine Session mit 500 Nachrichten und großen Tool-Karten wird träge |
| Markdown | `react-markdown` pro Nachricht, ohne Memoisierung im gestreamten Fall sichtbar teuer |
| Streaming-Puffer | String-Konkatenation im State pro Delta — bei langen Antworten O(n²)-Verhalten |
| Font | Eine `.woff2` lokal eingebunden — kein externes CDN. Gut für Offline/Privacy |

**Keines dieser Probleme ist bei den typischen Sessiongrößen kritisch.** Für VibeMind
mit Multi-Agent-Fan-out (viele parallele Streams) wären sie es sofort.

---

## 9.6 Erweiterbarkeit

| Erweiterung | Aufwand |
|---|---|
| Neue Ansicht/Tab | Mittel — `App.tsx` anfassen, State ergänzen |
| Neuer Event-Typ | Klein — `types.ts` + Handler in `App.tsx` |
| Neuer Connector (UI) | **Groß** — eigene Detail-Komponente von Hand |
| Neues Theme | Klein — `theme.ts` + Tailwind |
| Zweite Surface (z. B. Mobile) | **Sehr groß** — keine geteilte Logikschicht; `api.ts` wäre wiederverwendbar, `App.tsx` nicht |
| Plugin-/Widget-System | **Existiert nicht** |

Es gibt `src/flags.ts` (Feature-Flags) — ein Ansatz, aber kein Erweiterungsmechanismus.

---

## 9.7 Testabdeckung

- **8 Unit-Tests** (vitest): `ApprovalCard`, `Markdown`, `ModelChecklist`, `PersonaView`,
  `Sidebar`, `Transcript`, `UpdateBanner`, `ConnectorMessageCard`, `ConnectorIcon`,
  `streamGate`, `itemsFromMessages`, `api.auth`, `Composer.voice`.
- **55 hermetische E2E-Specs** mit gemocktem `/v1` + WS (`e2e/fixtures.ts`, 1.493 LOC).
  Laufen ohne Modell und ohne Netz in CI.
- **7 Live-E2E-Specs** gegen einen echten Server (`e2e-live/`), nicht in CI.

**Das ist die richtige Pyramide für ein UI mit wenig eigener Logik** — die Logik liegt
im Backend, das UI ist Darstellung, also testet man Verhalten statt Einheiten.
Der Preis: E2E-Läufe sind langsam, und der `fixtures.ts`-Mock ist selbst 1.493 Zeilen
Wartungslast, die vom echten Backend divergieren kann.

---

## 9.8 Bewertung

| Aspekt | Note | |
|---|---|---|
| UX-Konzeption | **A** | Stream-Gating, Prompt-Karten, Artefakt-Flow, Onboarding |
| Tauri-Integration | **A-** | Saubere Trennung, In-Memory-Token, Keep-Awake |
| E2E-Teststrategie | **A-** | 55 hermetische Specs |
| Komponentengranularität | B | Klein und fokussiert, aber Connector-Duplikation |
| State Management | **D** | 1.732-LOC-`App.tsx`, kein Store, kein Fetching-Layer |
| Typsicherheit gegen Backend | **D** | Handgepflegt, kein Codegen, `tsc` nicht in CI |
| Performance-Vorsorge | C | Keine Virtualisierung, kein Splitting, O(n²)-Streaming-Puffer |
| Erweiterbarkeit | C | Kein Plugin-Modell, Connector-UI von Hand |

**Entscheidung für VibeMind:** **Nicht übernehmen** (VibeMind hat Electron + Next.js).
**Übernehmen als Muster:** Stream-Gating-Regel, Prompt-Karten-Taxonomie, die strikte
Trennung Fach-API/OS-IPC, und die hermetische E2E-Strategie mit gemocktem Backend.

---

**Weiter:** [10 — Backend](10-backend.md)
