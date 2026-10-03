# Presentation Slides

## How to Export Slides to PDF

The presentation is a self-contained HTML file designed for landscape A4 printing (10 slides, one per page).

### Using the Export Script (Recommended)

**Windows (PowerShell):**
```powershell
.\scripts\export_slides.ps1
```

**Linux/macOS:**
```bash
./scripts/export_slides.sh
```

The script will:
1. Detect Edge or Chrome/Chromium on your system
2. Render `presentation/slides.html` to `presentation/slides.pdf`
3. Print the file size and path

### Manual Export (if script fails)

**Using Edge (Windows):**
```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --disable-gpu --print-to-pdf="$PWD\presentation\slides.pdf" --no-pdf-header-footer "file:///$PWD\presentation\slides.html"
```

**Using Chrome/Chromium (any platform):**
```bash
google-chrome --headless --disable-gpu --print-to-pdf="$(pwd)/presentation/slides.pdf" --no-pdf-header-footer "file://$(pwd)/presentation/slides.html"
```

### Browser Manual Export

1. Open `presentation/slides.html` in your browser
2. Press `Ctrl+P` (or Cmd+P on macOS)
3. Set:
   - Destination: **Save as PDF**
   - Paper size: **A4 landscape**
   - Margins: **None**
   - Headers/footers: **OFF**
4. Click **Save**

## Slide Contents

The deck has 10 slides (A4 landscape, page-break between each):

1. **Title + Team** — Project title, team members, date
2. **Problem** — Why AI agents need governance; attack scenarios
3. **Solution Overview** — Seven-stage pipeline; threat categories covered
4. **Architecture** — Component diagram; pipeline visualization
5. **Controls by Stage** — OWASP mappings; what each stage protects against
6. **Hybrid Defence** — Deterministic rules + ML + LLM judge; decision flow
7. **Budgets, Behavior, Hot Reload** — Token limits; per-user analytics; live policy tuning
8. **Security Reporting & Audit** — Dashboard screenshots; audit trails; alert system
9. **Self-Testing Suite Results** — Attack scenario table; pass/fail counts
10. **Implementability & Scalability** — Architecture diagram; deployment notes; next steps

## Printing Notes

- **Page size:** A4 landscape (297 × 210 mm)
- **Margins:** 0 (slides fill the page)
- **One slide per page**
- **No headers/footers**
- **Optimized for color printing** (use color for best results)

If printing in B&W, ensure sufficient contrast on diagrams and KPI cards.

## Customization

The slides use semantic HTML and embedded CSS. To customize:

1. Open `slides.html` in an editor
2. Find the `<style>` block (top of file)
3. Modify colors, fonts, or layout
4. Save and export to PDF

Note: Keep the `@page { size: A4 landscape; margin: 0 }` rule for correct page size.

## FAQ

**Q: PDF is too small / large**
A: Rendering depends on your system's DPI settings. Try adjusting zoom in your PDF viewer, or use the browser's print dialog to scale.

**Q: Some images/diagrams not showing**
A: All assets are embedded inline (data URIs or SVG). If a diagram is missing, check the SVG syntax in `<style>` and `<svg>` blocks.

**Q: Can I edit the PDF after export?**
A: Export creates a flattened PDF (not editable). Edit `slides.html` first, then re-export.

---

**See also:** [Demo Script](../WIKI/demo-script.md) for live presentation walkthrough.
