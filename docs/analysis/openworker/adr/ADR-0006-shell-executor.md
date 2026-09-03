# ADR-0006 — ContainerExecutor als Default-Ausführungsumgebung

**Status:** Vorgeschlagen · **Kategorie:** A (Executor-Muster) + C (Isolation neu) · **Phase:** 3
**Betrifft:** Sicherheit, Shell, Code-Ausführung, Multi-Agent

---

## Goal

> Kein von einem Agenten ausgeführtes Kommando läuft im Standardfall mit den Rechten
> des Nutzers. Der Blast-Radius einer Fehlentscheidung ist auf einen Container mit
> explizit gemounteten Verzeichnissen und begrenztem Netzzugang beschränkt.

**Messbar erreicht, wenn:** `cat ~/.ssh/id_rsa` in einer Standard-Session **fehlschlägt**;
`LocalExecutor` nur nach bewusster Einstellung erreichbar ist.

---

## Kontext

**Zwei getrennte Befunde aus OpenWorker:**

**(a) Das Executor-Muster ist gut.** `tools/shell.py` löst die schwierigen Teile
sauber:
- **Persistente Shell** statt `subprocess.run` pro Aufruf — `cd`, `export`, aktivierte
  venvs überleben zwischen Tool-Calls.
- **Marker-Protokoll**: nach jedem Kommando ein `printf "\n%s %s %s\n" "$MARKER" "$?" "$PWD"`,
  daraus werden Exit-Code und CWD geparst. Windows-Äquivalent mit `$?`/`$LASTEXITCODE`.
- **Timeout mit Resynchronisation**: SIGINT an den Vordergrund-Child, 3 s Gnadenfrist
  auf den Marker, sonst harter Kill + Respawn im letzten CWD.
- **Tail-Trunkierung**: Build-/Test-Verdikte stehen am Ende und gehen nie verloren.
- **Hintergrundtasks** als eigener detachter Prozess, nicht in der persistenten Shell.

