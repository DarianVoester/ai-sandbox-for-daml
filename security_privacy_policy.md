# Security & Privacy Policy

## Handling of API Keys and Credentials

1. **No Hardcoded Secrets:** Never commit API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) or personal tokens directly into the source code or `.devcontainer` configuration files.
2. **Runtime Entry & GitHub Secrets:** API keys entered into the Streamlit UI sidebar are stored strictly in volatile session memory (`st.session_state`) for the duration of the browser session and are transmitted directly via HTTPS to the selected API provider. For persistent keys in GitHub Codespaces, always use **GitHub Encrypted Secrets** (`Settings -> Secrets and variables -> Codespaces`).

## Subprocess Execution Safety

The application executes `daml test` via Python's `subprocess.run` module. To prevent command injection vulnerabilities:
- Execution is strictly isolated with `shell=False`.
- A hard execution timeout of 45 seconds is enforced.
- Do not expose the Streamlit port publicly without authentication, as the code editor allows arbitrary Daml Script execution within the container's workspace.

## Reporting a Vulnerability

If you discover a security issue in this repository, please open an issue or contact the repository maintainer directly via GitHub.