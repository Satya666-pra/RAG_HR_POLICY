"""04 · document_loader — read documents out of the local storage folder.

The local STORAGE_DIR plays the role Cloud Storage played in the deployment
version (same raw/ and processed/ zones). Two readers, nothing else:
  load_documents_from_storage()            — the raw .txt HR policies (raw zone)
  load_processed_documents_from_storage()  — the parsed JSON records (processed
                        zone), written by processor.py (05)

Binary formats (.pdf/.docx/.pptx) are parsed in processor.py, not here —
this file only loads text that is already text.
"""

import json
from pathlib import Path

from langchain_core.documents import Document

# A langchain Document holds two things:
#   1) page_content: the text of the document
#   2) metadata: a dict about it (source, policy_category, ...)

from hr_assistant import config


def storage_path(prefix: str = "") -> Path:
    """Folder inside STORAGE_DIR for a zone prefix like 'raw/hr-policies/'."""
    return Path(config.STORAGE_DIR) / prefix


def extract_policy_category(text: str) -> str:
    """Every policy file starts with a 'Policy Category: X' line (HR docs)
    or a 'Category: X' line (noise docs) — pull whichever is present out.
    Shared with processor.py (05)."""
    for line in text.splitlines()[:5]:
        stripped = line.strip().lower()
        if stripped.startswith("policy category:"):
            return line.split(":", 1)[1].strip()
        if stripped.startswith("category:"):
            return line.split(":", 1)[1].strip()
    return "Unknown"


def load_documents_from_storage(prefix: str = config.GCS_PREFIX) -> list[Document]:
    """Read every .txt file under the given raw-zone prefix, returning one
    LangChain Document per file with source + category metadata."""
    documents = []
    for path in sorted(storage_path(prefix).glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(
            page_content=text,
            metadata={
                "source": path.name,
                "policy_category": extract_policy_category(text),
                "gcs_path": str(path),
            },
        ))
    return documents


def load_processed_documents_from_storage(
    prefixes: tuple[str, ...] = (config.PROCESSED_HR_PREFIX, config.PROCESSED_NOISE_PREFIX),
) -> list[Document]:
    """Read the processed zone (JSON records written by processor.py) and
    return LangChain Documents. No parsing here — just reading already-parsed
    text out of JSON. This is what the ingestion pipeline (09) calls."""
    documents = []
    for prefix in prefixes:
        for path in sorted(storage_path(prefix).glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            documents.append(Document(
                page_content=record["text"],
                metadata={
                    "source": record["source"],
                    "policy_category": record["policy_category"],
                    "gcs_path": record["raw_gcs_path"],
                },
            ))
    return documents
