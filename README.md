# Bridgeland High School · Course Pathways Navigator

A student-built, AI-powered app to explore course pathways, discover your best-fit
endorsement, and get instant answers to all your high school planning questions.

---

## 📁 File Structure

```
/
├── index.html                 ← The app (permanent — never edit)
├── generate_handbook.py       ← Annual update pipeline
├── README.md                  ← This file
└── assets/
    └── handbook.json          ← Active year's data (swap this every year)
```

---


---

## 📅 Annual Update Process (takes ~5 minutes)

Each year CFISD releases a new Course Description Handbook PDF.
You only ever need to update **one file**: `assets/handbook.json`.

### Step 1 — Get the new handbook PDF

Download the PDF from CFISD (e.g. from the finalsite URL):
```
https://resources.finalsite.net/images/.../2027-28HighSchoolCourseDescriptionBooklet.pdf
```
Or save the PDF locally.

### Step 2 — Install dependencies (one-time)

```bash
pip install anthropic pdfplumber requests
```

### Step 3 — Set your Anthropic API key (one-time)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
Get a key at https://console.anthropic.com

### Step 4 — Run the pipeline

**From a local PDF:**
```bash
python generate_handbook.py \
  --pdf path/to/2027-28HighSchoolCourseDescriptionBooklet.pdf \
  --out assets/handbook.json
```

**From a URL (if the domain is accessible):**
```bash
python generate_handbook.py \
  --url https://resources.finalsite.net/.../2027-28...pdf \
  --out assets/handbook.json
```

The script will:
- Extract all text from the PDF
- Call Claude to parse: year label, graduation requirements, GPA scales,
  all 5 endorsements, 25+ Q&A entries, key reminders, suggested questions,
  and the 8th–12th grade planner
- Write a complete, valid `assets/handbook.json`

**Typical runtime: ~60–90 seconds** (10 Claude API calls)

### Step 5 — Review & deploy

Open the app locally to verify (`open index.html` in a browser that supports
`fetch` from `file://`, or serve with `python -m http.server 8080`), then:

```bash
git add assets/handbook.json
git commit -m "Update handbook to 2027-28"
git push
```

GitHub Pages auto-deploys within ~30 seconds.

---

## 🛠 What the Pipeline Extracts Automatically

| Section            | What's extracted                                              |
|--------------------|---------------------------------------------------------------|
| Year / label       | School year string and full publication title                 |
| Graduation reqs    | All subject rows with credit counts and notes                 |
| GPA scales         | All weighted grade-point tables (handles new 2030+ columns)   |
| Endorsements       | All 5 paths — routes, required courses, careers               |
| AI Q&A             | 25+ topic entries with keywords, answers, page references     |
| Reminders          | 6–8 must-know policy facts for students and families          |
| Suggested questions| 12 natural chat prompts auto-derived from Q&A topics          |
| Year Planner       | Full 8th–12th grade content: checklist, milestones, watchouts,|
|                    | what to review, family questions, core credits to watch       |

---

## ✏️ Manual Edits to handbook.json

You can always hand-edit `assets/handbook.json` after the pipeline runs —
for example to add a local reminder, tweak an answer, or add a new QA entry.
The JSON schema is documented inline.

---

## 🔑 JSON Schema Reference

```jsonc
{
  "year":   "2026–27",                  // displayed in header
  "label":  "CFISD 2026–2027 ...",     // full title string

  "stats": [                            // home page stat cards
    { "num": "26", "label": "...", "sub": "...", "color": "#hex" }
  ],

  "reminders": [                        // key things to know
    { "icon": "🔑", "text": "..." }
  ],

  "graduationReqs": [                   // requirements table
    { "subject": "English", "credits": 4, "note": "..." }
  ],

  "gpaScales": [                        // one or more GPA tables
    {
      "label":   "Classes of 2018–2029",
      "columns": ["K / AP / HORIZONS", "L-Level", ...],
      "rows": [
        { "grade": "A (90–100)", "pts": [7, 6, ...], "fail": false }
      ]
    }
  ],

  "endorsements": [                     // 5 endorsement objects
    {
      "id": "stem", "name": "STEM",
      "subtitle": "Science · Technology · Engineering · Math",
      "color": "#hex", "lightColor": "#hex", "emoji": "🔬",
      "bestFor": "...",
      "requiredCore": ["Algebra II", ...],
      "routes": [{ "name": "Option 1: ...", "desc": "..." }],
      "careers": ["Software Engineer", ...],
      "interestTags": ["coding", ...]
    }
  ],

  "interests": [ ... ],                 // 20 interest tiles (static)

  "suggestedQuestions": [ "..." ],      // 12 chat prompts

  "handbookQA": [                       // AI assistant knowledge base
    {
      "keywords": ["credits", ...],
      "answer":   "...",
      "source":   "Graduation Requirements (p. 23)"
    }
  ],

  "planner": {                          // grade-by-grade planner
    "9": {
      "grade": "9th Grade", "emoji": "🏁", "color": "#hex",
      "stage": "...", "focus": "...",
      "checklist":        ["..."],
      "milestones":       ["..."],
      "watchouts":        ["..."],
      "whatToReview":     [{ "icon": "📘", "item": "..." }],
      "familyQuestions":  ["..."],
      "coreCreditsToWatch": ["..."]
    }
    // keys "8" through "12"
  }
}
```

---

## 💡 Tips

- **Test locally** before pushing: `python -m http.server 8080` then open `http://localhost:8080`
- **The `interests` array is static** — it maps student interests to endorsement IDs and
  never needs updating unless CFISD adds a new endorsement type
- **Add QA entries manually** for campus-specific policies that aren't in the district handbook
  (e.g. Bridgeland-specific counselor contacts, club schedules)
- **The visit counter** persists across users via the app's shared storage — it keeps counting
  across years automatically
