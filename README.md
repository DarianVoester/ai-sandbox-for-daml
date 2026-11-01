# Smart Contract Sandbox & AI Tutor for Daml (Canton)

An interactive, browser-based learning environment for Daml and Canton built for GitHub Codespaces. It combines an isolated Daml SDK workspace with a Retrieval-Augmented Generation (RAG) AI Tutor powered by Qdrant and SentenceTransformers.

## Architecture

- **Dev Container (`.devcontainer/`):** Provisions Python 3.11, OpenJDK 17, Git LFS, and the latest stable Daml SDK release (automatically synchronized with `workspace/daml.yaml`) with private port forwarding.
- **Curriculum (`curriculum/`):** Markdown lessons and exercises automatically chunked and embedded into a local Qdrant database (`sentence-transformers/all-MiniLM-L6-v2`).
- **Workspace (`workspace/`):** Standard Daml project (`workspace/daml/Main.daml`) evaluated via isolated `daml test` subprocess execution (`shell=False`, 45s timeout).
- **Tutor UI (`src/app.py`):** Streamlit interface connecting your Daml code, compiler output, and retrieved curriculum chunks to multiple LLM backends via direct HTTP REST requests and local GGUF inference:
  - **Local Zero-Key Inference:** Built-in CPU execution via `llama-cpp-python` (`Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF`).
  - **Anthropic API:** Native `/v1/messages` integration with live `/v1/models` discovery and automatic filtering of thinking blocks.
  - **OpenAI-Compatible Endpoints:** Native `/chat/completions` support with presets for OpenAI, OpenRouter, Groq, and custom base URLs (including Google Gemini via its OpenAI-compatible endpoint).

## Quickstart in GitHub Codespaces

1. Launch a Codespace on the `main` branch. The `postCreateCommand` (`bash .devcontainer/setup.sh`) automatically installs the latest stable Daml SDK, updates `workspace/daml.yaml`, compiles CPU-optimized Python dependencies (preventing `SIGILL` crashes on standard Codespace CPUs), builds the Daml workspace, and populates the local Qdrant index (`./.qdrant_db`).
2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate

3. *(Optional)* If running on a standard Codespace CPU without AVX2/AVX-512 support, recompile the local inference dependencies to prevent `SIGILL` crashes:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu --upgrade
   pip install llama-cpp-python --no-binary llama-cpp-python --no-cache-dir
   ```
4. Start the interactive tutor:
   ```bash
   streamlit run src/app.py
   ```

## LLM Configuration

You can configure your preferred LLM provider directly in the Streamlit sidebar at runtime:

- **Free Built-in (Local Qwen-Coder):** Runs 100% locally inside the Codespace via Python. Requires no API keys or external network calls.
- **Anthropic (Claude):** Reads `ANTHROPIC_API_KEY` from your environment (or Codespace Secrets) or accepts a key via the UI input field. Automatically queries `/v1/models` to populate the dropdown with active models on your account.
- **OpenAI / Groq / OpenRouter / Custom:** Select a preset or define a custom Base URL (e.g., `https://generativelanguage.googleapis.com/v1beta/openai` for Google Gemini), enter your API key, and select from the dynamically fetched model list.

## AI Assistance & No-Warranty Disclosure

Significant portions of the source code, system architecture, and documentation in this repository were generated with the assistance of **Google Gemini** (Large Language Model by Google LLC) as part of an experimental learning project. 

The code has **not** undergone formal security auditing or exhaustive human verification. It may contain bugs, errors, or security vulnerabilities. Use this software entirely at your own risk.

## Legal & License

This project is licensed under the **Apache License 2.0** – see the [LICENSE](LICENSE) file for details. Third-party trademarks, SDKs, and dependencies are documented in the [NOTICE](NOTICE) file.

**Disclaimer:** This repository is provided strictly "AS IS" for educational and experimental sandbox purposes without warranty of any kind. Smart contract templates and AI-generated outputs do not constitute financial, legal, or production-grade security advice.
