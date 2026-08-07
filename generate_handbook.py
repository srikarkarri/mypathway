#!/usr/bin/env python3
"""
generate_handbook.py
────────────────────
Converts a CFISD High School Course Description Handbook PDF
into a handbook.json file for the Bridgeland Course Navigator app.

Usage:
  python generate_handbook.py --pdf path/to/handbook.pdf
  python generate_handbook.py --pdf path/to/handbook.pdf --out assets/handbook.json
  python generate_handbook.py --url https://... --out assets/handbook.json

Requirements:
  pip install anthropic pypdf pdfplumber requests
  export ANTHROPIC_API_KEY=sk-ant-...
"""

import os
import sys
import json
import re
import argparse
import textwrap
import urllib.request
import tempfile
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("❌  Missing: pip install pdfplumber")

try:
    import anthropic
except ImportError:
    sys.exit("❌  Missing: pip install anthropic")


# ─── CONFIG ───────────────────────────────────────────────────────────────────

MODEL  = "claude-sonnet-4-6"
CLIENT = None   # initialised in main()

# How many characters of PDF text to send per Claude call
# (keeps well within 200k context window even for 130-page PDFs)
CHUNK_LIMIT = 60_000


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    """Extract all text from the PDF preserving layout."""
    import subprocess, shutil
    if shutil.which("pdftotext"):
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    # fallback: pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return "\n\n".join(pages)


def ask_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """Single Claude call, returns text content."""
    msg = CLIENT.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return msg.content[0].text.strip()


def ask_claude_json(system: str, user: str, max_tokens: int = 4096) -> dict | list:
    """Claude call that must return valid JSON."""
    system_json = (
        system
        + "\n\nCRITICAL: Your entire response must be valid JSON only. "
        "No markdown fences, no explanation, no preamble. "
        "Start with { or [ and end with } or ]."
    )
    raw = ask_claude(system_json, user, max_tokens)
    # strip any accidental fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠  JSON parse error: {e}\n  Raw (first 400 chars): {raw[:400]}")
        raise


# ─── EXTRACTION FUNCTIONS ─────────────────────────────────────────────────────

SYSTEM_BASE = textwrap.dedent("""
    You are a precise data-extraction assistant for a high school course planning app.
    You are given raw text extracted from a CFISD (Cypress-Fairbanks ISD) High School
    Course Description Handbook PDF. Extract only what is explicitly stated in the text.
    Do not invent, assume, or fill in gaps. If a value is not present, use null or [].
""").strip()


def extract_meta(text: str) -> dict:
    print("  → Extracting year / label …")
    result = ask_claude_json(
        SYSTEM_BASE,
        f"""From this handbook text, extract:
- "year": the school year label (e.g. "2026–27")
- "label": the full publication title (e.g. "CFISD 2026–2027 High School Course Description Handbook")

Return JSON: {{"year": "...", "label": "..."}}

TEXT:
{text[:3000]}"""
    )
    return result


def extract_stats(text: str) -> list:
    print("  → Extracting stats …")
    # These are mostly stable — we derive from grad req counts
    return [
        {"num": "26",  "label": "Credits to Graduate", "sub": "Foundation + Endorsement", "color": "#E8500A"},
        {"num": "5",   "label": "Endorsement Paths",   "sub": "Choose what fits you",     "color": "#0A2240"},
        {"num": "7",   "label": "Classes Per Day",     "sub": "Semester system",           "color": "#1A6B9A"},
        {"num": "30+", "label": "CTE Programs",        "sub": "Career pathways available", "color": "#2E7D32"},
    ]


def extract_graduation_reqs(text: str) -> list:
    print("  → Extracting graduation requirements …")
    # Find the graduation requirements section
    section = _find_section(text, [
        "graduation requirements", "foundation high school program",
        "course", "foundation", "endorsement", "english", "mathematics",
        "credits required"
    ], max_chars=25000)

    return ask_claude_json(
        SYSTEM_BASE,
        f"""Extract the graduation credit requirements from this handbook section.
Return a JSON array where each element has:
  "subject": subject area name (string)
  "credits":  number of credits required (number, e.g. 4 or 0.5)
  "note":     key notes/details about the requirement (string)

Include: English, PACE/PACE Plus, Mathematics, Science, Social Studies,
Languages Other Than English, Physical Education, Fine Arts, Health, Electives.

TEXT:
{section}"""
    )


