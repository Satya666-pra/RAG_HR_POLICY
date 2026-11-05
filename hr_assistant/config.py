"""01 · config — every setting, read from .env. Everything imports this.

FREE / LOCAL VARIANT — no Google Cloud, no paid service is required.
Compared with the deployment version:

    Cloud Storage bucket   ->  a local folder           (STORAGE_DIR)
    Qdrant Cloud           ->  local on-disk Qdrant     (or Qdrant Cloud free tier if QDRANT_URL is set)
    Jina embeddings        ->  fastembed, runs locally  (EMBEDDING_PROVIDER=jina to switch back)
    Jina reranker          ->  fastembed cross-encoder  (RERANK_PROVIDER=jina to switch back)
    Vertex AI Gemini       ->  Groq free tier           (any LiteLLM model string works)
    Vertex Model Armor     ->  an LLM safety classifier (GUARDRAIL_PROVIDER=llm)
    Cloud Run + Secret Mgr ->  Render (Docker) + Secret File; Google login via Streamlit st.login

The only key you MUST have is GROQ_API_KEY (free at console.groq.com).

config.py holds values only. The system-prompt text lives in prompts.py (02).
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


## LOCAL "CLOUD STORAGE" — same raw -> processed zones, just folders on disk

STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")

# Raw zone — original files, untouched, in whatever format they arrived.
GCS_PREFIX = "raw/hr-policies/"
NOISE_GCS_PREFIX = "raw/other-data/"  # non-HR noise: Finance/Sales/Operations/Business

# Processed zone — one JSON record per raw file (parsed plain text + metadata),
# written by hr_assistant/processor.py. Ingestion reads ONLY from here for the
# noisy corpus, so PDFs/DOCX/PPTX are parsed once, not on every rebuild.
PROCESSED_HR_PREFIX = "processed/hr-policies/"
PROCESSED_NOISE_PREFIX = "processed/other-data/"

## QDRANT
# QDRANT_URL empty  -> local on-disk database in QDRANT_LOCAL_PATH (no account).
# QDRANT_URL set    -> Qdrant Cloud (free 1 GB cluster) using QDRANT_API_KEY.

QDRANT_URL = os.getenv("QDRANT_URL") or None
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_LOCAL_PATH = os.getenv("QDRANT_LOCAL_PATH", "qdrant_local")

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hr_policies")

# Reliability path: a separate collection holding HR docs + non-HR noise
# together, so retrieval is tested against real cross-domain noise instead
# of the clean single-domain collection above.
QDRANT_NOISY_COLLECTION_NAME = os.getenv("QDRANT_NOISY_COLLECTION_NAME", "hr_policies_noisy_demo")

## ACCESS CONTROL — Google OAuth login + employee allow-list (see app.py)
# Only used when Streamlit's [auth] secrets are configured (locally: open mode).
ALLOWED_EMPLOYEE_EMAILS = {
    e.strip().lower() for e in os.getenv("ALLOWED_EMPLOYEE_EMAILS", "").split(",") if e.strip()
}
# On a public deployment set REQUIRE_AUTH=true: if the login secrets are
# missing the app then refuses to start instead of running open to everyone.
REQUIRE_AUTH = _bool("REQUIRE_AUTH", "false")

## MODELS
# Chat models are full LiteLLM model strings ("<provider>/<model>"), so
# swapping provider is an .env change, not a code change.
#
# Primary: gpt-oss-20b (fast, small). Fallback: gpt-oss-120b (larger).
# NOTE: the eval judge (JUDGE_MODEL_NAME below) defaults to gpt-oss-120b too,
# which is the same family as the app, so evaluate.py is partly the model
# family grading itself. To get an independent judge, set JUDGE_MODEL_NAME in
# .env to a different family (e.g. llama-3.3-70b-versatile).
#
# Groq's model catalogue changes over time — if a model is retired, pick a
# current one from https://console.groq.com/docs/models and set it in .env.

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "groq/openai/gpt-oss-20b")
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "groq/openai/gpt-oss-120b")

# Embeddings: "local" (fastembed, free, offline after first model download)
# or "jina" (needs JINA_API_KEY; free starting tokens, non-commercial).
# Changing the embedding model/provider changes the vector dimension, so run
# `python ingest.py --force` afterwards.
JINA_API_KEY = os.getenv("JINA_API_KEY")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
_DEFAULT_EMBEDDING = {
    "local": "BAAI/bge-small-en-v1.5",       # 384-dim, ~130 MB, English
    "jina": "jina-embeddings-v2-base-en",    # 768-dim
}
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", _DEFAULT_EMBEDDING.get(EMBEDDING_PROVIDER, ""))

# Reranker: "local" (fastembed cross-encoder) or "jina".
# A local cross-encoder returns raw logits, not 0-1 scores; reranker.py squashes
# them through a sigmoid so RELEVANCE_THRESHOLD below keeps its "0-1" meaning.
RERANK_PROVIDER = os.getenv("RERANK_PROVIDER", "local").strip().lower()
_DEFAULT_RERANKER = {
    "local": "Xenova/ms-marco-MiniLM-L-6-v2",
    "jina": "jina-reranker-v2-base-multilingual",
}
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", _DEFAULT_RERANKER.get(RERANK_PROVIDER, ""))

## CHUNK / TEXT SPLITTING CONFIG

CHUNK_SIZE = 500
CHUNK_OVERLAP = 60

## RETRIEVAL RESULTS

TOP_K_RESULTS = 5
RERANK_CANDIDATE_K = 12  # wider shortlist retrieved before re-ranking

## RELIABILITY — scope guardrail (see hr_assistant/tools.py)

# Exact values used in each policy file's "Policy Category:" line. The
# search tool hard-filters retrieval to only these categories — non-HR
# chunks (Finance/Sales/Operations/Business) are structurally unreachable,
# regardless of how confused embedding similarity gets.
HR_POLICY_CATEGORIES = {
    "Leave", "Work From Home", "Probation", "Notice Period", "Reimbursement",
    "Code of Conduct", "Holidays", "Maternity Paternity", "Travel Expense", "Exit Process",
}

# Post-rerank relevance cutoff (0-1). Below this the tool reports "not found".
# IMPORTANT: score distributions differ per reranker. 0.35 was tuned for Jina;
# with the local cross-encoder it is a reasonable starting point, but calibrate
# it against real queries (run demo_reliability.py and look at the scores).
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.35"))

## RELIABILITY — input/output safety guardrail

# "llm"  : one structured-output call to the chat model classifying safe/unsafe
#          (free, no extra service). "gemini_lite" is accepted as an alias.
# "none" : disabled.
# (Vertex Model Armor is not part of this free variant.)
GUARDRAIL_PROVIDER = os.getenv("GUARDRAIL_PROVIDER", "llm").strip().lower()
if GUARDRAIL_PROVIDER == "gemini_lite":
    GUARDRAIL_PROVIDER = "llm"

# What to do when the guardrail PROVIDER itself errors (API failure / rate
# limit, not a content block). Input fails closed — an unscreened prompt must
# never reach the model. Output fails open — a transient screening failure
# shouldn't discard an answer the model already produced.
GUARDRAIL_FAIL_OPEN_INPUT = _bool("GUARDRAIL_FAIL_OPEN_INPUT", "false")
GUARDRAIL_FAIL_OPEN_OUTPUT = _bool("GUARDRAIL_FAIL_OPEN_OUTPUT", "true")

# The input guardrail screens the current question plus up to this many of
# the most recent *user* turns for the thread (0 disables history screening).
GUARDRAIL_HISTORY_TURNS = int(os.getenv("GUARDRAIL_HISTORY_TURNS", "6"))

## RELIABILITY — semantic cache

# Cosine similarity above this = cache hit. 0.93 was tuned for Jina; the local
# bge model has a different similarity spread — calibrate if you see wrong hits.
SEMANTIC_CACHE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.93"))

SEMANTIC_CACHE_MAX_ENTRIES = int(os.getenv("SEMANTIC_CACHE_MAX_ENTRIES", "500"))
SEMANTIC_CACHE_TTL_SECONDS = int(os.getenv("SEMANTIC_CACHE_TTL_SECONDS", "3600"))

## LANGSMITH — tracing (the app) + datasets/experiments (evaluate.py). Optional, free plan.

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "hr-policy-assistant")

## JUDGE LLM — Groq, read by hr_assistant/evaluation.py.
# gpt-oss on Groq is OpenAI-API-compatible, so langchain-openai's ChatOpenAI
# talks to it directly.

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-oss-120b")

# System-prompt text: hr_assistant/prompts.py (02).


def check_api_keys() -> None:
    """Stop early with a clear message if a required key/config is missing."""
    required = [("GROQ_API_KEY", GROQ_API_KEY)]
    if EMBEDDING_PROVIDER == "jina" or RERANK_PROVIDER == "jina":
        required.append(("JINA_API_KEY", JINA_API_KEY))
    if QDRANT_URL:
        required.append(("QDRANT_API_KEY", QDRANT_API_KEY))

    missing = [name for name, value in required if not value]
    if missing:
        raise ValueError(f"Missing required .env values: {', '.join(missing)}")
    if EMBEDDING_PROVIDER not in _DEFAULT_EMBEDDING:
        raise ValueError(f"EMBEDDING_PROVIDER must be 'local' or 'jina', got {EMBEDDING_PROVIDER!r}")
    if RERANK_PROVIDER not in _DEFAULT_RERANKER:
        raise ValueError(f"RERANK_PROVIDER must be 'local' or 'jina', got {RERANK_PROVIDER!r}")
