FROM python:3.11-slim
WORKDIR /app

# uv, copied straight from its own image — fast installs, no curl step.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Dependencies first: this layer is cached until requirements.txt changes,
# so a code-only change rebuilds in seconds.
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Pre-download the BM25 keyword model at BUILD time so a cold start on Render
# never has to fetch it from HuggingFace. (If you choose the LOCAL embedder /
# reranker instead of Jina, those models download on first start — see
# commands/commands-deployment.md.)
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"

COPY hr_assistant/ ./hr_assistant/
COPY data/ ./data/
COPY app.py ingest.py evaluate.py main.py demo_reliability.py redteam_test.py start.sh ./
RUN chmod +x start.sh

# Render injects PORT at runtime (default 10000); start.sh reads it.
ENV PORT=10000
EXPOSE 10000

CMD ["./start.sh"]
