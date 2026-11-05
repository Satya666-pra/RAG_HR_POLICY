"""10 · reranker — re-rank retrieved candidates with a cross-encoder.

Retrieval (08) is fast but rough; the reranker reads the question and each
candidate chunk *together* and re-scores the shortlist.

Default (free): a small cross-encoder from fastembed, run locally. It returns
raw logits (any real number), so they are passed through a sigmoid to land in
0-1 — that keeps config.RELEVANCE_THRESHOLD meaningful as a "0-1" cutoff.
  logit +5 -> 0.993 (strong match)   logit 0 -> 0.5   logit -5 -> 0.007

Optional: RERANK_PROVIDER=jina calls Jina's reranker REST API
(needs JINA_API_KEY). See https://jina.ai/reranker/
"""

import math
from functools import lru_cache

from hr_assistant import config

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


def _sigmoid(x: float) -> float:
    # numerically safe for large |x|
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


@lru_cache(maxsize=1)
def _local_cross_encoder():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=config.RERANKER_MODEL_NAME)


def _rerank_local(query: str, candidates: list, top_n: int) -> list[tuple]:
    scores = list(_local_cross_encoder().rerank(query, [c.page_content for c in candidates]))
    scored = [(doc, _sigmoid(float(s))) for doc, s in zip(candidates, scores)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_n]


def _rerank_jina(query: str, candidates: list, top_n: int) -> list[tuple]:
    import requests

    response = requests.post(
        JINA_RERANK_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.JINA_API_KEY}",
        },
        json={
            "model": config.RERANKER_MODEL_NAME,
            "query": query,
            "top_n": top_n,
            "documents": [c.page_content for c in candidates],
            "return_documents": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    # results are ranked, each with an "index" back into the original list
    return [(candidates[r["index"]], r["relevance_score"]) for r in response.json()["results"]]


def rerank_with_scores(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list[tuple]:
    """Re-rank candidates, returning (Document, relevance_score 0-1) pairs,
    best first. The guarded search tool (hr_assistant/tools.py) uses the
    scores to gate on relevance, not just reorder. candidates is typically a
    wider shortlist (see RERANK_CANDIDATE_K)."""
    if not candidates:
        return []
    if config.RERANK_PROVIDER == "jina":
        return _rerank_jina(query, candidates, top_n)
    return _rerank_local(query, candidates, top_n)


def rerank(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list:
    """Just the re-ordered Documents, no scores. Thin wrapper around
    rerank_with_scores()."""
    return [doc for doc, _score in rerank_with_scores(query, candidates, top_n)]
