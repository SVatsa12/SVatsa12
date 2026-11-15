#!/usr/bin/env python3
"""
Builds the SVATSA(1) profile: every panel in assets/*.svg plus README.md.

Static panels come from the data below. Two panels are live:
  - activity.svg : latest meaningful commits across my public repos (GitHub API)
  - dsa.svg      : LeetCode solved counts (LeetCode GraphQL)

If a live source fails, the last good value in assets/state.json is reused,
so a flaky API never breaks the profile.

Edit the data in this file, not README.md (README.md is generated).
Usage:  python scripts/build_profile.py            # fetch + build
        python scripts/build_profile.py --offline  # build from state.json only
Env:    GITHUB_TOKEN   (set automatically in Actions)
        PROFILE_EMAIL  (optional; adds an Email link — set as a repo variable)
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STATE = ASSETS / "state.json"
IST = timezone(timedelta(hours=5, minutes=30))

USER = "SVatsa12"
LEETCODE = "s_vatsa1972"
RAW = f"https://raw.githubusercontent.com/{USER}/{USER}/main/assets"

# ─────────────────────────────────────────────────────────────── profile data
PROFILE = {
    "handle": "SVATSA",
    "name": "Shubham Vatsa",
    "subtitle": "Backend Systems · Full-Stack Development · Applied AI",
    "status": "OPEN TO SDE INTERNSHIPS",
    "name_line": "svatsa — backend-first engineer. Final-year B.E. ISE, JSSATE Bengaluru.",
    "description": (
        "Builds systems where state is explicit, failure is planned for, and AI is "
        "a component — not the architecture. Most of the work: FastAPI and Node "
        "backends, real-time pipelines, schema design and LLM integration, with a "
        "React front end on top."
    ),
    "options": [
        ("code", "lang", "Java · Python · JavaScript · SQL"),
        ("server", "backend", "FastAPI · Node.js · Express · WebSockets"),
        ("layers", "frontend", "React · Vite · Tailwind · Three.js"),
        ("db", "data", "PostgreSQL · Prisma · MongoDB · SQLite"),
        ("spark", "ai", "LLM APIs · Whisper · Ollama · RAG"),
        ("box", "infra", "Docker · GitHub Actions · Linux"),
    ],
}

PROJECTS = [
    {
        "slug": "standnote", "icon": "wave", "name": "StandNote.AI",
        "repo": "StandNote",
        "tagline": "Real-time meeting intelligence that runs beside Meet, Zoom and Teams — it never hosts the call.",
        "features": "Live captions · Summaries · Action items",
        "works": "Tab audio → WebSocket → Whisper captions, saved transcripts, Llama 3 summaries and action items.",
        "hard": "One recorder socket, many listeners; dead listeners are pruned mid-broadcast so the stream never stalls.",
        "metric": "<2s caption latency · 5+ concurrent streams",
        "tags": ["FastAPI", "WebSockets", "Chrome MV3", "Whisper", "PostgreSQL"],
    },
    {
        "slug": "snaplink", "icon": "link", "name": "SnapLink",
        "repo": "SnapLink",
        "tagline": "URL shortener with accounts, ownership checks and click analytics.",
        "features": "Shorten · Redirect · Analytics",
        "works": "JWT auth, 7-char nanoid codes, per-link analytics, owner-only stats and delete.",
        "hard": "A redirect is one indexed read plus one atomic increment; indexes are shaped around the two hot queries.",
        "metric": "<50ms lookups · 1,000+ records",
        "tags": ["Node.js", "Express", "Prisma", "PostgreSQL", "Docker"],
    },
    {
        "slug": "tice", "icon": "shield", "name": "TICE",
        "repo": "IP-Information-Retriever",
        "tagline": "Threat Intelligence Correlation Engine — one IP in, one explained risk score out.",
        "features": "OSINT correlation · Risk scoring · AI reports",
        "works": "AbuseIPDB, Shodan and IPInfo correlated into one profile; Gemini report with a template fallback; mock mode.",
        "hard": "Weights re-normalise over the sources that answered — a missing key changes confidence, not scale.",
        "metric": "Top 5 / ~400 teams · AXIOM Hackathon",
        "tags": ["FastAPI", "React 19", "Three.js", "MongoDB", "Gemini"],
    },
    {
        "slug": "deploy", "icon": "flow", "name": "Deployment Automation Tool",
        "repo": "Deployment-Automation-Tool",
        "tagline": "Workflow engine that deploys GitHub repos with resume, retries and approval gates.",
        "features": "Resume · Step retries · Approvals",
        "works": "Persisted run and step state machines, background runs, repo analyzer; static deploys verified on Vercel / Netlify.",
        "hard": "Retry counts live in the DB row and the loop is iterative, so retries survive restarts.",
        "metric": "6 platform adapters · 2 verified end-to-end",
        "tags": ["FastAPI", "SQLAlchemy", "SQLite", "React"],
    },
]

API = [
    ("GET", "/v1/svatsa/projects", "featured systems", "200", "4 entries"),
    ("GET", "/v1/svatsa/stack", "languages · frameworks · infra", "200", "ok"),
    ("GET", "/v1/svatsa/education", "B.E. ISE · JSSATE · class of '27", "200", "CGPA 8.96"),
    ("POST", "/v1/svatsa/hire", "SDE · backend · full-stack internships", "201", "open"),
]

PRINCIPLES = [
    ("Design the degraded path first.", "TICE: template fallback · mock mode"),
    ("State belongs in a table, not a variable.", "Deploy Tool: persisted run + step state"),
    ("The hot path gets the index.", "SnapLink: indexes shaped around redirects"),
    ("One layer, one job.", "routes → controllers → middleware"),
    ("AI sits behind a function boundary.", "Groq · Ollama · Gemini are swappable calls"),
]

SEE_ALSO = ["GitHub", "LinkedIn", "LeetCode", "Portfolio"]
RECORD = [
    "AXIOM Hackathon: top 5 / ~400",
    "Smart India Hackathon: selected",
]
BUGS = [
    "AWS, vector DBs: not shipped yet.",
    "Distributed systems: in progress.",
]
LINKS = [
    ("GitHub", f"https://github.com/{USER}"),
    ("LinkedIn", "https://linkedin.com/in/svatsa12"),
    ("LeetCode", f"https://leetcode.com/u/{LEETCODE}"),
    ("Portfolio", "https://shubhamvatsa.vercel.app"),
]
if os.environ.get("PROFILE_EMAIL"):
    LINKS.append(("Email", "mailto:" + os.environ["PROFILE_EMAIL"]))

DSA_TOPICS = "arrays · trees · graphs · dynamic programming"
DSA_FALLBACK_TOTAL = "250+"

# Commits with these messages are noise and never shown in the activity feed.
NOISE = re.compile(
    r"^(merge\b|initial commit|init\b|changed?$|update[sd]?\b.*readme|readme|"
    r"fix(ed)?( some)? (issues?|bugs?)$|wip$|minor|test$|\.+$|[a-z]{1,3}$)",
    re.I,
)
SKIP_REPOS = {USER}  # the profile repo itself
ACTIVITY_ROWS = 5

# ─────────────────────────────────────────────────────────────── design system
C = {
    "bg": "#0d1117", "panel": "#111821", "tile": "#0b1f2a", "border": "#1f2a37",
    "line": "#202833", "text": "#e6edf3", "body": "#c9d1d9", "muted": "#7d8590",
    "accent": "#3ddc97", "accent2": "#2dd4bf", "blue": "#58a6ff",
    "warn": "#f0b429", "orange": "#ff9f43",
}
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
CW = 0.61  # average monospace glyph width as a fraction of font size

ICONS = {
    "wave": '<path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "flow": '<circle cx="5" cy="6" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="12" r="2.5"/><path d="M5 8.5v7M7.3 6.9l9.4 4M7.3 17.1l9.4-4"/>',
    "code": '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    "server": '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "spark": '<path d="M12 3l1.9 5.6L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.4z"/><path d="M19 17v4M17 19h4"/>',
    "box": '<path d="m21 8-9-5-9 5 9 5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "book": '<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2zM22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>',
    "bolt": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "bulb": '<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V16h8v-1.3A7 7 0 0 0 12 2z"/>',
    "bars": '<path d="M4 20v-4M10 20v-8M16 20V8M22 20V4"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "trophy": '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
    "linkout": '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
}


# ─────────────────────────────────────────────────────────────── svg helpers
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def tw(s: str, size: float, ls: float = 0) -> float:
    return len(s) * (size * CW + ls)


def wrap(s: str, size: float, maxw: float) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        cand = f"{cur} {word}".strip()
        if tw(cand, size) <= maxw or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def clip(s: str, size: float, maxw: float) -> str:
    if tw(s, size) <= maxw:
        return s
    n = max(1, int(maxw / (size * CW)) - 1)
    return s[:n].rstrip() + "…"


def t(x, y, s, size=15, fill=None, weight=400, anchor="start", ls=0, italic=False, raw=False):
    style = ' font-style="italic"' if italic else ""
    body = s if raw else esc(s)
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill or C["body"]}" '
            f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}"{style}>{body}</text>')


def icon(name, x, y, size=24, color=None, sw=2):
    s = size / 24
    return (f'<g transform="translate({x:.1f},{y:.1f}) scale({s:.3f})" fill="none" '
            f'stroke="{color or C["accent"]}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS[name]}</g>')


def frame(w, h, fill=None, r=14):
    return (f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{r}" '
            f'fill="{fill or C["bg"]}" stroke="{C["border"]}" stroke-width="1.5"/>')


def hline(x1, x2, y):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{C["line"]}" stroke-width="1.2"/>'


def pill(x, y, label, size=13, color=None, fill=None, h=None):
    color = color or C["body"]
    h = h or size + 14
    w = tw(label, size) + 22
    out = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h/2 if fill else 7}" '
           f'fill="{fill or C["tile"]}" stroke="{C["border"] if not fill else color}" stroke-width="1.2"/>'
           + t(x + w / 2, y + h / 2 + size * 0.36, label, size, color, anchor="middle"))
    return out, w


def heading(x, y, ico, label, sub=None, size=19):
    out = icon(ico, x, y - size + 1, size + 4)
    out += t(x + size + 16, y, label, size, C["accent"], 700, ls=1.2)
    if sub:
        out += t(x + size + 16, y + 24, sub, 13, C["muted"], italic=True)
    return out


def document(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title>'
            f'<style>text{{font-family:{MONO}}}</style>{body}</svg>\n')


def pulse(cx, cy, r=5, color=None):
    color = color or C["accent"]
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}">'
            f'<animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')


# ─────────────────────────────────────────────────────────────── panels
def hero():
    W, P = 1200, 48
    b = []
    # man-page rail
    b.append(t(P, 54, "SVATSA(1)", 16, C["accent2"], 600, ls=1.5))
    b.append(t(P + 128, 54, "·  ENGINEERING MANUAL", 14, C["muted"], ls=1.5))
    label = PROFILE["status"]
    bw = tw(label, 12.5, 1) + 46
    bx = W - P - bw
    b.append(f'<rect x="{bx:.1f}" y="34" width="{bw:.1f}" height="30" rx="15" fill="{C["accent"]}" '
             f'fill-opacity=".08" stroke="{C["accent"]}" stroke-width="1.3"/>')
    b.append(pulse(bx + 18, 49, 4.5))
    b.append(t(bx + 32, 53.5, label, 12.5, C["accent"], 600, ls=1))
    b.append(hline(P, W - P, 80))
    # title block
    b.append(t(P - 4, 166, PROFILE["handle"], 86, C["accent"], 800, ls=2))
    nx = P + tw(PROFILE["handle"], 86, 2) + 24
    b.append(t(nx, 132, PROFILE["name"], 22, C["text"], 600))
    b.append(t(nx, 162, "github.com/" + USER, 15, C["muted"]))
    b.append(t(P, 206, PROFILE["subtitle"], 20, C["text"]))
    b.append(hline(P, W - P, 234))
    # left column: NAME / SYNOPSIS / DESCRIPTION
    LX, LW = P, 570
    y = 276
    b.append(t(LX, y, "NAME", 17, C["accent"], 700, ls=1.5))
    y += 30
    for line in wrap(PROFILE["name_line"], 15, LW - 40):
        b.append(t(LX + 36, y, line, 15, C["body"]))
        y += 22
    y += 18
    b.append(t(LX, y, "SYNOPSIS", 17, C["accent"], 700, ls=1.5))
    y += 16
    b.append(f'<rect x="{LX+36}" y="{y}" width="{LW-36}" height="44" rx="8" fill="{C["panel"]}" stroke="{C["border"]}"/>')
    syn = (f'<tspan fill="{C["accent"]}">svatsa</tspan> '
           f'<tspan fill="{C["body"]}">[</tspan><tspan fill="{C["accent2"]}">--backend</tspan><tspan fill="{C["body"]}">] [</tspan>'
           f'<tspan fill="{C["accent2"]}">--realtime</tspan><tspan fill="{C["body"]}">] [</tspan>'
           f'<tspan fill="{C["accent2"]}">--llm</tspan><tspan fill="{C["body"]}">]</tspan>'
           f'<tspan dx="10" fill="{C["warn"]}">&lt;problem&gt;</tspan>')
    b.append(t(LX + 54, y + 28, syn, 16, raw=True))
    y += 44 + 38
    b.append(t(LX, y, "DESCRIPTION", 17, C["accent"], 700, ls=1.5))
    y += 30
    for line in wrap(PROFILE["description"], 15, LW - 40):
        b.append(t(LX + 36, y, line, 15, C["body"]))
        y += 23
    left_bottom = y
    # right column: OPTIONS
    RX = 664
    b.append(f'<line x1="{RX-34}" y1="256" x2="{RX-34}" y2="{left_bottom-6}" stroke="{C["line"]}" stroke-width="1.2"/>')
    ry = 276
    b.append(t(RX, ry, "OPTIONS", 17, C["accent"], 700, ls=1.5))
    b.append(t(RX + 92, ry, "(stack)", 14, C["muted"]))
    ry += 22
    step = max(38, (left_bottom - ry - 10) / len(PROFILE["options"]))
    for ico, flag, val in PROFILE["options"]:
        b.append(icon(ico, RX, ry + 6, 20, C["blue"], 1.8))
        b.append(t(RX + 32, ry + 21, "--" + flag, 12.5, C["muted"]))
        b.append(t(RX + 32 + 88, ry + 21, clip(val, 14.5, W - P - RX - 120), 14.5, C["text"]))
        ry += step
    H = int(max(left_bottom, ry) + 26)
    return document(W, H, frame(W, H) + "".join(b),
                    f"SVATSA(1) — {PROFILE['name']}: {PROFILE['subtitle']}. {PROFILE['description']}")


def section_bar(ico, label, sub):
    W, H = 1200, 76
    b = frame(W, H) + heading(40, 46, ico, label, size=22)
    b += t(40 + 22 + 16 + tw(label, 22, 1.2) + 22, 45, sub, 14, C["muted"], italic=True)
    return document(W, H, b, f"{label} — {sub}")


def card_layout(p, W=580):
    """Returns (height, parts) so paired cards can share one height."""
    P, TX = 26, 112
    tag_lines = wrap(p["tagline"], 15, W - TX - P)
    works = wrap(p["works"], 14, W - 2 * P - 92)
    hard = wrap(p["hard"], 14, W - 2 * P - 92)
    top = max(54 + 24 * len(tag_lines) + 30, 118)
    body_h = 22 + 21 * len(works) + 12 + 21 * len(hard) + 14 + 30 + 18 + 30 + P
    return top + body_h, (tag_lines, works, hard, top)


def card(p, H, parts, W=580):
    P, TX = 26, 112
    tag_lines, works, hard, top = parts
    b = [frame(W, H, C["panel"])]
    b.append(f'<rect x="{P}" y="{P}" width="66" height="66" rx="12" fill="{C["tile"]}" stroke="{C["border"]}"/>')
    b.append(icon(p["icon"], P + 17, P + 17, 32, C["blue"], 2))
    b.append(t(TX, 52, p["name"], 21, C["text"], 700))
    b.append(t(W - P, 50, "repo ↗", 13.5, C["blue"], anchor="end"))
    y = 78
    for line in tag_lines:
        b.append(t(TX, y, line, 15, C["body"]))
        y += 24
    b.append(t(TX, y + 2, p["features"], 13.5, C["muted"]))
    y = top + 4
    b.append(hline(P, W - P, y))
    y += 28
    b.append(t(P, y, "WORKS", 12, C["accent"], 700, ls=1.5))
    for line in works:
        b.append(t(P + 92, y, line, 14, C["body"]))
        y += 21
    y += 12
    b.append(t(P, y, "HARD PART", 12, C["accent"], 700, ls=1.2))
    for line in hard:
        b.append(t(P + 92, y, line, 14, C["body"]))
        y += 21
    y += 14
    b.append(t(P, y, "METRIC", 12, C["accent"], 700, ls=1.5))
    b.append(t(P + 92, y, p["metric"], 14, C["warn"], 600))
    x, ty = P, H - P - 27
    for tag in p["tags"]:
        s, w = pill(x, ty, tag, 12.5)
        if x + w > W - P:
            break
        b.append(s)
        x += w + 8
    return document(W, H, "".join(b),
                    f"{p['name']}: {p['tagline']} Works: {p['works']} Metric: {p['metric']}")


def api_panel(H, W=590):
    P = 30
    b = [frame(W, H), heading(P, 50, "book", "API REFERENCE", "query the svatsa service")]
    y = 98
    rh = (H - y - P) / len(API)
    b.append(f'<rect x="{P}" y="{y}" width="{W-2*P}" height="{rh*len(API):.1f}" rx="10" fill="{C["panel"]}" stroke="{C["border"]}"/>')
    for i, (m, path, desc, code, note) in enumerate(API):
        ry = y + i * rh
        if i:
            b.append(hline(P + 1, W - P - 1, ry))
        mc = C["warn"] if m == "POST" else C["accent2"]
        b.append(t(P + 18, ry + rh / 2 - 3, m, 14, mc, 700))
        b.append(t(P + 74, ry + rh / 2 - 3, path, 15, C["text"]))
        b.append(t(P + 74, ry + rh / 2 + 17, desc, 12.5, C["muted"]))
        label = f"{code} {note}"
        pw = tw(label, 12.5) + 22
        color = C["accent"] if code.startswith("2") else C["orange"]
        s, _ = pill(W - P - 16 - pw, ry + rh / 2 - 23, label, 12.5, color, C["bg"], 26)
        b.append(s)
    return document(W, H, "".join(b), "API reference: " + "; ".join(f"{m} {p} → {c} {n}" for m, p, _, c, n in API))


def activity_panel(items, updated, H, W=590):
    P = 30
    b = [frame(W, H), heading(P, 50, "bolt", "LATEST ACTIVITY", f"auto-updated daily · GitHub Actions · {updated}")]
    y = 108
    if not items:
        b.append(t(P, y + 20, "no public commits fetched yet — next run fills this in.", 14, C["muted"]))
    rh = (H - y - P + 8) / max(len(items), 1)
    for it in items[:ACTIVITY_ROWS]:
        b.append(f'<circle cx="{P+6}" cy="{y+5}" r="5" fill="{C["accent"]}"/>')
        b.append(t(P + 24, y + 10, clip(it["msg"], 14.5, W - 2 * P - 110), 14.5, C["text"]))
        b.append(t(P + 24, y + 31, it["repo"], 12.5, C["muted"]))
        b.append(t(W - P, y + 10, it["ago"], 12.5, C["muted"], anchor="end"))
        y += rh
    alt = ("Latest activity: " + "; ".join(f"{i['msg']} ({i['repo']}, {i['ago']})" for i in items)) if items else "Latest activity"
    return document(W, H, "".join(b), alt)


def principles_panel(H, W=590):
    P = 30
    b = [frame(W, H), heading(P, 50, "bulb", "ENGINEERING PRINCIPLES")]
    y = 96
    rh = (H - y - P + 6) / len(PRINCIPLES)
    for rule, where in PRINCIPLES:
        b.append(t(P, y + 4, "›", 18, C["accent"], 700))
        b.append(t(P + 22, y + 4, rule, 14.5, C["text"]))
        b.append(t(P + 22, y + 25, "→ " + where, 12.5, C["muted"]))
        y += rh
    return document(W, H, "".join(b), "Engineering principles: " + " ".join(r for r, _ in PRINCIPLES))


def dsa_panel(lc, H, W=590):
    P = 30
    b = [frame(W, H), heading(P, 50, "bars", "DSA PROGRESS", "LeetCode · auto-updated daily")]
    total = lc.get("total")
    big = f"{total}" if total else DSA_FALLBACK_TOTAL
    b.append(t(P, 150, big, 54, C["accent2"], 700))
    b.append(t(P + 4, 178, "problems solved", 14, C["body"]))
    b.append(t(P + 4, 200, "@" + LEETCODE, 13, C["muted"]))
    BX, BW = 252, W - 252 - P
    y = 112
    diffs = [("easy", C["accent2"]), ("medium", C["warn"]), ("hard", C["orange"])]
    if total and all(k in lc for k, _ in diffs):
        for k, col in diffs:
            v = lc[k]
            frac = v / total if total else 0
            b.append(t(BX, y, k.upper(), 12, C["muted"], 600, ls=1.2))
            b.append(t(BX + BW, y, str(v), 13, C["text"], anchor="end"))
            b.append(f'<rect x="{BX}" y="{y+9}" width="{BW}" height="8" rx="4" fill="{C["panel"]}" stroke="{C["border"]}"/>')
            b.append(f'<rect x="{BX}" y="{y+9}" width="{max(8, BW*frac):.1f}" height="8" rx="4" fill="{col}"/>')
            y += 40
    else:
        b.append(t(BX, y + 10, "difficulty split appears", 13, C["muted"]))
        b.append(t(BX, y + 30, "after the first live run.", 13, C["muted"]))
    b.append(hline(P, W - P, H - 74))
    b.append(t(P, H - 44, "TOPICS", 12, C["accent"], 700, ls=1.5))
    b.append(t(P + 82, H - 44, DSA_TOPICS, 13.5, C["body"]))
    alt = f"DSA progress: {big} LeetCode problems solved" + (
        f" (easy {lc['easy']}, medium {lc['medium']}, hard {lc['hard']})" if total and "easy" in lc else "")
    return document(W, H, "".join(b), alt)


def strip_panel():
    W, P = 1200, 40
    cols = [(P, "linkout", "SEE ALSO", [" · ".join(SEE_ALSO), "links below ↓"], C["accent"]),
            (P + 384, "trophy", "RECORD", RECORD, C["accent"]),
            (P + 768, "alert", "BUGS", BUGS, C["warn"])]
    lines = max(len(c[3]) for c in cols)
    H = 74 + 24 * lines + 22
    b = [frame(W, H)]
    for i, (x, ico, label, rows, col) in enumerate(cols):
        if i:
            b.append(f'<line x1="{x-24}" y1="26" x2="{x-24}" y2="{H-26}" stroke="{C["line"]}" stroke-width="1.2"/>')
        b.append(icon(ico, x, 28, 22, col))
        b.append(t(x + 34, 46, label, 17, col, 700, ls=1.5))
        for j, r in enumerate(rows):
            b.append(t(x + 34, 78 + 24 * j, clip(r, 13.5, 330), 13.5, C["muted"] if "↓" in r else C["body"]))
    alt = f"See also: {', '.join(SEE_ALSO)}. Record: {'; '.join(RECORD)}. Bugs: {' '.join(BUGS)}"
    return document(W, H, "".join(b), alt)


def footer_panel(updated):
    W, H = 1200, 64
    b = [frame(W, H)]
    prompt = (f'<tspan fill="{C["accent"]}" font-weight="700">svatsa@github</tspan>'
              f'<tspan fill="{C["body"]}">:</tspan><tspan fill="{C["blue"]}">~</tspan>'
              f'<tspan fill="{C["body"]}">$ make --keep-going</tspan>')
    b.append(t(36, 39, prompt, 16, raw=True))
    cx = 36 + tw("svatsa@github:~$ make --keep-going", 16) + 8
    b.append(f'<rect x="{cx:.1f}" y="25" width="9" height="18" fill="{C["accent"]}">'
             f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" calcMode="discrete" repeatCount="indefinite"/></rect>')
    end = "— END OF MANUAL —"
    b.append(t(W - 36, 38, end, 14, C["muted"], anchor="end", ls=1))
    b.append(t(W - 36 - tw(end, 14, 1) - 24, 38, f"rev {updated}", 12.5, C["muted"], anchor="end"))
    return document(W, H, "".join(b), "End of manual")


# ─────────────────────────────────────────────────────────────── live data
def http_json(url, data=None, headers=None):
    h = {"User-Agent": "svatsa-profile-builder", "Accept": "application/json"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def gh(path):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return http_json("https://api.github.com" + path, headers=headers)


def fetch_activity():
    repos = gh(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=12")
    items = []
    for r in repos:
        if r["fork"] or r["name"] in SKIP_REPOS:
            continue
        try:
            commits = gh(f"/repos/{USER}/{r['name']}/commits?author={USER}&per_page=10")
        except Exception:
            continue
        for c in commits:
            msg = c["commit"]["message"].splitlines()[0].strip()
            if NOISE.search(msg) or len(msg) < 8:
                continue
            items.append({"msg": msg, "repo": r["name"], "url": c["html_url"],
                          "date": c["commit"]["author"]["date"]})
        if len(items) >= ACTIVITY_ROWS * 3:
            break
    items.sort(key=lambda i: i["date"], reverse=True)
    out, per = [], {}
    for it in items:  # max 2 rows per repo so one busy repo can't take over
        if per.get(it["repo"], 0) < 2:
            out.append(it)
            per[it["repo"]] = per.get(it["repo"], 0) + 1
        if len(out) == ACTIVITY_ROWS:
            break
    return out


def fetch_leetcode():
    q = ("query($u:String!){matchedUser(username:$u){submitStats{acSubmissionNum"
         "{difficulty count}}}}")
    res = http_json("https://leetcode.com/graphql", {"query": q, "variables": {"u": LEETCODE}},
                    {"Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0"})
    nums = {d["difficulty"].lower(): d["count"]
            for d in res["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]}
    return {"total": nums["all"], "easy": nums["easy"], "medium": nums["medium"], "hard": nums["hard"]}


def ago(iso, now):
    d = now - datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.days <= 0:
        return f"{max(1, d.seconds // 3600)}h ago"
    if d.days < 14:
        return f"{d.days}d ago"
    if d.days < 60:
        return f"{d.days // 7}w ago"
    return f"{d.days // 30}mo ago"


# ─────────────────────────────────────────────────────────────── build
def write(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")
    return f"{RAW}/{name}?v={hashlib.sha1(content.encode()).hexdigest()[:8]}"


def main():
    offline = "--offline" in sys.argv
    ASSETS.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = datetime.now(timezone.utc)

    if not offline:
        try:
            state["activity"] = fetch_activity()
            print(f"activity: {len(state['activity'])} commits")
        except Exception as e:
            print(f"activity fetch failed, keeping last good: {e}")
        try:
            state["leetcode"] = fetch_leetcode()
            print(f"leetcode: {state['leetcode']}")
        except Exception as e:
            print(f"leetcode fetch failed, keeping last good: {e}")
    STATE.write_text(json.dumps(state, indent=2) + "\n")

    items = [dict(i, ago=ago(i["date"], now)) for i in state.get("activity", [])]
    updated = now.astimezone(IST).strftime("%d %b %Y")

    urls = {"hero": write("hero.svg", hero()),
            "logbook": write("logbook.svg", section_bar(
                "folder", "ENGINEERING LOGBOOK",
                "selected systems — what works today, separate from what's planned"))}
    for a, b_ in (PROJECTS[0:2], PROJECTS[2:4]):
        (ha, pa), (hb, pb) = card_layout(a), card_layout(b_)
        H = int(max(ha, hb))
        urls[a["slug"]] = write(f"card-{a['slug']}.svg", card(a, H, pa))
        urls[b_["slug"]] = write(f"card-{b_['slug']}.svg", card(b_, H, pb))
    urls["api"] = write("api.svg", api_panel(392))
    urls["activity"] = write("activity.svg", activity_panel(items, updated, 392))
    urls["principles"] = write("principles.svg", principles_panel(340))
    urls["dsa"] = write("dsa.svg", dsa_panel(state.get("leetcode", {}), 340))
    urls["strip"] = write("strip.svg", strip_panel())
    urls["footer"] = write("footer.svg", footer_panel(updated))

    def img(key, alt, width="100%"):
        return f'<img src="{urls[key]}" alt="{esc(alt)}" width="{width}" />'

    def card_link(p):
        return (f'<a href="https://github.com/{USER}/{p["repo"]}">'
                + img(p["slug"], f"{p['name']} — {p['tagline']}", "49%") + "</a>")

    activity_md = "\n".join(
        f"- [{esc(i['msg'])}]({i['url']}) · `{i['repo']}` · {i['ago']}" for i in items) or "- no activity yet"
    links_md = " &nbsp;·&nbsp; ".join(f"[{n}]({u})" for n, u in LINKS)

    readme = f"""<!-- Generated by scripts/build_profile.py. Edit the script, not this file. -->

<p align="center">
  {img("hero", "SVATSA(1) — Shubham Vatsa, backend-first engineer")}
</p>

<p align="center">
  {img("logbook", "Engineering logbook")}
</p>

<p align="center">
  {card_link(PROJECTS[0])}
  {card_link(PROJECTS[1])}
</p>
<p align="center">
  {card_link(PROJECTS[2])}
  {card_link(PROJECTS[3])}
</p>

<p align="center">
  {img("api", "API reference", "49%")}
  {img("activity", "Latest engineering activity", "49%")}
</p>

<p align="center">
  {img("principles", "Engineering principles", "49%")}
  {img("dsa", "DSA progress", "49%")}
</p>

<p align="center">
  {img("strip", "See also, record and known bugs")}
</p>

<p align="center">
  {links_md}
</p>

<details>
<summary><sub>activity log · plain text</sub></summary>

{activity_md}

</details>

<p align="center">
  {img("footer", "End of manual")}
</p>
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print("built README.md and", len(urls), "panels")


if __name__ == "__main__":
    main()

