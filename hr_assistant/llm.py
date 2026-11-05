"""12 · llm — connect to the model.

Every model call in the app goes through one place: get_llm(). It returns a
LangChain chat model backed by a LiteLLM *Router* (the litellm SDK, running
in-process — NOT a separate proxy service):

    primary   -> config.LLM_MODEL_NAME       (default: Groq gpt-oss-20b)
    fallback  -> config.FALLBACK_MODEL_NAME  (default: Groq gpt-oss-120b), used
                                             only if the primary errors after
                                             num_retries

The app always asks for one logical model ("hr-llm"); the Router decides
what actually serves it. Both names are full LiteLLM strings
("<provider>/<model>"), so moving to another provider (Gemini via AI Studio,
Ollama on your own machine, ...) is an .env change, not a code change.
"""

import litellm
from langchain_litellm import ChatLiteLLMRouter
from litellm import Router

from hr_assistant import config

# Some params are accepted by one provider and rejected by another. Drop
# unsupported params on the way to whichever backend serves the call, rather
# than 400-ing on the fallback.
litellm.drop_params = True

_PRIMARY_GROUP = "hr-llm"
_FALLBACK_GROUP = "hr-llm-fallback"

# One Router for the whole process — it holds per-deployment state
# (cooldowns, retry counters).
_router: "Router | None" = None


def _params(model: str) -> dict:
    """LiteLLM params for one model string. Groq models get the Groq key
    explicitly; any other provider reads its own key from the environment
    (e.g. GEMINI_API_KEY, OPENAI_API_KEY)."""
    params = {"model": model}
    if model.startswith("groq/"):
        params["api_key"] = config.GROQ_API_KEY
    return params


def _get_router() -> Router:
    global _router
    if _router is None:
        _router = Router(
            model_list=[
                {"model_name": _PRIMARY_GROUP, "litellm_params": _params(config.LLM_MODEL_NAME)},
                {"model_name": _FALLBACK_GROUP, "litellm_params": _params(config.FALLBACK_MODEL_NAME)},
            ],
            # Retry the primary a couple of times, THEN cross over to the fallback.
            num_retries=2,
            fallbacks=[{_PRIMARY_GROUP: [_FALLBACK_GROUP]}],
        )
    return _router


def get_llm():
    """The app's chat model: primary + fallback, one retry policy.

    A LangChain chat model (supports tool calling and structured output), so
    agent.py and guardrails.py use it unchanged. temperature=0 is set once
    here — the single source of truth for both backends."""
    return ChatLiteLLMRouter(router=_get_router(), model_name=_PRIMARY_GROUP, temperature=0)
