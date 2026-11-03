"""Streamlit-Oberfläche: Lektion, Editor mit Build/Test und RAG-Tutor für Daml."""
import os
from dataclasses import dataclass

import streamlit as st

import daml_runner
import lessons
import llm
import rag
import settings


@dataclass
class LLMConfig:
    provider: str
    model_id: str
    api_key: str
    base_url: str

    @property
    def is_local(self) -> bool:
        return self.provider == settings.LOCAL_PROVIDER


# --------------------------------------------------------------------------- helpers


@st.cache_data(ttl=300, show_spinner=False)
def cached_models(provider: str, api_key: str, base_url: str) -> tuple[list[str], str]:
    return llm.fetch_available_models(provider, api_key, base_url)


def run_text(result: daml_runner.RunResult | None) -> str:
    if result is None:
        return "No build or test execution recorded yet."
    return result.output or result.error or "Finished without console output."


def show_flash() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message)


def init_state() -> None:
    if "editor_code" not in st.session_state:
        st.session_state["editor_code"] = daml_runner.read_source()
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("last_run", None)


# --------------------------------------------------------------------------- sidebar


def render_status() -> None:
    st.subheader("Status")
    if daml_runner.daml_available():
        st.success(f"Daml SDK {daml_runner.sdk_version()} found")
    else:
        st.error("'daml' not found in PATH (expected ~/.daml/bin)")

    try:
        count = rag.index_count()
        if count:
            st.success(f"Qdrant index: {count} chunks")
        else:
            st.warning("Qdrant index is empty (built automatically on first question).")
    except Exception as e:
        st.error(f"Qdrant: {e}")

    if llm.local_model_cached():
        st.success("Local model downloaded")
    else:
        st.info("Local model not downloaded yet (first use downloads ~400 MB).")

    msg = st.session_state.pop("index_msg", None)
    if msg:
        getattr(st, msg[0])(msg[1])
    if st.button("Rebuild index", width="stretch"):
        try:
            with st.spinner("Embedding curriculum..."):
                n = rag.build_index()
            st.session_state["index_msg"] = ("success", f"Indexed {n} chunks.")
        except Exception as e:
            st.session_state["index_msg"] = ("error", f"Indexing failed: {e}")
        st.rerun()


def render_llm_config() -> LLMConfig:
    st.subheader("LLM")
    provider = st.selectbox("Provider", settings.PROVIDERS, index=0)
    api_key, base_url, model_id = "", "", ""

    if provider == settings.LOCAL_PROVIDER:
        st.caption("Runs locally via llama-cpp. No API key required.")
        model_id = "qwen2.5-coder-0.5b-instruct"

    elif provider == settings.ANTHROPIC_PROVIDER:
        api_key = st.text_input("Anthropic API Key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password")
        defaults = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-4-8", "claude-sonnet-4-5"]
        live, err = cached_models(provider, api_key, "") if api_key else ([], "")
        if live:
            st.caption(f"{len(live)} models loaded from your account.")
        elif err:
            st.warning(err)
        selected = st.selectbox("Model", (live or defaults) + ["Custom Model ID..."])
        model_id = (
            st.text_input("Custom Anthropic Model ID", value=defaults[0])
            if selected == "Custom Model ID..."
            else selected
        )

    else:
        presets = {
            "Google Gemini (Official)": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-pro", "GEMINI_API_KEY"),
            "OpenAI Official": ("https://api.openai.com/v1", "gpt-4o", "OPENAI_API_KEY"),
            "OpenRouter (All Models)": ("https://openrouter.ai/api/v1", "anthropic/claude-opus-5.5", "OPENROUTER_API_KEY"),
            "Groq (Fast & Free Tier)": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
            "Custom Base URL": ("", "qwen2.5-coder:7b", ""),
        }
        preset = st.selectbox("Endpoint Preset", list(presets))
        base_url, default_model, env_key = presets[preset]
        if preset == "Custom Base URL":
            base_url = st.text_input("Custom API Base URL", value="http://localhost:11434/v1")
        api_key = st.text_input("API Key", value=os.getenv(env_key, "") if env_key else "", type="password")
        live, err = cached_models(provider, api_key, base_url) if api_key else ([], "")
        if live:
            st.caption(f"{len(live)} models loaded from endpoint.")
            model_id = st.selectbox("Model", live)
        else:
            if err:
                st.warning(err)
            model_id = st.text_input("Model ID", value=default_model)

    return LLMConfig(provider, model_id, api_key, base_url)


# --------------------------------------------------------------------------- tabs


def _load_starter_cb(lesson: str) -> None:
    try:
        backup = lessons.load_starter(lesson)
        st.session_state["editor_code"] = daml_runner.read_source()
        note = f" Previous code saved as {backup.name}." if backup else ""
        st.session_state["flash"] = ("success", f"Starter code loaded.{note}")
    except Exception as e:
        st.session_state["flash"] = ("error", str(e))


