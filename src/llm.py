"""LLM-Anbindung: lokales GGUF-Modell, Anthropic und OpenAI-kompatible Endpunkte."""
import threading

import requests

import settings

_local_lock = threading.Lock()
_local_llm = None


def local_model_cached() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        path = try_to_load_from_cache(repo_id=settings.LOCAL_MODEL_REPO, filename=settings.LOCAL_MODEL_FILE)
        return isinstance(path, str)
    except Exception:
        return False


def _get_local_llm():
    global _local_llm
    if _local_llm is None:
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        model_path = hf_hub_download(repo_id=settings.LOCAL_MODEL_REPO, filename=settings.LOCAL_MODEL_FILE)
        _local_llm = Llama(model_path=model_path, n_ctx=settings.LOCAL_N_CTX, verbose=False)
    return _local_llm


def fetch_available_models(provider: str, api_key: str, base_url: str) -> tuple[list[str], str]:
    """Fragt live die Modell-IDs ab. Rückgabe: (Modelle, Fehlermeldung)."""
    if not api_key:
        return [], ""
    try:
        if provider == settings.ANTHROPIC_PROVIDER:
            resp = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key.strip(), "anthropic-version": "2023-06-01"},
                timeout=10,
            )
        else:
            resp = requests.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
                timeout=10,
            )
        if resp.status_code != 200:
            return [], f"Model list request failed (HTTP {resp.status_code})."
        return [m["id"] for m in resp.json().get("data", [])], ""
    except Exception as e:
        return [], f"Model list request failed: {type(e).__name__}"


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


def build_user_payload(context: str, code: str, output: str, question: str, max_chars: int) -> str:
    """Baut den Prompt und verteilt das Zeichenbudget auf die Abschnitte."""
    return (
        f"### CURRICULUM CONTEXT:\n{_cap(context, int(max_chars * 0.35))}\n\n"
        f"### CURRENT DAML CODE:\n```daml\n{_cap(code, int(max_chars * 0.30))}\n```\n\n"
        f"### COMPILER / TEST OUTPUT:\n```\n{_cap(output, int(max_chars * 0.20))}\n```\n\n"
        f"### DEVELOPER QUESTION:\n{_cap(question, int(max_chars * 0.15))}"
    )


def query_llm(
    provider: str,
    model_id: str,
    api_key: str,
    base_url: str,
    user_payload: str,
    history: list[dict] | None = None,
) -> str:
    history = history or []

    if provider == settings.LOCAL_PROVIDER:
        with _local_lock:
            llm = _get_local_llm()
            res = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": settings.SYSTEM_PROMPT},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.2,
                max_tokens=settings.LOCAL_MAX_TOKENS,
            )
        return res["choices"][0]["message"]["content"]

    messages = history + [{"role": "user", "content": user_payload}]

    if provider == settings.ANTHROPIC_PROVIDER:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key.strip(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model_id.strip(),
                "max_tokens": 4096,
                "system": settings.SYSTEM_PROMPT,
                "messages": messages,
            },
            timeout=90,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API status {resp.status_code}: {resp.text}")
        blocks = [b["text"] for b in resp.json().get("content", []) if b.get("type") == "text"]
        return "\n\n".join(blocks)

    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model_id.strip(),
            "messages": [{"role": "system", "content": settings.SYSTEM_PROMPT}] + messages,
            "temperature": 0.2,
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API status {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]
