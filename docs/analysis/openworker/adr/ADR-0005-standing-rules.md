# ADR-0005 — Standing Grants mit Zielbindung, TTL und Rate-Limit

**Status:** Vorgeschlagen · **Kategorie:** B (übernehmen und erweitern) · **Phase:** 2
**Betrifft:** Genehmigung, Automations, unbeaufsichtigter Betrieb

---

## Goal

> Wiederkehrende Automationen fragen **nicht** jedes Mal erneut, ohne dass dafür die
> Autonomie-Obergrenze angehoben wird.

**Messbar erreicht, wenn:** Eine tägliche Automation, die in denselben Kanal postet,
fragt einmalig; ein per Prompt-Injection gekaperter Agent kann die Erlaubnis **nicht**
zur Exfiltration missbrauchen.

---

## Kontext

Das UX-Problem ist real: Eine Automation, die jeden Morgen einen Bericht in
`#team-daily` postet, darf nicht jeden Morgen fragen — sonst schaltet der Nutzer sie in
den Vollautomatik-Modus, und damit ist **jede** Aktion erlaubt.

OpenWorker löst das mit **Standing Rules** (`permissions.py:160-171`,
`automation/models.py:20-56`) — und löst es bemerkenswert sorgfältig:

| Schutzmaßnahme | Umsetzung |
|---|---|
| Nur externe Risiken | `classify() == EXTERNAL` — nie `EXEC`, nie `WRITE_LOCAL` („shell asks forever") |
| Tool muss ein Ziel deklarieren | `target_arg_for(tool)` — schließt destruktive Tools konstruktiv aus |
| Call muss ein Ziel nennen | leerer Wert → nicht regelfähig |
| Exaktes Ziel | keine Wildcards, keine Präfixe |
| Besitz | Regel lebt auf dem Task-Record → Widerruf pro Automation, Löschen nimmt sie mit |
| Validierung fail-closed | `grant_entries()` verwirft alles, was nicht vollständig passt |
| Nachvollziehbarkeit | Jede Anwendung wird auditiert **mit der zitierten Regel** |

**Die verbleibende Lücke:** Das Ziel ist ein **Kanal**, kein **Inhalt**.
`send_message → slack:C123` erlaubt *beliebige Inhalte* in diesen Kanal, **dauerhaft**.
Ein gekaperter Agent kann darüber exfiltrieren
([08 R-03](../08-security-risikoanalyse.md#r-03)).
Zudem: kein Ablaufdatum, keine Rate-Begrenzung.

---

## Entscheidung

VibeMind übernimmt alle sieben Schutzmaßnahmen **unverändert** und ergänzt vier:

```python
@dataclass
class StandingGrant:
    tool: str
    target: str                     # exakt, keine Wildcards (aus OpenWorker)
    owner: GrantOwner               # Automation | Space | Session (aus OpenWorker: nur Task)
    # --- Erweiterungen ---
    expires_at: datetime            # 1. TTL, Default 90 Tage
    rate_limit: RateLimit           # 2. z. B. 5 Aufrufe/Tag
    content_class: ContentClass     # 3. z. B. "report_from_this_automation"
    taint_ceiling: TaintLevel       # 4. ungültig, sobald Fremdinhalt konsumiert wurde
```

**1. TTL** — Standing Grants verfallen. Erneuerung ist ein bewusster Akt, keine
Vergesslichkeit.

**2. Rate-Limit** — Eine tägliche Automation braucht 1–2 Sends/Tag. Wer 500 sendet,
tut etwas anderes als geplant. Überschreitung → Prompt statt Auto-Allow, plus
Governance-Event.

**3. Inhaltsklasse** — Die entscheidende Ergänzung. Der Grant bindet nicht nur an
*wohin*, sondern an *was*: „Berichte, die diese Automation erzeugt hat". Prüfung über
einen leichten Klassifikator oder — pragmatischer und robuster — über **Herkunft**:
Der gesendete Inhalt muss aus den Artefakten **dieses Laufs** stammen, nicht aus
beliebigem Kontext.

**4. Taint-Ceiling** — Sobald der Agent im aktuellen Lauf Fremdinhalt konsumiert hat
(externes Ticket, Webseite, E-Mail), sind Standing Grants **ungültig**; es wird wieder
gefragt. Direkte Kopplung an [ADR-0015](ADR-0015-taint-tracking.md). **Das ist die
eigentliche Injection-Abwehr für diesen Pfad.**

**Zusätzlich:** `DESTRUCTIVE` und `SPEND` ([ADR-0002](ADR-0002-risk-klassifikation.md))
sind **nie** regelfähig — analog zu OpenWorkers Ausschluss von `EXEC`.

---

## Begründung

- **Das Grundproblem ist echt.** Ohne Standing Grants schalten Nutzer auf Vollautomatik —
  das ist strikt schlechter als ein enger, zielgebundener Grant.
- **OpenWorkers Einschränkungen sind sämtlich richtig.** Besonders „nur `EXTERNAL`,
  nie `EXEC`": Shell kann man nicht an ein Ziel binden, also darf sie nie automatisch
  erlaubt werden.
- **Die vier Ergänzungen adressieren die einzige verbleibende Lücke** — dass ein Kanal
  ohne Inhaltsbindung ein offener Exfiltrationspfad ist.
- **Taint-Ceiling ist die wirksamste der vier.** Sie kostet fast nichts, sobald
  Taint-Tracking existiert, und schließt den realistischsten Angriffspfad.

---

## Konsequenzen

**Positiv**
- Automationen laufen ohne Genehmigungsmüdigkeit.
- Autonomie-Obergrenze bleibt unangetastet.
- Widerruf ist granular und auffindbar.
- TTL erzwingt regelmäßige Überprüfung.

**Negativ / Kosten**
- **Inhaltsklassifikation ist unscharf.** Der herkunftsbasierte Ansatz („Inhalt stammt
  aus Artefakten dieses Laufs") ist robuster als ein Klassifikator — aber er
  schränkt legitime Fälle ein (etwa ein Bericht, der Kontext aus einer früheren Session
  zitiert). **Empfehlung: mit Herkunftsprüfung starten, Klassifikator später ergänzen.**
- **TTL erzeugt Wiedervorlagen.** Braucht eine gute Erneuerungs-UX, sonst empfinden
  Nutzer es als Gängelung.
- Mehr Zustand pro Grant → mehr UI (Übersicht aller aktiven Grants, Widerruf,
  Erneuerung).
- Rate-Limits brauchen einen Zähler mit Zeitfenster — in Redis trivial, aber ein
  weiteres bewegliches Teil.

**Risiko**
- **Zu strenge Regeln führen zur Umgehung.** Wenn Grants ständig greifen, schalten
  Nutzer die Automation auf Vollautomatik — genau das, was verhindert werden soll.
  Gegenmaßnahme: Defaults großzügig wählen (90 Tage, großzügiges Rate-Limit) und
  über den Governance-Log messen, wie oft Grants tatsächlich blockieren.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Keine Standing Grants** (immer fragen) | Verworfen: führt in der Praxis zur Vollautomatik — strikt schlechter |
| **Tool-weite Grants ohne Ziel** (OpenWorkers Legacy-Form) | Verworfen: `send_message` global erlauben heißt „an jeden senden" |
| **Wildcards** (`slack:*`) | Verworfen: hebt die Zielbindung faktisch auf |
| **Zeitfenster-Grants** („heute erlaubt") | Als *Ergänzung* sinnvoll (Ad-hoc-Aufgaben), nicht als Ersatz für automationsgebundene Grants |
| **Vollautomatik-Modus pro Automation** | Verworfen: hebt die Autonomie-Obergrenze an — genau der Fehler, den Standing Grants vermeiden |
| **Nachträgliche Genehmigung** („gesendet, bitte prüfen") | Verworfen für `EXTERNAL`: nicht rücknehmbar. Vertretbar allenfalls für `WRITE_LOCAL` |