def render_lesson_tab() -> None:
    names = lessons.list_lessons()
    if not names:
        st.warning(f"No lessons found in {settings.CURRICULUM_DIR}.")
        return
    lesson = st.selectbox("Lesson", names, format_func=lessons.lesson_title, key="lesson")
    st.markdown(lessons.lesson_path(lesson).read_text(encoding="utf-8"))
    st.divider()
    if lessons.starter_for(lesson):
        st.button(
            "Load starter code into editor",
            on_click=_load_starter_cb,
            args=(lesson,),
            help="Overwrites workspace/daml/Main.daml. The previous version is saved as Main.daml.bak.",
        )
    else:
        st.caption("This lesson has no starter code.")


def _execute(command: str) -> None:
    daml_runner.write_source(st.session_state["editor_code"])
    with st.status(f"Running daml {command}...", expanded=False) as status:
        result = daml_runner.run(command)
        status.update(
            label=f"daml {command}: {'ok' if result.ok else 'failed'} ({result.duration:.0f}s)",
            state="complete" if result.ok else "error",
        )
    st.session_state["last_run"] = result


def render_editor_tab() -> None:
    st.text_area("workspace/daml/Main.daml", key="editor_code", height=420)
    if st.session_state["editor_code"] != daml_runner.read_source():
        st.caption("Unsaved changes (Build and Test save automatically).")

    save_col, build_col, test_col = st.columns(3)
    if save_col.button("Save", width="stretch"):
        daml_runner.write_source(st.session_state["editor_code"])
        st.toast("Saved Main.daml")
    if build_col.button("Build", width="stretch"):
        _execute("build")
    if test_col.button("Test", type="primary", width="stretch"):
        _execute("test")

    result: daml_runner.RunResult | None = st.session_state["last_run"]
    if result is None:
        st.info("No build or test run yet.")
        return
    if result.error:
        st.error(result.error)
        return

    main_output, coverage = daml_runner.split_coverage(result.output)
    rows = daml_runner.parse_test_summary(result.output) if result.command == "test" else []
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    if result.ok:
        st.success(f"daml {result.command} succeeded in {result.duration:.0f}s.")
    else:
        st.error(f"daml {result.command} failed (exit code {result.returncode}).")
    with st.expander("Console output", expanded=not result.ok):
        st.code(main_output or "(no output)", language="text")
    if coverage:
        with st.expander("Coverage report"):
            st.code(coverage, language="text")


def answer_question(cfg: LLMConfig, question: str, share_code: bool, share_output: bool) -> tuple[str, str]:
    if not cfg.is_local and not cfg.api_key.strip():
        raise ValueError("Please enter an API key in the sidebar or switch to the local model.")

    if rag.index_count() == 0:
        rag.build_index()

    if share_output:
        output = daml_runner.trim_for_prompt(run_text(st.session_state["last_run"]))
    else:
        output = "(not shared)"
    code = st.session_state["editor_code"] if share_code else "(not shared)"
    context = rag.retrieve(f"{question}\n{output[:300]}")

    max_chars = settings.LOCAL_PROMPT_CHARS if cfg.is_local else settings.REMOTE_PROMPT_CHARS
    payload = llm.build_user_payload(context, code, output, question, max_chars)

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state["chat"][-2 * settings.HISTORY_PAIRS:]
    ]
    answer = llm.query_llm(cfg.provider, cfg.model_id, cfg.api_key, cfg.base_url, payload, history)
    return answer, context


def render_tutor_tab(cfg: LLMConfig) -> None:
    opt_code, opt_output, clear = st.columns([2, 2, 1])
    share_code = opt_code.checkbox("Share my code", value=True)
    share_output = opt_output.checkbox("Share last build/test output", value=True)
    if clear.button("Clear chat", width="stretch"):
        st.session_state["chat"] = []
        st.rerun()

    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("context"):
                with st.expander("Retrieved curriculum chunks"):
                    st.text(msg["context"])

    question = st.chat_input("Ask about the lesson, your code or the compiler output")
    if not question:
        return

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            if cfg.is_local:
                spinner_text = "Running local model (the first call loads the model and can take a minute)..."
            else:
                spinner_text = f"Asking {cfg.model_id}..."
            with st.spinner(spinner_text):
                answer, context = answer_question(cfg, question, share_code, share_output)
        except Exception as e:
            st.error(f"Error: {e}")
            return
        st.markdown(answer)
        with st.expander("Retrieved curriculum chunks"):
            st.text(context or "(none)")
    st.session_state["chat"] += [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer, "context": context},
    ]


# --------------------------------------------------------------------------- main

st.set_page_config(page_title="AI Sandbox for Daml", layout="wide")
init_state()
st.title("Smart Contract Tutor for Daml")

with st.sidebar:
    render_status()
    st.divider()
    llm_config = render_llm_config()

show_flash()
tab_lesson, tab_editor, tab_tutor = st.tabs(["📘 Lesson", "💻 Editor & Test", "🤖 Tutor"])
with tab_lesson:
    render_lesson_tab()
with tab_editor:
    render_editor_tab()
with tab_tutor:
    render_tutor_tab(llm_config)
