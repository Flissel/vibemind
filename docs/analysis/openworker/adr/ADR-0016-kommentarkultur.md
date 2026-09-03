# ADR-0016 — Kommentarkultur: Warum + Incident-Bezug

**Status:** Vorgeschlagen · **Kategorie:** A (direkt übernehmen) · **Phase:** 1
**Betrifft:** Wartbarkeit, Onboarding, Wissenserhalt

---

## Goal

> Jede nicht-offensichtliche Entscheidung im VibeMind-Code trägt ihre **Begründung**
> im Code — und wo es einen konkreten Vorfall gab, auch dessen Datum.

**Messbar erreicht, wenn:** Code-Reviews Kommentare zur Begründung einfordern; ein
neuer Entwickler kann nicht-offensichtliche Stellen ohne Rückfrage verstehen.

---

## Kontext

OpenWorkers Kommentare erklären durchgängig **warum**, nicht was. Vier Beispiele
aus der Analyse:

> „An allowlist entry auto-runs a command **WITHOUT** approval, so prefix matching is
> unsafe: `git status` would auto-approve `git status && rm -rf ~`."
> — `permissions.py:217-219`

> „Windows has no such bits — `os.chmod` there only toggles the read-only flag, so a
> 0600 chmod is a **silent no-op** and the file inherits broad ACLs (SYSTEM,
> Administrators, …)."
> — `secrets.py:61-66`

> „A directory grant MUST be inheritable — (OI) object-inherit for files, (CI)
> container-inherit for subdirs … Without these flags, `/inheritance:r` leaves the
> directory with a non-inheritable ACE and any child file ends up with an empty DACL
> → sqlite3 'unable to open database file', **crashing the server on launch**."
> — `secrets.py:72-77`

> „Trailing model_switch notices don't break the guard — switching models and THEN
> retrying is the intended recovery path (**owner-hit 2026-07-23**)."
> — `engine.py:240-242`

Der letzte ist der interessanteste: Er dokumentiert einen **realen Vorfall mit Datum**.
Jemand ist auf diesen Fehler gestoßen, hat ihn behoben und den Anlass festgehalten —
damit niemand den Fix „aufräumt".

Weitere Beispiele: die Begründung, warum jeder ausstehende `tool_call` eine Antwort
braucht (`engine.py:124-127`), warum PowerShell nicht resynchronisiert wird
(`shell.py:251-255`), warum `_display` das Modell nicht erreichen darf
(`engine.py:642-647`), warum `explore` risikoarm sein **darf** (`subagent.py:7-11`).

**Kontrast:** Die Architekturdokumentation fehlt vollständig
([02](../02-repositorystruktur.md#docs)). Der Code referenziert
`UX-DECISIONS §16/§25/§30/§33/§34/§36`, `platform/docs/PERSONAS.md`,
`FAKE-SLACK-SPEC.md`, `AUTOMATION-SCHEDULING.md`, `PERMISSIONS-AND-INBOX.md` — **keine
davon existiert im Repository.**

**Das ist die eigentliche Lehre:** Die Kommentare überleben, weil sie beim Code stehen.
Die Dokumente sind beim Export verloren gegangen. Wissen, das im Code steht, wandert mit.

---

## Entscheidung

Verbindlicher Standard in `CLAUDE.md` / `AGENTS.md`:

### 1. Kommentiere das Warum, nicht das Was

```python
# ✗ Setzt die Anzahl der Iterationen auf 12
max_iterations = 12

# ✓ 12 Iterationen: mehr braucht kein sinnvoller Turn; darüber hinaus dreht
#   sich das Modell erfahrungsgemäß im Kreis statt zu konvergieren (Messung 2026-06).
max_iterations = 12
```

### 2. Bugfixes tragen ihren Anlass

```python
# Reihenfolge ist relevant: der Abbruch muss VOR dem Persistieren stehen, sonst
# landet ein halber Tool-Call in der Historie und der Resume-Pfad prompted ihn
# erneut. (Vorfall 2026-07-23, siehe #412)
```

**Warum das zählt:** Ein Fix ohne Begründung wird beim nächsten Refactoring
„vereinfacht" — und der Fehler kommt zurück.

### 3. Trade-offs stehen dort, wo sie getroffen wurden

```python
# Bewusst konservativ: nur als `low` deklarierte Tools laufen parallel. Schreiben
# und Shell bleiben in Aufrufreihenfolge, damit Seiteneffekte reproduzierbar sind.
# Kostet Durchsatz, kauft Determinismus.
```

### 4. Plattformspezifisches wird ausgeschrieben

Windows-/macOS-/Linux-Eigenheiten sind der häufigste Grund für „warum ist das so
kompliziert" — und der häufigste Anlass für falsche Vereinfachungen.

### 5. Architektur-Entscheidungen gehören in ADRs — und werden **verlinkt**

Ein Kommentar darf auf `docs/analysis/.../ADR-00xx.md` verweisen; er darf **nicht** auf
ein Dokument verweisen, das nicht im Repository liegt. Das ist exakt der Fehler, den
OpenWorker gemacht hat.

### 6. Kommentare, die lügen, sind schlimmer als keine

Jeder Kommentar wird bei einer Änderung mit angepasst. Teil des Code-Review-Checks.

---

## Begründung

- **Es ist die Maßnahme mit dem besten Verhältnis von Aufwand zu Nutzen** in der ganzen
  Analyse: Kosten praktisch null, Wirkung dauerhaft.
- **Bei einem Multi-Agenten-System ist es doppelt wichtig** — VibeMind wird von mehreren
  Claude-Sessions parallel bearbeitet (`CLAUDE.md`). Kommentare sind der einzige
  Kontext, den eine neue Session zuverlässig sieht.
- **Datierte Vorfälle verhindern Regressionen** durch gut gemeinte Vereinfachung.
- **Wissen im Code überlebt Umzüge.** OpenWorkers Kommentare sind erhalten, seine
  Design-Dokumente nicht.

---

## Konsequenzen

**Positiv**
- Schnelleres Onboarding (Mensch und Agent).
- Weniger Regressionen durch falsche Vereinfachung.
- Reviews werden inhaltlicher.
- Wissen bleibt beim Code.

**Negativ / Kosten**
- **Kommentare können veralten.** Ein falscher Kommentar ist schlimmer als keiner.
  Gegenmaßnahme: Regel 6 als Review-Punkt.
- **Überkommentierung.** Nicht jede Zeile braucht eine Begründung — nur die
  nicht-offensichtlichen. Faustregel: *Wenn ein kompetenter Kollege fragen würde
  „warum so?", kommentiere.*
- Etwas mehr Schreibaufwand pro PR.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Nur externe Dokumentation** | Verworfen: OpenWorker ist der Beleg — die Dokumente sind beim Export verloren gegangen, die Kommentare nicht |
| **Nur Commit-Messages** | Unzureichend: niemand liest `git blame` beim Refactoring. Ergänzend sinnvoll |
| **Nur ADRs** | Gut für Architektur, falsch für lokale Entscheidungen („warum wird der Tail behalten") |
| **Keine Regel** (Status quo) | Verworfen: bei mehreren parallelen Agenten-Sessions entsteht sonst Wissen, das niemand mehr rekonstruieren kann |
| **Automatische Kommentar-Generierung durch LLM** | Verworfen: erzeugt *Was*-Kommentare. Das *Warum* kennt nur, wer die Entscheidung getroffen hat |