**(b) Die Isolation fehlt vollständig.** Die `Executor`-ABC (`shell.py:55`) ist explizit
als „hedge for a future `ContainerExecutor`/`VMExecutor`" dokumentiert — implementiert
ist **nur** `LocalExecutor`. Jedes genehmigte Kommando läuft mit vollen Nutzerrechten;
die Pfad-Scoping-Logik der Permission-Engine greift für `run_shell` **nicht**
([08 R-01](../08-security-risikoanalyse.md#r-01)).

VibeMind betreibt bereits Docker Swarm und hat mit OpenClaw eine Docker-Variante
(`:18789` headless) — die Infrastruktur ist da.

---

## Entscheidung

**Das Executor-Muster wird portiert. Die ABC wird gefüllt. Container ist Default.**

```python
class ExecutionPolicy:
    backend: Literal["container", "local", "vm"] = "container"
    image: str                          # pro Space konfigurierbar
    mounts: list[Mount]                 # NUR die Roots der Session, explizit
    network: Literal["none", "allowlist", "full"] = "allowlist"
    egress_allowlist: list[str]
    limits: ResourceLimits              # CPU, RAM, PIDs, Wall-Clock, Disk
    persist_between_calls: bool = True  # persistente Shell IM Container
```

| Backend | Einsatz |
|---|---|
| `ContainerExecutor` | **Default.** Persistente Shell im Container; das Marker-Protokoll funktioniert unverändert |
| `LocalExecutor` | Nur nach bewusster Space-Einstellung, mit sichtbarem Warnhinweis |
| `VMExecutor` | Später, für maximal untrusted Workloads |

**Wichtig:** Alle Eigenschaften aus (a) bleiben erhalten — persistente Shell,
Marker-Protokoll, Timeout-Resync, Tail-Trunkierung, Hintergrundtasks. Der Container
ersetzt nur die *Umgebung*, nicht die *Mechanik*.

**Zusätzlich zu OpenWorker:**
- **Ein Container pro Agent-Session** (nicht pro Prozess) — löst gleichzeitig das
  Multi-Agent-Isolationsproblem.
- **Interrupt-Hook** = Container-Kill ([ADR-0003](ADR-0003-cancellation-invarianten.md)).
- **Hintergrundtasks werden beim Session-Ende getötet** — anders als bei OpenWorker,
  wo sie bewusst überleben (`shell.py:17-21`). In einem Container-Modell ist Überleben
  ein Leck.
- **Egress-Allowlist** pro Space, im Container erzwungen (Netzwerk-Policy), nicht nur
  in der Anwendungsschicht.

---

## Begründung

- **R-01 ist das schwerwiegendste Einzelrisiko** der Analyse. Ohne Isolation ist der
  Blast-Radius jeder Fehlentscheidung — eigene oder durch Injection ausgelöste — das
  gesamte Benutzerkonto.
- **Bei Multi-Agent potenziert sich das.** n parallele Worker mit vollen Nutzerrechten
  sind n unabhängige Fehlerquellen im selben Verantwortungsbereich.
- **VibeMind zahlt fast keinen Preis dafür.** Docker ist bereits die Betriebsform;
  OpenHands und Codex zeigen, dass Container-Isolation für Agenten praktikabel ist
  ([15.4](../15-architekturvergleich.md#154-sicherheit)).
- **Das Executor-Muster ist es wert, portiert zu werden.** Persistente Shell +
  Marker-Protokoll + Timeout-Resync sind nicht trivial und in OpenWorker
  produktionserprobt (inklusive Windows-Pfad).

---

## Konsequenzen

**Positiv**
- Schließt R-01 und entschärft R-02 und R-05 erheblich.
- Reproduzierbare Umgebungen pro Space (Image-Pinning).
- Ressourcenlimits verhindern Runaway-Prozesse.
- Container-Kill als sauberer Abbruchpfad.
- Voraussetzung für sicheren Worker-Pool ([ADR-0014](ADR-0014-worker-pool.md)).

**Negativ / Kosten**
- **Alle Annahmen über Pfade, Netz und verfügbare Werkzeuge brechen.** Das ist der
  aufwendigste Teil: Jeder Space braucht ein passendes Image und eine geprüfte
  Mount-Konfiguration.
- **Startzeit**: Container-Start kostet 0,5–3 s. Gegenmaßnahme: warme Pools pro Space.
- **Speicher**: n Sessions = n Container.
- **Desktop-Automation passt nicht hinein.** GUI-Steuerung braucht Zugriff auf die
  echte Desktop-Session. **Bewusste Ausnahme:** OpenClaw/Automation_ui laufen weiterhin
  außerhalb — mit eigener Genehmigungsschicht und eigenem Risikoprofil.
- **Entwicklerkomfort sinkt**: „Warum findet der Agent mein lokales Tool nicht?" wird
  eine häufige Frage. Braucht gute Fehlermeldungen.

**Risiko**
- **Ausrollung bricht bestehende Spaces.** Wahrscheinlichkeit hoch, Wirkung hoch.
  Gegenmaßnahme: schrittweise pro Space, `LocalExecutor` als Rückfallebene, Space-weise
  Testsuiten vor der Umstellung.
- **Container-Escape** ist nicht ausgeschlossen. Gegenmaßnahme: nicht-root im Container,
  `--cap-drop=ALL`, seccomp, read-only Root-FS, kein Docker-Socket im Container.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (`LocalExecutor`)** | Verworfen: R-01 bleibt offen; bei Multi-Agent nicht verantwortbar |
| **Nur Pfad-Scoping in der Anwendungsschicht** | Verworfen: nicht durchsetzbar. Shell kann jeden Pfad erreichen; jede Prüfung ist umgehbar (Symlinks, Subshells, `env`) |
| **VM statt Container** | Stärkere Isolation, aber deutlich teurer bei Start und Speicher. Sinnvoll als dritte Stufe für explizit untrusted Code, nicht als Default |
| **gVisor / Kata Containers** | Bessere Isolation bei Container-Ergonomie. **Empfehlung: als Härtungsoption in Phase 5 evaluieren**, nicht als v1-Voraussetzung |
| **Nur genehmigte Kommandos aus einer Allowlist** | Verworfen als alleinige Maßnahme: zu eng für Entwicklungsarbeit. Bleibt als *zusätzliche* Schicht sinnvoll ([ADR-0002](ADR-0002-risk-klassifikation.md)) |
| **WASM-Sandbox** | Verworfen: keine echte Shell, keine bestehenden Werkzeuge |
