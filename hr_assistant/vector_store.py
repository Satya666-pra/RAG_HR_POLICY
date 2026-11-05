"""08 · vector_store — Qdrant (dense + BM25 sparse hybrid) behind four functions.

    build_vector_store(chunks, hybrid, collection_name)  embed + upsert.  ONLY ingest.py calls this.
    load_vector_store(collection_name)                   connect, no embedding.
    collection_exists(collection_name)                   True only if it exists AND has points.
    get_retriever(vector_store, k, filter_categories)    search, optionally category-filtered.

Where the data lives:
  QDRANT_URL empty -> a local on-disk database in QDRANT_LOCAL_PATH (free, no account).
  QDRANT_URL set   -> Qdrant Cloud (free 1 GB cluster) with QDRANT_API_KEY.

Hybrid = each chunk has a dense vector (meaning) and a sparse BM25 vector
(exact keywords); Qdrant blends the two rankings into one list.

Chunk IDs are deterministic (uuid5 of source + text), so re-ingesting the
same chunks overwrites instead of duplicating — ingestion is idempotent.
"""

import atexit
import logging
import uuid

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models

from hr_assistant import config
from hr_assistant.embeddings import get_embeddings_model

logger = logging.getLogger(__name__)

_SPARSE_MODEL = "Qdrant/bm25"
_DENSE_NAME = ""                   # langchain-qdrant's default (unnamed) dense vector
_SPARSE_NAME = "langchain-sparse"  # langchain-qdrant's default sparse vector name
_CATEGORY_KEY = "metadata.policy_category"

# Local (on-disk) Qdrant allows ONE client per folder per process, so every
# function below shares this single client.
_client: "QdrantClient | None" = None


def _close_client() -> None:
    """Close the client before interpreter shutdown (otherwise the local
    client's __del__ prints a harmless but ugly ImportError at exit)."""
    global _client
    if _client is not None:
        try:
            _client.close()
        finally:
            _client = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        if config.QDRANT_URL:
            _client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
        else:
            _client = QdrantClient(path=config.QDRANT_LOCAL_PATH)
        atexit.register(_close_client)
    return _client


def _sparse_model() -> FastEmbedSparse:
    return FastEmbedSparse(model_name=_SPARSE_MODEL)


def collection_exists(collection_name: str) -> bool:
    """True only when the collection exists AND already holds points — an
    empty/half-built collection counts as 'not populated yet'."""
    client = _get_client()
    if not client.collection_exists(collection_name):
        return False
    return client.count(collection_name, exact=True).count > 0


def _chunk_id(chunk) -> str:
    key = f"{chunk.metadata.get('source', '')}\n{chunk.page_content}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def build_vector_store(chunks: list, hybrid: bool = True, collection_name: str = config.QDRANT_COLLECTION_NAME):
    """Embed the chunks and upsert them into a freshly created collection.

    Called only when the collection is missing/empty, or on --force, so it
    always starts from a clean collection (a rebuild must not keep stale
    chunks from documents that no longer exist)."""
    client = _get_client()
    embeddings = get_embeddings_model()
    dim = len(embeddings.embed_query("dimension probe"))

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config={_DENSE_NAME: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={_SPARSE_NAME: models.SparseVectorParams()} if hybrid else None,
    )
    try:  # index the filter field (matters on Qdrant Cloud; a no-op locally)
        client.create_payload_index(collection_name, _CATEGORY_KEY, models.PayloadSchemaType.KEYWORD)
    except Exception:  # noqa: BLE001
        logger.debug("Payload index not created (fine for local mode).", exc_info=True)

    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        sparse_embedding=_sparse_model() if hybrid else None,
        retrieval_mode=RetrievalMode.HYBRID if hybrid else RetrievalMode.DENSE,
    )
    store.add_documents(chunks, ids=[_chunk_id(c) for c in chunks])
    return store


def load_vector_store(collection_name: str = config.QDRANT_COLLECTION_NAME):
    """Connect to an existing collection. No embedding happens here."""
    if not collection_exists(collection_name):
        raise RuntimeError(
            f"Qdrant collection '{collection_name}' is missing or empty — run `python ingest.py` first."
        )
    return QdrantVectorStore(
        client=_get_client(),
        collection_name=collection_name,
        embedding=get_embeddings_model(),
        sparse_embedding=_sparse_model(),
        retrieval_mode=RetrievalMode.HYBRID,
    )


def get_retriever(vector_store, k: int = config.TOP_K_RESULTS, filter_categories=None):
    """A retriever returning the top-k chunks. With filter_categories, only
    chunks whose policy_category is in that set can ever be returned — a hard
    yes/no gate applied BEFORE ranking (this is the scope guardrail)."""
    search_kwargs = {"k": k}
    if filter_categories:
        search_kwargs["filter"] = models.Filter(
            must=[
                models.FieldCondition(
                    key=_CATEGORY_KEY,
                    match=models.MatchAny(any=sorted(filter_categories)),
                )
            ]
        )
    return vector_store.as_retriever(search_kwargs=search_kwargs)
