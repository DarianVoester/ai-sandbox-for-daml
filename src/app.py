import os
import subprocess
from pathlib import Path
import requests
import streamlit as st
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_PATH = "./.qdrant_db"
COLLECTION_NAME = "daml_curriculum"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
WORKSPACE_DIR = Path("./workspace").resolve()
DAML_FILE = WORKSPACE_DIR / "daml" / "Main.daml"

SYSTEM_PROMPT = """You are a senior Daml Smart Contract Architect and interactive Tutor.
Your task is to guide the developer based strictly on the provided CURRICULUM CONTEXT.
Rules:
1. Ground your explanations in the CURRICULUM CONTEXT and core Daml principles (Signatory, Observer, Controller, UTXO model, Sub-Transaction Privacy).
2. Analyze the user's CURRENT DAML CODE and the COMPILER OUTPUT.
3. Do not immediately output the full copy-paste solution for exercises; provide targeted architectural hints and explain the underlying authorization or ledger mechanics.
4. Keep responses concise, technical, and free of filler."""


@st.cache_resource
def load_rag_resources():
    embedder = SentenceTransformer(MODEL_NAME)
    qdrant = QdrantClient(path=QDRANT_PATH)
    return embedder, qdrant


@st.cache_resource
def load_local_free_llm():
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    model_path = hf_hub_download(
        repo_id="Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        filename="qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
    )
    return Llama(model_path=model_path, n_ctx=4096, verbose=False)


def retrieve_curriculum_context(query: str, top_k: int = 3) -> str:
    embedder, qdrant = load_rag_resources()
    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
    )
    chunks = []
    for hit in response.points:
        source_name = hit.payload.get("source", "curriculum")
        text_body = hit.payload.get("text", "")
        chunks.append(f"Source: {source_name} (Score: {hit.score:.2f})\n{text_body}")
    return "\n\n---\n\n".join(chunks)


def run_daml_test_safely() -> str:
    try:
        result = subprocess.run(
            ["daml", "test"],
            cwd=str(WORKSPACE_DIR),
            shell=False,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return output if output else "All Daml Script tests passed with no console errors."
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (greater than 45s) while running 'daml test'."
    except FileNotFoundError:
        return "Error: 'daml' binary not found in PATH."


def fetch_available_models(provider: str, api_key: str, base_url: str) -> list[str]:
    """Fragt live beim Anbieter ab, welche Modell-IDs für den Key existieren."""
    if not api_key:
        return []
    try:
        if provider == "Anthropic (Claude)":
            resp = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key.strip(), "anthropic-version": "2023-06-01"},
                timeout=10,
            )
            if resp.status_code == 200:
                return [m["id"] for m in resp.json().get("data", [])]
        else:
            url = f"{base_url.rstrip('/')}/models"
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key.strip()}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return [m["id"] for m in resp.json().get("data", [])]
    except Exception:
        pass
    return []


