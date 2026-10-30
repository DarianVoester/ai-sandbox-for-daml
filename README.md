# Daml Smart Contract Sandbox & RAG Tutor

An interactive, browser-based learning environment for **Daml** and **Canton** built for **GitHub Codespaces**. It combines an isolated Daml SDK workspace with a Retrieval-Augmented Generation (RAG) AI Tutor powered by **Qdrant** and **SentenceTransformers**.

## Architecture
- **Dev Container (`.devcontainer/`):** Provisions Python 3.11, OpenJDK 17, and Daml SDK v2.9.4 with private port forwarding.
- **Curriculum (`curriculum/`):** Markdown lessons and exercises automatically chunked and embedded into a local Qdrant database (`all-MiniLM-L6-v2`).
- **Workspace (`workspace/`):** Standard Daml project evaluated via `daml test` subprocess execution (`shell=False`).
- **Tutor UI (`src/app.py`):** Streamlit interface connecting your Daml code, compiler output, and curriculum chunks to any OpenAI-compatible LLM endpoint (OpenAI, Ollama, OpenRouter).

## Quickstart in GitHub Codespaces
1. Configure your repository secrets under **Settings -> Secrets and variables -> Codespaces**:
   - `LLM_API_KEY`: Your API key (or `ollama` for custom self-hosted endpoints).
   - `LLM_BASE_URL`: Endpoint URL (default: `https://api.openai.com/v1`).
   - `LLM_MODEL`: Model identifier (e.g., `gpt-4o-mini`, `qwen2.5-coder:14b`).
2. Launch a Codespace on the `main` branch. The `postCreateCommand` automatically installs the Daml SDK, builds the workspace, and populates Qdrant.
3. Start the interactive tutor:
   ```bash
   source .venv/bin/activate
   streamlit run src/app.py
