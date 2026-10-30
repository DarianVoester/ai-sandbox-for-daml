#!/usr/bin/env bash
set -euo pipefail

DAML_VERSION="2.9.4"

echo "[1/4] Installing Daml SDK v${DAML_VERSION}..."
if [ ! -d "$HOME/.daml" ]; then
    curl -sSL https://get.daml.com/ | sh -s "${DAML_VERSION}"
fi
export PATH="$HOME/.daml/bin:$PATH"

echo "[2/4] Creating isolated Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Compiling initial Daml workspace project..."
cd workspace
daml build
cd ..

echo "[4/4] Indexing curriculum into local Qdrant vector database..."
python3 src/indexer.py

echo "Setup completed successfully! Run: source .venv/bin/activate && streamlit run src/app.py"