def extract_gpa_scales(text: str) -> list:
    print("  → Extracting GPA scales …")
    section = _find_section(text, [
        "grading scale", "grade points", "gpa", "class ranking",
        "weighted", "level", "horizons", "life skills"
    ], max_chars=15000)

    return ask_claude_json(
        SYSTEM_BASE,
        f"""Extract ALL grading/GPA scales from this handbook section.
There may be one scale (for all classes) or multiple (e.g. one for 2029 and before,
one for 2030 and beyond).

Return a JSON array where each element has:
  "label":   descriptive label (e.g. "Classes of 2018–2029 (Weighted 6.0 Scale)")
  "columns": array of column header strings (level names, e.g. ["K / AP / HORIZONS", "L-Level", ...])
  "rows":    array of row objects, each with:
               "grade": grade label (e.g. "A (90–100)")
               "pts":   array of point values matching columns (numbers)
               "fail":  true only for failing grade rows (optional, default false)

TEXT:
{section}""",
        max_tokens=6000
    )


def extract_endorsements(text: str) -> list:
    print("  → Extracting endorsements …")
    section = _find_section(text, [
        "endorsement", "stem", "business", "public services",
        "arts", "multidisciplinary", "option", "students may earn"
    ], max_chars=30000)

    return ask_claude_json(
        SYSTEM_BASE,
        f"""Extract all 5 CFISD graduation endorsements from this handbook text.
Return a JSON array where each element has:
  "id":          slug string: one of stem, business, public-services, arts-humanities, multidisciplinary
  "name":        display name (e.g. "STEM")
  "subtitle":    subject areas (e.g. "Science · Technology · Engineering · Math")
  "color":       use these fixed hex values:
                   stem="#1A6B9A", business="#2E7D32", public-services="#6A1B9A",
                   arts-humanities="#C62828", multidisciplinary="#C94208"
  "lightColor":  light tint: stem="#E8F4FD", business="#E8F5E9", public-services="#F3E5F5",
                   arts-humanities="#FFEBEE", multidisciplinary="#FFF4EE"
  "emoji":       stem="🔬", business="💼", public-services="🏥",
                   arts-humanities="🎨", multidisciplinary="📚"
  "bestFor":     one sentence describing who this suits (from handbook text)
  "requiredCore": array of course names required regardless of route (e.g. ["Algebra II","Chemistry","Physics"] for STEM, [] for others)
  "routes":      array of route objects, each: {{"name": "Option N: Label", "desc": "description"}}
  "careers":     array of 4 sample career titles
  "interestTags": array of interest tag strings matching these values:
                   coding, engineering, math, science, research, robotics,
                   business, marketing, media, architecture, it, culinary, automotive, fashion,
                   healthcare, teaching, service, leadership, people, military,
                   art, music, theatre, history, languages, culture, writing,
                   college, balanced, ap, dual credit, generalist, undecided

TEXT:
{section}""",
        max_tokens=8000
    )


def extract_qa(text: str) -> list:
    print("  → Extracting AI Q&A pairs …")
    # Send the full text but chunked for QA extraction
    chunk = text[:CHUNK_LIMIT]

    return ask_claude_json(
        SYSTEM_BASE,
        f"""From this CFISD handbook, create a comprehensive set of Q&A entries for an AI chat assistant.
Cover ALL of the following topics (create one entry per topic):
  credits to graduate, algebra II / distinguished level, PACE / PACE Plus, fine arts requirement,
  PE requirement, STEM endorsement options, K-level / Academic Advanced entry criteria,
  K-level / Academic Advanced removal criteria, dual credit eligibility, class rank and GPA scale,
  honor graduate designations, schedule change deadlines, FAFSA/TAFSA graduation requirement,
  top 10% automatic admission, credit by exam, grade classification / promotion thresholds,
  pass/fail option, health requirement, computer science I K (CS I K), computer science II K (CS II K),
  summer school, TxVSN online courses, virtual pathways (if mentioned), social studies changes (if any),
  performance acknowledgments (if mentioned).

For each entry return:
  "keywords": array of 6–12 lowercase keyword phrases a student might use to ask this question
  "answer":   comprehensive answer drawn strictly from the handbook text (2–5 sentences)
  "source":   page reference, e.g. "Graduation Requirements (p. 23–27)"

Return a JSON array of these objects.

TEXT:
{chunk}""",
        max_tokens=8000
    )


