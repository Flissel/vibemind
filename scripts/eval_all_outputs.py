"""Evaluate all generated HR/Roarboot output files for quality.

Runs _file_evaluate locally (no MCP roundtrip — direct function call) on
every .xlsx and .docx in C:/Users/User/Desktop/HR/. Each file gets an
appropriate intent string. Outputs a markdown quality report with scores,
issues per file, and an overall summary.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Bring _file_evaluate into scope
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vibemind-os" / "spaces" / "desktop"
                       / "Automation_ui" / "backend" / "moire_agents"))

from dotenv import load_dotenv
load_dotenv(HERE.parent / ".env")

from mcp_server_handoff import _file_evaluate  # type: ignore

HR = Path("C:/Users/User/Desktop/HR")
REPORT = HERE.parent / "results" / "quality_report.md"
JSON_OUT = HERE.parent / "results" / "quality_report.json"

# (filename_substring, expected_intent, source_data_description)
INTENTS: list[tuple[str, str, str]] = [
    # HR-Suite v1 (synthetic data, hardcoded)
    ("Mitarbeiter_Stammdaten",
     "HR-Stammdatenliste mit allen relevanten Mitarbeiter-Feldern (Name, Vorname, Abteilung, Position, Eintrittsdatum, etc.). Eine Zeile pro Mitarbeiter.",
     "Synthetische Beispieldaten — der Skill wurde gelernt mit realistischen aber erfundenen 10 Mitarbeitern (Müller, Schmidt, ...)."),
    ("Bewerbungs_Tracker",
     "Bewerbungs-Pipeline-Tabelle mit Status pro Bewerber (eingegangen/Sichtung/IV/Angebot/Absage), inkl. Quelle und Recruiter.",
     "Synthetische Bewerber-Beispiele."),
    ("Stundenzettel",
     "Monatlicher Stundenzettel mit 4 Wochen-Sheets (Mo-Fr) und einem Summary-Sheet mit Cross-Sheet-Formeln. Pro Tag: Datum, Start, Ende, Pause, Stunden (als Formel).",
     "Synthetische 5-Tage-Wochen mit konstantem 9-17 Uhr und 30min Pause."),
    ("Urlaubs_Uebersicht",
     "Urlaubsverwaltung mit Anträge-Tab (Mitarbeiter, Von, Bis, Tage als Formel, Status) und Resturlaub-Tab (Anspruch, Genommen, Rest).",
     "Synthetische Beispieldaten."),
    ("Krankenstand",
     "Krankenstands-Tracker mit Q1-Q4-Tabs und Jahres-Summary mit Quartalstotalen. DSGVO-Hinweis im Sheet.",
     "Synthetische Beispieldaten."),
    ("Spesen_Abrechnung",
     "Spesen-Tabelle mit MwSt-Berechnung (7%/19%) und Genehmigungs-Footer. Pro Zeile: Datum, Beleg, Anlass, Kategorie, Brutto, MwSt-Satz, MwSt (Formel), Netto (Formel).",
     "Synthetische Beispieldaten (Hotel/Bahn/Flug/Verpflegung)."),
    ("Onboarding_Checkliste",
     "Onboarding-Checkliste mit 5 Phase-Sheets (Vor_Tag1, Tag1, Woche1, Monat1, Tag100). Pro Phase: Aufgabe, Verantwortlich, Frist, Status.",
     "Synthetische Standard-Onboarding-Aufgaben."),
    ("Offboarding_Checkliste",
     "Offboarding-Checkliste mit Bereich-Spalte (Personalwesen/IT/Finanzen/Übergabe), Aufgaben + Verantwortlich + Frist + Status.",
     "Synthetische Standard-Offboarding-Aufgaben."),
    ("Mitarbeitergespraech_Protokoll",
     "Word-Vorlage für Mitarbeitergespräch mit Sektionen Rückblick, Erreichte Ziele, Entwicklungsfelder, Neue Ziele, Gehalt, Sonstiges. Mit Tabellen für Zielvereinbarung + Unterschriften-Footer.",
     "Standard-deutsche HR-Vorlage."),
    ("Arbeitszeugnis_Vorlage",
     "Word-Arbeitszeugnis-Vorlage mit Standard-Formulierungen und Platzhaltern wie {{name}}, {{position}}, {{eintritt}}, {{austritt}}.",
     "Deutsche Arbeitszeugnis-Konvention."),
    ("Lohnabrechnung_Hilfstabelle",
     "Lohnabrechnung mit Parameter-Sheet (Beitragssätze RV/KV/AV/PV) und Abrechnungs-Sheet mit echten Formeln je Mitarbeiter (LSt, Soli, Sozialvers, Netto).",
     "Synthetische 5 Mitarbeiter mit Bruttogehältern 2500-6500€."),
    ("HR_Kennzahlen_Dashboard",
     "HR-KPI-Dashboard mit Daten-Sheet (12 Monate Headcount/Eintritte/Austritte/Kranktage/Bewerber/Interviews/Einstellungen) und KPIs-Sheet mit Formeln (Fluktuation, Krankenquote, Recruiting-Conversion).",
     "Synthetische Monatsdaten."),
    # Roarboot demos
    ("Roarboot_BrainRouter_Notes",
     "Excel mit allen Notizen aus der Rowboat-Bubble 'Brain Capability Router'. Eine Zeile pro Notiz.",
     "Echte Daten aus Rowboat MongoDB, Bubble 'VibeMind - Brain Capability Router' (~15 source_docs)."),
    ("Roarboot_Bewerbung_2026.xlsx",
     "Excel mit allen .md-Dateien aus dem Roarboot Bewerbung-Folder, eine Zeile pro File mit Pfad/Name/Inhalt-Auszug/Größe/Modified.",
     "Roarboot Filesystem-Folder ~/.rowboat/knowledge/Bewerbung — enthält EINE Datei: Felix Baumann.md"),
    ("Bewerbungen_Strukturiert",
     "Excel mit strukturierten Bewerber-Daten (eine Zeile pro Bewerber): Name, Position, Email, Telefon, Top-Skills, Erfahrung-Jahre, Status. Extrahiert via LLM.",
     "Roarboot Bewerbung-Folder mit 1 Datei (Felix Baumann CV)."),
    ("Roarboot_people_extract_2026.xlsx",
     "Excel mit den Personen aus Roarboot People-Folder, dynamische Felder (User wählt: name, beschreibung, kategorie). Eine Zeile pro Person.",
     "Roarboot People-Folder mit 2 Dateien: User_Profile.md (Stimmungs-History des Users) und Felix Baumann.md (sein Profil)."),
    ("Roarboot_people_extract_2026.BUGGY",
     "Excel mit den Personen aus Roarboot People-Folder, Felder name/beschreibung/kategorie.",
     "Roarboot People-Folder mit 2 Dateien. (Diese Datei ist die ALTE Version VOR dem Z-Bug-Fix — als Vergleich.)"),
    ("Bewerbungen_Joined_People",
     "Excel mit JOIN von Bewerbung × People auf Name. Pro Bewerber: Name, Position, Email + Profil-Zusammenfassung, Letzter Kontakt, Interessen aus People.",
     "Roarboot Bewerbung (1 file) + People (2 files), JOIN auf Name-Match."),
]


def find_intent(filename: str) -> tuple[str, str]:
    for sub, intent, source in INTENTS:
        if sub in filename:
            return intent, source
    return ("Unbekannte Datei — keine spezifische Intent-Beschreibung verfügbar.",
            "Keine Source-Beschreibung verfügbar.")


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(list(HR.glob("*.xlsx")) + list(HR.glob("*.docx")))
    print(f"Evaluating {len(files)} files...")
    print()

    reports = []
    md_lines = [
        f"# HR/Roarboot Output Quality Report",
        f"_Generated: {datetime.now().isoformat(timespec='seconds')}_",
        f"_Files evaluated: {len(files)}, model: gpt-4o-mini_",
        "",
        "## Score Heuristic",
        "- 90-100: produktionsreif",
        "- 70-89: brauchbar mit kleinen Mängeln",
        "- 50-69: nur Konzept-Demo",
        "- <50: nicht akzeptabel",
        "",
        "## Per-File Scores",
        "",
        "| File | Score | Severity | Top Issue |",
        "|---|---:|---|---|",
    ]

    for f in files:
        intent, source = find_intent(f.name)
        print(f"  evaluating {f.name} ...", flush=True)
        r = _file_evaluate(
            file_path=str(f),
            expected_intent=intent,
            source_data_description=source,
        )
        reports.append({"file": f.name, "report": r})
        if not r.get("success"):
            md_lines.append(f"| {f.name} | ERROR | - | {r.get('error','?')} |")
            continue
        score = r.get("score", "?")
        issues = r.get("issues", [])
        top_issue = ""
        top_severity = ""
        if issues:
            # Find highest severity issue
            order = {"high": 0, "medium": 1, "low": 2}
            issues_sorted = sorted(issues, key=lambda x: order.get(x.get("severity", "low"), 3))
            top = issues_sorted[0]
            top_severity = top.get("severity", "?")
            top_issue = top.get("issue", "")[:120].replace("|", "\\|")
        md_lines.append(f"| {f.name} | **{score}** | {top_severity} | {top_issue} |")

    md_lines.append("")
    md_lines.append("## Detailed Issues")
    md_lines.append("")
    for entry in reports:
        f = entry["file"]
        r = entry["report"]
        if not r.get("success"):
            continue
        md_lines.append(f"### {f}  —  Score: **{r.get('score')}**")
        md_lines.append(f"_{r.get('summary', '')}_")
        md_lines.append("")
        md_lines.append(f"- **Vollständigkeit:** {r.get('completeness', '-')}")
        if r.get("issues"):
            md_lines.append("- **Issues:**")
            for i in r["issues"]:
                sev = i.get("severity", "?")
                txt = i.get("issue", "")
                fix = i.get("fix_suggestion", "")
                md_lines.append(f"  - **[{sev}]** {txt}")
                if fix:
                    md_lines.append(f"    - Fix: {fix}")
        if r.get("recommendations"):
            md_lines.append("- **Empfehlungen:**")
            for rec in r["recommendations"]:
                md_lines.append(f"  - {rec}")
        md_lines.append("")

    # Aggregate stats
    scores = [e["report"].get("score") for e in reports if e["report"].get("success") and isinstance(e["report"].get("score"), (int, float))]
    if scores:
        md_lines.insert(8, "## Summary Stats")
        md_lines.insert(9, f"- Average score: **{sum(scores)/len(scores):.1f}/100**")
        md_lines.insert(10, f"- Highest: {max(scores)} | Lowest: {min(scores)}")
        md_lines.insert(11, f"- Production-ready (≥90): {sum(1 for s in scores if s >= 90)}")
        md_lines.insert(12, f"- Brauchbar (70-89): {sum(1 for s in scores if 70 <= s < 90)}")
        md_lines.insert(13, f"- Demo-only (50-69): {sum(1 for s in scores if 50 <= s < 70)}")
        md_lines.insert(14, f"- Inakzeptabel (<50): {sum(1 for s in scores if s < 50)}")
        md_lines.insert(15, "")

    REPORT.write_text("\n".join(md_lines), encoding="utf-8")
    JSON_OUT.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"=== Report written: {REPORT} ===")
    print(f"=== JSON written:   {JSON_OUT} ===")

    if scores:
        print()
        print(f"Average: {sum(scores)/len(scores):.1f}/100")
        print(f"Highest: {max(scores)}, Lowest: {min(scores)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
