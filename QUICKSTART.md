# 🚀 Quick Start — Deploy in 5 Minutes

## Why you must use a web server (not double-click)

Browsers block local file access for security. The app fetches
`assets/handbook.json` at load time — this works fine on any web
server (GitHub Pages, school server, localhost) but NOT when you
open `index.html` directly from Finder or File Explorer.

---

## Option 1 — GitHub Pages (recommended, free, permanent URL)

1. Go to https://github.com/new and create a repo (e.g. `bhs-pathways`)
2. Upload all files keeping the folder structure:
   ```
   index.html
   assets/handbook.json
   generate_handbook.py
   README.md
   QUICKSTART.md
   ```
3. Go to **Settings → Pages → Source: Deploy from branch → main / (root)**
4. Click Save — your app is live in ~30 seconds at:
   `https://<your-username>.github.io/bhs-pathways/`

That's it. Share that URL with students, parents, and counselors.

---

## Option 2 — Test locally (no internet needed)

Open Terminal in the folder containing `index.html` and run:

```bash
python -m http.server 8080
```

Then open your browser to: **http://localhost:8080**

Press Ctrl+C in Terminal when done.

---

## Every August — Update for New School Year

Only ONE file changes: `assets/handbook.json`

```bash
# Install once
pip install anthropic pdfplumber
export ANTHROPIC_API_KEY=sk-ant-...

# Run the pipeline with new PDF
python generate_handbook.py \
  --pdf path/to/2027-28-handbook.pdf \
  --out assets/handbook.json

# Push to GitHub — live in 30 seconds
git add assets/handbook.json
git commit -m "Update to 2027-28"
git push
```

`index.html` never changes. Ever.
