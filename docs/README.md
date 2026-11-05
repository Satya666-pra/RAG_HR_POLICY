# Phase 3 — Deployment: docs

The complete set, 01–17, numbered like the original project. Docs 12, 13, 16 and 17 are new to this phase.

| Doc | Topic |
|---|---|
| [01-overview.md](01-overview.md) | Problem, what this phase adds, free-variant swaps |
| [02-tech-stack.md](02-tech-stack.md) | Components and why |
| [03-document-processing.md](03-document-processing.md) | Ingestion: raw → processed → chunks |
| [04-chunking-and-embeddings.md](04-chunking-and-embeddings.md) | 500/60 chunks; local vs Jina embeddings |
| [05-retrieval-and-vector-storage.md](05-retrieval-and-vector-storage.md) | Qdrant local vs Cloud; two collections |
| [06-filtering-and-hybrid-search.md](06-filtering-and-hybrid-search.md) | Category filter; dense + BM25 hybrid |
| [07-re-ranking.md](07-re-ranking.md) | Retrieve 12 → re-rank to 5; sigmoid scores |
| [08-the-agent.md](08-the-agent.md) | Agent, tool, prompt, memory |
| [09-reliability.md](09-reliability.md) | Noisy corpus, memory, semantic cache, pipeline order |
| [10-evaluation-and-redteam.md](10-evaluation-and-redteam.md) | LangSmith eval; 7-attack red-team and its results |
| [11-free-accounts-and-keys.md](11-free-accounts-and-keys.md) | Which free accounts/keys, and where each goes |
| [12-containerization-and-render.md](12-containerization-and-render.md) | Dockerfile, start.sh, compose, Render deploy, free-plan limits |
| [13-access-control.md](13-access-control.md) | Google login, allow-list, secrets.toml, fail-closed |
| [14-llm-routing.md](14-llm-routing.md) | LiteLLM Router, primary/fallback, memory cost |
| [15-content-guardrails.md](15-content-guardrails.md) | Safety classifier, scope filter, identity lock |
| [16-hosting-architecture.md](16-hosting-architecture.md) | Whole system on Render + external services |
| [17-troubleshooting.md](17-troubleshooting.md) | Every error hit while building and deploying, with fixes |