def query_llm(provider: str, model_id: str, api_key: str, base_url: str, user_payload: str) -> str:
    # 1. Lokales Gratis-Modell (100% offline im Codespace, kein Key nötig)
    if provider == "Free Built-in (Local Qwen-Coder - No API Key)":
        llm = load_local_free_llm()
        res = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return res["choices"][0]["message"]["content"]

    # 2. Direkter offizieller Anthropic-Aufruf (unterstützt Claude Opus 5.5, Sonnet 5.5 etc.)
    if provider == "Anthropic (Claude)":
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
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_payload}],
            },
            timeout=90,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API Status {resp.status_code}: {resp.text}")
        data = resp.json()
        # Filtert bei Opus 5.5 / Sonnet 5.5 eventuelle Thinking-Blöcke sauber heraus
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n\n".join(text_blocks)

    # 3. Universeller OpenAI-kompatibler Aufruf (OpenAI, OpenRouter, Groq, DeepSeek, vLLM)
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    resp = requests.post(
        url,
        headers=headers,
        json={
            "model": model_id.strip(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            "temperature": 0.2,
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API Status {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]


st.set_page_config(page_title="AI Sandbox for Daml", layout="wide")
st.title("Smart Contract Tutor for Daml")

with st.sidebar:
    st.header("LLM Configuration")
    provider = st.selectbox(
        "Select Provider",
        [
            "Anthropic (Claude)",
            "Free Built-in (Local Qwen-Coder - No API Key)",
            "OpenAI / Groq / OpenRouter / Custom",
        ],
    )

    api_key = ""
    base_url = ""
    model_id = ""

    if provider == "Free Built-in (Local Qwen-Coder - No API Key)":
        st.success("Runs 100% locally inside Codespaces via Python. Zero API keys or external servers needed.")
        model_id = "qwen2.5-coder-0.5b-instruct"

    elif provider == "Anthropic (Claude)":
        api_key = st.text_input("Anthropic API Key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password")
        default_claude_models = [
            "claude-opus-5-5",
            "claude-sonnet-5-5",
            "claude-haiku-5-5",
            "claude-opus-4-8",
            "claude-sonnet-4-5",
        ]
        live_models = fetch_available_models(provider, api_key, "") if api_key else []
        model_options = live_models if live_models else default_claude_models
        if live_models:
            st.caption(f"✅ Key verified! Loaded {len(live_models)} active models directly from your Anthropic account.")

        selected_model = st.selectbox("Select Claude Model", model_options + ["Custom Model ID..."])
        if selected_model == "Custom Model ID...":
            model_id = st.text_input("Enter Custom Anthropic Model ID", value="claude-opus-5-5")
        else:
            model_id = selected_model

    else:
        preset = st.selectbox(
            "Endpoint Preset",
            [
                "Google Gemini (Official)",
                "OpenAI Official",
                "OpenRouter (All Models)",
                "Groq (Fast & Free Tier)",
                "Custom Base URL",
            ],
        )
        if preset == "Google Gemini (Official)":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            default_m = "gemini-2.5-pro"
            default_key = os.getenv("GEMINI_API_KEY", "")
        elif preset == "OpenAI Official":
            base_url = "https://api.openai.com/v1"
            default_m = "gpt-4o"
            default_key = os.getenv("OPENAI_API_KEY", "")
        elif preset == "OpenRouter (All Models)":
            base_url = "https://openrouter.ai/api/v1"
            default_m = "anthropic/claude-opus-5.5"
            default_key = os.getenv("OPENROUTER_API_KEY", "")
        elif preset == "Groq (Fast & Free Tier)":
            base_url = "https://api.groq.com/openai/v1"
            default_m = "llama-3.3-70b-versatile"
            default_key = os.getenv("GROQ_API_KEY", "")
        else:
            base_url = st.text_input("Custom API Base URL", value="http://localhost:11434/v1")
            default_m = "qwen2.5-coder:7b"
            default_key = ""

        api_key = st.text_input("API Key", value=default_key, type="password")
        live_models = fetch_available_models(provider, api_key, base_url) if api_key else []
        if live_models:
            st.caption(f"✅ Loaded {len(live_models)} models from endpoint.")
            model_id = st.selectbox("Select Model", live_models)
        else:
            model_id = st.text_input("Model ID", value=default_m)

col_code, col_tutor = st.columns([1, 1])

with col_code:
    st.subheader("Workspace (`workspace/daml/Main.daml`)")
    current_code = DAML_FILE.read_text(encoding="utf-8") if DAML_FILE.exists() else ""
    edited_code = st.text_area("Daml Code Editor", value=current_code, height=380)

    if st.button("Save & Run 'daml test'"):
        DAML_FILE.write_text(edited_code, encoding="utf-8")
        with st.spinner("Running Canton / Daml Script tests..."):
            st.session_state["compiler_output"] = run_daml_test_safely()

    compiler_out = st.session_state.get("compiler_output", "No test execution recorded yet.")
    st.code(compiler_out, language="text")

with col_tutor:
    st.subheader("RAG Tutor (Curriculum-Grounded)")
    user_question = st.text_area(
        "Ask a question about the current lesson or compiler output:",
        placeholder="Why did my test produce 2 transactions and leave 1 active contract?",
    )

    if st.button("Ask Tutor") and user_question:
        if provider != "Free Built-in (Local Qwen-Coder - No API Key)" and not api_key:
            st.error("Please enter your API Key in the sidebar or switch to the Free Built-in model.")
        else:
            with st.spinner(f"Querying {model_id} with Qdrant curriculum context..."):
                search_query = f"{user_question}\n{compiler_out[:300]}"
                rag_context = retrieve_curriculum_context(search_query)

                user_payload = (
                    f"### CURRICULUM CONTEXT:\n{rag_context}\n\n"
                    f"### CURRENT DAML CODE:\n```daml\n{edited_code}\n```\n\n"
                    f"### COMPILER / TEST OUTPUT:\n```\n{compiler_out}\n```\n\n"
                    f"### DEVELOPER QUESTION:\n{user_question}"
                )

                try:
                    answer = query_llm(provider, model_id, api_key, base_url, user_payload)
                    st.markdown(answer)
                    with st.expander("Retrieved Curriculum Chunks (Qdrant)"):
                        st.text(rag_context)
                except Exception as e:
                    st.error(f"Execution Error: {e}")