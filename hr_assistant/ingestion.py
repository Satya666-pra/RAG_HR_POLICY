"""09 · ingestion — the one place documents get loaded into Qdrant.
Orchestrates steps 04–08.

    local data/ files
        -> storage/raw/hr-policies/  +  storage/raw/other-data/   (stage / copy)
        -> storage/processed/...     (pdf/docx/pptx parsed to JSON, once — 05)
        -> chunk (06) -> embed (07) -> Qdrant collections (08)

Idempotent by default: a Qdrant collection that already has points in it is
left alone. Pass force=True to rebuild it from scratch. `ingest.py` is the
runnable entry point; the app never ingests — it connects to what this built.
"""

import glob
import logging
import os
import shutil

from hr_assistant import config
from hr_assistant.document_loader import (
    load_documents_from_storage,
    load_processed_documents_from_storage,
    storage_path,
)
from hr_assistant.processor import process_raw_to_json
from hr_assistant.splitter import split_into_chunks
from hr_assistant.vector_store import build_vector_store, collection_exists

logger = logging.getLogger(__name__)

_LOCAL_HR_GLOB = os.path.join("data", "*.txt")
_LOCAL_NOISE_GLOB = os.path.join("data", "noise", "*")


def stage_corpus_locally() -> None:
    """Copy the repo's data/ files into the local raw zone (storage/raw/...).
    Overwrites — cheap, and keeps the zone in sync with data/."""
    pairs = [(_LOCAL_HR_GLOB, config.GCS_PREFIX), (_LOCAL_NOISE_GLOB, config.NOISE_GCS_PREFIX)]
    for local_glob, prefix in pairs:
        dest = storage_path(prefix)
        dest.mkdir(parents=True, exist_ok=True)
        files = [f for f in glob.glob(local_glob) if os.path.isfile(f)]
        for path in files:
            shutil.copyfile(path, dest / os.path.basename(path))
        logger.info("Staged %d file(s) -> %s", len(files), dest)


def ingest_hr_policies(force: bool = False) -> None:
    """The clean HR-only collection the app connects to."""
    name = config.QDRANT_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info("Collection '%s' already populated — skipping (use --force to rebuild).", name)
        return

    documents = load_documents_from_storage()
    if not documents:
        raise RuntimeError("No HR .txt files found in the raw zone — run `python ingest.py` without --no-upload.")
    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info("Ingested %d HR document(s) -> %d chunk(s) into '%s'.", len(documents), len(chunks), name)


def ingest_noisy_corpus(force: bool = False) -> None:
    """The mixed HR + noise collection — built alongside the clean one so a
    later stage can test retrieval against real cross-domain noise.

    Raw pdf/docx/pptx are parsed into the processed JSON zone first —
    always on force=True, otherwise only when that zone is still empty."""
    name = config.QDRANT_NOISY_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info("Collection '%s' already populated — skipping (use --force to rebuild).", name)
        return

    if force:
        logger.info("Parsing raw files into the processed/ zone...")
        process_raw_to_json()

    documents = load_processed_documents_from_storage()
    if not documents:
        logger.info("Processed zone is empty — parsing raw files...")
        process_raw_to_json()
        documents = load_processed_documents_from_storage()

    if not documents:
        raise RuntimeError("Still no processed documents after parsing — check the raw zone.")

    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info(
        "Ingested %d document(s) (HR + noise) -> %d chunk(s) into '%s'.",
        len(documents), len(chunks), name,
    )


def run_ingestion(force: bool = False,
    hr: bool = True,
    noisy: bool = True,
    upload: bool = True) -> None:
    config.check_api_keys()
    if upload:
        stage_corpus_locally()
    if hr:
        ingest_hr_policies(force=force)
    if noisy:
        ingest_noisy_corpus(force=force)
