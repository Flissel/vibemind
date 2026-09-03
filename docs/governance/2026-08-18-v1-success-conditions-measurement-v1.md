# V1-Erfolgsbedingungen: Messung gegen das Repository

**Task:** `task-governance-0036-v1-success-conditions-measurement-v1`
**Gemessen am:** 2026-08-18
**Base-Commit:** `9815322559e3d40d5a00e48f13f16f3f5b060f92` (`origin/master`, selbst gemessen mit `git rev-parse origin/master`, nicht aus dem Auftrag übernommen)
**Gemessene Autorität:** Abschnitt 12 von `docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md`
**Umgebung:** Python 3.11.15, pytest 8.4.2 und PyYAML aus `tools/v1_governance/requirements.txt`. Ein blankes `pip install pytest` liefert 9.x und andere Zahlen.

## 0. Was dieses Dokument ist und was nicht

Dies ist eine **Messung**. Es repariert nichts, entscheidet nichts, ändert keinen Contract, kein Werkzeug und keinen Session-Request. Wo der Spec-Text eine Frage offenlässt, steht die Frage in Abschnitt 11 als User-Frage — sie wird hier nicht beantwortet.

Jede Bedingung bekommt: den Wortlaut, ein Urteil aus `holds` / `does-not-hold` / `cannot-be-determined`, und das Kommando oder den Dateipfad, der das Urteil entscheidet. Alle Zahlen in diesem Dokument sind in dieser Session aus den Dateien gezählt, nicht aus früheren Dokumenten übernommen. Wo eine frühere Angabe von der gemessenen abweicht, steht die Abweichung ausdrücklich da (Abschnitt 10).

**Reproduktionsbasis.** Alle Kommandos laufen im Superprojekt-Worktree auf `9815322`. Das `vibemind-os`-Submodul wurde **nicht** im Working-Tree initialisiert; wo Submodul-Inhalt gemessen wurde, geschah das in einem separaten Klon außerhalb des Superprojekts (`git clone https://github.com/Flissel/vibemind-os /workspace/vibemind-os`, HEAD `760da810`), weil `git submodule update --init` `manifest validate` bricht.

## 1. Übersicht

| # | Bedingung (Kurzform) | Urteil |
|---|---|---|
| 1 | alle 22 Cockpits eindeutig registriert | **holds** |
| 2 | jedes Cockpit gültige Authority | **holds** (mit benannter Außengrenze) |
| 3 | jedes *gestartete* Cockpit: Repo-first Audit und Space Brief geliefert | **cannot-be-determined** |
| 4 | kein Cockpit hat ungefragt Code oder Git-Zustand verändert | **holds** (für die drei gemessenen Repos, Git-Zustand) |
| 5 | jeder Implementierungstask: Parent-Cockpit, dauerhafter Request, gültige Authority | **cannot-be-determined** (Struktur vollständig, Auslegung offen) |
| 6 | Worktrees, Branches, Handoffs und PRs eindeutig zugeordnet | **does-not-hold** |
| 7 | Orchestrator pflegt Abhängigkeiten und Merge-Reihenfolge nachweisbar | **holds** |
| 8 | OpenFang-Grenzen dokumentiert **und taskweise verifiziert** | **does-not-hold** |
| 9 | mindestens ein vollständiger Cockpit→Task→PR→Merge→Verifikation-Zyklus | **does-not-hold** |

Drei Bedingungen halten, zwei sind nicht entscheidbar, drei halten nicht, eine hält mit benannter Grenze. Keine dieser Zahlen ist ein Fortschrittsmaß: Bedingung 8 und 9 sind die inhaltlich schwersten.

---

## 2. Bedingung 1

> alle 22 Cockpits eindeutig registriert sind;

**Urteil: holds.**

**Entscheidet:** `docs/governance/session-portfolio-registry-v1.json` gegen Abschnitt 4 des Spec.

```
python - <<'EOF'
import json,re
spec=open('docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md').read()
sec4=spec.split('## 4. Vollständiges Cockpit-Portfolio')[1].split('## 5.')[0]
spec_ids=re.findall(r'`(cockpit-[a-z0-9-]+)`',sec4)
reg=[c['cockpit_session_id'] for c in json.load(open('docs/governance/session-portfolio-registry-v1.json'))['cockpits']]
print(len(spec_ids),len(set(spec_ids)),len(reg),len(set(reg)),spec_ids==reg)
EOF
```

**Gemessen:** Der Spec nennt in Abschnitt 4 genau 22 Cockpit-IDs, alle verschieden. Die Registry führt genau 22 Einträge, alle `cockpit_session_id` verschieden. Die Mengen sind identisch (keine ID nur im Spec, keine nur in der Registry), und sogar die Reihenfolge stimmt überein. Die Registry deklariert sich selbst als `authority.normative_membership: portfolio`.

**Zusatz:** `tools/v1_governance/portfolio.py` führt dieselbe Menge als `_CANONICAL_COCKPIT_IDS` fest; `python -m pytest tests/v1_governance -q` (273 passed) deckt sie ab. Die Bedingung ist damit nicht nur erfüllt, sondern gegen Drift abgesichert.

---

## 3. Bedingung 2

> jedes Cockpit eine gültige Standing- oder request-spezifische Authority besitzt;

**Urteil: holds**, mit einer Außengrenze, die unten ausdrücklich steht.

**Population: Cockpits.** Das ist eine andere Population als Bedingung 5 (Implementierungstasks). Beide werden hier getrennt gemessen und nirgends vermischt.

**Entscheidet:** `docs/governance/cockpit-approval-ledger-v1.json` gegen die Registry.

```
python - <<'EOF'
import json,collections
led=json.load(open('docs/governance/cockpit-approval-ledger-v1.json'))
reg=[c['cockpit_session_id'] for c in json.load(open('docs/governance/session-portfolio-registry-v1.json'))['cockpits']]
ap={a['cockpit_session_id']:a['approval_reference'] for a in led['approvals']}
print(len(led['approvals']),len(ap),sorted(set(reg)-set(ap)),sorted(set(ap)-set(reg)))
print(collections.Counter(v.split(':')[0] for v in ap.values()))
EOF
```

**Gemessen:** 22 Approval-Einträge, 22 verschiedene Cockpit-IDs, deckungsgleich mit der Registry — keine Lücke, kein Überhang. Jeder Eintrag trägt eine nichtleere `approval_reference`:

* 20 × `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@…`
* 2 × `codex-user-message:019fa01e-…@…` (`cockpit-openfang`, `cockpit-agentfarm`)

Alle 22 passen auf `_INDIVIDUAL_APPROVAL_REFERENCE` in `tools/v1_governance/portfolio.py`; die Ledger-Policy ist `individual-user-approval-required`.

