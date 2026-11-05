"""07 · embeddings — turn text into vectors.

Default (free): fastembed runs a small embedding model on your own CPU — no
API key, no per-token cost. The model (~130 MB) downloads once on first use.

Optional: EMBEDDING_PROVIDER=jina uses the Jina API (needs JINA_API_KEY;
free starting tokens, non-commercial use).

Documents and questions MUST be embedded by the same model. Changing the
model/provider changes the vector size -> run `python ingest.py --force`.
"""

from functools import lru_cache

from hr_assistant import config


@lru_cache(maxsize=1)
def get_embeddings_model():
    """Return the embeddings model (cached — loading it is not free)."""
    if config.EMBEDDING_PROVIDER == "jina":
        from langchain_community.embeddings import JinaEmbeddings

        return JinaEmbeddings(
            jina_api_key=config.JINA_API_KEY,
            model_name=config.EMBEDDING_MODEL_NAME,
        )

    from langchain_community.embeddings import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)
