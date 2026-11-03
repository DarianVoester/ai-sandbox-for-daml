#!/usr/bin/env bash
set -euo pipefail

# Daml 2.x (daml assistant). Daml 3.x nutzt eine andere Toolchain und würde den Build brechen.
DAML_SDK_VERSION="2.10.6"

echo "[1/4] Installing Daml SDK ${DAML_SDK_VERSION}..."
if [ ! -x "$HOME/.daml/bin/daml" ]; then
    curl -sSL https://get.daml.com/ | sh -s "${DAML_SDK_VERSION}"
fi
export PATH="$HOME/.daml/bin:$PATH"

# workspace/daml.yaml auf die gepinnte SDK-Version setzen
if [ -f "workspace/daml.yaml" ]; then
    sed -i "s/^sdk-version:.*/sdk-version: ${DAML_SDK_VERSION}/" workspace/daml.yaml
fi

echo "[2/4] Creating isolated Python virtual environment & installing dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Nur auf CPUs ohne AVX2 aus dem Quellcode kompilieren (verhindert 'Illegal instruction'/SIGILL).
if ! grep -qw avx2 /proc/cpuinfo; then
    echo "No AVX2 detected: compiling llama-cpp-python from source..."
    pip install llama-cpp-python --no-binary llama-cpp-python --no-cache-dir
fi

echo "[3/4] Compiling initial Daml workspace project..."
cd workspace
daml build
cd ..

echo "[4/4] Indexing curriculum into local Qdrant vector database..."
python3 src/indexer.py

echo "Setup completed successfully! Run: bash start.sh"