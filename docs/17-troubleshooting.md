# 17. Troubleshooting

Errors that came up while building and deploying this free variant, in
plain words: what you see, why it happens, how to fix it. (Google-login
errors §1–4 and §15 follow the original project's list, updated for
Render.)

## Quick index

| Symptom | Section |
|---|---|
| "This deployment requires Google login, but the [auth] secrets are not configured" | [1](#1-this-deployment-requires-google-login) |
| `StreamlitAuthError … missing for the authentication provider "google"` | [2](#2-streamlitautherror-credentials-missing-for-google) |
| `Error 400: redirect_uri_mismatch`, a login loop, or "Access blocked" | [3](#3-redirect_uri_mismatch-login-loop-access-blocked) |
| `secrets.toml` looks right but is ignored / rejected | [4](#4-secretstoml-looks-right-but-is-rejected) |
| `[Errno -2] Name or service not known` talking to Qdrant | [5](#5-qdrant-name-or-service-not-known) |
| `RuntimeError: Qdrant collection '…' is missing or empty` | [6](#6-qdrant-collection-missing-or-empty) |
| `Storage folder … is already accessed by another instance` | [7](#7-local-qdrant-is-locked) |
| Cold start crashes: `Could not load model Qdrant/bm25` | [8](#8-could-not-load-model-qdrantbm25) |
| Every question is refused by the input guardrail | [9](#9-everything-is-blocked-by-the-input-guardrail) |
| "I don't have that" for a topic that exists | [10](#10-i-dont-have-that-for-a-topic-that-exists) |
| Render is slow, resets chats, or runs out of memory | [11](#11-render-free-plan-slow-resets-out-of-memory) |
| `TypeError: 'function' object is not subscriptable`, missing modules | [12](#12-python-environment-errors) |
| Docker ignores my `.env` change / `docker build` image isn't there | [13](#13-docker-env-and-build-gotchas) |
| `langgraph dev` complains about a checkpointer | [14](#14-langgraph-dev-checkpointer-conflict) |
| A Google Console change "didn't take" | [15](#15-oauth-changes-take-time-to-propagate) |
| Groq: model not found / decommissioned | [16](#16-groq-model-not-found) |

---

## 1. This deployment requires Google login

**You see:** *"This deployment requires Google login, but the [auth] secrets
are not configured, so access is blocked."*

**Why:** this is the fail-closed guard working. `REQUIRE_AUTH=true` (set in
`render.yaml`) and the container found no `[auth]` block — i.e. the Render
Secret File is missing, misnamed or malformed. It cannot appear locally
unless you set `REQUIRE_AUTH=true` yourself.

**Fix:**

1. Render → your service → **Environment → Secret Files**.
2. Filename exactly `secrets.toml` (the boot script looks for
   `/etc/secrets/secrets.toml`; `secret.toml` or `secrets.toml.txt` won't be
   found).
3. Contents include the `[auth]` header and the `[auth.google]` block (doc 13).
4. Save, wait for the redeploy to show **Live**, reload.

---

## 2. `StreamlitAuthError`: credentials missing for "google"

**You see:** `Authentication credentials in .streamlit/secrets.toml are
missing for the authentication provider "google"`.

**Why:** the app calls `st.login("google")`, a *named* provider, so Streamlit
looks for `[auth.google]`. A flat layout with `client_id` directly under
`[auth]` is for the unnamed default provider and fails this check.

**Fix:** use the nested layout from `.streamlit/secrets.toml.example`:
`redirect_uri` + `cookie_secret` under `[auth]`, and `client_id`,
`client_secret`, `server_metadata_url` under `[auth.google]`.

---

## 3. `redirect_uri_mismatch`, login loop, "Access blocked"

**`Error 400: redirect_uri_mismatch`** — the `redirect_uri` the app sent is
not in the OAuth client's **Authorized redirect URIs**. Google compares the
two strings exactly. Click **error details** on Google's page to see the
exact URI the app sent, then add that string (Console → APIs & Services →
Credentials → the client whose ID matches your `secrets.toml`; the *redirect
URIs* box, not "JavaScript origins").

| Wrong | Right |
|---|---|
| `https://x.onrender.com` (bare) | `https://x.onrender.com/oauth2callback` |
| `https://x.onrender.com/oauth2callback/` (trailing slash) | `https://x.onrender.com/oauth2callback` |
| `http://x.onrender.com/…` | `https://…` (Render is always https) |
| `http://localhost:8502/…` (wrong port) | the port Streamlit actually started on |

**Login loop** (you approve, then land on the login screen again, no error):
`redirect_uri` in `secrets.toml` is missing the `/oauth2callback` path, so
Google sends the code back to `/` where Streamlit never processes it. Fix the
string in **both** places and update the Render Secret File (saving redeploys).

**"Access blocked: this app's request is invalid"** — usually the same cause
as above; otherwise the consent screen is incomplete (app name, support email,
developer contact) or your email isn't under **Test users**.

---

## 4. `secrets.toml` looks right but is rejected

Three real causes:

- **A stray quote**, e.g. `redirect_uri = "http://…/oauth2callback""` — the
  file is invalid TOML.
- **Missing `cookie_secret`** — Streamlit won't start the login without it.
- **A UTF-8 BOM** at the start of the file. Windows PowerShell's
  `Set-Content -Encoding utf8` writes one and the file then fails silently.
  Create the file in an editor (save as plain UTF-8) or use a BOM-free write.

You can test a file locally without starting the app:

```python
from streamlit.auth_util import validate_auth_credentials
validate_auth_credentials("google")   # run from the folder that contains .streamlit/
```

It raises with a clear message if something is missing.

---

## 5. Qdrant `Name or service not known`

**You see:** `ResponseHandlingException: [Errno -2] Name or service not
known`, traceback through `qdrant_client`.

**Why:** the host in `QDRANT_URL` doesn't resolve in DNS. Two real causes:

1. **A placeholder URL** copied from a template (`xxxx.cloud.qdrant.io`).
   Use the real cluster URL from Qdrant Cloud, no trailing path.
2. **A stale container.** Docker Compose reads `.env` only when the
   container is *created*. You fixed the URL but the running container still
   holds the old value.

**Fix:**

```bash
docker compose down
docker compose run --rm ingest     # fills the (new, empty) cluster once
docker compose up --build
```

To check the cluster itself, a read-only call such as `GET <url>:6333/collections`
with the header `api-key: <key>` should return JSON; an empty cluster returns
`{"collections":[]}`.

---

## 6. Qdrant collection missing or empty

**You see:** `RuntimeError: Qdrant collection 'hr_policies' is missing or
empty. Run \`python ingest.py\` once to ingest the corpus.`

**Why:** the pipeline connects to a collection that ingestion never built (or
that was cleared — a brand-new Qdrant Cloud cluster starts with none).

**Fix:**

```bash
python ingest.py                 # builds both collections
python ingest.py --force         # rebuild from scratch
```

`app.py` / `main.py` try to bootstrap ingestion on first run, but on Render
that first request would take minutes and use Jina tokens. Run `ingest.py`
once from your laptop with the **same** `.env` values (Qdrant URL, Jina key)
*before* the first user arrives. Expect 61 points in `hr_policies` and 75 in
`hr_policies_noisy_demo`.

---

## 7. Local Qdrant is locked

**You see:** `Storage folder … is already accessed by another instance of
Qdrant client`.

**Why:** the on-disk Qdrant allows one process at a time (doc 05). Another
Python process (a running app, a notebook, `ingest.py`) still holds it.

**Fix:** stop the other process, then retry. Or avoid the limit by using a
Qdrant Cloud cluster (`QDRANT_URL`).

---

## 8. `Could not load model Qdrant/bm25`

**You see:** the image builds, then the container crashes with
`ValueError: Could not load model Qdrant/bm25 from any source.`

**Why:** `fastembed` downloads the BM25 file from HuggingFace on first use,
and a fresh container keeps no disk between runs; the download got
rate-limited. 

**Fix (already in the `Dockerfile`):** download at *build* time:

```dockerfile
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"
```

If you removed that line, put it back (doc 12).

---

## 9. Everything is blocked by the input guardrail

**You see:** every question — even a harmless one — returns *"I can't
process that request — it was flagged by the input safety guardrail."* Logs
show `INPUT GUARDRAIL: block (guardrail provider error — failing closed …)`.

**Why:** the safety check is an LLM call to Groq. If that call *errors* — a
rate limit on the free tier, a wrong or missing key, a retired model — the
input check **fails closed** on purpose: an unscreened prompt must never reach
the model. Because the guardrail and the answer share one Groq key, heavy
use makes this likely.

**Fix:** read the full error in the logs, then one of —

| Situation | Do this |
|---|---|
| Rate limit | wait a minute; ask less often; consider a smaller `GUARDRAIL_HISTORY_TURNS` |
| Bad/missing key | check `GROQ_API_KEY` |
| Model retired | §16 |
| Local dev only, you want it off | `GUARDRAIL_PROVIDER=none` in `.env` (never on a public deployment) |

(*Output*-side errors fail **open** instead — a transient error shouldn't
throw away a valid answer. See doc 15.)

---

## 10. "I don't have that" for a topic that exists

**You see:** a question about a policy that clearly exists is answered with
"I don't have that / not found", while other policies work.

**Why (two real causes):**

1. **The data file is empty.** `work_from_home_policy.txt` was 0 bytes in the
   original project; it ingests without error and produces no chunks. Check
   `data/*.txt` sizes, fill the file, then `python ingest.py --force`.
2. **The relevance threshold** (`RELEVANCE_THRESHOLD`, 0.35) is too strict
   for your reranker. Run `demo_reliability.py`, look at the scores, and
   lower the value slightly if good chunks score just under it.

---

## 11. Render free plan: slow, resets, out of memory

- **First request takes 30–60 s:** the service slept after ~15 minutes idle.
  Normal on the free plan.
- **Chat history / cache vanished:** both are in-process memory and reset
  when the service sleeps or restarts. Qdrant data is unaffected.
- **Service restarts, logs say "Out of memory":** the free plan has 512 MB;
  the app needs roughly 330 MB just to import (`litellm` ≈ 280 MB), plus
  per-session state. The next paid tier is also 512 MB, so upgrading is not
  a sure fix. Check **Metrics → Memory**. Real remedies: replace `litellm`
  with a direct Groq client (doc 14), reduce concurrent sessions, or pick an
  instance size with more RAM.

---

## 12. Python environment errors

**You see:** `TypeError: 'function' object is not subscriptable` from
LangChain/pydantic, or `ModuleNotFoundError` for `litellm`, `qdrant_client`,
`fastembed`.

**Why:** a shared/old environment — in one case Python 3.14 with
`langchain 0.3.x` — instead of the pinned stack. This project needs
LangChain 1.x (`create_agent`).

**Fix:** use a clean Python 3.11 virtual environment per phase:

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 13. Docker `.env` and build gotchas

- **`.env` change ignored:** `env_file` is read when a container is created.
  `docker compose down` then `up` (see doc 12 and §5).
- **`docker build` finished but the image isn't listed:** with the buildx
  builder, add `--load` (`docker build --load -t name .`), or use
  `docker compose build`, which loads it.
- **Docker Desktop must be running** before any `docker` command.

---

## 14. `langgraph dev` checkpointer conflict

**You see:** `langgraph dev` fails to load the graph with an error about a
checkpointer already being set.

**Why:** LangGraph Studio supplies its **own** persistence and rejects a
graph with an `InMemorySaver` baked in.

**Fix (already done):** `hr_assistant/studio_graph.py` builds the agent with
`checkpointer=False`, which `pipeline._resolve_checkpointer` turns into "no
checkpointer at all". On an older copy, pass `checkpointer=False` there.

---

## 15. OAuth changes take time to propagate

**You see:** you fixed the redirect URI / added a test user, but the old
behaviour persists.

**Why:** Google caches OAuth client config; the Console says it can take
minutes to hours. In practice 1–5 minutes.

**Fix:** wait, then retry in a **fresh incognito window**. If it still fails
after ~15 minutes, it's an actual string mismatch — recheck §3.

---

## 16. Groq model not found

**You see:** an error from LiteLLM such as *model not found* or
*decommissioned* for `openai/gpt-oss-20b` / `-120b`.

**Why:** Groq's model catalogue changes; a model you configured was retired.

**Fix:** pick a current model from console.groq.com/docs/models and set
`LLM_MODEL_NAME` / `FALLBACK_MODEL_NAME` (and `JUDGE_MODEL_NAME`) in `.env` —
LiteLLM strings look like `groq/<model-id>`. On Render, change them in the
service's environment variables.

---

Next: back to **[README](../README.md)** · full command list in
**`commands/commands-deployment.md`**.
