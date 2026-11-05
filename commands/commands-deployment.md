# Phase 3 — Deployment on Render — commands

Run from inside `3 - DEPLOYMENT SRC`. The app is the Phase 2 secure pipeline plus Google login, packaged in Docker and hosted on **Render's free plan**.

## 0. What you need (all free)
| Thing | Where |
|---|---|
| Groq API key | console.groq.com/keys |
| Qdrant Cloud free cluster (URL + API key) | cloud.qdrant.io |
| Jina API key (embeddings + reranker) | jina.ai — free starting tokens, **non-commercial** |
| Google OAuth client (login) | Google Cloud Console → APIs & Services → Credentials (no paid plan needed) |
| GitHub account + a repo | Render deploys from Git |
| Render account | render.com |

## 1. Why Jina + hosted Qdrant on Render (not the local models)
The free Render instance has **512 MB RAM** and an **ephemeral disk** (wiped on every restart/sleep). The local embedder + reranker would not fit comfortably, and a local Qdrant folder would vanish. So on Render the retrieval backend is API-based and hosted. (A paid instance with a persistent disk could run the fully local setup — change the env vars, nothing else.)

## 2. Ingest ONCE from your laptop into Qdrant Cloud
Put these in a local `.env` (same values you will give Render):
```
GROQ_API_KEY=...
EMBEDDING_PROVIDER=jina
RERANK_PROVIDER=jina
JINA_API_KEY=...
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=...
```
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python ingest.py            # fills hr_policies + hr_policies_noisy_demo in Qdrant Cloud
```
Render then only *connects* (the app skips ingestion when the collection already has data).

## 3. (Optional) test the container locally
```bash
docker compose up --build   # http://localhost:8501  (open local mode, no login)
```
Local compose uses the `.env` above. Requires Docker Desktop running.

## 4. Google login setup
1. Google Cloud Console → APIs & Services → **OAuth consent screen** (External, "Testing") → add each employee email as a **Test user**.
2. **Credentials → Create OAuth client ID → Web application** → Authorized redirect URI:
   `https://<your-service>.onrender.com/oauth2callback` (you learn the exact URL after step 5; add it, then redeploy).
3. Copy `.streamlit/secrets.toml.example` → fill `redirect_uri` and a long random `cookie_secret` (under `[auth]`) and `client_id`, `client_secret` (under `[auth.google]` — the app calls `st.login("google")`, so a flat `[auth]` layout fails with "credentials ... are missing for the authentication provider google")
   (`python -c "import secrets; print(secrets.token_hex(32))"`).

## 5. Deploy on Render
```bash
git init && git add . && git commit -m "hr rag on render"
# create an empty GitHub repo, then:
git remote add origin https://github.com/<you>/<repo>.git && git push -u origin main
```
Render dashboard → **New → Blueprint** → select the repo → it reads `render.yaml`. Fill the prompted values:
`GROQ_API_KEY`, `JINA_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `ALLOWED_EMPLOYEE_EMAILS`.

Then: service → **Environment → Secret Files → Add** → filename `secrets.toml`, contents = your filled `[auth]` block.
`start.sh` copies it into `.streamlit/secrets.toml` at boot. Redeploy once.

> `REQUIRE_AUTH=true` is preset: if the secret file is missing the app shows a "login not configured" error and refuses to serve — it will **not** fall back to open mode on a public URL.

## 6. Every user session
Open URL → "Log in with Google" → email must be in `ALLOWED_EMPLOYEE_EMAILS` → chat.

## 7. Free-plan behaviour to expect
- Sleeps after ~15 min idle; the first request afterwards takes ~30–60 s to wake.
- The semantic cache and chat memory are in-process, so they reset on every sleep/restart.
- If the service is killed for running out of memory (logs show "Out of memory"), the free 512 MB is too small for the Python + litellm stack: move to the next paid plan.

## 8. Updating
`git push` → Render auto-deploys (`autoDeploy: true`). Re-run `python ingest.py --force` locally if policy files change.