**Warum das die Bedingung trifft:** Abschnitt 6 des Spec verlangt für Cockpit-Threads gerade **keine** Standing Authority, sondern „eine individuelle User-Freigabe im geschlossenen `docs/governance/cockpit-approval-ledger-v1.json`". Genau das liegt vor, für alle 22. Die Bedingung nennt „Standing- **oder** request-spezifische Authority"; die request-spezifische Variante ist erfüllt.

**Außengrenze, die im Urteil nicht versteckt wird:** Das Repository belegt, dass jede Referenz existiert, wohlgeformt und eindeutig ist. Es belegt **nicht**, dass die referenzierten User-Nachrichten tatsächlich gesendet wurden — eine `claude-user-message:`-Referenz zeigt aus dem Repo hinaus. 20 der 22 Referenzen teilen sich zudem nur zwei Zeitstempel (`2026-08-13T09:58:00Z` und `13:09:00Z`), sind also in zwei Blöcken vergeben worden. Ob eine Block-Freigabe eine „individuelle" Freigabe im Sinne von Abschnitt 6 ist, entscheidet das Repository nicht. **Wer das auflösen kann:** der User, aus dem Verlauf der Session `session_01SdA3ftgP3wciDbcFzKw4uk` und des Codex-Threads `019fa01e-5cd6-7ac0-b320-7222affb6164`.

---

## 4. Bedingung 3

> jedes gestartete Cockpit seinen Repo-first Audit und Space Brief geliefert hat;

**Urteil: cannot-be-determined.**

Die Bedingung sagt **gestartet**, nicht **registriert**. Vor dem Zähler muss der Nenner stehen, und genau der ist repo-first nicht herstellbar.

### 4.1 Der Nenner: welche Cockpits sind gestartet?

**Entscheidet:** `docs/governance/cockpit-activation-evidence-v1.json` und `docs/governance/session-request-queue-v1.md` §2.1.

```
python -c "
import json,collections
cs=json.load(open('docs/governance/cockpit-activation-evidence-v1.json'))['cockpits']
print(len(cs))
print(collections.Counter(c['current_evidence']['activation'] for c in cs))
print(collections.Counter((c['historical_observation']['status'],c['historical_observation']['observation']) for c in cs))
"
```

**Gemessen:** Alle 22 Einträge tragen `activation: "git-evidenced-creation"` mit einer durablen Referenz `ccr-session:<session-id>@<rfc3339>`, und alle 22 tragen `historical_observation.observation: "final_reported"` — dieses aber mit `evidence_scope: "external-not-git-verified"`.

Das Ledger widerspricht ausdrücklich der Gleichsetzung von *erstellt* und *gestartet*. Drei Stellen sagen dasselbe:

* `standing_activation_authority.proves_activation: false` in jedem der 22 Einträge;
* `authority.standing_activation_authority_scope: "authority-available-not-activation-proof"`;
* `session-request-queue-v1.md` §2.1, Schlussabsatz, wörtlich: *„Dies ist ein reiner Erstellungs-Record. Er behauptet keine Aktivierung, Interaktivität oder Live-Evidence."*

Damit gilt: **das Repository evidenziert 22 Erstellungen und null Starts.** Der Nenner ist repo-first nicht bestimmbar — er ist nicht kleiner als 22, er ist unbekannt. Die einzige Aussage über tatsächliche Läufe (`final_reported`, 22×) ist als nicht-git-verifiziert deklariert und trägt deshalb keinen Nenner.

**Wer das auflösen kann:** der User. Die 22 CCR-Session-Verläufe (`session_01RPNeXk…` bis `session_01MVDw1b…`, vollständig in §2.1 tabelliert) und die 22 Codex-/Claude-Threads aus `cockpit-external-observations-v1.json` liegen außerhalb des Repos.

### 4.2 Der Zähler: sind Audit und Space Brief geliefert?

**Entscheidet:** die Suche nach dem in Abschnitt 5 des Spec definierten Ausgabeschema.

```
grep -rl "recommended_first_task" . --exclude-dir=.git
grep -ril "space.brief" docs/
```

**Gemessen:** Beide Suchen liefern **genau eine** Datei — den Spec selbst. Das strukturierte Cockpit-Ausgabeformat aus Abschnitt 5 (`audit:`, `mvp:`, `gaps:`, `dependencies:`, `risks:`, `backlog:`, `recommended_first_task:`) existiert nirgendwo im Repository, in keiner Ausprägung, für kein Cockpit. Der Begriff „Space Brief" kommt außerhalb des Spec nicht vor.

Was im Repository stattdessen liegt, sind **Ableitungen** des Orchestrators aus den Audits: `session-request-queue-v1.md` §3.1b und §3.1d entscheiden namentlich benannte offene Fragen einzelner Cockpits (`cockpit-ideas`, `cockpit-bubbles`, `cockpit-minibook`, `cockpit-agentfarm`, `cockpit-coding`, `cockpit-rowboat`), und §3.1d behauptet in einem Satz: *„Alle elf Welle-4–6-Cockpits haben ihre Repo-first-Audits am Erstellungstag abgeschlossen."* Diese Ableitungen belegen, dass Audits stattgefunden haben; sie sind aber nicht die Lieferung selbst, und sie decken nur einen Teil der 22 ab.

### 4.3 Warum das Urteil nicht „does-not-hold" lautet

Der Spec sagt nicht, **wohin** geliefert wird. Zwei Lesarten sind möglich, und sie fallen auseinander:

* **Lesart A (Artefakt im Repo):** Zähler = 0, für jeden denkbaren Nenner. Unter dieser Lesart hält die Bedingung nicht — und das ist repo-first entscheidbar.
* **Lesart B (Lieferung an den Orchestrator im Cockpit-Thread):** Zähler nicht messbar, Nenner nicht messbar. Unter dieser Lesart ist die Bedingung nicht entscheidbar.

Da der Spec die Lesart nicht festlegt und der Nenner unter **beiden** Lesarten unbekannt bleibt, ist das Gesamturteil `cannot-be-determined`. Die Frage nach der Lesart steht als F1 in Abschnitt 11. Beide Teilergebnisse stehen oben ausgeschrieben, damit niemand das mildere davon für das ganze hält.

---

## 5. Bedingung 4

> kein Cockpit ungefragt Code oder Git-Zustand verändert hat;

**Urteil: holds** für den Git-Zustand der gemessenen Repositories.

**Entscheidet:**

```
git branch -r | sed 's|origin/||' | awk -F/ '{print $1}' | sort | uniq -c
git log --pretty='%an <%ae>' origin/master | sort | uniq -c | sort -rn
git -C /workspace/vibemind-os branch -r | grep -ci cockpit
```

