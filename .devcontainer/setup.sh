#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Installing latest stable Daml SDK..."
if [ ! -d "$HOME/.daml" ]; then
    # Ohne Versions-Parameter installiert das Skript automatisch das neueste stabile Release
    curl -sSL https://get.daml.com/ | sh
fi
export PATH="$HOME/.daml/bin:$PATH"

# Aktuell installierte SDK-Version auslesen und in workspace/daml.yaml synchronisieren
INSTALLED_DAML_VERSION=$(daml version | awk '/[0-9]+\.[0-9]+\.[0-9]+/ {print $1; exit}')
if [ -n "${INSTALLED_DAML_VERSION}" ] && [ -f "workspace/daml.yaml" ]; then
    sed -i "s/^sdk-version:.*/sdk-version: ${INSTALLED_DAML_VERSION}/" workspace/daml.yaml
    echo "Synchronized workspace/daml.yaml to SDK v${INSTALLED_DAML_VERSION}"
fi

echo "[2/4] Creating isolated Python virtual environment & compiling CPU dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Verhindert 'Illegal instruction (core dumped)' auf Standard-Codespace-CPUs:
pip install llama-cpp-python --no-binary llama-cpp-python --no-cache-dir

echo "[3/4] Compiling initial Daml workspace project..."
cd workspace
daml build
cd ..

echo "[4/4] Indexing curriculum into local Qdrant vector database..."
python3 src/indexer.py

echo "Setup completed successfully! Run: source .venv/bin/activate && streamlit run src/app.py"