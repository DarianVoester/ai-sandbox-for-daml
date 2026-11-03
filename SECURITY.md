# Security & Privacy Policy

## Handling of API Keys and Credentials

1. **No Hardcoded Secrets:** Never commit API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) or personal tokens directly into the source code or `.devcontainer` configuration files.
2. **Runtime Entry & GitHub Secrets:** API keys entered into the Streamlit UI sidebar live only in the memory of the running Streamlit process (widget state; the model-list cache uses the key only as a hashed cache key) and are never written to disk or logs. They are sent directly to the selected provider over HTTPS (the *Custom Base URL* preset uses whatever URL you enter, e.g. a local `http://localhost` server). For persistent keys in GitHub Codespaces, always use **GitHub Encrypted Secrets** (`Settings -> Secrets and variables -> Codespaces`), e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`.
3. **What the app sends where:** When a remote provider is selected, the tutor sends the retrieved curriculum chunks, your current Daml code and the last build/test output (both can be switched off in the Tutor tab) to that provider. The local Qwen model sends nothing outside the Codespace.
4. **`.gitignore` guards:** `.env`, `.env.*`, `.streamlit/secrets.toml`, `*.pem`, `*.key` and `.streamlit/certs/` are git-ignored. Run `git status` before every commit.

## Subprocess Execution Safety

The application executes `daml build` / `daml test` via Python's `subprocess.run` (`src/daml_runner.py`). To prevent command injection:
- Execution is strictly isolated with `shell=False` and a fixed argument list; only the commands `build` and `test` are accepted (anything else raises `ValueError`).
- Hard execution timeouts are enforced (build 180 s, test 120 s) and only one run can execute at a time.
- The editor writes only to `workspace/daml/Main.daml`.

## Network Exposure

- Port 8501 is forwarded with **private** visibility (`.devcontainer/devcontainer.json`); only the Codespace owner can reach it after GitHub authentication. **Never change it to public**: the editor allows arbitrary Daml Script execution inside the container.
- `.streamlit/config.toml` sets `enableCORS = false` and `enableXsrfProtection = false`, which is required behind the Codespaces port-forwarding proxy and acceptable only because of the private visibility above. Re-enable both if you run the app anywhere else.
- `start.sh` may create a self-signed TLS certificate in `.streamlit/certs/` (git-ignored, private key `chmod 600`). It is used only for the hop between the Codespaces proxy and Streamlit.
- `start.sh` uses the Codespace's own `GITHUB_TOKEN` solely to test the forwarded URL. The token is written to a temporary `chmod 600` header file (never passed on the command line) and deleted immediately.

> **Disclaimer / Intended Environment:** This repository is strictly designed as an isolated single-user sandbox for GitHub Codespaces or local development (`127.0.0.1`). Deploying this application on a publicly accessible server or multi-tenant network is unsupported and done entirely at the user's own risk.

## Dependency Security

Dependencies were audited with `pip-audit` on 2026-11-03 and minimum versions raised in `requirements.txt` (streamlit ≥ 1.54, sentence-transformers ≥ 5.6, transformers ≥ 5.10, pillow ≥ 13.0, filelock ≥ 4.2.1).

Known remaining issue:
- **diskcache 5.6.3 – CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v** (unsafe pickle deserialization, CVSS 4.0 medium, local attack vector). No fixed version exists yet. It is a transitive dependency of `llama-cpp-python`; this project never enables the llama.cpp disk cache, and exploitation would require write access to the cache directory inside the Codespace.

Re-run the audit regularly:
```bash
pip install pip-audit && pip-audit
```

## Reporting a Vulnerability

If you discover a security issue in this repository, please use GitHub's **private vulnerability reporting** (Security tab → *Report a vulnerability*) or contact the repository maintainer directly via GitHub. Please do not open public issues for unpatched vulnerabilities.