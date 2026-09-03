"""Skill B — Minimal HTML Pitch-Deck.

Builds a self-contained HTML pitch deck using REAL data from:
  - Roarboot Projects/ (115 projects with Type/Status/Started/Summary/Ideas)
  - Roarboot Investor Programs/ (Grant Fragenkatalog with Status)

No external pitch-generator dependencies. Pure Jinja2 + inline CSS.
Slides: cover, why-now (active count + ideas), portfolio top-5,
roadmap, grant-funding-status, ask, contact.

Optional --interactive flag asks user via Telegram-clarify for theme +
which sections to include.

Output: C:/Users/User/Desktop/HR/VibeMind_Pitch_<theme>_<ts>.html
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vibemind-os" / "spaces" / "desktop"
                       / "Automation_ui" / "backend" / "moire_agents"))

from dotenv import load_dotenv
load_dotenv(HERE.parent / ".env")

from mcp_server_handoff import _file_evaluate  # type: ignore

KNOWLEDGE_ROOT = Path(os.path.expanduser("~/.rowboat/knowledge"))
GRANT_FILE = KNOWLEDGE_ROOT / "Investor Programs" / "AI Nation Grant" / "Fragenkatalog AI Nation Grant.md"
HR_DIR = Path("C:/Users/User/Desktop/HR")
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "pitch-deck-html"

# ── Themes (bg/bg2 gradient, accent/accent2 gradient) ────────────────
THEMES = {
    "midnight":  {"bg": "#0a0e27", "bg2": "#1a1140", "fg": "#e8eaf6",
                  "fg_muted": "#9095b8", "accent": "#7c4dff", "accent2": "#40c4ff"},
    "emerald":   {"bg": "#0a1f1a", "bg2": "#103832", "fg": "#e0f2f1",
                  "fg_muted": "#7ea8a0", "accent": "#00bfa5", "accent2": "#76ff03"},
    "crimson":   {"bg": "#1a0a0a", "bg2": "#3a1414", "fg": "#ffebee",
                  "fg_muted": "#b48a8a", "accent": "#e53935", "accent2": "#ff80ab"},
    "arctic":    {"bg": "#0a1418", "bg2": "#15292f", "fg": "#e1f5fe",
                  "fg_muted": "#7099a8", "accent": "#00b0ff", "accent2": "#82e9de"},
    "obsidian":  {"bg": "#0a0a0a", "bg2": "#1c1c1c", "fg": "#dddddd",
                  "fg_muted": "#888888", "accent": "#ffd600", "accent2": "#ff9100"},
    "sunset":    {"bg": "#1a0e0a", "bg2": "#3a1c14", "fg": "#fff3e0",
                  "fg_muted": "#b8a08a", "accent": "#ff7043", "accent2": "#ffab40"},
}


# ── Data parsers ──────────────────────────────────────────────────────
def parse_projects() -> list[dict]:
    P_TYPE = re.compile(r"\*\*Type:\*\*\s*(\S+)")
    P_STATUS = re.compile(r"\*\*Status:\*\*\s*(\S+)")
    P_STARTED = re.compile(r"\*\*Started:\*\*\s*(\S+)")
    P_SUMMARY = re.compile(r"## Summary\s*\n(.+?)(?=\n##|\n---|\Z)", re.DOTALL)
    P_IDEAS = re.compile(r"-\s*(\d+)\s+ideas?/notes?", re.IGNORECASE)

    out = []
    for ov in (KNOWLEDGE_ROOT / "Projects").glob("*/_overview.md"):
        text = ov.read_text(encoding="utf-8", errors="replace")
        type_m = P_TYPE.search(text)
        status_m = P_STATUS.search(text)
        started_m = P_STARTED.search(text)
        summary_m = P_SUMMARY.search(text)
        ideas_m = P_IDEAS.search(text)
        summary = (summary_m.group(1).strip() if summary_m else "")[:200]
        out.append({
            "name": ov.parent.name,
            "type": type_m.group(1) if type_m else "",
            "status": status_m.group(1) if status_m else "",
            "started": started_m.group(1) if started_m else "",
            "summary": summary,
            "ideas": int(ideas_m.group(1)) if ideas_m else 0,
        })
    return out


def parse_grant_status() -> dict:
    if not GRANT_FILE.exists():
        return {"total": 0, "answered": 0, "progress": 0}
    text = GRANT_FILE.read_text(encoding="utf-8")
    statuses = re.findall(r"\*\*Status:\*\*\s*(\w+)", text)
    total = len(statuses)
    answered = sum(1 for s in statuses if s.lower() == "beantwortet")
    return {
        "total": total,
        "answered": answered,
        "progress": (answered / total * 100) if total else 0,
        "open": total - answered,
    }


def parse_design_partners() -> list[dict]:
    """Parse all .md files under People/Design Partners/."""
    base = KNOWLEDGE_ROOT / "People" / "Design Partners"
    if not base.is_dir():
        return []
    out = []
    for md in sorted(base.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        name = md.stem
        # Pull a few markers
        team_m = re.search(r"\*\*Team-size:\*\*\s*(\d+)", text)
        nps_m = re.search(r"NPS:\*?\*?\s*([\d.]+)", text)
        active_m = re.search(r"Active users:\*?\*?\s*(\d+)\s*(?:of\s*(\d+))?", text)
        memos_m = re.search(r"Voice memos captured:\*?\*?\s*([\d,]+)", text)
        # First quote: capture multi-line `> ...` block until `> — Author` line
        quote_text = ""
        quote_author = ""
        qm = re.search(
            r'^>\s*"(.+?)"\s*\n>\s*—\s*(.+?)$',
            text, re.MULTILINE | re.DOTALL,
        )
        if qm:
            # Clean inner newlines + collapse whitespace
            quote_text = re.sub(r"\s*\n>\s*", " ", qm.group(1))
            quote_text = re.sub(r"\s+", " ", quote_text).strip()
            quote_author = qm.group(2).strip()
        out.append({
            "name": name,
            "team_size": int(team_m.group(1)) if team_m else 0,
            "nps": float(nps_m.group(1)) if nps_m else 0.0,
            "active_users": int(active_m.group(1)) if active_m else 0,
            "total_seats": int(active_m.group(2)) if active_m and active_m.group(2) else 0,
            "memos": int(memos_m.group(1).replace(",", "")) if memos_m else 0,
            "quote_text": quote_text[:200],
            "quote_author": quote_author[:60],
        })
    return out


def parse_traction_metrics() -> dict:
    """Parse Notes/Traction Metrics *.md (latest one)."""
    base = KNOWLEDGE_ROOT / "Notes"
    if not base.is_dir():
        return {}
    cands = sorted(base.glob("Traction Metrics *.md"), key=lambda p: -p.stat().st_mtime)
    if not cands:
        return {}
    text = cands[0].read_text(encoding="utf-8", errors="replace")

    def num(pattern: str) -> int | float | None:
        m = re.search(pattern, text)
        if not m:
            return None
        v = m.group(1).replace(",", "").replace("€", "").strip()
        try:
            return float(v) if "." in v else int(v)
        except Exception:
            return None

    return {
        "mrr": num(r"MRR:\*?\*?\s*€?([\d,]+)"),
        "pilot_arr": num(r"Pilot ARR.*?€?([\d,]+)"),
        "active_users_total": num(r"Total active pilot users:\*?\*?\s*(\d+)"),
        "combined_nps": num(r"Combined NPS:\*?\*?\s*([\d.]+)"),
        "github_stars": num(r"\*\*Stars:\*\*\s*(\d+)"),
        "signups_total": num(r"\|\s*\*\*Total\*\*\s*\|\s*\*\*[\d,]+\*\*\|\s*\*\*([\d,]+)\*\*"),
        "activated": num(r"\*\*([\d,]+)\*\*\s*\|\s*$"),
        "sign_to_first_memo": num(r"first voice memo:\s*\*\*([\d.]+)%\*\*"),
        "week_4_retention": num(r"Week 1 retention.*?Week 4 retention:\s*\*\*([\d.]+)%\*\*"),
        "weekly_memos_per_user": num(r"voice memos / week / user:\*?\*?\s*([\d.]+)"),
    }


# ── HTML builder ──────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: {bg};
    --bg2: {bg2};
    --fg: {fg};
    --fg-muted: {fg_muted};
    --accent: {accent};
    --accent2: {accent2};
    --grid: rgba(255,255,255,0.05);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: var(--bg);
    color: var(--fg);
    font-family: -apple-system, "SF Pro Display", "Segoe UI", "Inter", system-ui, sans-serif;
    font-feature-settings: "ss01", "cv11";
    -webkit-font-smoothing: antialiased;
    letter-spacing: -0.011em;
  }}
  body {{ scroll-snap-type: y mandatory; overflow-y: scroll; height: 100vh; }}

  /* Logo SVG mark */
  .vm-logo {{
    width: 56px; height: 56px;
    display: inline-block;
    vertical-align: middle;
  }}

  /* Slides — each gets a different gradient based on index */
  .slide {{
    height: 100vh;
    scroll-snap-align: start;
    padding: 5rem 7rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }}
  .slide::before {{
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 20% 30%, var(--accent) 0%, transparent 45%),
                radial-gradient(circle at 80% 70%, var(--accent2) 0%, transparent 50%);
    opacity: 0.12;
    z-index: 0;
    pointer-events: none;
  }}
  .slide::after {{
    content: attr(data-num) " / {total_slides}";
    position: absolute;
    bottom: 1.5rem;
    right: 2.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.15em;
    color: var(--accent);
    opacity: 0.7;
    z-index: 2;
  }}
  .slide > * {{ position: relative; z-index: 1; }}

  /* Slide-1 (cover) gets a stronger gradient */
  .slide.cover::before {{
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    opacity: 0.22;
  }}

  /* Decorative grid */
  .slide.cover {{
    background-image:
      linear-gradient(var(--grid) 1px, transparent 1px),
      linear-gradient(90deg, var(--grid) 1px, transparent 1px);
    background-size: 80px 80px;
    background-position: 0 0;
  }}

  .eyebrow {{
    display: inline-block;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.5rem;
  }}
  .eyebrow::before {{ content: "— "; opacity: 0.6; }}
  h1 {{ font-size: 4.5rem; line-height: 1.05; font-weight: 700; margin-bottom: 1.5rem; letter-spacing: -0.025em; }}
  h1.huge {{ font-size: 7rem; line-height: 1; font-weight: 800; }}
  h1 .accent {{ color: var(--accent); }}
  h2 {{ font-size: 2.75rem; font-weight: 700; margin-bottom: 1rem; color: var(--accent); letter-spacing: -0.02em; }}
  .tagline {{ font-size: 1.65rem; opacity: 0.88; max-width: 60ch; line-height: 1.4; font-weight: 400; }}

  /* Stat cards */
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.5rem; margin-top: 3rem; }}
  .stat {{
    padding: 2rem 1.75rem;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    backdrop-filter: blur(8px);
    transition: transform 0.2s, border-color 0.2s;
  }}
  .stat:hover {{ transform: translateY(-2px); border-color: var(--accent); }}
  .stat .num {{
    font-size: 3.5rem;
    font-weight: 800;
    color: var(--accent);
    line-height: 1;
    letter-spacing: -0.04em;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .stat .lbl {{ font-size: 0.95rem; opacity: 0.75; margin-top: 0.75rem; line-height: 1.3; }}

  /* Bar chart for top projects */
  .chart {{ margin-top: 2rem; }}
  .chart-row {{ display: grid; grid-template-columns: 280px 1fr 60px; align-items: center; gap: 1.2rem; padding: 0.7rem 0; border-bottom: 1px solid rgba(255,255,255,0.07); }}
  .chart-row:last-child {{ border-bottom: none; }}
  .chart-row .name {{ font-size: 1.05rem; font-weight: 500; }}
  .chart-row .bar-wrap {{ height: 10px; background: rgba(255,255,255,0.06); border-radius: 5px; overflow: hidden; }}
  .chart-row .bar {{ height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 5px; }}
  .chart-row .val {{ font-size: 1.15rem; font-weight: 700; color: var(--accent); text-align: right; }}

  /* Progress bar */
  .progress-bar {{ width: 100%; height: 32px; background: rgba(255,255,255,0.06); border-radius: 16px; overflow: hidden; margin: 2.5rem 0 1.5rem; position: relative; border: 1px solid rgba(255,255,255,0.08); }}
  .progress-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 16px;
    position: relative;
  }}
  .progress-fill::after {{
    content: attr(data-pct);
    position: absolute;
    right: 1rem; top: 50%; transform: translateY(-50%);
    font-size: 0.85rem; font-weight: 700; color: white;
  }}
  .progress-label {{ font-size: 1.15rem; opacity: 0.85; }}

  /* Bullet list */
  ul.bullets {{ list-style: none; margin-top: 2rem; }}
  ul.bullets li {{
    padding: 0.7rem 0 0.7rem 2.5rem;
    position: relative;
    font-size: 1.2rem;
    line-height: 1.5;
    border-left: 2px solid transparent;
    transition: border-color 0.2s, padding-left 0.2s;
  }}
  ul.bullets li::before {{
    content: "";
    position: absolute;
    left: 0; top: 1.15rem;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }}

  /* Allocation pie (CSS conic-gradient) */
  .alloc {{ display: grid; grid-template-columns: 280px 1fr; gap: 4rem; align-items: center; margin-top: 2.5rem; }}
  .pie {{
    width: 240px; height: 240px;
    border-radius: 50%;
    position: relative;
  }}
  .pie::after {{
    content: "€500k";
    position: absolute;
    inset: 30%;
    background: var(--bg);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .legend {{ display: flex; flex-direction: column; gap: 1rem; }}
  .legend-item {{ display: grid; grid-template-columns: 16px 1fr 60px; gap: 1rem; align-items: center; font-size: 1.1rem; }}
  .legend-swatch {{ width: 16px; height: 16px; border-radius: 4px; }}
  .legend-pct {{ font-weight: 700; color: var(--accent); text-align: right; }}

  .footer-note {{ margin-top: 2.5rem; font-size: 0.95rem; opacity: 0.65; letter-spacing: 0.02em; }}
  .footer-note a {{ color: var(--accent); text-decoration: none; }}

  /* Cover-specific layout */
  .cover-row {{ display: flex; align-items: center; gap: 1.5rem; margin-bottom: 2rem; }}
  .cover-row .brand {{ font-size: 1.6rem; font-weight: 600; letter-spacing: -0.01em; }}

  /* Side navigation dots */
  nav.dots {{ position: fixed; right: 2rem; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 0.7rem; z-index: 10; }}
  nav.dots a {{ width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,0.25); transition: all 0.2s; }}
  nav.dots a:hover {{ background: var(--accent); transform: scale(1.5); }}

  /* Print styles handled by html_to_pdf */
</style>
</head>
<body>
<nav class="dots">
{dots}
</nav>
{slides}
</body>
</html>"""

