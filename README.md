# AutomathAgent

**Dual-Lean Verified Agent** for automated mathematical proof generation.

LLM generates Lean4 proofs, Lean4 verifies them, translates to natural language, a second LLM reconstructs the proof from NL, Lean4 verifies again. Supports any LLM provider.

```
Problem → LLM 1 generates proof → Lean4 verifies → translates to NL
       → LLM 2 reconstructs proof from NL → Lean4 verifies again → saves data
```

---

## Prerequisites

You need **two things** before starting:

1. **A computer** running macOS or Linux
2. **At least one LLM API key** from any of these providers:

| Provider | Get API Key |
|----------|------------|
| OpenAI (GPT-4o) | https://platform.openai.com/api-keys |
| Claude (Anthropic) | https://console.anthropic.com/settings/keys |
| DeepSeek | https://platform.deepseek.com/api_keys |
| Qwen (Alibaba) | https://dashscope.console.aliyun.com/apiKey |
| Kimi (Moonshot) | https://platform.moonshot.cn/console/api-keys |
| MiniMax | https://platform.minimaxi.com/user-center/basic-information/interface-key |
| Ollama (local) | No key needed, [install Ollama](https://ollama.com) |

---

## Installation (Step by Step)

### Step 1: Install Homebrew (macOS only, skip if already installed)

Open **Terminal** (search "Terminal" in Spotlight) and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Python and Git

```bash
# macOS
brew install python git

# Ubuntu / Debian Linux
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
```

Verify:
```bash
python3 --version   # should show 3.10+
git --version       # should show git version x.x.x
```

### Step 3: Install Lean4

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y
```

Then add it to your shell (so it works every time you open Terminal):

```bash
# macOS (zsh)
echo 'source ~/.elan/env' >> ~/.zshrc
source ~/.elan/env

# Linux (bash)
echo 'source ~/.elan/env' >> ~/.bashrc
source ~/.elan/env
```

Verify:
```bash
lean --version   # should show Lean version 4.x.x
```

### Step 4: Download the project

```bash
git clone https://github.com/your-username/AutomathAgent.git
cd AutomathAgent
```

### Step 5: Build Lean project

This downloads the math library (~3 GB). Takes 3-5 minutes.

```bash
cd lean_project
lake exe cache get
lake build
cd ..
```

### Step 6: Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic pydantic-settings structlog anthropic openai python-dotenv
```

### Step 7: Configure your API keys

```bash
cp .env.example .env
```

Now **edit the `.env` file** with any text editor:

```bash
nano .env     # or: code .env (VS Code) / open .env (macOS TextEdit)
```

Fill in your API keys. For example, if using MiniMax + Kimi:

```env
MODEL1_PROVIDER=minimax
MODEL1_API_KEY=sk-api-your-minimax-key-here
MODEL1_MODEL=MiniMax-Text-01

MODEL2_PROVIDER=kimi
MODEL2_API_KEY=sk-your-kimi-key-here
MODEL2_MODEL=kimi-k2.5
```

Save and close. You only need to do this **once**.

---

## Usage

### Quick run (uses keys from .env)

```bash
source .venv/bin/activate
python demo.py --problem "Prove that if n is even, then n^2 is even"
```

### Interactive mode

```bash
python demo.py
```

If `.env` has your keys, it auto-loads them. Otherwise it will ask you to pick models and enter keys interactively.

### More examples

```bash
# Easy
python demo.py --problem "Prove that 1 + 1 = 2"

# Medium
python demo.py --problem "Prove that for all natural numbers n, n + 0 = n"

# Hard
python demo.py --problem "Prove that for all positive integers n, n^3 - n is divisible by 6"

# Override models from command line
python demo.py --model1 deepseek --model2 openai --problem "Prove that sqrt(2) is irrational"
```

### Output

After each run, a complete data entry is saved to `data/demo_output/result_<timestamp>.json` containing:

- The original problem
- First Lean4 proof (Model 1)
- Lean4 verification result
- Natural language explanation
- Structured DSL proof steps
- Second Lean4 proof (Model 2, reconstructed from NL)
- Second verification result
- All metadata (models used, repair iterations, timing)

---

## Supported Providers

| # | Provider | Model | Notes |
|---|----------|-------|-------|
| 1 | **OpenAI** | gpt-4o | Most popular, good baseline |
| 2 | **Claude** | claude-sonnet-4-20250514 | Strong reasoning |
| 3 | **DeepSeek** | deepseek-chat | Cost-effective |
| 4 | **Qwen** | qwen-plus | Alibaba Cloud |
| 5 | **Kimi** | kimi-k2.5 | Moonshot AI |
| 6 | **MiniMax** | MiniMax-Text-01 | Fast inference |
| 7 | **Ollama** | llama3 | Free, runs locally |
| 8 | **Custom** | any | Any OpenAI-compatible API |

You can use **any combination** of two providers. For example:
- MiniMax generates proofs, Kimi verifies
- DeepSeek generates proofs, Claude verifies
- Ollama generates proofs, Ollama verifies (fully offline)

---

## Architecture

```
Math Problem
     |
     v
+--------------------+
| LLM 1: Generate    |  Generates N proof candidates
+--------+-----------+
         v
+--------------------+
| Lean4: Verify      |  Formally verifies each candidate
+--------+-----------+
         | failed?
         v
+--------------------+
| Auto-Repair Loop   |  Re-prompts with error info (max 3x)
+--------+-----------+
         v
+--------------------+
| Translate to NL    |  Verified proof -> natural language
+--------+-----------+
         v
+--------------------+
| LLM 2: Reconstruct |  NL -> new Lean4 proof (independent)
+--------+-----------+
         v
+--------------------+
| Lean4: Verify #2   |  Verifies the reconstructed proof
+--------+-----------+
         v
+--------------------+
| Save Data Entry    |  Full record saved as JSON
+--------------------+
```

---

## Batch Benchmarking

For research experiments on standard datasets:

```bash
# Edit .env with your API keys first, then:
source .venv/bin/activate

# Run on miniF2F (first 10 problems)
python scripts/run_pipeline.py \
  --dataset miniF2F \
  --data-path data/raw/minif2f_lean4.jsonl \
  --limit 10 --verbose

# Compare models
python scripts/run_benchmark.py \
  --dataset miniF2F \
  --data-path data/raw/minif2f_lean4.jsonl \
  --limit 10

# Generate charts
python scripts/visualize.py
```

Included datasets:
- **miniF2F** (488 problems) — formal math benchmarks
- **ProofNet** (349 problems) — undergraduate math
- **LeanWorkbook** (140K problems) — large-scale math problems

---

## Project Structure

```
AutomathAgent/
├── demo.py                  # <-- Start here!
├── .env.example             # <-- Copy to .env and fill in keys
├── lean_project/            # Lean4 + Mathlib (built in Step 5)
├── src/automath/            # Core library
│   ├── llm/                 #   LLM clients (universal OpenAI-compatible)
│   ├── lean/                #   Lean4 REPL verifier
│   ├── translation/         #   Lean <-> NL/DSL translation
│   ├── repair/              #   Auto-repair feedback loop
│   ├── data/                #   Data pool + dataset loaders
│   └── metrics/             #   Experiment tracking
├── scripts/                 # Batch pipeline + benchmarks
├── tests/                   # Unit tests (31 tests)
└── data/
    ├── raw/                 # Datasets
    └── demo_output/         # Your results
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `lean: command not found` | Run `source ~/.elan/env` |
| `ModuleNotFoundError: pydantic` | Run `source .venv/bin/activate && pip install pydantic pydantic-settings structlog anthropic openai python-dotenv` |
| `Authentication failed` | Check your API key in `.env` |
| `Empty response from model` | Try a different model name or check your API quota |
| `lake build` fails | Run `cd lean_project && lake exe cache get && lake build` |

---

## License

MIT
