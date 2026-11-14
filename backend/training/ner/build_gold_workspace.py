"""Phase 1: turn raw resumes into text files plus blank gold-label templates.

For every resume in an input folder (images, PDF, DOCX, TXT) this writes
    gold/<id>.txt   the extracted text (what the parsers will actually see)
    gold/<id>.json  a label template to fill in by hand

Templates are deliberately blank: pre-filling them with regex output would bias
the gold set towards the regex parser. Existing files are never overwritten.

Usage (from backend/):
    python training/ner/build_gold_workspace.py --input training/ner/samples
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
_reader = None


def _ocr(path: Path) -> str:
    """OCR an image the same way app.py does, so gold text matches production text."""
    global _reader
    import easyocr
    from PIL import Image

    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    img = Image.open(path).convert("RGB")
    # Scale so the long side is about 2000px: shrinks a 12 MB photo and enlarges
    # tiny screenshots. Very small images still OCR badly, so check the .txt output.
    scale = 2000 / max(img.size)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return " ".join(_reader.readtext(buf.getvalue(), detail=0))


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return _ocr(path)
    if ext == ".pdf":
        import fitz
        return "".join(page.get_text() for page in fitz.open(path))
    if ext == ".docx":
        import docx
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs if p.text)
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"unsupported file type: {ext}")


TEMPLATE = {
    "_instructions": "Fill by hand from the resume, see LABELING.md. Delete this key when done.",
    "source_file": "",
    "labeller": "",
    "name": "",
    "skills": [],
    "degree": "",
    "experience_years": None,
    "job_titles": [],
    "companies": [],
    "notes": "",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "gold")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    for path in sorted(args.input.iterdir()):
        if not path.is_file() or path.suffix.lower() == ".svg":
            if path.suffix.lower() == ".svg":
                print(f"skip {path.name}: SVG needs converting to PNG first")
            continue
        stem = path.stem
        txt_path, json_path = args.output / f"{stem}.txt", args.output / f"{stem}.json"
        if not txt_path.exists():
            try:
                txt_path.write_text(extract_text(path), encoding="utf-8")
            except Exception as exc:  # keep going so one bad file doesn't stop the batch
                print(f"FAILED {path.name}: {exc}")
                continue
        if not json_path.exists():
            json_path.write_text(
                json.dumps({**TEMPLATE, "source_file": path.name}, indent=2), encoding="utf-8")
        print(f"ok {path.name} -> {txt_path.name}, {json_path.name}")


if __name__ == "__main__":
    main()
