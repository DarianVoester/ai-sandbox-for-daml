"""Zentrale Konfiguration: Pfade, Konstanten und Prompts (keine Abhängigkeit zu Streamlit)."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- RAG / Qdrant ---
QDRANT_PATH = str(BASE_DIR / ".qdrant_db")
COLLECTION_NAME = "daml_curriculum"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CURRICULUM_DIR = BASE_DIR / "curriculum"
STARTERS_DIR = CURRICULUM_DIR / "starters"

# --- Daml workspace ---
WORKSPACE_DIR = BASE_DIR / "workspace"
DAML_FILE = WORKSPACE_DIR / "daml" / "Main.daml"
DAML_YAML = WORKSPACE_DIR / "daml.yaml"
DAML_TIMEOUTS = {"build": 180, "test": 120}
COVERAGE_MARKER = "Modules internal to this package"
TEST_SUMMARY_MARKER = "Test Summary"
MAX_OUTPUT_CHARS = 3000

# --- LLM ---
LOCAL_PROVIDER = "Free Built-in (Local Qwen-Coder - No API Key)"
ANTHROPIC_PROVIDER = "Anthropic (Claude)"
OPENAI_PROVIDER = "OpenAI / Groq / OpenRouter / Custom"
PROVIDERS = [LOCAL_PROVIDER, ANTHROPIC_PROVIDER, OPENAI_PROVIDER]

LOCAL_MODEL_REPO = "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF"
LOCAL_MODEL_FILE = "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf"
LOCAL_N_CTX = 4096
LOCAL_MAX_TOKENS = 768
# Zeichenbudget für den Prompt (n_ctx 4096 Tokens minus Antwort, ca. 3 Zeichen pro Token)
LOCAL_PROMPT_CHARS = 7000
REMOTE_PROMPT_CHARS = 40000
HISTORY_PAIRS = 3

SYSTEM_PROMPT = """You are a senior Daml Smart Contract Architect and interactive Tutor.
Your task is to guide the developer based strictly on the provided CURRICULUM CONTEXT.
Rules:
1. Ground your explanations in the CURRICULUM CONTEXT and core Daml principles (Signatory, Observer, Controller, UTXO model, Sub-Transaction Privacy).
2. Analyze the user's CURRENT DAML CODE and the COMPILER OUTPUT.
3. Do not immediately output the full copy-paste solution for exercises; provide targeted architectural hints and explain the underlying authorization or ledger mechanics.
4. Keep responses concise, technical, and free of filler."""
