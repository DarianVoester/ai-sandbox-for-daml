# Smart Contract Sandbox & AI Tutor for Daml (Canton)

An interactive, browser-based learning environment for Daml and Canton built for GitHub Codespaces. It combines an isolated Daml SDK workspace with a Retrieval-Augmented Generation (RAG) AI Tutor powered by Qdrant and SentenceTransformers.

## Features

- **Lesson tab:** pick a lesson from `curriculum/`, read it, and load its starter code into the editor (the previous `Main.daml` is backed up as `Main.daml.bak`).
- **Editor & Test tab:** edit `workspace/daml/Main.daml`, then **Save**, **Build** (`daml build`) or **Test** (`daml test`). Test results are shown as a table; console output and coverage report are collapsible.
- **Tutor tab:** chat with an AI tutor that is grounded in the curriculum (RAG) and optionally sees your code and the last build/test output.
- **Sidebar:** live status (Daml SDK, Qdrant index, local model), **Rebuild index** button and LLM configuration.

## Architecture

| Path | Purpose |
|---|---|
| `.devcontainer/` | Python 3.11, OpenJDK 17, Git LFS, Daml SDK **2.10.6** (pinned; Daml 3.x uses a different toolchain), private port forwarding of 8501 |
| `curriculum/*.md` | Lessons, chunked by `##` headings and embedded with `sentence-transformers/all-MiniLM-L6-v2` into a local Qdrant database (`.qdrant_db/`) |
| `curriculum/starters/*.daml` | Starter code per lesson (same file stem as the lesson) |
| `workspace/` | Daml project (`daml.yaml`, `daml/Main.daml`) |
| `src/app.py` | Streamlit UI only |
| `src/settings.py` | Paths, constants, timeouts, system prompt |
| `src/daml_runner.py` | `daml build` / `daml test` via `subprocess` (`shell=False`, timeouts 180 s / 120 s), output parsing |
| `src/rag.py` | Embeddings + one shared local Qdrant client per process, index build and retrieval |
| `src/llm.py` | LLM backends, prompt budget, cached model lists |
| `src/lessons.py` | Lesson list, starter code, backups |
| `src/indexer.py` | CLI to rebuild the index (`python src/indexer.py`) |
| `start.sh` | Reliable start script with Codespaces HTTP/HTTPS detection |
| `tests/test_app.py` | Smoke and unit tests (`unittest` + `streamlit.testing`) |

LLM backends (selectable at runtime):
- **Local zero-key inference:** CPU execution via `llama-cpp-python` (`Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF`, downloaded on first use, about 400 MB).
- **Anthropic API:** `/v1/messages` with live `/v1/models` discovery; thinking blocks are filtered out.
- **OpenAI-compatible endpoints:** `/chat/completions` with presets for OpenAI, OpenRouter, Groq, Google Gemini (OpenAI-compatible endpoint) and custom base URLs (e.g. a local Ollama server).

## Quickstart in GitHub Codespaces

1. Launch a Codespace on the `main` branch. The `postCreateCommand` (`bash .devcontainer/setup.sh`) installs Daml SDK 2.10.6, creates `.venv` with all Python dependencies (compiling `llama-cpp-python` from source only on CPUs without AVX2), builds the Daml workspace and populates the local Qdrant index.
2. Start the tutor:
   ```bash
   bash start.sh
   ```
   The script stops stale instances, starts Streamlit, verifies the forwarded URL and prints it. Use `bash start.sh --foreground` to run Streamlit in the terminal.
3. Open the printed URL (or the globe icon for port 8501 in the VS Code **Ports** tab).

Run the tests:
```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Troubleshooting: HTTP 502/504 in Codespaces

**Root cause:** the Codespaces port forwarder connects to port 8501 either via plain HTTP or via HTTPS (column *Protocol* in the VS Code **Ports** tab). If Streamlit speaks the other protocol, the browser shows HTTP 502 or 504 although the app is healthy inside the container.

`bash start.sh` handles this automatically: it starts Streamlit with plain HTTP, tests the forwarded URL with the Codespace's `GITHUB_TOKEN` and, if that fails, restarts Streamlit with a self-signed certificate (`.streamlit/certs/`, git-ignored). Force a mode with `TLS=on bash start.sh` or `TLS=off bash start.sh`.

If the page still does not load:

1. Check the app inside the container: `curl -sk https://127.0.0.1:8501/_stcore/health` (TLS mode) or `curl -s http://127.0.0.1:8501/_stcore/health` (HTTP mode) must print `ok`.
2. In the **Ports** tab make sure port `8501` is listed (add it if missing). Alternatively set its protocol back to *HTTP* (right-click → *Change Port Protocol* → HTTP) and run `TLS=off bash start.sh`.
3. Open the app via the globe icon (**Open in Browser**) or the URL printed by `start.sh`, not an old tab.
4. Check the log: `tail -50 /tmp/streamlit-daml.log`.

Only run `python src/indexer.py` while Streamlit is stopped (the local Qdrant database allows a single process); inside the app use **Rebuild index** instead.

## LLM Configuration

Configure the provider in the Streamlit sidebar at runtime:

- **Free Built-in (Local Qwen-Coder):** runs 100% locally inside the Codespace. No API key and no external LLM calls (only the one-time model download from Hugging Face). The 0.5B model is small; for higher-quality hints use a remote model.
- **Anthropic (Claude):** reads `ANTHROPIC_API_KEY` from the environment (Codespaces secret) or accepts a key in the UI, then lists the models available to your account.
- **OpenAI / Groq / OpenRouter / Gemini / Custom:** select a preset or enter a custom base URL, provide the API key (`OPENAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`) and pick a model from the fetched list.

When a remote provider is used, the curriculum context, your code and the last build/test output are sent to that provider (code and output can be switched off in the Tutor tab). See [SECURITY.md](SECURITY.md).

## Security

See [SECURITY.md](SECURITY.md) for secret handling, subprocess safety, network exposure (keep port 8501 **private**) and the dependency audit status.

## AI Assistance & No-Warranty Disclosure

This repository was developed with substantial AI assistance:

- **Google Gemini** (Large Language Model by Google LLC) generated the initial architecture, source code and documentation.
- **Anthropic Claude** (Large Language Model by Anthropic PBC), used through an AI coding agent in VS Code / GitHub Codespaces, performed the code review and bug analysis, refactored the application into modules, wrote `start.sh` (including the Codespaces HTTP/HTTPS port-forwarding fix), the test suite, the Dev Container updates, the dependency security updates and the current documentation.

All changes were reviewed and accepted by the maintainer, but the code has **not** undergone formal security auditing or exhaustive human verification. It may contain bugs, errors, or security vulnerabilities. Use this software entirely at your own risk.

## Legal & License

This project is licensed under the **Apache License 2.0**; see [LICENSE](LICENSE). Third-party components, trademarks and the AI assistance disclosure are documented in [NOTICE](NOTICE).

**Disclaimer:** This repository is provided strictly "AS IS" for educational and experimental sandbox purposes without warranty of any kind. Smart contract templates and AI-generated outputs do not constitute financial, legal, or production-grade security advice. This project is not affiliated with or endorsed by Digital Asset, Anthropic or Google.
