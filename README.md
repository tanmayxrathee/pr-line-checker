<<<<<<< HEAD
# DriftCheck

> **Automated Documentation Drift Detection**
>
> *"The code moved. The docs didn't. DriftCheck notices before your users do."*

[![CI](https://github.com/<owner>/driftcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/driftcheck/actions/workflows/ci.yml)

## Overview

DriftCheck automatically detects when documentation becomes outdated due to code changes. It analyzes git diffs, extracts changed symbols (CLI flags, environment variables, config keys, function parameters, defaults, etc.), searches documentation for references to those symbols, and reports drift with precise locations and suggested fixes.

## Features

- **Tier 1 (Hard Drift)**: Exact matching for renamed/removed flags, changed defaults, removed env vars — zero false positives, no LLM required
- **Tier 2 (Soft Drift)**: Qwen3-4B local model catches prose/behavior drift
- **Verification**: Nemotron-3-Ultra-550B (NVIDIA NIM) confirms/rejects Tier 2 findings
- **Noise Control**: Multi-stage filters (drift-ignore markers, `.driftignore`, same-PR-edit skip, confidence thresholds, deduplication, severity ranking, caps)
- **Outputs**: Console, JSON, Markdown, SARIF, GitHub Check Runs, sticky PR comments with permalinks
- **Triggers**: CLI, pre-push hook, GitHub Action (fast Tier 1 on Ubuntu, LLM tier on self-hosted runner)
- **Offline First**: `--llm none` gives full Tier 1 results with no network calls

## Quick Start

```bash
# Install
pip install driftcheck

# Check drift in current branch vs main
driftcheck check --base main --head HEAD

# Install pre-push hook (runs fast Tier 1 check on push)
driftcheck hook install

# GitHub Action - add to .github/workflows/driftcheck.yml
```

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| Offline | `--llm none` | Tier 1 only, no network, <2s |
| Local | `--llm local` | Tier 1 + Qwen3-4B + self-check |
| Full | `--llm full` | Tier 1 + Qwen3-4B + Nemotron verify |

## Documentation

- [Configuration](docs/configuration.md)
- [How It Works](docs/how-it-works.md)
- [Local Model Setup](docs/local-model.md)
- [Self-Hosted Runner](docs/self-hosted-runner.md)

## Models

- **Qwen3-4B** (local, GGUF via llama.cpp) — Tier 2 judge
- **Nemotron-3-Ultra-550B** (NVIDIA NIM) — Verification

## AI Disclosure

This project was built with:
- **Coding agent**: OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM)
- **Models used in project**: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)

## License

MIT License - see LICENSE file for details.
=======
# pr-line-checker
This is a repo for a tool that tells what line of README.md just changed or broke after a pull request
>>>>>>> origin/main