**Gemessen im Superprojekt:** 209 Remote-Branches (`git branch -r` listet 210 Zeilen, davon eine der `HEAD ->`-Zeiger), verteilt auf die Präfixe `codex/` (197), `claude/` (5), `feat/` (5), `backup/` (1), `master` (1). **Kein einziger Branch ist einer Cockpit-Session zugeordnet** — die elf Branches, deren Name „cockpit" enthält, sind Task-Branches unter `codex/<space>/task-…`, deren *Gegenstand* Cockpit-Ledger sind (z. B. `codex/governance/task-governance-0013-cockpit-approval-ledger-v1`). Auf `origin/master` gibt es 6 Autor-Identitäten, keine davon eine Cockpit-Session. In `vibemind-os` (Klon auf `760da810`): null Cockpit-Branches, drei Autoren, keiner eine Cockpit-Session.

**Strukturelle Absicherung:** `tools/v1_governance/models.py` lehnt eine schreibende Cockpit-Session hart ab — `if session_type == "space-cockpit" and writes_allowed: raise GovernanceError("space-cockpit sessions are read-only")`. Cockpits können unter dem Validator gar keinen Schreib-Scope bekommen.

**Grenzen des Urteils, ausdrücklich:**

1. Gemessen ist der **Git-Zustand** von `Vibemind_V1` und `vibemind-os`. Nicht-Git-Wirkungen (Laufzeit, externe Systeme, Datenbanken) sind repo-first prinzipiell unsichtbar.
2. `openfang` und `DaveFelix-Coding-Engine` wurden nicht geklont und nicht gemessen.
3. Das Urteil ruht auf **Abwesenheit** jeder cockpit-attribuierbaren Spur. Das ist die stärkste Form, die dieses Repo für diese Bedingung hergibt: es gibt keinen Commit, keinen Branch und keinen PR, den man einem Cockpit zuordnen könnte, also auch keinen ungefragten.
4. Das Wort „ungefragt" wurde nicht separat geprüft, weil es gegenstandslos ist, solange der Zähler der Cockpit-Änderungen 0 ist.

---

## 6. Bedingung 5

> jeder Implementierungstask auf ein Parent-Cockpit, einen dauerhaften Request und eine gültige Authority verweist;

**Urteil: cannot-be-determined.** Die drei strukturellen Teile sind vollständig erfüllt; das Urteil hängt an einer Auslegungsfrage, die der Spec-Text nicht entscheidet.

**Population: Implementierungstasks.** Nicht Cockpits. Bedingung 2 wurde getrennt gemessen (Abschnitt 3).

### 6.1 Die drei strukturellen Teile

**Entscheidet:** `docs/governance/session-requests/*.json`.

```
python - <<'EOF'
import json,glob,os
files=sorted(glob.glob('docs/governance/session-requests/*.json'))
valid={c['cockpit_session_id'] for c in json.load(open('docs/governance/session-portfolio-registry-v1.json'))['cockpits']}
bad=[]
for f in files:
    d=json.load(open(f))
    if d['parent_cockpit'] not in valid: bad.append(('parent',f))
    if d['request_reference']!='task-request:'+d['session_id']: bad.append(('reqref',f))
    if not d['approval_reference'].strip(): bad.append(('auth',f))
print(len(files),bad)
EOF
```

**Gemessen (Stand `9815322`): 54 Session-Requests.**

* **Parent-Cockpit:** 54 von 54 tragen `parent_cockpit`, und jeder Wert ist eine der 22 registrierten Cockpit-IDs. Null Fehlzuordnungen.
* **Dauerhafter Request:** 54 von 54 tragen `request_reference`, und in **allen 54** Fällen lautet sie exakt `task-request:<session_id>` — die Referenz zeigt auf die Datei, in der sie steht. Kein toter Verweis.
* **Authority vorhanden:** 54 von 54 tragen eine nichtleere `approval_reference`, alle passen auf `APPROVAL_REFERENCE_PATTERN` in `tools/v1_governance/models.py`.

Alle drei Verweise existieren also für jeden Task. Wäre die Bedingung als reine Existenzforderung zu lesen, hielte sie.

### 6.2 Die Klassenfrage — selbst gezählt

```
python - <<'EOF'
import json,glob,collections
tab=collections.Counter()
for f in sorted(glob.glob('docs/governance/session-requests/*.json')):
    d=json.load(open(f))
    cls=d['approval_reference'].split(':')[0]
    tab[('routine' if d['risk_class'] in ('docs','code') else 'höher:'+d['risk_class'], cls)]+=1
for k,v in sorted(tab.items()): print(k,v)
EOF
```

**Gemessen:**

| Population | `claude-user-message:` | `standing-autonomy:v1` |
|---|---|---|
| Routine (`risk_class` ∈ {`docs`, `code`}), n=50 | **44** | 6 |
| Höhere Risikoklassen (`deployment` 2, `destructive` 1, `database-migration` 1), n=4 | 4 | 0 |

**44 von 50 Routine-Tasks tragen eine per-task User-Nachricht als Authority, wo Abschnitt 6 `standing-autonomy:v1` vorschreibt.** Die vom Orchestrator berichtete Zahl „44 von 50" trifft heute exakt zu — aber nicht mehr auf dieselbe Grundgesamtheit: die Dateizahl ist inzwischen 54, nicht 50, und die 4 zusätzlichen Dateien sind die vier Requests höherer Risikoklasse, für die eine request-spezifische User-Authority **korrekt** ist. Der Befund ist also weder gewachsen noch geschrumpft; er ist unverändert 44/50 und betrifft nur die Routine-Population.

**Eine Präzisierung am Auftragstext.** Der Auftrag nennt den einen Zeitstempel `…@2026-08-13T13:09:00Z`. Auf genau diesen entfallen aber nur **32** der 54 Requests. Wer nur nach diesem Zeitstempel zählt, misst 32 und hält es für einen Widerspruch zu den 44.

*Orchestrator-Korrektur vom 2026-08-18, nach dem Merge nachgezählt:* Der Absatz stand hier zunächst mit „elf verschiedene Zeitstempel" und einer Aufschlüsselung, die die 44 mit den Zahlen der Gesamtpopulation belegt. Beides ist falsch, und zwar in zwei Richtungen. Gemessen über alle 54 Requests: **48** tragen eine `claude-user-message:`-Referenz, verteilt auf **zehn** verschiedene Zeitstempel (13.08. 13:09 → 32, 14.08. 13:45 → 3, 15.08. 11:38 → 3, 16.08. 15:45 → 2, 17.08. 07:02 → 2, 17.08. 11:36 → 2, je 1 an vier weiteren; Summe 48). Die **44 der Routine-Population** verteilen sich dagegen auf nur **acht** Zeitstempel (32, 3, 2, 2, 2, 1, 1, 1), weil zwei Zeitstempel ausschließlich von höheren Risikoklassen getragen werden (`…@2026-08-13T19:42:00Z`, `…@2026-08-17T09:35:00Z`) und zwei weitere sich zwischen beiden Populationen aufteilen. Die inhaltliche Aussage — die 44 sind keine Folge eines einzigen Zeitstempels — bleibt unverändert richtig; die beiden Zahlen dahinter waren es nicht.