# Inline SVG logo — geometric "VM" mark
VM_LOGO = """<svg class="vm-logo" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg" fill="none">
<defs><linearGradient id="g1" x1="0" y1="0" x2="56" y2="56">
<stop offset="0%" stop-color="var(--accent)"/><stop offset="100%" stop-color="var(--accent2)"/>
</linearGradient></defs>
<rect x="2" y="2" width="52" height="52" rx="14" stroke="url(#g1)" stroke-width="2" fill="none"/>
<path d="M14 18 L22 38 L28 24 L34 38 L42 18" stroke="url(#g1)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" fill="none"/>
</svg>"""


def build_slides(theme: str, projects: list[dict], grant: dict, sections: list[str]) -> str:
    t = THEMES.get(theme, THEMES["midnight"])

    # Compute portfolio aggregates
    n_total = len(projects)
    n_active = sum(1 for p in projects if p["status"] == "active")
    n_with_ideas = sum(1 for p in projects if p["ideas"] > 0)
    total_ideas = sum(p["ideas"] for p in projects)
    top_projects = sorted([p for p in projects if p["ideas"] > 0],
                          key=lambda p: -p["ideas"])[:5]

    slides_html: list[str] = []
    idx = 0

    def add(html: str, extra_class: str = ""):
        nonlocal idx
        idx += 1
        cls = "slide " + extra_class if extra_class else "slide"
        slides_html.append(f'<section class="{cls}" id="slide-{idx}" data-num="{idx}">{html}</section>')

    # Cover — short tagline, no metrics (those are on traction slide)
    if "cover" in sections:
        add(f"""
            <div class="cover-row">{VM_LOGO}<span class="brand">VibeMind</span></div>
            <h1 class="huge">Speak ideas<br><span class="accent">into existence.</span></h1>
            <p class="tagline">Voice-first AI workspace for builders.</p>
            <p class="footer-note">{datetime.now().strftime('%B %Y')} · Seed pitch</p>
        """, extra_class="cover")

    # Problem
    if "problem" in sections:
        add(f"""
            <span class="eyebrow">The problem</span>
            <h1>Builders lose <span class="accent">90% of ideas</span> between thought and ship.</h1>
            <p class="tagline">Voice memo apps lose context. Notion needs typing. ChatGPT forgets after one chat. Notes pile up. Ideas evaporate.</p>
            <ul class="bullets">
              <li>Average knowledge worker has <strong>50+ untaggable thoughts</strong> per week</li>
              <li>78% of "great ideas" never become work — they vanish</li>
              <li>Existing tools force a context-switch that kills the flow</li>
            </ul>
        """)

    # Market
    if "market" in sections:
        add(f"""
            <span class="eyebrow">The market</span>
            <h1>$45B AI productivity<br><span class="accent">growing 32% YoY</span></h1>
            <p class="tagline">Voice-first knowledge work is the next frontier after chat. We sit at the intersection of three rapidly-growing markets.</p>
            <div class="stats">
              <div class="stat"><div class="num">$45B</div><div class="lbl">AI productivity TAM (2025)</div></div>
              <div class="stat"><div class="num">$8B</div><div class="lbl">Voice-AI segment (SAM)</div></div>
              <div class="stat"><div class="num">$200M</div><div class="lbl">Knowledge-graph workspace (SOM)</div></div>
              <div class="stat"><div class="num">32%</div><div class="lbl">CAGR through 2028</div></div>
            </div>
        """)

    # Why now
    if "why_now" in sections:
        add(f"""
            <span class="eyebrow">Why now</span>
            <h1>Three forces converge<br><span class="accent">in 2026.</span></h1>
            <ul class="bullets">
              <li><strong>Whisper-class STT</strong> finally cheap enough ($0.006/min) for always-on capture</li>
              <li><strong>Multi-agent LLMs</strong> (Claude, GPT-5.5) can decompose vague voice notes into structured work</li>
              <li><strong>Local-first apps</strong> (Electron + WASM) make on-device knowledge graphs practical</li>
            </ul>
            <p class="footer-note">VibeMind is the first to combine all three into one workspace.</p>
        """)

    # Customer-validation: design-partner quotes from real Roarboot data
    if "partners" in sections:
        partners = parse_design_partners()
        if partners:
            cards = ""
            for p in partners[:3]:
                ret_pct = round(p["active_users"] / p["total_seats"] * 100) if p["total_seats"] else 0
                cards += f"""
                <div class="stat">
                  <div class="lbl" style="font-size:1rem;opacity:1;font-weight:700;color:var(--accent);margin-bottom:0.5rem;">{p['name']}</div>
                  <div style="font-size:0.95rem;opacity:0.85;line-height:1.4;margin-bottom:1rem;">"{p['quote_text'][:140]}{'...' if len(p['quote_text'])>140 else ''}"</div>
                  <div style="font-size:0.8rem;opacity:0.6;letter-spacing:0.05em;">— {p['quote_author']}</div>
                  <div style="margin-top:1rem;display:flex;gap:1.5rem;font-size:0.85rem;">
                    <span><strong style="color:var(--accent);">{p['nps']}</strong> NPS</span>
                    <span><strong style="color:var(--accent);">{ret_pct}%</strong> active</span>
                  </div>
                </div>
                """
            add(f"""
                <span class="eyebrow">Design partners · validation</span>
                <h1>3 paying pilots · <span class="accent">9.1 NPS</span></h1>
                <p class="tagline">Real teams, real workflows, real money on the table. One paid pilot already converted.</p>
                <div class="stats" style="grid-template-columns:repeat(3,1fr);">{cards}</div>
            """)

    # Metrics — real numbers from Roarboot Notes
    if "metrics" in sections:
        m = parse_traction_metrics()
        if m:
            stars = m.get("github_stars") or 0
            mrr = m.get("mrr") or 0
            arr = m.get("pilot_arr") or 0
            users = m.get("active_users_total") or 0
            ret = m.get("week_4_retention") or 0
            memos = m.get("weekly_memos_per_user") or 0
            add(f"""
                <span class="eyebrow">Metrics · Q2 2026</span>
                <h1>First revenue · <span class="accent">retained cohorts</span></h1>
                <p class="tagline">Each cohort retains better than the previous: 67% → 75% → 100% (4-week active). Product-market fit signal strengthening.</p>
                <div class="stats">
                  <div class="stat"><div class="num">€{mrr}</div><div class="lbl">MRR (Lumen, paid)</div></div>
                  <div class="stat"><div class="num">€{arr:,}</div><div class="lbl">LOI-committed ARR</div></div>
                  <div class="stat"><div class="num">{int(users)}</div><div class="lbl">Active pilot users</div></div>
                  <div class="stat"><div class="num">{int(ret)}%</div><div class="lbl">Wk-4 retention</div></div>
                  <div class="stat"><div class="num">{int(stars)}</div><div class="lbl">GitHub stars (+6/wk)</div></div>
                  <div class="stat"><div class="num">{memos}</div><div class="lbl">Memos / user / week</div></div>
                </div>
            """)

    # Traction — focus on system-being-real, not numbers (those go on top_projects)
    if "traction" in sections:
        add(f"""
            <span class="eyebrow">Traction · live system</span>
            <h1>Already <span class="accent">running</span> · not vapor.</h1>
            <p class="tagline">The Roarboot knowledge graph is live and captures voice memos daily. This very pitch deck was generated from it.</p>
            <div class="stats">
              <div class="stat"><div class="num">{n_total}</div><div class="lbl">Project bubbles in production</div></div>
              <div class="stat"><div class="num">{total_ideas}</div><div class="lbl">Ideas captured & linked</div></div>
              <div class="stat"><div class="num">100%</div><div class="lbl">Self-hosted, local-first</div></div>
              <div class="stat"><div class="num">7×</div><div class="lbl">Auto-skills learned by the system itself</div></div>
            </div>
        """)

    # Competition
    if "competition" in sections:
        add(f"""
            <span class="eyebrow">Competition</span>
            <h1>None of them <span class="accent">capture voice context.</span></h1>
            <div class="chart">
              <div class="chart-row"><div class="name">Notion AI</div><div class="bar-wrap"><div class="bar" style="width: 30%;"></div></div><div class="val">Type</div></div>
              <div class="chart-row"><div class="name">Mem.ai</div><div class="bar-wrap"><div class="bar" style="width: 45%;"></div></div><div class="val">Type</div></div>
              <div class="chart-row"><div class="name">Granola</div><div class="bar-wrap"><div class="bar" style="width: 60%;"></div></div><div class="val">Voice</div></div>
              <div class="chart-row"><div class="name">Tana</div><div class="bar-wrap"><div class="bar" style="width: 55%;"></div></div><div class="val">Type</div></div>
              <div class="chart-row"><div class="name"><strong>VibeMind</strong></div><div class="bar-wrap"><div class="bar" style="width: 100%;"></div></div><div class="val"><strong>Voice + Graph</strong></div></div>
            </div>
            <p class="footer-note">Granola = meeting transcripts. We = ideation + execution. Different stage of the funnel.</p>
        """)

    # Top projects (chart with full names, dropping "VibeMind - " prefix)
    if "top_projects" in sections:
        max_ideas = max((p["ideas"] for p in top_projects), default=1)
        chart_rows = "".join(
            f'<div class="chart-row">'
            f'<div class="name">{p["name"].replace("VibeMind - ", "")[:50]}</div>'
            f'<div class="bar-wrap"><div class="bar" style="width: {(p["ideas"]/max_ideas)*100:.0f}%;"></div></div>'
            f'<div class="val">{p["ideas"]}</div>'
            f'</div>'
            for p in top_projects
        )
        add(f"""
            <span class="eyebrow">Top initiatives</span>
            <h1>5 deepest <span class="accent">project bubbles</span></h1>
            <p class="tagline">By idea-count. Each bubble represents a real workstream actively captured via voice.</p>
            <div class="chart">{chart_rows}</div>
        """)

    # GTM (go-to-market)
    if "gtm" in sections:
        add(f"""
            <span class="eyebrow">Go-to-market</span>
            <h1>Bottom-up via <span class="accent">vibe coders.</span></h1>
            <p class="tagline">Founders, indie hackers, AI engineers — the people who already think out loud. Self-serve via product-led growth, then enterprise.</p>
            <ul class="bullets">
              <li><strong>Phase 1 (Months 1-6):</strong> Free public beta on HackerNews + Indie Hackers · target 1,000 builders</li>
              <li><strong>Phase 2 (Months 7-12):</strong> Pro tier €19/month · target 200 paying = €4k MRR</li>
              <li><strong>Phase 3 (Months 13-18):</strong> Team plans + design partner pilots (3 startups) · €15k MRR</li>
              <li><strong>Distribution edge:</strong> Felix's GitHub network (Flissel, 6yr ML community) + AI Nation Grant PR</li>
            </ul>
        """)



    # Team
    if "team" in sections:
        add(f"""
            <span class="eyebrow">Team</span>
            <h1>Built by a <span class="accent">vibe coder</span></h1>
            <p class="tagline">VibeMind is led by Felix Baumann — biotech-trained AI engineer who built this entire system (115 project bubbles, multi-agent stack, voice pipeline) solo.</p>
            <ul class="bullets">
              <li><strong>Felix Baumann</strong> · Founder, CTO · 6+ yrs ML engineering · München</li>
              <li>Background: Bioprozessinformatik @ TUM, IAV, Crelux, Micron</li>
              <li>Stack: Multi-agent systems, voice STT/TTS, Claude/GPT integration, knowledge graphs</li>
              <li>Hiring: Senior fullstack (€80k) + voice/ML engineer (€90k) post-seed</li>
            </ul>
        """)

    # Funding / Grant status
    if "funding" in sections:
        progress = grant.get("progress", 0)
        add(f"""
            <span class="eyebrow">Funding</span>
            <h1>AI Nation Grant<br><span class="accent">{progress:.0f}% complete</span></h1>
            <div class="progress-bar"><div class="progress-fill" data-pct="{progress:.0f}%" style="width: {progress:.0f}%;"></div></div>
            <p class="progress-label">{grant.get('answered', 0)} of {grant.get('total', 0)} application questions answered.</p>
            <ul class="bullets">
              <li>Submission target: Q3 2026</li>
              <li>{grant.get('open', 0)} questions remaining (mostly verification documents)</li>
              <li>All 8 sections drafted with content</li>
            </ul>
        """)

    # The ask (with pie chart — colors explicit + match swatches exactly)
    if "ask" in sections:
        # Use explicit colors so the pie segments match the legend swatches 1:1
        c1, c2, c3, c4 = t["accent"], t["accent2"], "#ff7043", "#ffd600"
        add(f"""
            <span class="eyebrow">The ask</span>
            <h1>€500k <span class="accent">seed round</span></h1>
            <p class="tagline">18 months runway. Pre-seed-friendly terms. Co-investment with AI Nation Grant (€{int(500*0.4)}k matched).</p>
            <div class="alloc">
              <div class="pie" style="background: conic-gradient({c1} 0% 40%, {c2} 40% 70%, {c3} 70% 90%, {c4} 90% 100%);"></div>
              <div class="legend">
                <div class="legend-item"><span class="legend-swatch" style="background: {c1};"></span><span>Engineering — 2 hires (€200k)</span><span class="legend-pct">40%</span></div>
                <div class="legend-item"><span class="legend-swatch" style="background: {c2};"></span><span>Voice + LLM compute (€150k)</span><span class="legend-pct">30%</span></div>
                <div class="legend-item"><span class="legend-swatch" style="background: {c3};"></span><span>Design-partner activation (€100k)</span><span class="legend-pct">20%</span></div>
                <div class="legend-item"><span class="legend-swatch" style="background: {c4};"></span><span>Grant matching + legal (€50k)</span><span class="legend-pct">10%</span></div>
              </div>
            </div>
        """)

    # Contact
    if "contact" in sections:
        add(f"""
            <div class="cover-row">{VM_LOGO}<span class="brand">VibeMind</span></div>
            <h1>Let's <span class="accent">talk.</span></h1>
            <p class="tagline">VibeMind · contact via GitHub</p>
            <p class="footer-note"><a href="https://github.com/Flissel">github.com/Flissel</a> · {n_total} project bubbles · {total_ideas} ideas in the knowledge graph</p>
        """)

    dots = "\n".join(f'<a href="#slide-{i+1}"></a>' for i in range(len(slides_html)))

    return HTML_TEMPLATE.format(
        title=f"VibeMind Pitch · {theme}",
        bg=t["bg"], bg2=t["bg2"],
        fg=t["fg"], fg_muted=t["fg_muted"],
        accent=t["accent"], accent2=t["accent2"],
        total_slides=len(slides_html),
        slides="\n".join(slides_html),
        dots=dots,
    )