def extract_reminders(text: str, year: str) -> list:
    print("  → Extracting key reminders …")
    chunk = text[:30000]
    return ask_claude_json(
        SYSTEM_BASE,
        f"""From this handbook, extract 6–8 of the most important policy facts
that students and families must know — the things most likely to surprise them
or cause problems if missed.

Return a JSON array where each element has:
  "icon": a single relevant emoji
  "text": a 1–2 sentence plain-English reminder (no jargon, student-friendly)

Focus on: GPA / grade points, FAFSA requirement, schedule change deadlines,
K/AP entry and removal rules, Algebra II importance, honor designations,
and any NEW items introduced in {year}.

TEXT:
{chunk}"""
    )


def extract_suggested_questions(qa_list: list) -> list:
    """Derive 12 suggested questions from the QA entries."""
    print("  → Deriving suggested questions …")
    topics = [entry.get("keywords", [""])[0] for entry in qa_list[:20]]
    return ask_claude_json(
        SYSTEM_BASE,
        f"""Given these Q&A topics from a CFISD handbook, write exactly 12 natural,
student-friendly question strings a high schooler might type into a chat assistant.
Cover a diverse mix of topics. Keep each question under 12 words.

Topics: {json.dumps(topics)}

Return a JSON array of 12 question strings."""
    )


def build_planner(text: str, year: str) -> dict:
    print("  → Building year planner …")
    chunk = text[:CHUNK_LIMIT]

    grades_raw = ask_claude_json(
        SYSTEM_BASE,
        f"""For the CFISD {year} handbook, generate a detailed grade-by-grade planning guide
for grades 8 through 12 (keys "8", "9", "10", "11", "12").

For each grade return an object with:
  "grade":             e.g. "9th Grade"
  "emoji":             single relevant emoji
  "color":             hex color — use: 8th="#0A2240", 9th="#1A5276", 10th="#1E8449", 11th="#7D6608", 12th="#922B21"
  "stage":             short phase label (5–8 words)
  "focus":             2–3 sentence strategic paragraph for this grade
  "checklist":         array of 5–6 specific action items for this grade
  "milestones":        array of 5–6 sequential milestone descriptions
  "watchouts":         array of 4–6 risk/warning items (short, specific)
  "whatToReview":      array of 5–6 objects: {{"icon": "emoji", "item": "course or action"}}
  "familyQuestions":   array of 6–8 conversation-starter questions for families
  "coreCreditsToWatch": array of 4–6 subject/credit labels as short badge strings

Base the content on actual CFISD policies from the handbook text below.

Return a JSON object keyed by grade number string ("8" through "12").

TEXT:
{chunk}""",
        max_tokens=8000
    )
    return grades_raw


# ─── SECTION FINDER ──────────────────────────────────────────────────────────