Die 6 korrekt getragenen Routine-Tasks sind `task-deployment-0018`, `task-git-0039`, `task-governance-0036` (dieser Task), `task-governance-0037`, `task-observability-0012`, `task-research-0007` — durchweg die jüngsten. Die Praxis hat sich also bereits gedreht; die 44 sind Altbestand.

### 6.3 Was der Text zu „gültig" sagt — und was nicht

Die entscheidende Frage: Macht eine **klassenfalsche, aber echte** Authority-Referenz Bedingung 5 unwahr, oder verlangt Bedingung 5 nur, dass überhaupt eine gültige Authority referenziert ist?

Gelesen wurden beide maßgeblichen Stellen.

**Abschnitt 12, Bedingung 5** sagt: *„eine gültige Authority"*. Das Wort „gültig" wird an keiner Stelle des Spec definiert. Abschnitt 12 kennt keine Klassenzuordnung und keinen Verweis auf Abschnitt 6.

**Abschnitt 6, Autonomievertrag**, sagt zwei Dinge:
> „Für Routine-`docs`/`code` wird `approval_reference: standing-autonomy:v1` verwendet; eine synthetische per-task User-Freigabe wird nicht erzeugt."

Das ist eine **Verwendungsregel und ein Erzeugungsverbot**. Es ist keine Gültigkeitsaussage: der Satz sagt nicht, dass eine per-task User-Freigabe *ungültig* ist, sondern dass sie *nicht erzeugt werden soll*. Und das Verbot trifft ausdrücklich die **synthetische** Freigabe — eine Freigabe also, die es in Wahrheit nicht gibt. Ob die 44 Referenzen synthetisch sind, kann das Repository nicht sagen: sie zeigen auf User-Nachrichten außerhalb des Repos.

Damit ergibt sich ein dreiteiliger Befund:

1. **Der Text stützt keine der beiden Lesarten eindeutig.** Für die strenge Lesart spricht, dass Abschnitt 6 für Routine-Arbeit genau eine Klasse benennt und die Alternative verbietet; für die milde Lesart spricht, dass Abschnitt 12 nur „gültig" verlangt, „gültig" nirgends an eine Klasse gebunden wird, und Abschnitt 6 das Verbot auf *synthetische* Freigaben beschränkt statt auf die Klasse als solche.
2. **Die Werkzeugebene folgt der milden Lesart** — `APPROVAL_REFERENCE_PATTERN` akzeptiert alle drei Klassen für jede Risikoklasse und beschränkt nur `standing-autonomy:v1` auf `docs`/`code`. Das ist eine Implementierungstatsache, kein Spec-Argument, und wird hier nicht als eines verwendet.
3. **Die Frage, die beide Lesarten trennt, ist repo-first ohnehin nicht beantwortbar**: ob die 44 Referenzen echte User-Nachrichten bezeichnen oder synthetisch erzeugt wurden. Genau daran hängt, ob Abschnitt 6 überhaupt verletzt ist.

**Deshalb: cannot-be-determined.** Das Urteil wird nicht auf die milde Lesart gesetzt, obwohl sie dem Programm schmeichelt und obwohl die Werkzeuge sie stützen. Die Auslegungsfrage steht als F2 in Abschnitt 11, die Tatsachenfrage als F3.

---

## 7. Bedingung 6

> Worktrees, Branches, Handoffs und PRs eindeutig zugeordnet sind;

**Urteil: does-not-hold.** Zwei der vier Glieder halten, zwei nicht.

### 7.1 Branches — hält

```
python -c "
import json,glob,collections
b=collections.Counter(json.load(open(f))['branch'] for f in glob.glob('docs/governance/session-requests/*.json'))
print(len(b),[k for k,v in b.items() if v>1])
"
```

54 Requests, 54 verschiedene Branch-Namen, keine Kollision. Alle folgen `codex/<domain>/<task-id>` gemäß Abschnitt 7; `BRANCH_PATTERN` in `models.py` erzwingt es für jede schreibende Session.

### 7.2 PRs — hält im Superprojekt, mit vollständig aufgelöstem Rest

```
python - <<'EOF'
import json,glob,subprocess,re
reqs=[json.load(open(f)) for f in sorted(glob.glob('docs/governance/session-requests/*.json'))]
m={}
for l in subprocess.run(['git','log','--merges','--pretty=%H|%s','origin/master'],capture_output=True,text=True).stdout.splitlines():
    h,s=l.split('|',1)
    g=re.match(r'Merge pull request #(\d+) from Flissel/(.+)$',s)
    if g: m.setdefault(g.group(2),[]).append((int(g.group(1)),h))
print(sum(1 for d in reqs if d['branch'] in m),'von',len(reqs))
print([k for k,v in m.items() if len(v)>1 and k.startswith('codex/')])
print([d['session_id'] for d in reqs if d['branch'] not in m])
EOF
```

**49 von 54** Request-Branches haben genau einen Merge-PR im Superprojekt. **Kein Branch ist zweimal gemergt.** Die fünf ohne Superprojekt-Merge sind restlos aufgeklärt:

| Task | Lage |
|---|---|
| `task-git-0028-vibemind-os-child-gitlink-lifts-v1` | gemergt in `vibemind-os#139` (`c5cba96`), Register §3.3 |
| `task-openfang-0008-mcp-env-whitelist-v1` | gemergt in `openfang#17` (`5d38662`), Register §3.4 Zeile 585 |
| `task-coding-0008-ci-unmask-continue-on-error-v1` | admittiert, aber **blockiert und nie gestartet** (§3.1s) — ein fehlender PR ist hier korrekt |
| `task-governance-0036-…` | dieser Task, in Arbeit |
| `task-governance-0037-…` | in Arbeit |

Die Zuordnung ist damit auf der PR-Ebene eindeutig und lückenlos, sobald man Service-Repo-Merges mitzählt.

### 7.3 Handoffs — hält nicht

```
python - <<'EOF'
import json,glob,os,re
allh=[p for d in ('docs/operations','docs/governance/session-handoffs','docs/governance/handoffs') for p in os.listdir(d)]
for f in sorted(glob.glob('docs/governance/session-requests/*.json')):
    sid=json.load(open(f))['session_id']
    t=re.match(r'^(task-[a-z0-9]+-\d+[a-z]?)',sid).group(1)
    if not [p for p in allh if p.startswith(t) or t+'-' in p]: print(sid)
EOF
```