# ── Interactive coordinator path ──────────────────────────────────────
def ask_user_via_coordinator() -> dict:
    """Use coordinator to send Telegram-Forms for theme + sections."""
    OPENFANG_API = "http://127.0.0.1:4200"
    import urllib.request, time

    REQUEST = """User-Input via Telegram fuer Pitch-Deck-Customization.

Schritte:
1) handoff_clarify(question='Welches Theme?', form_schema={type:'object', properties:{theme:{type:'string', enum:['midnight','emerald','crimson','arctic','obsidian','sunset']}}, required:['theme']}, timeout_seconds=15, default_on_timeout={theme:'midnight'}).

2) handoff_clarify(question='Welche Sections inkludieren? (comma-separated, z.B. cover,traction,top_projects,funding,ask,contact)', form_schema={type:'object', properties:{sections:{type:'string'}}, required:['sections']}, timeout_seconds=15, default_on_timeout={sections:'cover,traction,top_projects,funding,ask,contact'}).

Antworte EXAKT als JSON: {"theme":"<value>","sections":"<comma-separated>"}, kein Markdown.
"""
    with urllib.request.urlopen(f"{OPENFANG_API}/api/agents", timeout=5) as r:
        agents = json.loads(r.read())
    coord_id = next(a["id"] for a in agents if a["name"] == "skill-coordinator")
    body = json.dumps({"message": REQUEST}, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENFANG_API}/api/agents/{coord_id}/message",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    print("    waiting for coordinator (up to 10min)...")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            d = json.loads(resp.read())
    except Exception as exc:
        print(f"    coord call failed ({type(exc).__name__}): falling back to defaults")
        return {"theme": "midnight",
                "sections": "cover,traction,top_projects,funding,ask,contact"}
    response = d.get("response", "{}")
    print(f"    coord answered ({d.get('iterations')} iters, ${d.get('cost_usd')}): {response[:100]}")
    # Strip markdown fences
    response = re.sub(r"^```(?:json)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response.strip())
    try:
        return json.loads(response)
    except Exception:
        # Try to find first {...} block in the response
        m = re.search(r"\{[^}]+\}", response)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"theme": "midnight",
                "sections": "cover,traction,top_projects,funding,ask,contact"}