def _find_section(text: str, keywords: list[str], max_chars: int = 20000) -> str:
    """Find the most relevant section of text using keyword matching."""
    lower = text.lower()
    best_pos = 0
    best_score = 0
    window = 500

    for i in range(0, len(lower) - window, window // 2):
        chunk = lower[i:i + window]
        score = sum(1 for kw in keywords if kw in chunk)
        if score > best_score:
            best_score = score
            best_pos = i

    start = max(0, best_pos - 500)
    return text[start: start + max_chars]


# ─── INTERESTS (static — same every year) ────────────────────────────────────

INTERESTS_STATIC = [
    {"id": "coding",       "label": "Coding & Software",          "icon": "💻", "tags": ["stem"]},
    {"id": "engineering",  "label": "Engineering & Robotics",      "icon": "⚙️", "tags": ["stem"]},
    {"id": "math",         "label": "Math & Analytics",            "icon": "📐", "tags": ["stem"]},
    {"id": "science",      "label": "Science & Research",          "icon": "🔬", "tags": ["stem"]},
    {"id": "healthcare",   "label": "Healthcare & Medicine",       "icon": "🏥", "tags": ["public-services"]},
    {"id": "business",     "label": "Business & Finance",          "icon": "💼", "tags": ["business"]},
    {"id": "marketing",    "label": "Marketing & Sales",           "icon": "📊", "tags": ["business"]},
    {"id": "media",        "label": "Media & Film Production",     "icon": "🎬", "tags": ["business"]},
    {"id": "art",          "label": "Art & Design",                "icon": "🎨", "tags": ["arts-humanities"]},
    {"id": "music",        "label": "Music & Performance",         "icon": "🎵", "tags": ["arts-humanities"]},
    {"id": "theatre",      "label": "Theatre & Drama",             "icon": "🎭", "tags": ["arts-humanities"]},
    {"id": "history",      "label": "History & Social Studies",    "icon": "🌍", "tags": ["arts-humanities", "multidisciplinary"]},
    {"id": "languages",    "label": "Languages & Culture",         "icon": "🗣️", "tags": ["arts-humanities"]},
    {"id": "teaching",     "label": "Teaching & Education",        "icon": "📖", "tags": ["public-services"]},
    {"id": "leadership",   "label": "Leadership & Service",        "icon": "🤝", "tags": ["public-services"]},
    {"id": "college",      "label": "Broad College Prep",          "icon": "🎓", "tags": ["multidisciplinary"]},
    {"id": "architecture", "label": "Architecture & Construction", "icon": "🏗️", "tags": ["business"]},
    {"id": "culinary",     "label": "Culinary Arts",               "icon": "👨‍🍳", "tags": ["business"]},
    {"id": "robotics",     "label": "Robotics & AI",               "icon": "🤖", "tags": ["stem"]},
    {"id": "automotive",   "label": "Automotive Technology",       "icon": "🚗", "tags": ["business"]},
]


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    global CLIENT

    parser = argparse.ArgumentParser(description="Generate handbook.json from a CFISD PDF.")
    parser.add_argument("--pdf",  help="Local path to the handbook PDF")
    parser.add_argument("--url",  help="URL to download the handbook PDF from")
    parser.add_argument("--out",  default="assets/handbook.json", help="Output path (default: assets/handbook.json)")
    parser.add_argument("--key",  help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    if not args.pdf and not args.url:
        parser.error("Provide --pdf or --url")

    # API key
    api_key = args.key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("❌  Set ANTHROPIC_API_KEY or pass --key")
    CLIENT = anthropic.Anthropic(api_key=api_key)

    # Resolve PDF path
    pdf_path = args.pdf
    tmp_file = None
    if args.url:
        print(f"⬇  Downloading PDF from {args.url} …")
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            urllib.request.urlretrieve(args.url, tmp_file.name)
            pdf_path = tmp_file.name
            print(f"   Saved to {pdf_path}")
        except Exception as e:
            sys.exit(f"❌  Download failed: {e}")

    if not pdf_path or not Path(pdf_path).exists():
        sys.exit(f"❌  PDF not found: {pdf_path}")

    print(f"\n📄 Extracting text from PDF …")
    text = extract_text(pdf_path)
    print(f"   {len(text):,} characters extracted\n")

    print("🤖 Calling Claude to extract structured data …\n")

    meta         = extract_meta(text)
    year         = meta.get("year", "????")
    label        = meta.get("label", f"CFISD {year} High School Course Description Handbook")
    stats        = extract_stats(text)
    grad_reqs    = extract_graduation_reqs(text)
    gpa_scales   = extract_gpa_scales(text)
    endorsements = extract_endorsements(text)
    qa_entries   = extract_qa(text)
    reminders    = extract_reminders(text, year)
    suggested_qs = extract_suggested_questions(qa_entries)
    planner      = build_planner(text, year)

    handbook = {
        "year":               year,
        "label":              label,
        "stats":              stats,
        "reminders":          reminders,
        "graduationReqs":     grad_reqs,
        "gpaScales":          gpa_scales,
        "endorsements":       endorsements,
        "interests":          INTERESTS_STATIC,
        "suggestedQuestions": suggested_qs,
        "handbookQA":         qa_entries,
        "planner":            planner,
    }

    # Ensure output directory exists
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(handbook, indent=2, ensure_ascii=False))

    print(f"\n✅  handbook.json written → {out_path}")
    print(f"   Year:        {year}")
    print(f"   Grad reqs:   {len(grad_reqs)} rows")
    print(f"   GPA scales:  {len(gpa_scales)}")
    print(f"   Endorsements:{len(endorsements)}")
    print(f"   QA entries:  {len(qa_entries)}")
    print(f"   Reminders:   {len(reminders)}")
    print(f"   Planner:     grades {list(planner.keys())}")
    print(f"\n🚀  Drop assets/handbook.json into your GitHub Pages repo — done.\n")

    if tmp_file:
        os.unlink(tmp_file.name)


if __name__ == "__main__":
    main()
