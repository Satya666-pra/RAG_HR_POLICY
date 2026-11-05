# Phase 3 — Deployment on Render (free plan)

Phase 2's secure pipeline, wrapped for production: Google login + employee allow-list, Docker, and a Render Blueprint (diagrams 5 and 6, with Render in place of Cloud Run).

```
Layer 1  Employee browser -> Google OAuth login -> allow-list check   (secrets.toml as a Render Secret File)
Layer 2  Render web service (Docker): Streamlit UI -> input guard -> cache -> guarded agent -> output guard
Layer 3  Hosted services: Qdrant Cloud, Jina (embeddings + rerank), Groq (primary + fallback), LangSmith (optional)
```

| Original (Cloud Run) | Here (Render) |
|---|---|
| `gcloud run deploy --source .` | `git push` → Render builds the Dockerfile (Blueprint = `render.yaml`) |
| Secret Manager `streamlit-auth` | Render **Secret File** `secrets.toml` |
| `deploy.env.yaml` | `envVars` in `render.yaml` (+ dashboard for secrets) |
| Artifact Registry / Cloud Build | handled by Render |
| Cloud Storage bucket | not needed — data baked into the image, vectors live in Qdrant Cloud |

Extras added for a public URL: `REQUIRE_AUTH=true` makes the app **refuse to serve** if the login config is missing (no accidental open mode).

Start with `commands/commands-deployment.md`.

**Verified locally:** the Docker image builds (1.37 GB), the container serves on the injected `PORT` with a healthy `/_stcore/health`, `start.sh` copies a mounted `/etc/secrets/secrets.toml` into `.streamlit/`, and `REQUIRE_AUTH=true` blocks the app when login is not configured.

**Not verified:** an actual Render deploy (no Render account was available), the Google login round trip, and a live Groq/Jina/Qdrant Cloud request.

**Memory warning for the free plan (512 MB):** importing the app's Python stack alone (mostly `litellm`) measured about 330 MB inside the container, before Streamlit sessions, the agent graph or any request. It may fit for a single user but is tight; if Render logs "Out of memory", move to the next plan.
