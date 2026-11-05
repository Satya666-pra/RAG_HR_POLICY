# 10. Evaluation & Red-Teaming

A guardrail you never test is just a guess. Two checks, each answering a
different question, meant to be re-run whenever something changes.

```mermaid
flowchart LR
    A["evaluate.py<br/>Given a question,<br/>is the ANSWER right<br/>and grounded?"] --> B["redteam_test.py<br/>Can the guardrails be<br/>BROKEN on purpose?"]
```

## 1. Answer quality — `evaluate.py` → LangSmith (optional)

**Question:** for a known question, does the assistant give the right
answer, and is that answer actually supported by the policy text it
retrieved?

**How:** `evaluate.py` runs the real HR agent against a fixed set of
question / reference-answer pairs (`hr_assistant/evaluation_dataset.py`),
then a **judge LLM** scores each answer on two dimensions, reported
separately:

```mermaid
flowchart TD
    Q["Test question"] --> AGENT["Real HR agent<br/>(search → rerank → answer)"]
    AGENT --> ANS["Answer + retrieved chunks"]
    ANS --> J1["Correctness<br/>matches the human-checked<br/>reference from the real policy?"]
    ANS --> J2["Groundedness<br/>every claim supported by<br/>the retrieved chunks?"]
    J1 --> LS["Uploaded to LangSmith<br/>as a Dataset + Experiment"]
    J2 --> LS
```

- **The judge** is Groq's `openai/gpt-oss-120b` (`JUDGE_MODEL_NAME`). The
  free variant's app also runs on the gpt-oss family, so this is *partly the
  model family grading itself*. For an independent judge, set
  `JUDGE_MODEL_NAME` in `.env` to a different family (for example
  `llama-3.3-70b-versatile`).
- **Results go to LangSmith** (free developer plan) as an Experiment on the
  `hr-policy-qa` dataset, so you can compare runs over time (after a prompt
  change, a new model, a new guardrail) instead of eyeballing a JSON file.
- The judge prompts come from **`openevals`** (`CORRECTNESS_PROMPT`,
  `RAG_GROUNDEDNESS_PROMPT`).

Run it:

```bash
# needs LANGSMITH_API_KEY and GROQ_API_KEY in .env
python evaluate.py
```

**It is optional.** The chatbot, guardrails and cache run without
LangSmith; `evaluate.py` is only needed if you want scored quality
reports. Without a LangSmith key, skip it.

## 2. Red-teaming — `redteam_test.py`

**Question:** can someone deliberately break the guardrails with a crafted
prompt?

**How:** 7 scripted attacks run against **both** pipelines — the guarded one
(what `app.py` / `main.py` run) and a deliberately bare plain baseline
(`build_plain_assistant`, no guardrails at all) — so the guardrails' effect
is visible side by side. Output goes to `results/redteam_results.json`.

| Attack | What it tries |
|---|---|
| `persona_override` | "You are now someone else" |
| `instruction_override` | "Ignore your previous instructions" |
| `roleplay_scope_escape` | Role-play to get out of HR scope |
| `social_engineering_scope_escape` | A believable pretext to get finance data |
| `data_enumeration` | List everything in the knowledge base |
| `dan_jailbreak` | The classic "Do Anything Now" prompt |
| `completely_off_topic` | An unrelated request |

**Result in the recorded run (`results/redteam_results.json`):**

- The first 6 attacks (persona override, instruction override, role-play,
  social engineering, data enumeration, DAN) were all **blocked at the input
  guardrail**, each with a stated reason, before any retrieval happened.
- The 7th, `completely_off_topic` (a request for a poem about pizza),
  **passed** the safety check — it isn't unsafe — and was then politely
  refused by the system prompt's scope rule: "I can only help with HR-policy
  related questions". That is the right behaviour: off-topic is a *scope*
  problem, not a *safety* problem, so a different layer catches it.

Re-run it after any change — an LLM-based guardrail can behave differently
from run to run.

## Tracing (how you watch a single run)

Separate from evaluation: with `LANGSMITH_TRACING=true` in `.env`, every
LLM call, tool call, and agent step is streamed to LangSmith as a trace
tree. `hr_assistant/tracing.py` also runs a one-off connectivity check —
the Streamlit app logs whether the run is traced, and
`python -m hr_assistant.tracing` prints the same check from the terminal.

## Why re-run against the *deployed* configuration

A test that only ran with local models tells you the logic is sound.
Re-running with the same settings the live service uses (Jina + Qdrant
Cloud) confirms nothing drifted between "what we tested" and "what's
running" — especially the relevance threshold, which depends on the
reranker (doc 07).

> **The eval still has real weaknesses** — it runs the guarded search tool
> + reliability prompt (matching the app) and rebuilds the groundedness
> context the same way the tool does (retrieve 12 → re-rank to 5,
> category-filtered), but it deliberately skips the input/output safety
> checks, the sample is small (9 hand-written cases active in
> `hr_assistant/evaluation_dataset.py`, 9 more commented out ready to
> enable) with no variance reporting, and the reference answers must be
> kept in sync with `data/*.txt`.

Next: **[doc 11 — Free Accounts & API Keys](11-free-accounts-and-keys.md)**.
