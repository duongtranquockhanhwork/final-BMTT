#!/bin/zsh
# Rebuild the SecureChat final report (docx + pdf) in the midterm format.
# Needs: python-docx, PyMuPDF (fitz), macOS Pages (for TOC page numbers).
set -e
HERE=${0:A:h}                       # secure-chat-demo/report
PROJ=${HERE:h}                      # secure-chat-demo
MID="$PROJ/../midterm/BMTT_N05_G05_524H0005_523H0040_523H0189/Midterm_Report.docx"
SHOTS="$PROJ/screenshots"
TMP=$(mktemp -d)
cd "$HERE"
python3 build_report.py "$MID" "$SHOTS" "$TMP/p1.docx" >/dev/null
./topdf.sh "$TMP/p1.docx" "$TMP/p1.pdf"
python3 pages.py "$TMP/p1.pdf" "$TMP/p1.docx.keys.json" "$TMP/pages.json" >/dev/null
python3 build_report.py "$MID" "$SHOTS" "$TMP/final.docx" "$TMP/pages.json"
./topdf.sh "$TMP/final.docx" "$TMP/final.pdf"
python3 pages.py "$TMP/final.pdf" "$TMP/final.docx.keys.json" "$TMP/check.json" >/dev/null
diff -q "$TMP/pages.json" "$TMP/check.json" >/dev/null || echo "WARNING: page numbers moved between passes; run again"
cp "$TMP/final.docx" "$HERE/Final_Report_SecureChat_N05_G05.docx"
cp "$TMP/final.pdf" "$HERE/Final_Report_SecureChat_N05_G05.pdf"
echo "Report updated: $HERE/Final_Report_SecureChat_N05_G05.{docx,pdf}"
