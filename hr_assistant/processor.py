"""05 · processor — parse raw binary formats to plain text, once.

    storage/raw/<prefix>/file.pdf|docx|pptx|txt  --parse-->  storage/processed/<prefix>/file.json

Called by the ingestion pipeline (09) so PDFs/DOCX/PPTX are parsed a single
time, not on every vector-store rebuild. document_loader.py (04) then reads
the JSON back.
"""

import json
import logging
from pathlib import Path

from docx import Document as DocxReader
from pptx import Presentation
from pypdf import PdfReader

from hr_assistant import config
from hr_assistant.document_loader import extract_policy_category, storage_path

logger = logging.getLogger(__name__)

_RAW_TO_PROCESSED = {
    config.GCS_PREFIX: config.PROCESSED_HR_PREFIX,
    config.NOISE_GCS_PREFIX: config.PROCESSED_NOISE_PREFIX,
}


def _parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(path: Path) -> str:
    doc = DocxReader(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _parse_pptx(path: Path) -> str:
    prs = Presentation(str(path))
    lines = []
    for slide in prs.slides:
        if slide.shapes.title is not None:
            lines.append(slide.shapes.title.text)
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                lines.append(shape.text_frame.text)
    return "\n".join(lines)


def _parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_PARSERS = {".txt": _parse_txt, ".pdf": _parse_pdf, ".docx": _parse_docx, ".pptx": _parse_pptx}


def parse_file(path: Path) -> str:
    """Return a file's plain text, dispatching on extension."""
    parser = _PARSERS.get(path.suffix.lower())
    if parser is None:
        raise ValueError(f"No parser registered for file extension {path.suffix!r} ({path.name})")
    return parser(path)


def process_raw_to_json() -> int:
    """Parse every raw file (any format) and write it as a processed JSON
    record. Returns how many records were written.

    The record holds exactly what load_processed_documents_from_storage()
    reads back: source, policy_category, text, raw_gcs_path.
    """
    count = 0
    for raw_prefix, processed_prefix in _RAW_TO_PROCESSED.items():
        raw_dir = storage_path(raw_prefix)
        out_dir = storage_path(processed_prefix)
        out_dir.mkdir(parents=True, exist_ok=True)

        for path in sorted(raw_dir.glob("*.*")):
            if not path.is_file():
                continue
            text = parse_file(path)
            record = {
                "source": path.name,
                "policy_category": extract_policy_category(text),
                "text": text,
                "raw_gcs_path": str(path),
            }
            out_path = out_dir / (path.stem + ".json")
            out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            logger.info("  %s  ->  %s", path, out_path)
            count += 1

    return count
