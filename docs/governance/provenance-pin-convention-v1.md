# Provenance-Pin-Konvention — programmweit (V1)

**Status:** programmweit verbindlich, Orchestrator-Disposition unter `standing-autonomy:v1`
**Datum:** 2026-08-17
**Abgeleitet aus:** `task-research-0004-provenance-pin-convention-v1`
**Fachliche Herleitung:** `docs/spaces/research/provenance-pin-convention-v1.md`
**Referenz-Enforcement:** `tests/contracts/research/test_research_provenance_pins_v1.py`

## Warum dieses Dokument existiert

`task-research-0004` hat die Konvention entschieden und belegt, konnte sie aber
nur für die Research-Contract-Familie festlegen: die Session hat keine Autorität
in `docs/governance/` — dieselbe Grenze, unter der `task-research-0003` es
abgelehnt hat, E14 selbst zu protokollieren. Ihr Handoff benennt die Lücke
ausdrücklich: ohne einen Governance-Eintrag hat die nächste Pin-Kette in einem
anderen Space keine Regel, sondern nur einen Präzedenzfall.

Dieses Dokument schließt die Lücke. Es hebt die Regel von einer Space-Konvention
zu einer Programmregel.

## Die Regel

> **Ein zitierter Pin wird einmal geschrieben — an dem Commit, an dem die
> Aussage tatsächlich nachgelesen wurde — und nie umgeschrieben. Ein späteres
> Nachlesen wird daneben protokolliert, nicht an seiner Stelle.**

Vier Pflichten, wörtlich aus der fachlichen Herleitung übernommen:

1. **`pin` ist write-once.** Er benennt den Commit, an dem jemand die Datei
   geöffnet hat. Eine Pin-Hebung berührt ihn nicht. Ein Refresh-Pass berührt ihn
   nicht. **Ein `sed` über SHAs ist ein Defekt, keine Pflege.**
2. **Jede Upstream-Referenz deklariert eine `role`.** `observation` hält fest,
   wo eine Aussage gelesen wurde. `binding` behauptet etwas darüber, was
   Upstream *jetzt* sagt. Nur `binding` trägt eine dauerhafte
   Re-Verifikationspflicht.
3. **Re-Verifikation ist additiv.** Ein Verifikations-Pass hängt einen Eintrag
   an, der den geprüften Pin, das Datum und je Referenz ein Ergebnis nennt —
   `holds`, `holds_with_locator_drift` oder `diverged`. Er editiert `pin` nie.
4. **Divergenz ist ein Befund, keine Lizenz.** Hält eine Aussage am geprüften
   Pin nicht mehr, protokolliert der Pass `diverged` und benennt, was sich
   geändert hat. Er passt **nicht** an, was der Contract behauptet, damit es zum
   neuen Upstream passt. Das ist eine eigene Änderung mit eigener Begründung und
   eigener Autorität.

## Geltungsbereich

Verbindlich für **alle** Spaces und alle Artefakte, die Upstream-Aussagen mit
einem Commit belegen: `shared/contracts/`, `tests/contracts/`, `docs/spaces/`,
`docs/operations/` sowie Handoffs.

Für Pin-Ketten (`cockpit-git`) folgt daraus konkret: **eine Gitlink-Hebung und
`repo-manifest.yaml` reichen nicht in Provenance hinein.** `expected_gitlink_pin`
und `evidence.parent_pin` sind Live-Stände und werden gehoben; zitierte
Beobachtungs-Pins sind es nicht und bleiben stehen. Ein Pin-Ketten-Task, der
Provenance-Zitate mitzieht, verfehlt seinen Auftrag.

## Was diese Disposition nicht tut

Sie schafft keine neue Autorität, lockert kein Gate und ändert keine
Risikoklasse. Sie ändert nichts daran, *was* irgendein Contract behauptet — nur,
*wie* dessen Provenienz ausgedrückt wird. Sie verpflichtet keinen bestehenden
Artefaktbestand zur Nachrüstung: bereits existierende Zitate ohne `role` bleiben
gültig, bis der zuständige Space sie im normalen Verlauf anfasst.

Sie ist eine **Orchestrator-Disposition**, kein User-Beschluss. Sie ist
begründet, dokumentiert und **jederzeit durch den User überstimmbar**; sie wurde
unter `standing-autonomy:v1` als Routine-`docs`-Arbeit getroffen, weil sie
Evidence-Hygiene regelt und keine Produkt-Architekturentscheidung ist. Wenn der
User sie anders will, wird sie ersetzt, nicht verteidigt.

## Belege, die die Entscheidung tragen

Aus dem Verifikations-Pass von `task-research-0004` über zwölf
Upstream-Referenzen:

- **Elf von zwölf** zeigen auf Dateien, die am Live-Pin **byte-identisch** sind
  — gleicher Blob-Hash, gleiche Zeilen.
- **Genau eine** ist gedriftet, und nur im Locator:
  `config/space_agent_registry.yml` von `lines 162-176` (`c5cba96`) auf
  `lines 162-203` (`731288b`), weil E9/E10 den Research-Block von 15 auf 42
  Zeilen erweitert hat. Alle drei Aussagen dieses Zitats gelten wörtlich weiter.

Unter einer Refresh-Konvention wären alle zwölf SHAs gewandert, der Diff hätte
wie Arbeit ausgesehen, und nichts davon wäre neu gewesen — die eine echte
Information wäre darin untergegangen.

Ein zweiter Befund derselben Session zeigt, dass die eigentliche Lücke nicht die
veralteten Pins waren: **zwei Referenzen trugen überhaupt keinen Anker.**
`context_policy.registry_evidence` behauptete live etwas über genau die eine
Datei, die sich bewegt hat, ohne Commit zum Nachprüfen; `report_persistence.artifact_side`
nannte eine Migration, die an keinem gepinnten Commit existierte. Die
`role`-Pflicht aus Regel 2 ist die Antwort darauf.

## Querverweise

- Fachliche Herleitung samt Abwägung: `docs/spaces/research/provenance-pin-convention-v1.md`
- Programm-Projektion und Task-Historie: `docs/governance/session-request-queue-v1.md`
- Charter und Delegationsgrenzen: `docs/governance/multi-session-program-charter-v1.md`