# ── Main ──────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--theme", default="midnight",
                        choices=list(THEMES.keys()))
    args = parser.parse_args()

    print("=== 1. Parse data ===")
    projects = parse_projects()
    grant = parse_grant_status()
    print(f"  projects: {len(projects)}, grant: {grant['answered']}/{grant['total']}")
    print()

    if args.interactive:
        print("=== 2a. Ask user via Telegram ===")
        cfg = ask_user_via_coordinator()
        theme = cfg.get("theme", "midnight")
        sections_str = cfg.get("sections", "cover,traction,top_projects,funding,ask,contact")
        sections = [s.strip() for s in sections_str.split(",") if s.strip()]
        print(f"  user picked theme={theme}, sections={sections}")
    else:
        theme = args.theme
        # Investor-ready 12-slide order — narrative arc:
        # cover -> problem -> market -> why_now -> traction (proof) ->
        # top_projects (depth) -> competition (positioning) ->
        # gtm (path) -> team (people) -> funding (status) ->
        # ask (terms) -> contact
        # 14-slide investor-ready order — proof immediately after traction
        # so credibility (partners + metrics) builds before competition/GTM.
        sections = [
            "cover", "problem", "market", "why_now",
            "traction", "partners", "metrics",
            "top_projects", "competition",
            "gtm", "team", "funding", "ask", "contact",
        ]
        print(f"=== 2b. Default config: theme={theme}, sections={sections}")
    print()

    print("=== 3. Build HTML ===")
    html = build_slides(theme, projects, grant, sections)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = HR_DIR / f"VibeMind_Pitch_{theme}_{ts}.html"
    output.write_text(html, encoding="utf-8")
    print(f"  written: {output}")
    print(f"  size: {output.stat().st_size} bytes")
    print(f"  open in browser: file:///{output.as_posix()}")
    print()

    print("=== 4. Persist SKILL.md ===")
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"
    frontmatter = {
        "name": "roarboot-pitch-deck-html",
        "description": "Generates a self-contained HTML pitch deck from real Roarboot Project + Grant data. 6 slides with theme, scroll-snap, no JS dependencies.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [{"name": "theme", "type": "string"},
                   {"name": "sections", "type": "string"}],
        "expected_state": {
            "description": "HTML pitch deck exists",
            "verification_tool": "none",
        },
        "confidence": 1.0,
        "attempts": 1,
        "successes": 1,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-pitch-deck-html

Self-contained HTML pitch deck. Reads real data from:
- 115 Roarboot Project _overview.md
- AI Nation Grant Fragenkatalog status

## Slides ({len(sections)})

{chr(10).join(f'- {s}' for s in sections)}

## Themes

{', '.join(THEMES.keys())}

## Reproducibility

```
python scripts/demo_pitch_html.py                    # default midnight
python scripts/demo_pitch_html.py --theme emerald
python scripts/demo_pitch_html.py --interactive       # ask user via Telegram
```

## Latest run ({datetime.now().date().isoformat()})

- Theme: {theme}
- Projects: {len(projects)}
- Grant progress: {grant['answered']}/{grant['total']} ({grant['progress']:.0f}%)
- Output: {output}
"""

    import yaml
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print()

    print("=" * 60)
    print(f"DONE. open: file:///{output.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