**42 von 54 Requests haben ein Handoff-Artefakt, 12 haben keines.** Zwei der zwölf sind laufende Sessions (0036, 0037), einer ist der blockierte `task-coding-0008` — bleiben **neun abgeschlossene Tasks ohne auffindbares Handoff** im Superprojekt:

`task-deployment-0016`, `task-deployment-0018`, `task-git-0026`, `task-git-0027`, `task-git-0028`, `task-integration-0005a`, `task-integration-0005b`, `task-observability-0012`, `task-openfang-0008`.

Ein zehnter Fall ist nur beinahe einer und wird deshalb nicht mitgezählt: `task-governance-0034` hat ein Handoff, aber es heißt `docs/operations/2026-08-17-task-governance-0034-validator-gitlink-coverage-handoff.md` und folgt damit nicht dem sonst durchgehaltenen Muster `<datum>-<task-id>-handoff.*`. Die Zuordnung ist inhaltlich da und nur der Konvention nach schief — ein milder Zuordnungsdefekt, kein fehlendes Artefakt.

Für `task-git-0028` wurde zusätzlich im `vibemind-os`-Klon gesucht (`find . -name "*task-git-0028*"`): kein Treffer. Der Spec verlangt in Abschnitt 7 von jeder Implementierungs-Session einen Handoff und in Abschnitt 11, dass Ergebnisse ohne vollständigen Handoff nicht merge-ready sind. Neun gemergte Tasks ohne auffindbaren Handoff sind keine eindeutige Zuordnung.

### 7.4 Worktrees — hält nicht, und zwar strukturell

**Entscheidet:** die Schemata selbst.

```
grep -n "worktree" tools/v1_governance/models.py tools/v1_governance/handoff.py
grep -l "worktree" docs/governance/session-requests/*.json
```

