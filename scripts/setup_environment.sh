#!/bin/bash
# AutomathAgent Environment Setup Script
set -e

echo "=== AutomathAgent Environment Setup ==="

# Step 1: Install elan (Lean version manager) if not present
if ! command -v elan &> /dev/null; then
    echo "[1/5] Installing elan (Lean version manager)..."
    curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y
    source "$HOME/.elan/env"
else
    echo "[1/5] elan already installed: $(elan --version)"
fi

# Step 2: Check Python version
echo "[2/5] Checking Python..."
PYTHON_CMD="python3"
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
fi
echo "Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Step 3: Create virtual environment
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[3/5] Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
else
    echo "[3/5] Virtual environment already exists."
fi
source "$VENV_DIR/bin/activate"

# Step 4: Install Python dependencies
echo "[4/5] Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev,viz]"

# Step 5: Build Lean project
echo "[5/5] Setting up Lean project..."
cd lean_project
if [ -f "lakefile.toml" ]; then
    echo "Fetching Mathlib cache (this may take a few minutes)..."
    lake exe cache get || echo "Warning: cache get failed, will build from source"
    echo "Building Lean project..."
    lake build
fi
cd ..

echo ""
echo "=== Setup Complete ==="
echo "Activate the environment with: source .venv/bin/activate"
echo "Run tests with: make test"
echo "Run the pipeline with: python scripts/run_pipeline.py --help"
