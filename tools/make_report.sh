#!/bin/zsh
# Rebuild the final report (docx + pdf) in the midterm format.
# Needs: python-docx, PyMuPDF (fitz), macOS Pages (for the PDF export used to compute TOC page numbers).
set -e
ROOT=${0:A:h:h}
SUB="$ROOT/BMTT_N05_G05_524H0005_523H0040_523H0189"
MID="$ROOT/tools/template/Midterm_Report.docx"   # format template (midterm report layout)
TMP=$(mktemp -d)
cd "${0:A:h}"
python3 build_report.py "$MID" "$SUB/screenshots" "$TMP/p1.docx" >/dev/null
./topdf.sh "$TMP/p1.docx" "$TMP/p1.pdf"
python3 pages.py "$TMP/p1.pdf" "$TMP/p1.docx.keys.json" "$TMP/pages.json" >/dev/null
python3 build_report.py "$MID" "$SUB/screenshots" "$TMP/final.docx" "$TMP/pages.json"
./topdf.sh "$TMP/final.docx" "$TMP/final.pdf"
python3 pages.py "$TMP/final.pdf" "$TMP/final.docx.keys.json" "$TMP/check.json" >/dev/null
diff -q "$TMP/pages.json" "$TMP/check.json" >/dev/null || echo "WARNING: page numbers moved between passes; run again"
cp "$TMP/final.docx" "$SUB/Final_Report_BMTT_N05_G05.docx"
cp "$TMP/final.pdf" "$SUB/Final_Report_BMTT_N05_G05.pdf"
echo "Report updated: $SUB/Final_Report_BMTT_N05_G05.{docx,pdf}"
