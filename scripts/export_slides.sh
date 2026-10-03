#!/bin/bash
# Export slides script for AI Control Layer
# Renders presentation/slides.html to PDF using Chrome or Edge

set -e

echo "=== AI Control Layer Slides Export ==="

# Resolve absolute paths
SLIDES_HTML="$(cd presentation && pwd)/slides.html"
SLIDES_PDF="$(cd presentation && pwd)/slides.pdf"

echo "Source: $SLIDES_HTML"
echo "Output: $SLIDES_PDF"

# Find browser
BROWSER_PATH=""

if command -v google-chrome &> /dev/null; then
    BROWSER_PATH="google-chrome"
    echo "Using: Google Chrome"
elif command -v chrome &> /dev/null; then
    BROWSER_PATH="chrome"
    echo "Using: Google Chrome"
elif command -v chromium &> /dev/null; then
    BROWSER_PATH="chromium"
    echo "Using: Chromium"
elif command -v chromium-browser &> /dev/null; then
    BROWSER_PATH="chromium-browser"
    echo "Using: Chromium"
else
    echo "Error: Chrome/Chromium not found!"
    exit 1
fi

# Render PDF
echo "Rendering PDF..."
$BROWSER_PATH --headless --disable-gpu \
    --print-to-pdf="$SLIDES_PDF" \
    --no-pdf-header-footer \
    "file://$SLIDES_HTML"

if [ -f "$SLIDES_PDF" ]; then
    SIZE=$(du -h "$SLIDES_PDF" | cut -f1)
    echo "✓ PDF exported successfully"
    echo "  File: $SLIDES_PDF"
    echo "  Size: $SIZE"
else
    echo "✗ PDF export failed"
    exit 1
fi
