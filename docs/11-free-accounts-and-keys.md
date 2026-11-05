# 11. Free Accounts & API Keys

(This slot held "GCP Role, APIs & IAM" in the original project. With no
Google Cloud in the picture, it becomes a map of the free accounts and keys
you actually need.)

## What you need, by phase

| Account / key | Phase 1 | Phase 2 | Phase 3 (Render) | Cost |
|---|---|---|---|---|
| **Groq** — `GROQ_API_KEY` | required | required | required | Free tier (rate-limited) |
| Jina — `JINA_API_KEY` | optional | optional | needed for the free Render plan | Free starting tokens, **non-commercial**; paid token packs after |
| Qdrant Cloud — `QDRANT_URL`, `QDRANT_API_KEY` | optional | optional | **required** | Free 1 GB cluster |
| LangSmith — `LANGSMITH_API_KEY` | optional | optional (for `evaluate.py`) | optional | Free developer plan |
| Google OAuth client | – | – | required (login) | Free to create |
| GitHub repo | – | – | required | Free |
| Render account | – | – | required | Free plan |

Phases 1 and 2 run completely offline apart from the Groq call: local
embeddings, local re-ranker, local on-disk Qdrant.

> **Jina licensing.** The starting tokens are for non-commercial use, and the
> exact allowance has been described differently in different places. Check
> jina.ai for the current terms before relying on it for anything beyond a
> course project.

## Where each value goes

| Value | Local run | Render |
|---|---|---|
| `GROQ_API_KEY`, `JINA_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `ALLOWED_EMPLOYEE_EMAILS` | `.env` file (git-ignored) | **Environment variables** (the Blueprint prompts for them) |
| `REQUIRE_AUTH`, `EMBEDDING_PROVIDER`, `RERANK_PROVIDER`, model names | `.env` | preset in `render.yaml` |
| Google login: `redirect_uri`, `cookie_secret`, `client_id`, `client_secret` | `.streamlit/secrets.toml` (git-ignored) | **Secret File** named `secrets.toml` |

The two mechanisms are different on purpose: the app reads plain settings
from environment variables, but Streamlit's login reads *only* a
`secrets.toml` file (doc 13).

## A starter `.env`

```
# required
GROQ_API_KEY=...

# for Phase 3 / Render (API-based retrieval + hosted vector DB)
EMBEDDING_PROVIDER=jina
RERANK_PROVIDER=jina
JINA_API_KEY=...
QDRANT_URL=https://<your-cluster-id>.<region>.aws.cloud.qdrant.io
QDRANT_API_KEY=...
ALLOWED_EMPLOYEE_EMAILS=you@example.com,colleague@example.com
```

`.env.example` in each phase lists every supported setting.

## Keep keys out of Git and out of chat

- `.env` and `.streamlit/secrets.toml` are in `.gitignore` and
  `.dockerignore`. Before pushing, run `git ls-files` and confirm only the
  `.example` files appear.
- A key that has been pasted into a chat, a screenshot or a public repo
  should be treated as leaked: regenerate it in that provider's console.

Next: **[doc 12 — Containerization & Render](12-containerization-and-render.md)**.
