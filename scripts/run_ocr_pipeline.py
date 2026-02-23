"""
Usage:
    uv run python scripts/run_ocr_pipeline.py /path/to/your/file.pdf
"""

import sys
from backend.ocr.pipeline import OCRPipeline

if len(sys.argv) < 2:
    print("Usage: uv run python scripts/run_ocr_pipeline.py <pdf_path>")
    sys.exit(1)

pdf_path = sys.argv[1]

pipeline = OCRPipeline(
    pdf_path=pdf_path,
    output_folder="./cache/ocr_output",
    dpi=150
)

results = pipeline.run()

for page_num, page_lines in enumerate(results, start=1):
    print(f"=== Page {page_num} ({len(page_lines)} lines) ===")
    for line in page_lines:
        print(f"  [{line['confidence']:.2f}] {line['text']}")