**Beide Suchen liefern nichts.** Weder das Session-Request-Schema (`models.py`) noch das Handoff-Schema (`handoff.py`) kennt ein Worktree-Feld, und kein einziger der 54 Requests nennt einen Worktree — obwohl Abschnitt 6 des Spec den Worktree ausdrücklich als Pflichtbestandteil des Task-Briefs führt („Base-Ref, Branch und Worktree") und Abschnitt 7 „genau einen isolierten Worktree pro Repository" verlangt.

Worktrees sind lokal und flüchtig; `python -m tools.v1_governance audit --repo .` zeigt sie nur für den gerade laufenden Klon. Eine dauerhafte Zuordnung „Worktree ↔ Task" existiert im Repository nicht und kann dort in der heutigen Form auch nicht entstehen.

**Gesamturteil der Bedingung: does-not-hold.** Branches und PRs sind eindeutig zugeordnet; Handoffs haben neun Lücken; Worktrees haben überhaupt keine Zuordnung. Die Bedingung nennt alle vier konjunktiv.

---

## 8. Bedingung 7

> der Haupt-Orchestrator Abhängigkeiten und Merge-Reihenfolge nachweisbar pflegt;

**Urteil: holds.**

**Entscheidet:** die Felder `dependencies` und `merge_position` in jedem Request, `docs/governance/session-request-queue-v1.md` §3.3, und `tools/v1_governance/pr_gate.py`.

**Gemessen:**

* **Erhoben:** Alle 54 Requests tragen `dependencies` und `merge_position`; `merge_position` ist im Schema für `schema_version: 2` pflichtig (`models.py`). 35 Requests deklarieren mindestens eine Abhängigkeit, 19 deklarieren ausdrücklich die leere Liste — nicht „fehlend", sondern bewusst leer, wie Abschnitt 5 des Spec es für leere Listen verlangt.
* **Belegt:** `session-request-queue-v1.md` §3.3 führt eine Tabelle „Abgeschlossene Implementierungs-Tasks" mit 33 Zeilen, jede mit PR-Nummer und Merge-Commit, inklusive der Service-Repo-PRs (`vibemind-os#139`, `openfang#18`, `DaveFelix-Coding-Engine#3`). §3.1 führt die admittierten Tasks mit Parent-Cockpit, Branch und Merge-Stufe.
* **Nachgemessen — die Ordnung selbst:**

```
python - <<'EOF'
import json,glob,subprocess,re
R={json.load(open(f))['session_id']:json.load(open(f)) for f in glob.glob('docs/governance/session-requests/*.json')}
M={}
for l in subprocess.run(['git','log','--merges','--pretty=%H|%ct|%s','origin/master'],capture_output=True,text=True).stdout.splitlines():
    h,ct,s=l.split('|',2)
    g=re.match(r'Merge pull request #(\d+) from Flissel/(.+)$',s)
    if g: M[g.group(2)]=int(ct)
for sid,d in R.items():
    for dep in d.get('dependencies') or []:
        dd=R.get(dep.get('session_id') if isinstance(dep,dict) else dep)
        if not dd: continue
        a,b=M.get(d['branch']),M.get(dd['branch'])
        if a and (not b or b>a): print('PRÜFEN:',sid,'<-',dd['session_id'])
EOF
```

Das liefert **zwei** Treffer, und beide lösen sich bei Betrachtung auf:

1. `task-git-0029` ← `task-git-0028`: Die Abhängigkeit ist in `vibemind-os#139` gemergt, nicht im Superprojekt. Sachlich vor dem Dependent.
2. `task-git-0031` ← `task-git-0030`: Der Superprojekt-PR #234 des Vorgängers landete am 18.08. **nach** PR #199 des Nachfolgers am 16.08. Nachgesehen mit `git show --stat 464d385`: **#234 enthält ausschließlich die beiden Handoff-Dokumente** (156 Zeilen, zwei Dateien unter `docs/operations/`). Der substanzielle Pin-Lift lag in `vibemind-os#141` (`a9a48af`) und war vor #199 gemergt. §3.1ai der Queue nennt #234 selbst „nachgeholte `task-git-0030`-Evidence".

**Null echte Reihenfolgeverletzungen.** Beide Treffer sind Artefakte der Zwei-Repo-Staffelung, nicht der Pflege.

* **Erzwungen:** `pr_gate.py` prüft das Gate gegen Request und Handoff, inklusive Abhängigkeiten und Risikoklassen-Authority.

Die Bedingung verlangt „nachweisbar pflegt". Das ist erfüllt: die Pflege ist im Repo, sie ist maschinell nachrechenbar, und die Nachrechnung geht auf.

---

## 9. Bedingung 8

> OpenFangs Execution-, Provider-, Cost-, Approval- und Evidence-Grenzen eindeutig dokumentiert und taskweise verifiziert sind;

**Urteil: does-not-hold.** Die Bedingung fordert zwei Dinge — *eindeutig dokumentiert* **und** *taskweise verifiziert*. Beide scheitern, unabhängig voneinander.

**Entscheidet:** `shared/contracts/openfang-mcp-authority-v1.json`.

### 9.1 Die drei falschen Aussagen — selbst nachgemessen

Der Auftrag nennt sie; sie wurden hier **nicht** übernommen, sondern gegen den Pin nachgelesen, den der Contract selbst führt.

```
python -c "import json;d=json.load(open('shared/contracts/openfang-mcp-authority-v1.json'));print(d['source_pins']);print(json.dumps(d['spaces']['agentfarm'],indent=2))"
git -C /workspace/vibemind-os show 760da8105c1cdca407dc5904b6e1e0e42af4d265:config/space_agent_registry.yml | sed -n '288,318p'
```

Der Contract deklariert `source_pins.vibemind-os: 760da8105c1cdca407dc5904b6e1e0e42af4d265` und zitiert für `spaces.agentfarm` den Locator `vibemind-os/config/space_agent_registry.yml:289-317`. Der Klon steht exakt auf diesem Pin. Gelesen an genau dieser Stelle:

| Feld | Contract behauptet | Registry bei `760da81` | |
|---|---|---|---|
| `agent_role` / `agent` | `"vibemind"` | `null` | **falsch** |
| `enabled` | `false` | `true` | **falsch** |
| `mcp_servers` | `[]` | `[captain-cook]` | **falsch** |
| `manifest` | `null` | kein `manifest_path` | stimmt |

Der **Locator stimmt** — Zeile 289 ist `agentfarm:`, Zeile 317 ist `agentfarm.status`. Der Contract zeigt also präzise auf die Stelle, an der er widerlegt wird. Drei von vier Aussagen des Eintrags sind gegen den Baum falsch, den der Contract selbst benennt.

`task-git-0039` hat sie so gemessen und bewusst stehen lassen, weil die Korrektur eine Autorisierungsentscheidung ist, die beim User liegt (`docs/operations/2026-08-18-task-git-0039-handoff.yaml`, Finding `repinned_contract_now_asserts_three_false_things_about_agentfarm`). Diese Messung bestätigt den Befund unabhängig.

**Was das für Bedingung 8 bedeutet:** „Eindeutig dokumentiert" heißt mindestens „nicht nachweislich falsch". Ein Autoritäts-Contract, der am eigenen deklarierten Pin in drei von vier Feldern eines Space widerlegt wird, dokumentiert die Execution-Grenze dieses Space nicht — er dokumentiert sie falsch. Die Bedingung fällt daran, und zwar unabhängig davon, ob man den offenen Zustand für richtig oder falsch hält: **dass der Befund bewusst offen steht, ändert nichts daran, dass er offen steht.** Bedingung 8 misst den Zustand, nicht die Absicht.

### 9.2 Die fünf Grenzen einzeln

```
python -c "
import json;d=json.load(open('shared/contracts/openfang-mcp-authority-v1.json'))
print([g['kind'] for g in d['gaps']])
print(json.dumps(d['registration_authority'],indent=2)[:400])
"
```

| Grenze | Befund |
|---|---|
| **Execution** | Am besten belegt: `registration_authority` benennt Registrierungsmechanismus, Agent-Scope-Mechanismus und die Fail-closed-Semantik einer leeren Allowlist. Aber sechs der zwölf `gaps` betreffen genau diese Grenze (`unregistered-but-scoped`, `template-only`, 2× `commented-out-but-scoped`, `dual-dispatch-coding`, `protected-manifest-not-generated`). Dokumentiert, aber mit offenen Löchern. |
| **Provider** | **Ausdrücklich als Lücke geführt**, nicht als Grenze: `gaps` enthält `static-provider-pinning` — „Generated manifests pin provider=openai model=gpt-4o-mini at generation time; under E1 the instance/provider/model binding belongs to OpenFang at execution time." Der Contract sagt selbst, dass die Provider-Grenze nicht dort liegt, wo sie liegen sollte, und verweist die Klärung an `task-brain-0018`. |
| **Cost** | Kommt ausschließlich als `cost_ref` in `required_provenance` von sechs Golden-Path-Einträgen vor. Das ist eine **Forderung an Envelopes**, keine dokumentierte Kostengrenze: kein Budget, kein Limit, kein Träger, keine Durchsetzung. |
| **Approval** | Dasselbe Bild: `approval_ref` als `required_provenance`, sonst nichts. |
| **Evidence** | Der Contract führt die fehlende Evidence selbst auf: „Runtime enforcement evidence that bubble.create and idea.connect envelopes carry approval_ref and cost_ref provenance" steht unter dem, was **noch zu erbringen** ist. Die Evidence-Grenze ist als Fehlstelle dokumentiert, nicht als Grenze. |

`scope_statement` sagt es selbst: *„Static authority only … No live registration, no runtime activation, no OpenFang mutation. Live claims are owned by task-integration-0005b."* — und `task-integration-0005b` ist ausweislich §3.3 fail-closed geendet (Runtime aus der Cloud-Session nicht erreichbar, Blocker B1).

### 9.3 „Taskweise verifiziert" — es gibt keinen Mechanismus

Gesucht wurde nach einem Verfahren, das je Task die fünf Grenzen prüft: im Request-Schema (`models.py`), im Handoff-Schema (`handoff.py`), im PR-Gate (`pr_gate.py`) und in den 54 Requests. **Es existiert kein Feld, kein Gate und kein Test, der pro Task eine OpenFang-Grenze verifiziert.** Die Verifikation, die stattfindet, ist die des jeweiligen Task-Gegenstands, nicht die der OpenFang-Grenzen.

Selbst wenn die Dokumentation vollständig wäre, fiele die Bedingung an dieser zweiten Hälfte.

---

## 10. Bedingung 9

> mindestens ein vollständiger Cockpit→Task→PR→Merge→Verifikation-Zyklus abgeschlossen ist.

**Urteil: does-not-hold.** Kein einziger Zyklus ist auf allen fünf Gliedern repo-belegt. Zwei kommen nahe, jeder scheitert an einem anderen Glied — und zwar an einem anderen.

### 10.1 Kandidat A — `task-research-0007` (scheitert am ersten Glied)

| Glied | Beleg | |
|---|---|---|
| Cockpit | `cockpit-research`, registriert, Approval-Ledger-Eintrag, `ccr-session:session_01QNovqXMThUdDuUVjgbow7Y@2026-08-14T13:52:16Z` | ✅ |
| Cockpit **→** Task | **nur deklariert**: `parent_cockpit: cockpit-research` im Request. `cockpit-next-task-register-v1.json` führt `cockpit-research` als `row_type: "planning-gap"` mit dem Grund „no new bounded next implementation task is evidenced" | ❌ |
| Task | `docs/governance/session-requests/task-research-0007-provenance-reverification-760da81-v1.json`, validiert | ✅ |
| PR | **#261** | ✅ |
| Merge | `658557cb828840e7ae729a717d4cf38cd42aeb75` | ✅ |
| Verifikation | `session-request-queue-v1.md` §3.1ba: „Post-Merge nachgemessen: Zieltest 16 passed, `tests/v1_governance` 273 passed, `manifest validate` exit 0 mit den drei bekannten Legacy-Warnungen." | ✅ |

Vier von fünf Gliedern sind git-belegt. Der Cockpit→Task-Pfeil ist es nicht: das Register sagt für dieses Cockpit ausdrücklich, dass **kein** Folgetask evidenziert ist. Der `parent_cockpit`-Eintrag ist eine Deklaration im Request, kein Beleg einer Cockpit-Empfehlung.

### 10.2 Kandidat B — `task-coding-0005` (scheitert am letzten Glied)

| Glied | Beleg | |
|---|---|---|
| Cockpit | `cockpit-coding`, `ccr-session:session_01LGsUreNkJQ9Z95HG3FU5SB@2026-08-14T13:51:49Z` | ✅ |
| Cockpit **→** Task | `session-request-queue-v1.md` §3.1d Punkt 1, wörtlich: „**`task-coding-0005-code-event-binding-reconciliation-v1`** (Empfehlung `cockpit-coding`)"; §3.1 Tabelle führt `cockpit-coding` als Parent | ✅ |
| Task | Request validiert, Session `session_01UcwQKJAK1PePP5BVri8wWk` (§3.1) | ✅ |
| PR | **#181** | ✅ |
| Merge | `93ca0edfa2115faa21a48122e05109eec8762000` (§3.3) | ✅ |
| Verifikation | **keine Post-Merge-Verifikation im Repository auffindbar** | ❌ |

Dies ist der einzige Zyklus, dessen **Cockpit→Task**-Pfeil im Repository dokumentiert ist. Aber für PR #181 ist keine Post-Merge-Prüfung festgehalten; der Absatz „Einsammlung der Großrunde" in §3.3 verifiziert #174, nicht #181.

### 10.3 Wie selten die Verifikation überhaupt ist

```
grep -rn -i "post-merge\|Post-Merge verifiziert" docs/governance/session-request-queue-v1.md
```

Das Repository hält für **genau drei** von 49 gemergten Superprojekt-Tasks eine ausgeführte Post-Merge-Verifikation fest: §3.1ai (minibook-Kette, „Gitlink `da2a29a`, `audit` sauber, drei Legacy-Warnungen, Suite 266"), §3.1aa/981 (`task-git-0037`) und §3.1ba (`task-research-0007`). Alle drei sind jung und alle drei sind orchestrator-abgeleitete Pin-/Provenance-Tasks — keiner hat einen belegten Cockpit→Task-Pfeil. Umgekehrt hat der einzige Task mit belegtem Cockpit→Task-Pfeil keine Verifikation. **Die beiden Enden des geforderten Zyklus überschneiden sich im Repository nirgends.**

### 10.4 Zum Urteil

Unter der strengen Lesart — der erste Pfeil meint den Ablauf aus Abschnitt 5 Schritte 7–8, das Cockpit formuliert den empfohlenen ersten Task und legt dafür die Implementierungs-Session an — ist kein Zyklus vollständig. Das ist die Lesart, die der Wortlaut „Cockpit→Task" mit Abschnitt 5 im Rücken nahelegt, und darauf steht das Urteil.

Unter der milden Lesart — der Pfeil ist erfüllt, sobald der Task ein gültiges `parent_cockpit` deklariert (Abschnitt 7: „besitzt genau ein Parent-Cockpit") — wäre `task-research-0007` ein vollständiger Zyklus, und die Bedingung hielte. Diese Auslegungsfrage steht als F4 in Abschnitt 11. Das Urteil wird bewusst auf die strenge Lesart gesetzt, nicht auf die für das Programm günstigere: die Bedingung nennt einen *Zyklus*, und ein Zyklus, dessen erster Pfeil nur eine Feldangabe im Zieldokument ist, ist keiner.

---

## 11. Korrekturen an früheren Angaben

Drei Angaben aus dem Umfeld dieses Auftrags weichen von der Messung ab. Alle drei sind klein; alle drei stehen hier, damit sie nicht weiterwandern.

1. **„44 von 50" ist richtig, der zugehörige Zeitstempel nicht.** Die Zahl 44/50 trifft die Routine-Population heute exakt. Sie entfällt aber auf **acht verschiedene** `claude-user-message:`-Zeitstempel, nicht auf den einen genannten `…@2026-08-13T13:09:00Z` — auf den entfallen 32 von 54. (Über alle 54 Requests sind es 48 Referenzen auf zehn Zeitstempel. Diese Stelle sagte zunächst „elf"; korrigiert vom Orchestrator nach eigener Nachzählung, siehe 6.2.) Siehe 6.2.
2. **„die Dateizahl ist seither gewachsen" trifft zu, der Befund ist dadurch nicht gewachsen.** 50 → 54 Requests; die vier neuen sind sämtlich höhere Risikoklassen, für die eine request-spezifische Authority korrekt ist. Der Befund bleibt 44/50.
3. **Der Nenner von Bedingung 3 ist nicht „kleiner als 22", sondern unbekannt.** Der Auftrag erwartet eine kleinere Startmenge. Das Repository evidenziert 22 *Erstellungen* und **null** Starts und widerspricht der Gleichsetzung an drei Stellen ausdrücklich. Die Startmenge ist repo-first weder kleiner noch gleich 22 — sie ist nicht bestimmbar. Siehe 4.1.

## 12. Interaktivität — geprüft, nicht angetastet

Der Auftrag hält fest, dass Interaktivität **keine** der neun Bedingungen ist, und verbietet, daran zu rühren. Beides wurde eingehalten; hier steht nur das Messergebnis.

```
grep -n -i "interaktiv" docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md
sed -n '74,82p' tools/v1_governance/portfolio.py
```

Das Wort kommt im Spec an **drei** Stellen vor, und keine davon ist Abschnitt 12:

* **Zeile 5** (Ziel): „mindestens ein dauerhaftes, **interaktives** Codex-Cockpit pro Space" — eine Zielbeschreibung.
* **Zeile 13** (Abschnitt 3): „Cockpit-Session: dauerhaft, **interaktiv** und zunächst read-only" — eine *definitorische Eigenschaft* der Sessionart.
* **Zeile 175** (Abschnitt 7): „bestätigt den Task-Plan **interaktiv**" — ein Verfahrensschritt der Implementierungs-Session, der im selben Spec mit Abschnitt 6 („ohne per-session User-Interaktion" für Routine-`docs`/`code`) in Spannung steht.

**Abschnitt 12 macht Interaktivität an keiner Stelle bindend.** Keine der neun Bedingungen nennt sie, und keine erreicht sie über einen Zwischenschritt: Bedingungen 1–4 messen Registrierung, Authority, Lieferung und Nicht-Veränderung, nicht Interaktivität. Die einzige Berührung ist die Definition in Zeile 13 — wer „Cockpit" liest, liest eine per Definition interaktive Session mit. Das ist eine Begriffsbestimmung, keine messbare Bedingung, und es macht Interaktivität nicht zu einem Prüfgegenstand von Abschnitt 12.

`tools/v1_governance/portfolio.py:81` definiert `_INTERACTIVITY_EVIDENCE_CLASSES` als das bewusste Singleton `{"not-git-evidenced"}`; der Kommentar darüber begründet es: Interaktivität hat keine durable Referenzform. Das ist mit Abschnitt 12 konsistent und wird hier **nicht** angetastet. Es wird keine Evidence-Klasse vorgeschlagen — das wäre eine Designänderung und liegt außerhalb der Autorität dieses Tasks.

## 13. Offene Fragen an den User

Diese Fragen werden hier **nicht** beantwortet. Jede entscheidet mindestens ein Urteil oben.

**F1 — Wohin liefert ein Cockpit? (entscheidet Bedingung 3)**
Muss der Repo-first Audit und der Space Brief als Artefakt im Repository liegen, oder genügt die Lieferung an den Orchestrator im Cockpit-Thread? Unter der Artefakt-Lesart ist der Zähler 0 von 22 und die Bedingung fällt; unter der Thread-Lesart ist sie nicht messbar. Das Ausgabeschema aus Abschnitt 5 des Spec existiert im Repo für kein einziges Cockpit.

**F2 — Was heißt „gültige Authority"? (entscheidet Bedingung 5)**
Macht eine klassenfalsche, aber echte Authority-Referenz Bedingung 5 unwahr, oder verlangt sie nur, dass überhaupt eine gültige Authority referenziert ist? Abschnitt 12 definiert „gültig" nicht; Abschnitt 6 formuliert eine Verwendungsregel und ein Verbot **synthetischer** per-task-Freigaben, keine Gültigkeitsaussage. Der Text entscheidet es nicht.

**F3 — Sind die 44 Referenzen echt? (Tatsachenfrage unter F2)**
Bezeichnen die 44 `claude-user-message:`-Referenzen der Routine-Tasks tatsächlich gesendete User-Nachrichten, oder wurden sie synthetisch erzeugt? Nur im zweiten Fall greift das Verbot aus Abschnitt 6 unmittelbar. **Wer es auflösen kann:** der User, aus dem Verlauf von `session_01SdA3ftgP3wciDbcFzKw4uk`. Dasselbe gilt für die 22 Cockpit-Freigaben aus Bedingung 2.

**F4 — Was ist der erste Pfeil des Zyklus? (entscheidet Bedingung 9)**
Meint „Cockpit→Task" den Ablauf aus Abschnitt 5 Schritte 7–8 (das Cockpit empfiehlt den Task und legt die Session an), oder genügt ein deklariertes `parent_cockpit` nach Abschnitt 7? Unter der strengen Lesart ist kein Zyklus vollständig; unter der milden ist `task-research-0007` einer.

**F5 — Was geschieht mit den drei falschen agentfarm-Aussagen? (Voraussetzung für Bedingung 8)**
`shared/contracts/openfang-mcp-authority-v1.json` behauptet für `spaces.agentfarm` `agent_role "vibemind"`, `enabled false`, `mcp_servers []`, während die Registry am selben deklarierten Pin `760da81` `agent: null`, `enabled: true`, `mcp_servers: [captain-cook]` sagt. `task-git-0039` hat den Befund bewusst offengelassen, weil die Korrektur eine Autorisierungsentscheidung ist. Solange er offen ist, kann Bedingung 8 nicht halten.

**F6 — Sollen Worktrees dauerhaft zugeordnet werden? (entscheidet ein Glied von Bedingung 6)**
Abschnitt 6 des Spec führt den Worktree als Pflichtbestandteil des Task-Briefs, aber weder Request- noch Handoff-Schema kennt ein Worktree-Feld. Entweder fehlt das Feld, oder Bedingung 6 meint mit „Worktrees … eindeutig zugeordnet" etwas anderes als eine dauerhafte Aufzeichnung.

**F7 — Neun gemergte Tasks ohne auffindbaren Handoff.** (entscheidet ein Glied von Bedingung 6)
Abschnitt 11 des Spec sagt, Ergebnisse ohne vollständigen Handoff seien nicht merge-ready. Für `task-deployment-0016`, `task-deployment-0018`, `task-git-0026`, `task-git-0027`, `task-git-0028`, `task-integration-0005a`, `task-integration-0005b`, `task-observability-0012` und `task-openfang-0008` ist im Superprojekt keiner auffindbar; für `task-git-0028` auch nicht in `vibemind-os`. Liegen sie anderswo, oder fehlen sie?

## 14. Was außerhalb des Repositorys liegt

Zusammengefasst, weil drei Urteile daran hängen:

| Evidenz | Entscheidet | Wer hält sie |
|---|---|---|
| 22 CCR-Cockpit-Session-Verläufe (`session_01RPNeXk…` ff., §2.1 der Queue) | Bedingung 3, Nenner | User / Claude-Code-Kontoverlauf |
| 22 Cockpit-Threads (`cockpit-external-observations-v1.json`) | Bedingung 3, Zähler unter Lesart B | User / Codex- und Claude-Threads |
| Existenz der User-Nachrichten hinter 44 + 22 Authority-Referenzen | Bedingungen 2 und 5 | User, Session `session_01SdA3ftgP3wciDbcFzKw4uk`, Thread `019fa01e-…` |
| OpenFang-Laufzeit (Registrierung, Provider-Binding, Kosten, Approval-Envelopes) | Bedingung 8 | User, OpenFang-Host (`api_listen 127.0.0.1:4200`) |

## 15. Gates dieser Messung

Wörtlich, wie ausgeführt auf dem Task-Branch:

```
python -m tools.v1_governance audit --repo .
→ exit 0; dirty_paths [], branch codex/governance/task-governance-0036-…, upstream origin/master

python -m tools.v1_governance manifest validate --repo .
→ exit 0; genau drei declared-without-gitlink-Warnungen
  (external/minibook, spaces/desktop/Automation_ui/moire_tracker, spaces/flowzen/flowzen)

python -m pytest tests/v1_governance -q
→ 273 passed (pytest 8.4.2 aus tools/v1_governance/requirements.txt)
```

Das `vibemind-os`-Submodul blieb im Superprojekt-Working-Tree uninitialisiert; die Submodul-Messung in Abschnitt 9.1 lief in einem separaten Klon. Diese Messung ändert keine Datei außerhalb von `docs/governance/` und `docs/operations/`.
