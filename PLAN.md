# PLAN.md — DriftCheck

> **Automated Documentation Drift Detection** · Problem 05 · Hacktoberfest 2026 Hack Day
>
> *"The code moved. The docs didn't. DriftCheck notices before your users do."*

This file is the single source of truth for building DriftCheck. It is written so that **any feature can be handed to any coding agent (or a human) in isolation**: read §0–§4 once, then jump to your feature card.

---

## Table of contents

- [§0 How to use this plan (read first, every agent)](#0-how-to-use-this-plan-read-first-every-agent)
- [§1 The product in one picture](#1-the-product-in-one-picture)
- [§2 Tech stack and repo layout](#2-tech-stack-and-repo-layout)
- [§3 Contracts — shared data models (frozen after Phase 0)](#3-contracts--shared-data-models-frozen-after-phase-0)
- [§4 Hackathon compliance rules](#4-hackathon-compliance-rules)
- [§5 Phase map and dependency graph](#5-phase-map-and-dependency-graph)
- [Phase 0 — Foundation and contracts](#phase-0--foundation-and-contracts)
- [Phase 1 — Diff → Facts](#phase-1--diff--facts)
- [Phase 2 — Docs indexing and candidate search](#phase-2--docs-indexing-and-candidate-search)
- [Phase 3 — Tier 1: hard drift (no LLM)](#phase-3--tier-1-hard-drift-no-llm)
- [Phase 4 — Tier 2 (Qwen3-4B) and verification (Nemotron)](#phase-4--tier-2-qwen3-4b-and-verification-nemotron)
- [Phase 5 — Filters and noise control](#phase-5--filters-and-noise-control)
- [Phase 6 — Outputs](#phase-6--outputs)
- [Phase 7 — Triggers: CLI, pre-push hook, GitHub Action](#phase-7--triggers-cli-pre-push-hook-github-action)
- [Phase 8 — Replay, mining and evaluation](#phase-8--replay-mining-and-evaluation)
- [Phase 9 — Extras that win](#phase-9--extras-that-win)
- [Phase 10 — Examples, docs, demo, ship](#phase-10--examples-docs-demo-ship)
- [Appendix A — Prompts](#appendix-a--prompts)
- [Appendix B — Config reference](#appendix-b--config-reference)
- [Appendix C — Glossary](#appendix-c--glossary)

---

## §0 How to use this plan (read first, every agent)

### 0.1 Structure

```
Phase  (sequential, follows the pipeline flow)
 └── Part   (a coherent sub-area, usually one Python sub-package)
      └── Feature  (one PR, one branch, one owner, 30–180 min of work)
```

Every feature card looks like this:

| Field | Meaning |
|---|---|
| **ID** | `P<phase>.<part>.<feature>` e.g. `P1.2.3`. Used in the branch name and PR title. |
| **Priority** | 🟥 **MVP** (demo breaks without it) · 🟧 **Core** (scores points) · 🟨 **Stretch** |
| **Owner hint** | 🧑 **Human** (judgement/tuning/secrets) · 🤖 **Agent** (well-specified, testable) · 🧑🤖 **Pair** |
| **Depends on** | Feature IDs that must be merged first. "Contracts" = Phase 0 done. |
| **Files** | The only files this feature should create/modify. Touching others = scope creep. |
| **Build** | What to implement. |
| **Done when** | Acceptance criteria. All must hold. |
| **Tests** | Tests that must exist and pass in CI. |

### 0.2 The agent brief (paste this at the top of every agent task)

```
You are implementing feature <ID> of DriftCheck.
1. Read PLAN.md §0–§4 and the feature card <ID>. Nothing else is required context.
2. Only modify the files listed in the card. Never modify HACKATHON.md.
3. Never change driftcheck/models.py or any contract in §3. If you believe a contract
   must change, stop and write the proposal in the PR description instead.
4. Branch: feat/<ID>-<short-slug>. One PR per feature. PR title: "<ID>: <title>".
5. Every commit message ends with:
     Coding agent: <your agent name and model>
     Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)
6. Write the tests listed in the card. Run `make check` (ruff + mypy + pytest) before pushing.
7. No network calls in tests. LLMs are always faked via tests/fakes/fake_llm.py.
8. Fill every section of .github/pull_request_template.md.
```

### 0.3 Golden rules

1. **Determinism first.** Anything that can be decided by code is decided by code. LLMs only judge prose.
2. **IDs, not text.** The LLM never returns file paths or line numbers — it returns sentence IDs (`S17`) and fact IDs (`F3`). Code maps them back.
3. **Quote or it didn't happen.** Every LLM finding must include a `doc_quote` that is a literal substring of the sentence and a `code_quote` that is a literal substring of the diff. Otherwise it is dropped (anti-hallucination guard).
4. **Silence is a feature.** A missed warning costs a little. Ten false warnings cost the tool its credibility. When in doubt, don't post.
5. **Offline must always work.** `--llm none` gives full Tier 1 results, no model, no network.
6. **CI never depends on the laptop.** Tests run on `ubuntu-latest` with faked LLMs. The self-hosted Qwen runner is only for the live drift check, never for the required test job.

---

## §1 The product in one picture

```
                ┌────────────────────────────────────────────────────────────┐
  TRIGGERS      │  driftcheck CLI      pre-push git hook      GitHub Action   │
                └───────────────┬────────────────────────────────────────────┘
                                │  base..head  (or a .diff file)
                                ▼
 ① DIFF → FACTS   unidiff + Python ast + regex/tree-sitter fallback
                  ── argparse/click flags, env vars, config keys, defaults,
                     function params, removed/renamed symbols, enum choices
                  ── rename pairing  ── "needs a doc update?" gate
                                │  list[ChangeFact]  {F1: --timeout default 30→60 @ cli.py:42}
                                ▼
 ② DOC INDEX      md / mdx / rst / txt → sentences with IDs [S1..Sn]
                  (prose, table rows, list items, headings, code-block lines)
                                │
 ③ CANDIDATES     exact match (old value, symbol, aliases) + BM25 + link graph
                                │  list[Candidate]  (F1 ↔ S17, S42, S88)
                ┌───────────────┴────────────────┐
                ▼                                ▼
 ④ TIER 1 (hard, no LLM)              ⑤ TIER 2 (soft, Qwen3-4B local)
    old flag still documented            prose / behaviour claims
    old default still documented         JSON: verdict, confidence,
    removed env var/key/function            doc_quote, code_quote, fix
    → certain, severity high/critical              │
                │                                  ▼
                │                    ⑥ VERIFY (Nemotron-3-Ultra-550B, NIM)
                │                       confirm / reject / revise
                │                       (offline fallback: Qwen self-consistency)
                └───────────────┬──────────────────┘
                                ▼
 ⑦ FILTERS        gate → drift-ignore markers → .driftignore → same-PR-edit skip
                  → confidence threshold → dedupe → severity rank → comment cap
                                │  list[Finding]
                                ▼
 ⑧ OUTPUTS        console · JSON · SARIF · Markdown · GitHub Check Run
                  · sticky PR summary comment (permalinks doc line ↔ code line)
                  · fix.patch (auto-fix)
                                │
 ⑨ REPLAY / EVAL  driftcheck mine → dataset.jsonl → driftcheck eval
                  → precision / recall / F1, per-tier ablation table
```

### 1.1 A drift, end to end (the story we demo)

A PR changes `src/app/cli.py`:

```diff
-    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
+    parser.add_argument("--request-timeout", type=int, default=60, help="Request timeout in seconds")
```

`docs/usage.md` still says:

```markdown
Use `--timeout` to control how long DriftCheck waits. It defaults to 30 seconds,
which is plenty for most servers.
```

and `docs/troubleshooting.md` says:

```markdown
If large uploads fail, the client probably gave up too early — raise the wait limit.
```

What happens:

1. **Facts:** `F1 = {symbol: "--timeout", kind: cli_flag, change: renamed, old: "--timeout", new: "--request-timeout"}`, `F2 = {symbol: "--request-timeout", kind: cli_flag, change: default_changed, old: "30", new: "60"}`. Rename pairing linked them (same `help=`, same `type=`).
2. **Candidates:** `S17` (usage.md:12) matches `--timeout` exactly. `S18` matches "30 seconds". `S203` (troubleshooting.md:40) only matches via BM25 ("wait", "timeout" synonyms in help text).
3. **Tier 1:** `S17` → *critical*: removed flag still documented, fix = `--request-timeout`. `S18` → *high*: wrong default 30 → 60.
4. **Tier 2:** `S203` → Qwen says `still_accurate` (generic advice). Dropped. No noise.
5. **Output:** a Check Run with 2 annotations, one sticky comment:

````markdown
### 🧭 DriftCheck — 2 docs drifted from this PR

| Sev | Doc | Says | Code now | Caused by |
|---|---|---|---|---|
| 🔴 critical | [docs/usage.md#L12](…) | `--timeout` | `--request-timeout` | [cli.py#L42](…) |
| 🟠 high | [docs/usage.md#L12-L13](…) | defaults to 30 seconds | `default=60` | [cli.py#L42](…) |

<details><summary>Suggested fix (1 file) — download fix.patch from the run artifacts</summary>

```diff
-Use `--timeout` to control how long DriftCheck waits. It defaults to 30 seconds,
+Use `--request-timeout` to control how long DriftCheck waits. It defaults to 60 seconds,
```
</details>

Mode: full (Tier 1 + Qwen3-4B + Nemotron verify) · 37 sentences checked · 1 dismissed by verifier
````

---

## §2 Tech stack and repo layout

### 2.1 Stack

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | `ast` is built in; fast to build. |
| Packaging | `pyproject.toml` (hatchling), entry point `driftcheck` | `pip install -e .` in CI. |
| CLI | `typer` + `rich` | Nice help, coloured output. |
| Diff parsing | `unidiff` | Robust hunks and line numbers. |
| Git | `subprocess` calls to `git` (thin wrapper) | No heavy GitPython dependency. |
| Markdown | `markdown-it-py` (+ `mdit-py-plugins` for tables/front-matter) | Gives token line maps. |
| reStructuredText | `docutils` | Node line numbers. |
| Sentence split | Custom splitter (regex + abbreviations list) | Must keep code spans intact. |
| Search | `rank-bm25` | Tiny, pure Python. |
| Config files | `tomllib`, `pyyaml`, `json` | Defaults in config files. |
| Non-Python code | regex rules; optional `tree-sitter-language-pack` | Fallback for JS/TS/Go/Rust. |
| Models | `pydantic` v2 | Validation of contracts and LLM JSON. |
| LLM client | `openai` SDK (OpenAI-compatible) | Same client for llama.cpp server and NVIDIA NIM. |
| Local model | **Qwen3-4B** GGUF (Q4_K_M) via **llama.cpp `llama-server`** (Ollama as alternative) | JSON-schema constrained output. |
| Verifier | **Nemotron-3-Ultra-550B** via **NVIDIA NIM API** (`https://integrate.api.nvidia.com/v1`) | Strong second opinion, free tier. |
| Cache | `sqlite3` | LLM results keyed by hash. |
| HTTP (GitHub) | `httpx` | Check Runs and comments REST API. |
| Quality | `ruff`, `mypy`, `pytest`, `pytest-cov` | `make check`. |

### 2.2 Repo layout (target)

```
driftcheck/
├── HACKATHON.md                      # ⚠️ first commit, NEVER modified
├── PLAN.md
├── README.md
├── pyproject.toml
├── Makefile                          # make check / test / lint / examples / eval
├── action.yml                        # composite GitHub Action
├── .driftcheck.toml                  # dogfooding config for this repo
├── .driftignore                      # dismissal memory
├── .github/
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml                    # REQUIRED: install + test, ubuntu-latest
│       ├── driftcheck.yml            # fast Tier 1 (ubuntu) + LLM tier (self-hosted laptop)
│       └── eval.yml                  # manual dispatch, self-hosted
├── driftcheck/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                        # typer app, all subcommands
│   ├── config.py                     # load .driftcheck.toml + env + flags
│   ├── models.py                     # §3 CONTRACTS (frozen)
│   ├── pipeline.py                   # orchestrates ①→⑧
│   ├── gitutil.py                    # git wrapper
│   ├── extract/
│   │   ├── __init__.py               # registry + run_extractors()
│   │   ├── base.py                   # Extractor protocol
│   │   ├── diffparse.py              # unidiff → FileChange/hunks
│   │   ├── py_symbols.py             # functions, classes, params, constants
│   │   ├── py_cli.py                 # argparse / click / typer flags
│   │   ├── py_env.py                 # os.getenv / os.environ / pydantic-settings
│   │   ├── py_models.py              # dataclass / pydantic / attrs defaults
│   │   ├── config_files.py           # yaml / toml / json / .env.example defaults
│   │   ├── generic_regex.py          # JS/TS/Go/Rust/shell fallback
│   │   ├── rename.py                 # pair removed+added → renamed
│   │   └── gate.py                   # "needs a doc update?"
│   ├── docs/
│   │   ├── __init__.py
│   │   ├── discover.py               # which files are docs
│   │   ├── markdown.py               # md/mdx → blocks
│   │   ├── rst.py                    # rst → blocks
│   │   ├── plaintext.py              # txt / README without markup
│   │   ├── splitter.py               # blocks → DocSentence
│   │   └── index.py                  # DocIndex (sentences + token maps)
│   ├── search/
│   │   ├── __init__.py               # find_candidates()
│   │   ├── exact.py
│   │   ├── bm25.py
│   │   ├── aliases.py                # --foo-bar ↔ foo_bar ↔ FOO_BAR ↔ fooBar
│   │   └── links.py                  # indirect links (call graph, docstrings)
│   ├── tier1/
│   │   ├── __init__.py               # run_tier1()
│   │   ├── values.py                 # value normalisation (30, 30s, "30 seconds")
│   │   └── rules.py                  # R1..R8
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                 # LLMClient protocol + OpenAI-compatible impl
│   │   ├── qwen.py                   # Tier 2 judge
│   │   ├── nemotron.py               # verifier
│   │   ├── selfcheck.py              # offline verifier (Qwen x2)
│   │   ├── schemas.py                # JSON schemas for constrained decoding
│   │   ├── guards.py                 # quote checks, ID checks
│   │   ├── cache.py                  # sqlite cache
│   │   └── prompts/
│   │       ├── tier2_system.md
│   │       ├── tier2_user.md
│   │       ├── verify_system.md
│   │       └── verify_user.md
│   ├── filters/
│   │   ├── __init__.py               # apply_filters() in fixed order
│   │   ├── markers.py                # <!-- drift-ignore -->
│   │   ├── driftignore.py            # .driftignore load/save
│   │   ├── same_pr.py                # PR already edits that sentence
│   │   ├── threshold.py
│   │   ├── dedupe.py
│   │   ├── severity.py
│   │   └── cap.py
│   ├── output/
│   │   ├── console.py
│   │   ├── json_out.py
│   │   ├── sarif.py
│   │   ├── markdown.py               # summary comment body
│   │   ├── patch.py                  # fix.patch
│   │   └── links.py                  # permalink builders
│   ├── github/
│   │   ├── context.py                # read GITHUB_EVENT_PATH etc.
│   │   ├── api.py                    # httpx client
│   │   ├── checks.py                 # Check Run + annotations
│   │   └── comment.py                # sticky summary comment
│   ├── hooks/
│   │   ├── pre_push.py
│   │   └── install.py
│   └── eval/
│       ├── mine.py
│       ├── replay.py
│       ├── match.py                  # finding ↔ label matching
│       ├── metrics.py
│       └── report.py
├── tests/
│   ├── conftest.py                   # tmp git repo builder fixture
│   ├── fakes/fake_llm.py
│   ├── fixtures/                     # diffs, docs, mini repos
│   └── test_*.py
├── eval/
│   ├── repos.txt                     # repos we mine
│   ├── datasets/*.jsonl
│   └── results/*.md
└── examples/
    ├── 01-renamed-flag/
    ├── 02-changed-default/
    ├── 03-removed-env-var/
    ├── 04-prose-behaviour/
    └── 05-no-drift-refactor/
```

---

## §3 Contracts — shared data models (frozen after Phase 0)

These live in `driftcheck/models.py`. **They are the API between phases.** Agents code against them; nobody changes them without a "contract change" PR approved by the human lead.

```python
# driftcheck/models.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

class SymbolKind(str, Enum):
    CLI_FLAG = "cli_flag"          # --timeout, -t, subcommand names
    ENV_VAR = "env_var"            # APP_TIMEOUT
    CONFIG_KEY = "config_key"      # server.timeout (dotted path)
    FUNCTION = "function"          # module.func
    CLASS = "class"
    PARAMETER = "parameter"        # func(param)
    CONSTANT = "constant"          # MAX_RETRIES = 3
    FIELD = "field"                # dataclass / pydantic field
    CHOICE = "choice"              # enum / choices=[...] value
    ENDPOINT = "endpoint"          # "/api/v1/users" (regex fallback)

class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    RENAMED = "renamed"
    DEFAULT_CHANGED = "default_changed"
    TYPE_CHANGED = "type_changed"
    CHOICES_CHANGED = "choices_changed"
    SIGNATURE_CHANGED = "signature_changed"
    BEHAVIOR_CHANGED = "behavior_changed"   # body changed, public symbol (Tier 2 only)

class CodeLocation(BaseModel):
    path: str
    line_old: int | None = None    # line in base version (for removed lines)
    line_new: int | None = None    # line in head version
    commit: str | None = None

class ChangeFact(BaseModel):
    id: str                         # "F1", "F2"… assigned by pipeline in order
    symbol: str                     # canonical name, e.g. "--request-timeout"
    kind: SymbolKind
    change_type: ChangeType
    old: str | None = None          # old name/value/signature (string form)
    new: str | None = None
    aliases: list[str] = []         # other spellings that may appear in docs
    location: CodeLocation
    code_snippet: str = ""          # the relevant diff lines (± and context), ≤ 20 lines
    help_text: str | None = None    # argparse help=, docstring first line, field description
    extractor: str                  # which extractor produced it, e.g. "py_cli"
    public: bool = True             # gate result: does it plausibly affect users?
    related: list[str] = []         # other fact IDs (e.g. rename ↔ default change)

class BlockType(str, Enum):
    PROSE = "prose"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    HEADING = "heading"
    CODE = "code"                   # one line inside a fenced/literal block
    ADMONITION = "admonition"

class DocSentence(BaseModel):
    id: str                         # "S1".. unique per run
    path: str
    line_start: int
    line_end: int
    text: str                       # raw text as in the file (markup kept)
    plain: str                      # markup stripped, for BM25
    block: BlockType
    heading_path: list[str] = []    # ["Usage", "Options"]
    code_spans: list[str] = []      # contents of `inline code`
    ignored: bool = False           # inside a drift-ignore region

class MatchType(str, Enum):
    EXACT_OLD = "exact_old"         # sentence contains fact.old
    EXACT_SYMBOL = "exact_symbol"   # contains fact.symbol or an alias
    BM25 = "bm25"
    LINK = "link"                   # indirect (call graph, docstring, same section)

class Candidate(BaseModel):
    fact_id: str
    sentence_id: str
    match: MatchType
    score: float                    # 0..1 normalised
    matched_token: str | None = None

class Tier(str, Enum):
    HARD = "tier1"
    SOFT = "tier2"

class Severity(str, Enum):
    CRITICAL = "critical"           # docs tell users to run something that no longer exists
    HIGH = "high"                   # wrong default / renamed param
    MEDIUM = "medium"               # type/choices/signature mismatch
    LOW = "low"                     # prose/behaviour mismatch
    INFO = "info"                   # doc gap (new public thing undocumented)

class Verification(BaseModel):
    by: str                         # "nemotron-3-ultra", "qwen-selfcheck", "none"
    decision: str                   # "confirm" | "reject" | "revise" | "skipped"
    confidence: float
    reason: str = ""

class Finding(BaseModel):
    id: str                         # "D1".. (D for drift)
    fingerprint: str                # stable hash, see §3.1
    tier: Tier
    rule: str                       # "R1_removed_flag" … or "T2_prose"
    severity: Severity
    confidence: float               # 1.0 for Tier 1
    fact: ChangeFact
    sentence: DocSentence
    doc_quote: str                  # literal substring of sentence.text
    code_quote: str                 # literal substring of fact.code_snippet
    message: str                    # one-line human explanation
    suggested_text: str | None = None   # full corrected sentence
    verification: Verification | None = None
    suppressed_by: str | None = None    # filter name if filtered (kept for debug/eval)

class RunMode(str, Enum):
    NONE = "none"                   # Tier 1 only
    LOCAL = "local"                 # Tier 1 + Qwen + Qwen self-check
    FULL = "full"                   # Tier 1 + Qwen + Nemotron verify

class RunReport(BaseModel):
    tool_version: str
    mode: RunMode
    base: str
    head: str
    facts: list[ChangeFact]
    sentences_checked: int
    candidates: int
    findings: list[Finding]         # after filters (suppressed_by is None)
    suppressed: list[Finding]       # for --debug and eval
    timings_ms: dict[str, int]
    models: dict[str, str]          # {"tier2": "qwen3-4b-q4_k_m", "verify": "nemotron-3-ultra-550b"}
```

### 3.1 Fingerprint (stable across line moves)

```python
fingerprint = sha1(f"{rule}|{fact.kind}|{fact.symbol}|{fact.old}|{normalize(sentence.plain)}").hexdigest()[:16]
# normalize = lowercase, collapse whitespace, strip punctuation at ends
```

### 3.2 Stage function signatures (also frozen)

```python
# extract/__init__.py
def extract_facts(diff_text: str, repo: RepoView, cfg: Config) -> list[ChangeFact]: ...
# docs/index.py
def build_index(repo: RepoView, cfg: Config) -> DocIndex: ...           # DocIndex.sentences: dict[str, DocSentence]
# search/__init__.py
def find_candidates(facts, index, cfg) -> list[Candidate]: ...
# tier1/__init__.py
def run_tier1(facts, index, candidates, cfg) -> tuple[list[Finding], list[Candidate]]: ...  # (findings, leftover candidates)
# llm/qwen.py
def run_tier2(facts, index, candidates, client, cfg) -> list[Finding]: ...
# llm/nemotron.py  /  llm/selfcheck.py
def verify(findings, client, cfg) -> list[Finding]: ...                  # sets .verification
# filters/__init__.py
def apply_filters(findings, ctx: FilterContext, cfg) -> tuple[list[Finding], list[Finding]]: ...  # (kept, suppressed)
# pipeline.py
def run(base: str, head: str, cfg: Config, *, diff_text: str | None = None) -> RunReport: ...
```

`RepoView` (in `gitutil.py`) abstracts "read file X at revision R" so replay and eval work on any commit without checking out:

```python
class RepoView:
    def __init__(self, root: Path, rev: str): ...
    def read(self, path: str) -> str | None: ...       # git show rev:path
    def list_files(self) -> list[str]: ...             # git ls-tree -r --name-only rev
```

---

## §4 Hackathon compliance rules

These are **non-negotiable**. A feature isn't done if it breaks one.

1. **`HACKATHON.md` is the first commit and must never be modified.** CI enforces it (P0.1.4).
2. **Every change goes on a new branch and through a PR.** No direct pushes to `main` (turn on branch protection: require PR + require `ci / test` to pass).
3. **CI runs tests on every PR. Merge only when CI is green.** Solo? Merge your own PR after green.
4. **Every commit message and every PR names the coding agent and the project's models.**

   ```
   P1.2.1: Add argparse flag extractor

   Coding agent: OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM)
   Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)
   ```

   If a feature is built with a different agent (Claude Code, Cursor, Copilot…), change **only** the `Coding agent:` line. The `Models used in project:` line never changes.
5. **`.github/pull_request_template.md`** exists and asks for the models. Use the **official template text from the Problem Statements doc**. Until it's pasted in, use the fallback in P0.1.3.
6. **Real tests** for real code. No `assert True`.
7. **CI workflow installs the project and runs the tests, and must pass on the last commit.**
8. **`examples/`** contains real inputs and the **real output the tool produced** (generated by a script, never hand-written).

---

## §5 Phase map and dependency graph

| Phase | Name | Flow step | Can start when | Parallel with |
|---|---|---|---|---|
| 0 | Foundation and contracts | — | now | nothing (do it first, fast) |
| 1 | Diff → Facts | ② | P0 merged | **P2** |
| 2 | Docs index + candidates | ③ | P0 merged | **P1** |
| 3 | Tier 1 hard drift | ④ | P1.1, P1.2, P2.1–P2.3 merged | P4 (with fakes) |
| 4 | Tier 2 + verify | ⑤⑥ | P0 merged (uses fakes), integrates after P2 | P3 |
| 5 | Filters | ⑦ | P0 merged (works on `Finding` contract) | P3, P4 |
| 6 | Outputs | ⑧ | P0 merged (works on `RunReport` contract) | P3–P5 |
| 7 | Triggers | ① | P3 + P6.1 merged (needs a working pipeline) | P8 |
| 8 | Replay + eval | ⑨ | P3 merged | P7, P9 |
| 9 | Extras | — | P5, P6 merged | P8 |
| 10 | Examples, docs, demo | — | P7 merged | — |

```
P0 ──┬── P1 ──┐
     ├── P2 ──┼── P3 ──┬── P7 ──┐
     ├── P4 ──┘(integr)│        ├── P10
     ├── P5 ───────────┤        │
     └── P6 ───────────┴── P8 ──┤
                          P9 ───┘
```

**Cross-phase links (intentional):** `P4.3.3` tuning needs the eval harness (`P8.3.1`); `P6.2.4` patch artifact needs `P9.1.1`; `P7.1.2` `ignore` needs `P9.3.1`. Schedule those three after their dependency merges — every other feature only depends on earlier phases.

**Critical path to a demo (all 🟥 MVP):** P0 → P1.1–P1.2 → P2.1–P2.3 → P3.1–P3.2 → P5.1 → P6.1, P6.4 → P7.1, P7.3 → P10.1.
Everything else adds score on top of a demo that already works.

### Suggested split: you vs agents

| You (🧑) personally | Agents (🤖) |
|---|---|
| P0.2 contracts, P0.3 pipeline skeleton | Extractors (P1.2–P1.6), parsers (P2.1–P2.2) |
| P3.2 Tier 1 rule precision tuning | BM25, aliases, splitter, value normaliser |
| P4.3 prompts, P4.6 thresholds | LLM client, cache, guards, schemas |
| P7.4 self-hosted runner on your mate's laptop | Output formats, SARIF, patch, GitHub API |
| P8.4 eval runs and threshold tuning | Mining, replay, metrics |
| P10.3 demo script and pitch | Examples generator, README sections |

---

# Phase 0 — Foundation and contracts

> **Goal:** a repo where any agent can start any later feature without stepping on anyone. After Phase 0 the contracts are frozen, CI is green, and `driftcheck --version` works.
>
> **Exit criteria:** `pip install -e .[dev] && make check` passes on a clean clone; `ci.yml` green on `main`; `models.py` merged; pipeline skeleton runs end to end with stubbed stages and prints an empty report.

## Part 0.1 — Repo scaffolding and CI

### P0.1.1 — Project skeleton and packaging
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** —
- **Files:** `pyproject.toml`, `driftcheck/__init__.py`, `driftcheck/__main__.py`, `driftcheck/cli.py`, `Makefile`, `.gitignore`, `README.md` (stub)
- **Build:**
  - `pyproject.toml` with hatchling, name `driftcheck`, `requires-python = ">=3.11"`, script `driftcheck = "driftcheck.cli:app"`.
  - Runtime deps: `typer`, `rich`, `unidiff`, `markdown-it-py`, `mdit-py-plugins`, `docutils`, `rank-bm25`, `pyyaml`, `pydantic>=2`, `openai>=1`, `httpx`.
  - Extras: `dev = [pytest, pytest-cov, ruff, mypy, types-PyYAML]`, `treesitter = [tree-sitter-language-pack]`.
  - `cli.py`: Typer app with `--version` and placeholder subcommands `check`, `replay`, `mine`, `eval`, `hook`, `ignore`, `github`, `doctor` that print "not implemented yet" and exit 2.
  - `Makefile`: `lint` (ruff check + ruff format --check), `type` (mypy driftcheck), `test` (pytest -q --cov=driftcheck), `check` (all three), `examples`, `eval`.
- **Done when:** `pip install -e .[dev]` works; `driftcheck --version` prints the version; `make check` passes.
- **Tests:** `tests/test_cli_smoke.py` — invokes `--version` and `--help` via `typer.testing.CliRunner`.

### P0.1.2 — CI workflow (required check)
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.1.1
- **Files:** `.github/workflows/ci.yml`
- **Build:**
  ```yaml
  name: ci
  on:
    pull_request:
    push:
      branches: [main]
  permissions:
    contents: read
  jobs:
    test:
      runs-on: ubuntu-latest
      strategy:
        matrix:
          python: ["3.11", "3.12"]
      steps:
        - uses: actions/checkout@v4
          with: { fetch-depth: 0 }        # history needed for replay tests + HACKATHON.md guard
        - uses: actions/setup-python@v5
          with: { python-version: "${{ matrix.python }}", cache: pip }
        - run: pip install -e .[dev]
        - run: make check
        - name: HACKATHON.md untouched
          run: python scripts/check_hackathon_md.py
  ```
  (The job id `test` + workflow `ci` make the required status check `ci / test`.)
- **Done when:** workflow green on the PR that adds it. Branch protection on `main` requires it.
- **Tests:** the workflow itself.

### P0.1.3 — PR template and commit convention
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** —
- **Files:** `.github/pull_request_template.md`, `CONTRIBUTING.md`
- **Build:** paste the **official template from the Problem Statements doc**. If not at hand, use this fallback and replace later:
  ```markdown
  ## What does this PR do?
  <!-- one or two sentences; include the PLAN.md feature ID, e.g. P1.2.1 -->

  ## How was it tested?
  <!-- tests added/changed, commands run -->

  ## AI disclosure (required)
  - **Coding agent used:** <!-- e.g. OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM), Claude Code, Cursor -->
  - **Models used in the project:** Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)

  ## Checklist
  - [ ] CI is green
  - [ ] HACKATHON.md not modified
  - [ ] Commit messages include "Coding agent:" and "Models used in project:"
  ```
  `CONTRIBUTING.md` restates §4 rules, the branch naming `feat/<ID>-<slug>`, and the commit footer.
- **Done when:** opening a PR shows the template.
- **Tests:** —

### P0.1.4 — Guard scripts
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P0.1.1
- **Files:** `scripts/check_hackathon_md.py`, `scripts/check_commit_trailers.py`, `tests/test_guards.py`
- **Build:**
  - `check_hackathon_md.py`: finds the root commit (`git rev-list --max-parents=0 HEAD`), checks `HACKATHON.md` blob hash at root equals at `HEAD`. Exit 1 with a loud message otherwise.
  - `check_commit_trailers.py`: for commits in `origin/main..HEAD` (PR range), checks each message contains `Coding agent:` and `Models used in project:`. Add it as a CI step on `pull_request` only.
- **Done when:** both scripts run in CI; a commit without trailers fails the PR.
- **Tests:** functions tested on a tmp git repo (fixture from P0.4.1).

## Part 0.2 — Contracts

### P0.2.1 — `models.py` (the contracts)
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P0.1.1
- **Files:** `driftcheck/models.py`, `tests/test_models.py`
- **Build:** exactly §3. Plus helpers: `Finding.compute_fingerprint()` (§3.1), `RunReport.to_json()`, `RunReport.from_json()`.
- **Done when:** models import; JSON round-trip works; fingerprint stable for same inputs, different when sentence text changes.
- **Tests:** round-trip; fingerprint stability; enum values serialise as strings.

### P0.2.2 — Config loader
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.2.1
- **Files:** `driftcheck/config.py`, `tests/test_config.py`, `.driftcheck.toml`
- **Build:** a pydantic `Config` model with every key in [Appendix B](#appendix-b--config-reference). Precedence: **CLI flags > env vars (`DRIFTCHECK_*`) > `.driftcheck.toml` > defaults**. `load_config(repo_root, overrides: dict) -> Config`.
- **Done when:** missing file → defaults; env overrides file; flags override env.
- **Tests:** precedence matrix; invalid values produce a clear error.

## Part 0.3 — Pipeline skeleton

### P0.3.1 — `gitutil.py` and `RepoView`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.1.1
- **Files:** `driftcheck/gitutil.py`, `tests/test_gitutil.py`
- **Build:** `run_git(args, cwd) -> str`; `merge_base(a, b)`; `diff(base, head, paths=None, unified=3) -> str` (use `--no-color --find-renames`); `changed_files(base, head)`; `RepoView` (§3.2); `blob_permalink_parts()` helper returning `(owner, repo)` from `git remote get-url origin`.
- **Done when:** works on a tmp repo; `RepoView.read` returns `None` for missing files.
- **Tests:** tmp repo with 2 commits; diff contains the change; read at both revs.

### P0.3.2 — `pipeline.py` with stubbed stages
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P0.2.1, P0.2.2, P0.3.1
- **Files:** `driftcheck/pipeline.py`, stub `__init__.py` in every sub-package with the §3.2 signatures returning empty lists, `tests/test_pipeline_skeleton.py`
- **Build:** `run()` calls each stage in order, records `timings_ms` per stage, assigns `F#`/`S#`/`D#` IDs, returns `RunReport`. Mode logic: `none` skips LLM stages; `local` uses `selfcheck.verify`; `full` uses `nemotron.verify` and falls back to selfcheck on connection/auth errors (recording `verification.by`).
- **Done when:** `driftcheck check --base HEAD~1 --head HEAD --llm none` (wired minimally in cli) prints an empty report without crashing.
- **Tests:** skeleton returns a valid `RunReport`; stages called in order (monkeypatched spies).

## Part 0.4 — Test infrastructure

### P0.4.1 — Tmp git repo builder fixture
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.1.1
- **Files:** `tests/conftest.py`, `tests/repo_builder.py`
- **Build:** `make_repo(tmp_path)` returns a builder: `.write(path, text)`, `.commit(msg) -> sha`, `.root`. Sets `user.name/email` locally. Used by every integration test.
- **Done when:** other tests can build a 3-commit repo in < 10 lines.
- **Tests:** builder self-test.

### P0.4.2 — Fake LLM
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.2.1
- **Files:** `tests/fakes/fake_llm.py`
- **Build:** `FakeLLM(responses: dict[str, dict] | Callable)` implementing the `LLMClient` protocol (P4.1.1): matches on a substring of the prompt or a callable; records every call; can simulate timeouts and malformed JSON.
- **Done when:** importable from tests; used by Phase 4 tests.
- **Tests:** self-test.

### P0.4.3 — Fixture corpus
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** —
- **Files:** `tests/fixtures/diffs/*.diff`, `tests/fixtures/docs/*.md|rst`, `tests/fixtures/README.md`
- **Build:** at least 12 hand-made diff + doc pairs covering: renamed flag, removed flag, changed default (int, bool, string, duration), renamed env var, removed config key, renamed function param, removed function, choices changed, prose behaviour change, pure refactor (no drift), private symbol change (no drift), PR that already fixes docs (no drift). Each has an `expected.json` listing expected `(rule, doc path, line)`.
- **Done when:** README explains each case.
- **Tests:** used by Phases 1–5 golden tests.

---

# Phase 1 — Diff → Facts

> **Goal:** turn a unified diff into a precise list of `ChangeFact`s. Pure, deterministic, fast. This phase decides the ceiling of the whole tool: a fact that's never extracted can never be flagged.
>
> **Exit criteria:** on the fixture corpus, the extractors produce every expected fact (recall 100% on fixtures) with zero facts on the "no drift" fixtures after the gate.

**Extractor protocol** (`extract/base.py`, part of P1.1.1):

```python
class Extractor(Protocol):
    name: str
    def applies_to(self, path: str) -> bool: ...
    def extract(self, fc: FileChange, old_src: str | None, new_src: str | None) -> list[ChangeFact]: ...
```

Strategy for Python extractors: **parse both full versions** of the file (`old_src` from base, `new_src` from head) with `ast`, build a symbol table for each, **diff the symbol tables**, and keep only differences whose line ranges intersect the diff hunks. This is far more robust than parsing diff lines.

## Part 1.1 — Diff plumbing

### P1.1.1 — Diff parser and extractor registry
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `extract/base.py`, `extract/diffparse.py`, `extract/__init__.py`, `tests/test_diffparse.py`
- **Build:**
  - `FileChange` dataclass: `old_path, new_path, status (added/removed/modified/renamed), hunks: list[Hunk]`, each `Hunk` with `old_start, old_len, new_start, new_len, lines: list[(tag, old_no, new_no, text)]`.
  - `parse_diff(text) -> list[FileChange]` using `unidiff`.
  - `extract_facts()` (§3.2): for each FileChange, fetch old/new source via `RepoView`, run every extractor whose `applies_to` matches, then `rename.pair()`, then `gate.apply()`, then de-duplicate identical facts, then assign `F#` IDs in file/line order.
  - Classify files: `is_doc(path)` (delegates to `docs/discover.py` rules), `is_test(path)` (`tests/`, `test_*.py`, `*_test.go`, `*.spec.ts`…). Doc and test files are skipped by code extractors.
- **Done when:** fixture diffs parse with correct line numbers; registry runs extractors.
- **Tests:** added/removed/renamed file diffs; line numbers on both sides; binary files ignored.

## Part 1.2 — Python extractors

### P1.2.1 — CLI flags: argparse / click / typer
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/py_cli.py`, `tests/test_py_cli.py`
- **Build:** walk the AST for:
  - `*.add_argument("--name", "-n", default=..., type=..., choices=[...], help="...", dest=..., action=...)`
  - `@click.option("--name", "-n", default=..., type=click.Choice([...]), help=...)`, `@click.argument`, `@click.command(name=...)`, `@group.command("sub")`
  - Typer: params with `typer.Option(default, "--name", "-n", help=...)` and function names as commands.
  - Symbol table key = primary long flag (or subcommand path like `serve` / `db migrate`). Record default (as source text via `ast.unparse`), type, choices, help, line.
  - Diff tables → facts: `ADDED`, `REMOVED`, `DEFAULT_CHANGED`, `TYPE_CHANGED`, `CHOICES_CHANGED`. Short flags are aliases. `action="store_true"` means default `False`.
  - Aliases: `--dry-run` → also `dry_run`, `dry-run`.
- **Done when:** handles all three styles; ignores flags whose lines are outside hunks.
- **Tests:** one test per style per change type (≥ 12 cases).

### P1.2.2 — Function, class, parameter and constant symbols
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/py_symbols.py`, `tests/test_py_symbols.py`
- **Build:**
  - Collect module-level and class-level `def`/`async def`/`class`, qualified as `module.Class.method` (module from path: `src/pkg/mod.py` → `pkg.mod`; strip `src/`).
  - Parameters with defaults: `func(param=default)`; record kind (pos-only, kw-only, *args, **kwargs).
  - Module-level UPPER_CASE constants with literal values (`MAX_RETRIES = 3`).
  - `__all__` membership → marks public.
  - Facts: function/class `REMOVED`/`ADDED`/`SIGNATURE_CHANGED`; parameter `REMOVED`/`ADDED`/`DEFAULT_CHANGED`; constant `DEFAULT_CHANGED`/`REMOVED`.
  - `BEHAVIOR_CHANGED`: a public function whose **body** changed but signature didn't — emit with `old`/`new` = the changed body lines (≤ 20) for Tier 2 only. Skip if only comments/whitespace/logging changed (compare `ast.dump` with docstrings & `logging.*` calls removed).
  - Docstring first line → `help_text`.
- **Done when:** private names (`_x`) are emitted with `public=False` (gate decides later).
- **Tests:** rename of param; default change; removed method in a class; body-only change → BEHAVIOR_CHANGED; comment-only change → nothing.

### P1.2.3 — Environment variables
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/py_env.py`, `tests/test_py_env.py`
- **Build:** detect `os.getenv("X", default)`, `os.environ.get("X", default)`, `os.environ["X"]`, `environ.get` after `from os import environ`, and `pydantic-settings` `BaseSettings` fields (env name = `env_prefix` + field name upper-cased, or `Field(validation_alias=...)`/`alias`). Facts: `ADDED`, `REMOVED`, `DEFAULT_CHANGED`; RENAMED comes later from rename pairing.
- **Done when:** f-string env names are skipped (unknowable), not crashed on.
- **Tests:** each access style; pydantic-settings with prefix.

### P1.2.4 — Dataclass / pydantic / attrs field defaults
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/py_models.py`, `tests/test_py_models.py`
- **Build:** classes decorated with `@dataclass`/`@attrs.define`/`@attr.s`, or subclassing `BaseModel`/`BaseSettings`: fields with annotations and defaults, `Field(default=..., description=...)`, `field(default=...)`, `default_factory`. Kind `FIELD` (or `CONFIG_KEY` when the class name ends in `Config`/`Settings`/`Options`). `description=` → `help_text`.
- **Done when:** nested config classes give dotted paths (`ServerConfig.timeout` → `server.timeout` if referenced as attribute `server: ServerConfig`; otherwise `ServerConfig.timeout`).
- **Tests:** dataclass default change; pydantic field rename (pairs later); Field(description).

## Part 1.3 — Non-Python sources

### P1.3.1 — Config files (YAML / TOML / JSON / .env.example / INI)
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/config_files.py`, `tests/test_config_files.py`
- **Build:** for files matching `cfg.config_globs` (default: `**/*.example.*`, `**/config*.{yml,yaml,toml,json,ini}`, `**/defaults*.{…}`, `**/settings*.{…}`, `.env.example`, `**/values.yaml`), load both versions, flatten to dotted keys, diff → `CONFIG_KEY` facts (`ADDED`/`REMOVED`/`DEFAULT_CHANGED`). Line numbers: regex-locate `key:`/`key =` in the new/old text. `.env.example` → `ENV_VAR`.
- **Done when:** lists diffed as whole values; unparseable file → no facts, logged warning.
- **Tests:** yaml nested key removal; toml default change; .env.example rename.

### P1.3.2 — Generic regex fallback (JS/TS/Go/Rust/shell)
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P1.1.1
- **Files:** `extract/generic_regex.py`, `tests/test_generic_regex.py`
- **Build:** run on removed (`-`) and added (`+`) lines only. Patterns:
  - CLI flags: `"--[a-z][a-z0-9-]+"` inside quotes; Go `flag.String("name", def, "help")`, `flag.Int…`; Rust clap `#[arg(long = "name", default_value = "…")]`, `.long("name")`; JS `commander` `.option('--name <v>', 'help', default)`, `yargs` `.option('name', { default })`.
  - Env vars: `process.env.X`, `process.env["X"]`, `os.Getenv("X")`, `env::var("X")`, `std::env::var`, `${X}` and `$X` in shell.
  - Endpoints: string literals matching `^/(api|v\d)/…`.
  - Token removed on a `-` line and not present anywhere on `+` lines of the same file → `REMOVED`; mirrored → `ADDED`. Default changes for Go/clap/commander when the same name appears on both sides with different default literal.
- **Done when:** no false facts on a JS refactor fixture that only reorders lines.
- **Tests:** one per language; reorder-only diff → zero facts.

### P1.3.3 — tree-sitter upgrade (optional extra)
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P1.3.2
- **Files:** `extract/ts_symbols.py`, `tests/test_ts_symbols.py` (skipped if extra not installed)
- **Build:** when `tree-sitter-language-pack` is importable, extract exported function names and parameter lists for JS/TS/Go/Rust and diff symbol tables like P1.2.2. Fall back silently otherwise.
- **Done when:** `pytest -m "not treesitter"` is what CI runs by default; extra job may run it.
- **Tests:** TS exported function param rename.

## Part 1.4 — Fact post-processing

### P1.4.1 — Rename pairing
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P1.2.1, P1.2.3
- **Files:** `extract/rename.py`, `tests/test_rename.py`
- **Build:** within the same file and same `kind`, pair each `REMOVED` with an `ADDED` using a score:
  `+0.4` same default · `+0.3` same help text (or ratio > 0.8 via `difflib`) · `+0.2` same type/choices · `+0.2` same position (line distance ≤ 3, or same index in parameter list) · `+0.2` name similarity (`difflib` ratio > 0.5, or one contains the other: `timeout` ⊂ `request_timeout`).
  Pair greedily by highest score ≥ 0.5. Output one `RENAMED` fact (`old`=old name, `new`=new name). If defaults also differ, emit an extra `DEFAULT_CHANGED` fact on the new name and link both via `related`.
- **Done when:** `--timeout`→`--request-timeout` with changed default yields exactly two linked facts (the §1.1 story).
- **Tests:** clean rename; rename + default change; two removes and two adds pair correctly; no pairing across kinds.

### P1.4.2 — "Needs a doc update?" gate
- **Priority:** 🟥 MVP · **Owner:** 🧑🤖 · **Depends on:** P1.2.2
- **Files:** `extract/gate.py`, `tests/test_gate.py`
- **Build:** set `public=False` (fact kept for debug, excluded from search) when any holds:
  - Name starts with `_` (but not dunder `__init__` params of public classes), or module path contains `/_`, `internal`, `tests`, `migrations`, `vendor`.
  - File matches `cfg.ignore_code_globs`.
  - `BEHAVIOR_CHANGED` where the diff only touches logging, type hints, comments, docstrings, f-string formatting, or import order.
  - `ADDED` facts (new things can't make *existing* docs wrong) — kept only for the optional doc-gap feature (P9.5).
  - Symbol not referenced anywhere in docs **and** not exported — cheap check deferred to search stage (no candidates = no findings anyway).
  - If the diff touches only docs → the whole run short-circuits to "docs-only PR, nothing to check".
- **Done when:** all "no drift" fixtures produce zero public facts.
- **Tests:** each rule; regression fixture of a big refactor PR.

---

# Phase 2 — Docs indexing and candidate search

> **Goal:** split every doc into addressable sentences, then for each fact find the handful of sentences that could be talking about it. High recall here, precision comes later.
>
> **Exit criteria:** on fixtures, every expected drifted sentence appears in the candidates for its fact; median candidates per fact ≤ 8.

## Part 2.1 — Parsing docs into blocks

### P2.1.1 — Doc discovery
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `docs/discover.py`, `tests/test_discover.py`
- **Build:** doc files = `cfg.doc_globs` (default `**/*.md`, `**/*.mdx`, `**/*.rst`, `**/*.txt` under `docs/`, plus `README*`, `CONTRIBUTING*`, `CHANGELOG*` excluded by default since changelogs are historical by design), minus `cfg.doc_exclude_globs` (`node_modules/**`, `.venv/**`, `vendor/**`, `site/**`, `_build/**`, `**/CHANGELOG*`, `**/HISTORY*`, `**/RELEASE*`). Uses `RepoView.list_files()`.
- **Done when:** CHANGELOG never indexed by default.
- **Tests:** glob matrix.

### P2.1.2 — Markdown / MDX → blocks
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P2.1.1
- **Files:** `docs/markdown.py`, `tests/test_markdown.py`
- **Build:** `markdown-it-py` with table + front-matter plugins. Walk tokens, using `token.map` for line ranges. Emit `Block(type, text, line_start, line_end, heading_path)`:
  - paragraphs → PROSE; list items → LIST_ITEM; each table body row → TABLE_ROW (include header cells as prefix: `"Option: --timeout | Default: 30 | …"` in `plain`, original row in `text`); headings → HEADING (and update heading_path); fenced/indented code → one CODE block **per line**; blockquotes/admonitions (`> **Note**`, `:::note`, `!!! note`) → ADMONITION.
  - MDX: strip JSX tags/imports lines before parsing; keep text children.
  - Track `<!-- drift-ignore -->`, `<!-- drift-ignore-start -->` / `<!-- drift-ignore-end -->` and set `ignored`.
- **Done when:** line numbers exact for every block type.
- **Tests:** table row mapping; fenced code lines; ignore regions; front-matter skipped.

### P2.1.3 — reStructuredText → blocks
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P2.1.1
- **Files:** `docs/rst.py`, `tests/test_rst.py`
- **Build:** `docutils.core.publish_doctree` with `report_level=5` (silence) and unknown directives/roles tolerated (register a permissive fallback so Sphinx-only directives like `.. option::`, `:func:` don't crash). Map paragraphs, list items, table rows, literal blocks, `option` directives (as TABLE_ROW-like), section titles. Use `node.line` (+ source scan fallback when `None`). Ignore marker: `.. drift-ignore` comment.
- **Done when:** a Sphinx-style `.. option:: --timeout` block produces a block containing `--timeout`.
- **Tests:** paragraphs, `.. code-block::`, `.. option::`, `:func:\`foo\`` role text preserved as `foo`.

### P2.1.4 — Plain text docs
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P2.1.1
- **Files:** `docs/plaintext.py`, `tests/test_plaintext.py`
- **Build:** blank-line separated paragraphs → PROSE; lines starting with 4 spaces/tab → CODE; `--flag   description` two-column lines → TABLE_ROW.
- **Tests:** man-page-like help text.

## Part 2.2 — Sentences and index

### P2.2.1 — Sentence splitter
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P2.1.2
- **Files:** `docs/splitter.py`, `tests/test_splitter.py`
- **Build:** PROSE/LIST_ITEM/ADMONITION blocks split into sentences; TABLE_ROW, HEADING, CODE blocks are one "sentence" each.
  - Protect before splitting: inline code (`` `a.b()` ``), URLs, version numbers (`v1.2.3`), file names (`config.yaml`), abbreviations (`e.g.`, `i.e.`, `etc.`, `vs.`, `Dr.`), decimals.
  - Split on `[.!?]` + space + capital/backtick/digit, and on newlines inside list items.
  - Compute `line_start`/`line_end` per sentence by tracking character offsets → line numbers within the block.
  - `plain` = strip markdown/rst markup; `code_spans` = list of inline code contents.
- **Done when:** a sentence containing `` `os.path.join()` `` is never split at its dots.
- **Tests:** ≥ 15 tricky cases; line mapping for a sentence spanning lines 12–13.

### P2.2.2 — `DocIndex`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P2.2.1
- **Files:** `docs/index.py`, `docs/__init__.py`, `tests/test_index.py`
- **Build:** `build_index(repo, cfg)` → `DocIndex` with: `sentences: dict[str, DocSentence]` (IDs `S1..Sn` in path/line order), `by_path`, an inverted index `token → set[sentence_id]` over **raw tokens** (keep `--flags`, `UPPER_ENV`, `dotted.keys`, `func()` intact, plus lower-cased word tokens), and a `neighbors(sentence_id, k)` helper (sentences before/after in the same block/section, used for LLM context).
  Cache the index per `(rev, cfg hash)` in `.driftcheck/index-<rev>.json` for replay speed.
- **Done when:** builds the index of a 300-file docs tree in < 3 s.
- **Tests:** IDs stable for same input; tokens include `--request-timeout` intact.

## Part 2.3 — Candidate search

### P2.3.1 — Alias generator
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `search/aliases.py`, `tests/test_aliases.py`
- **Build:** `aliases(fact) -> set[str]`: for `--dry-run`: `--dry-run`, `dry-run`, `dry_run`, `DRY_RUN`, `dryRun`, `--dry-run=`; for `pkg.mod.func`: `func`, `func()`, `mod.func`, `pkg.mod.func`; for `server.timeout`: `server.timeout`, `timeout` (leaf, marked weak), `[server] timeout`, `SERVER_TIMEOUT`; for env vars: `X`, `$X`, `${X}`. Each alias tagged `strong` or `weak` (weak = generic leaf words like `timeout`, `name`, `path`, `debug`, `port`; list in `cfg.weak_words`).
- **Tests:** table-driven.

### P2.3.2 — Exact matcher
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P2.2.2, P2.3.1
- **Files:** `search/exact.py`, `tests/test_exact.py`
- **Build:** for each public fact: look up `old` value/name and strong aliases in the inverted index → `EXACT_OLD`/`EXACT_SYMBOL` candidates, `score=1.0`. Weak aliases only count if the sentence is a TABLE_ROW, CODE line, or the alias is inside a code span. Word-boundary checks (`--timeout` must not match `--timeout-ms`). For `DEFAULT_CHANGED`, also emit candidates for sentences containing the symbol (any alias) **and** the old value within the same sentence or table row.
- **Done when:** `--timeout` doesn't match `--timeout-ms`; `30` alone never creates a candidate.
- **Tests:** boundary cases; default-with-symbol co-occurrence.

### P2.3.3 — BM25 matcher
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P2.2.2
- **Files:** `search/bm25.py`, `tests/test_bm25.py`
- **Build:** BM25 over `sentence.plain` tokens (lowercase, split snake/kebab/camel into parts, small stopword list). Query per fact = symbol parts + old/new value + help text words + docstring first line. Take top `cfg.bm25_top_k` (default 5) above a min normalised score (default 0.35), excluding sentences already found by exact match. These go to Tier 2 only.
- **Done when:** in the §1.1 story, `S203` (troubleshooting) appears as BM25 candidate.
- **Tests:** ranking sanity; threshold respected.

### P2.3.4 — `find_candidates()` merge
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P2.3.2 (P2.3.3 optional)
- **Files:** `search/__init__.py`, `tests/test_find_candidates.py`
- **Build:** run exact, then BM25, then links (P2.3.5 if present); merge by `(fact_id, sentence_id)` keeping the strongest match type (EXACT_OLD > EXACT_SYMBOL > LINK > BM25); drop `ignored` sentences; cap per fact at `cfg.max_candidates_per_fact` (default 12).
- **Tests:** merge precedence; cap.

### P2.3.5 — Indirect links (one hop)
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P2.3.4, P1.2.2
- **Files:** `search/links.py`, `tests/test_links.py`
- **Build:** answers *"How can the system identify indirect relationships?"*:
  1. **Wrapper hop:** if public function `cli_main()` calls changed `connect(timeout=…)` and passes a param through, docs mentioning `cli_main`/its flag are linked to the `connect` fact (build a simple name-based call graph of the head revision with `ast`).
  2. **Docstring hop:** if the changed function's docstring mentions a flag/env var, sentences mentioning that token are linked.
  3. **Section hop:** sentences in the same doc section (heading_path) as an exact match get `LINK` with lower score — catches "It defaults to 30" two sentences after the flag name.
  4. **mkdocstrings/autodoc refs:** `::: pkg.mod.func` or `.. autofunction:: pkg.mod.func` link that page section to the symbol.
- **Done when:** the "It defaults to 30" case (symbol in previous sentence) is caught via section hop.
- **Tests:** each hop type.

---

# Phase 3 — Tier 1: hard drift (no LLM)

> **Goal:** certain, explainable findings with zero model calls. This is the backbone of the demo, offline mode, and the pre-push hook.
>
> **Exit criteria:** on fixtures, Tier 1 precision = 100%, recall ≥ 90% of hard cases; on the mined eval set, Tier 1 precision ≥ 0.85.

## Part 3.1 — Values

### P3.1.1 — Value normaliser
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `tier1/values.py`, `tests/test_values.py`
- **Build:** `normalize(raw: str) -> NormValue(kind, value, unit)`:
  - numbers: `30`, `30.0`, `"30"`, `1_000`, `1e3`, `1k`, `1,000`;
  - durations: `30s`, `30 sec`, `30 seconds`, `0.5m`, `timedelta(seconds=30)`, `30_000` with `_ms` symbol suffix → all to seconds;
  - sizes: `10MB`, `10 MiB`, `10*1024*1024`;
  - booleans: `True/true/yes/on/enabled/1` vs `False/false/no/off/disabled/0`;
  - null: `None/null/nil/unset/empty`;
  - strings: strip quotes; case-sensitive compare.
  - Words → numbers for 0–20 (`thirty` not needed, keep `zero…twenty`).
  `find_values(text) -> list[(NormValue, span)]` scans a sentence for values.
  `equal(a, b)` compares normalised forms.
- **Done when:** `"30 seconds"` equals `30` when symbol unit is seconds; `"30"` ≠ `"300"`.
- **Tests:** ≥ 30 table cases.

## Part 3.2 — Rules

### P3.2.1 — Rule engine and the eight rules
- **Priority:** 🟥 MVP · **Owner:** 🧑🤖 · **Depends on:** P3.1.1, P2.3.4, P1.4.1
- **Files:** `tier1/rules.py`, `tier1/__init__.py`, `tests/test_tier1_rules.py`
- **Build:** each rule = function `(fact, sentence, candidate) -> Finding | None`. A candidate becomes a Tier 1 finding **only if the token match is "hard"**: inside a code span, a CODE line, a TABLE_ROW, or a strong alias (contains `--`, `_`, `.`, `()`, or is ALL_CAPS ≥ 4 chars). Otherwise it's passed to Tier 2 as leftover.

  | Rule | Fact | Fires when | Severity | Suggested fix |
  |---|---|---|---|---|
  | `R1_removed_flag` | cli_flag REMOVED | old flag appears (hard) | critical | delete mention / "flag removed in <sha>" note |
  | `R2_renamed_flag` | cli_flag RENAMED | old flag appears (hard) | critical | replace old → new |
  | `R3_default_changed` | any DEFAULT_CHANGED | symbol (any alias) + old value in same sentence/table row, new value absent | high | replace old value → new value (preserve unit/format, e.g. "30 seconds" → "60 seconds") |
  | `R4_env_var` | env_var REMOVED/RENAMED | old name appears | critical (removed) / high (renamed) | replace / delete |
  | `R5_config_key` | config_key REMOVED/RENAMED | full dotted key, or leaf key in TABLE_ROW/CODE under matching section | high | replace |
  | `R6_symbol_removed` | function/class REMOVED/RENAMED | `name(` or qualified name or in code span | high | replace / delete |
  | `R7_param` | parameter REMOVED/RENAMED | `func(old=` in code, or `old` code span in a sentence that also mentions `func` | high | replace |
  | `R8_choices` | CHOICES_CHANGED | a removed choice appears next to symbol | medium | list new choices |

  Each finding: `confidence=1.0`, `doc_quote` = matched substring, `code_quote` = the changed line from `fact.code_snippet`, `message` like *"`--timeout` was renamed to `--request-timeout` in cli.py:42, but docs/usage.md:12 still uses `--timeout`."*
  **Code blocks get special care:** in CODE lines, only R1/R2/R4/R6/R7 fire (exact tokens), never R3 (values in example code are often arbitrary).
- **Done when:** golden test passes on all fixtures; leftovers returned for Tier 2.
- **Tests:** one positive + one negative (near miss) per rule; golden test over `tests/fixtures` comparing to `expected.json`.

### P3.2.2 — Fix text generator for Tier 1
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P3.2.1
- **Files:** `tier1/fixes.py`, `tests/test_tier1_fixes.py`
- **Build:** produce `suggested_text` = the full sentence with a minimal edit: token replacement for renames, value replacement preserving format (`30 seconds` → `60 seconds`, `` `30` `` → `` `60` ``, `30s` → `60s`), and for removals a strike-through suggestion is NOT applied automatically — instead `suggested_text=None` and the message says "remove or update this reference" (removals need human judgement).
- **Tests:** format preservation cases.

### P3.2.3 — Pipeline integration for offline mode
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P3.2.1, P1.*, P2.*
- **Files:** `pipeline.py` (wire real stages), `tests/test_e2e_offline.py`
- **Build:** replace stubs with real stages for `--llm none`.
- **Done when:** the §1.1 story, built in a tmp repo, yields exactly the two Tier 1 findings.
- **Tests:** e2e on tmp repo; e2e on "no drift refactor" → zero findings.

---

# Phase 4 — Tier 2 (Qwen3-4B) and verification (Nemotron)

> **Goal:** catch drift in prose and behaviour descriptions that exact matching can't, while never hallucinating line numbers or quotes.
>
> **Exit criteria:** with the fake LLM, all guards and fallbacks are tested; with the real stack on the laptop, Tier 2 adds recall on the eval set without dropping overall precision below Tier 1-only − 0.05.

## Part 4.1 — LLM plumbing

### P4.1.1 — `LLMClient` protocol and OpenAI-compatible client
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `llm/client.py`, `tests/test_llm_client.py`
- **Build:**
  ```python
  class LLMClient(Protocol):
      model: str
      def complete_json(self, system: str, user: str, schema: dict, *,
                        temperature: float = 0.0, max_tokens: int = 1024,
                        extra: dict | None = None) -> dict: ...
  ```
  `OpenAICompatClient(base_url, api_key, model, timeout_s, max_retries)`, using the `openai` SDK:
  - **Qwen (llama.cpp server):** `base_url=http://127.0.0.1:8080/v1`, `api_key="local"`, `response_format={"type":"json_schema","json_schema":{"name":…,"schema":…,"strict":true}}`; disable thinking with `extra_body={"chat_template_kwargs":{"enable_thinking": False}}` **and** prepend `/no_think` to the user message (belt and braces); strip any `<think>…</think>` from output before `json.loads`.
  - **Nemotron (NVIDIA NIM):** `base_url=https://integrate.api.nvidia.com/v1`, `api_key=$NVIDIA_API_KEY`, `model=cfg.verify_model` (default `nvidia/nemotron-3-ultra-550b-a55b`, configurable since catalogue names change). Use `response_format={"type":"json_object"}` if `json_schema` is rejected; then validate with pydantic.
  - Retries with exponential backoff on 429/5xx/timeouts (free tier rate limits); max concurrency `cfg.verify_concurrency` (default 2).
  - On malformed JSON: one repair retry ("Return only valid JSON matching the schema"), then raise `LLMError`.
- **Done when:** fake HTTP (respx or monkeypatch) tests cover success, 429-retry, malformed-then-fixed, think-tag stripping.
- **Tests:** as above. **No real network.**

### P4.1.2 — JSON schemas and pydantic response models
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P4.1.1
- **Files:** `llm/schemas.py`, `tests/test_schemas.py`
- **Build:** pydantic models `Tier2Result`, `Tier2Response`, `VerifyResult`, `VerifyResponse` matching [Appendix A](#appendix-a--prompts), and `.model_json_schema()` exports used for constrained decoding. Enums: `verdict ∈ {outdated, still_accurate, unrelated}`, `decision ∈ {confirm, reject, revise}`.
- **Tests:** schema export; validation of good/bad payloads.

### P4.1.3 — Guards (anti-hallucination)
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P4.1.2
- **Files:** `llm/guards.py`, `tests/test_guards_llm.py`
- **Build:** for every Tier 2 result:
  1. `sentence_id` must be one of the IDs sent in that prompt; `fact_id` likewise.
  2. `doc_quote` must be a substring of `sentence.text` (after whitespace normalisation); if not, try fuzzy (`difflib` ratio ≥ 0.9 on a sliding window) and replace with the real substring; else drop.
  3. `code_quote` must be a substring of `fact.code_snippet` (same treatment).
  4. `suggested_fix` must differ from the original sentence and be ≤ 2× its length.
  5. `confidence` clamped to [0, 1].
  Each drop recorded with a reason in debug logs (`--debug`).
- **Tests:** each guard, positive and negative.

### P4.1.4 — LLM result cache
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P4.1.1
- **Files:** `llm/cache.py`, `tests/test_cache.py`
- **Build:** sqlite at `.driftcheck/cache.sqlite`; key = `sha256(model | prompt_version | system | user)`; value = JSON response + timestamp. `CachedClient(inner, cache)` wraps any `LLMClient`. `--no-cache` flag. Prompt version is a constant in `llm/prompts/__init__.py` bumped whenever prompts change.
- **Done when:** a second identical eval run makes zero LLM calls.
- **Tests:** hit/miss; version bump invalidates.

## Part 4.2 — Tier 2 judge (Qwen3-4B)

### P4.2.1 — Prompt builder
- **Priority:** 🟥 MVP · **Owner:** 🧑🤖 · **Depends on:** P4.1.2
- **Files:** `llm/prompts/tier2_system.md`, `llm/prompts/tier2_user.md`, `llm/qwen.py` (builder part), `tests/test_tier2_prompt.py`
- **Build:** one prompt **per fact** with ≤ `cfg.tier2_max_sentences` (default 6) candidate sentences. Include: fact record (kind, change type, old → new, file:line, help text), the code snippet (≤ 20 lines), and each candidate as `[S17] (docs/usage.md, section "Options") <text>` plus one neighbour sentence before/after as read-only context marked `(context, do not judge)`. Keep each prompt ≤ ~2,500 tokens (truncate snippet first, then neighbours). Templates in Appendix A.
- **Done when:** snapshot test of a rendered prompt is stable.
- **Tests:** snapshot; truncation behaviour.

### P4.2.2 — `run_tier2()`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P4.2.1, P4.1.3
- **Files:** `llm/qwen.py`, `tests/test_tier2.py`
- **Build:** for each fact with leftover candidates (Tier 1 leftovers + BM25 + LINK), call Qwen, validate, guard, and convert `verdict == "outdated"` with `confidence ≥ cfg.tier2_min_confidence` (default 0.6) to `Finding(tier=SOFT, rule="T2_prose", severity=LOW by default, raised to MEDIUM if fact is DEFAULT_CHANGED/RENAMED/REMOVED)`. Facts processed sequentially (a 4B model on a laptop handles one request well; llama-server `--parallel 2` is the max). Per-run budget `cfg.tier2_max_calls` (default 40) — over budget, prioritise facts by severity potential.
- **Done when:** with FakeLLM, an "outdated" result becomes a Finding; an invalid quote is dropped; budget enforced.
- **Tests:** as above, plus LLM error → fact skipped, run continues, warning recorded.

## Part 4.3 — Verification

### P4.3.1 — Nemotron verifier
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P4.2.2
- **Files:** `llm/nemotron.py`, `llm/prompts/verify_system.md`, `llm/prompts/verify_user.md`, `tests/test_verify_nemotron.py`
- **Build:** only Tier 2 findings go to verification (Tier 1 is already certain). Batch up to 5 findings per call. Prompt shows: fact, full code snippet, sentence + neighbours, Qwen's claim and fix. Response per finding: `confirm` (keep, confidence = mean(qwen, nemotron)), `reject` (suppressed_by="verifier"), `revise` (keep with `revised_fix`). Sets `verification`.
  On auth/connection failure (or missing `NVIDIA_API_KEY`): log one warning and fall back to `selfcheck.verify`.
- **Tests:** confirm/reject/revise with FakeLLM; fallback path.

### P4.3.2 — Offline verifier: Qwen self-consistency
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P4.2.2
- **Files:** `llm/selfcheck.py`, `tests/test_selfcheck.py`
- **Build:** re-ask Qwen with the **verify** prompt (different framing: "Here is a claim that this sentence is outdated. Is the claim correct?") at temperature 0.3, twice. Keep only if both say confirm. `verification.by = "qwen-selfcheck"`.
- **Tests:** agree/disagree cases.

### P4.3.3 — Prompt and threshold tuning
- **Priority:** 🟧 Core · **Owner:** 🧑 · **Depends on:** P4.3.1, P8.3.1
- **Files:** `llm/prompts/*.md`, `.driftcheck.toml` defaults, `eval/results/tuning.md`
- **Build:** run `driftcheck eval --split dev` with 3–4 prompt variants and thresholds `{0.5, 0.6, 0.7, 0.8}`; pick the best F1 with precision ≥ 0.8; record the table in `eval/results/tuning.md`; bump prompt version. Never tune on the `test` split.
- **Done when:** chosen settings committed with the evidence table.

## Part 4.4 — Local model setup (runs on the laptop)

### P4.4.1 — Qwen3-4B serving script and `doctor`
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P4.1.1
- **Files:** `scripts/serve_qwen.sh`, `scripts/serve_qwen.ps1`, `docs/local-model.md`, `driftcheck/cli.py` (`doctor` subcommand)
- **Build:**
  - `serve_qwen.sh`: downloads `Qwen3-4B-Q4_K_M.gguf` (official Qwen GGUF on Hugging Face) if missing into `~/.cache/driftcheck/models/`, then
    `llama-server -m <gguf> --host 127.0.0.1 --port 8080 -c 8192 --jinja --parallel 2 -ngl 99` (drop `-ngl` without GPU).
  - Ollama alternative documented: `ollama pull qwen3:4b`, base URL `http://127.0.0.1:11434/v1`.
  - `driftcheck doctor`: checks git, Python, docs found, Qwen endpoint reachable (`GET /v1/models`) and returns valid JSON for a 1-line test prompt (prints latency), `NVIDIA_API_KEY` set and NIM reachable, GitHub token scopes when in Actions. Green/red table.
- **Done when:** on the laptop, `driftcheck doctor` is all green.

---

# Phase 5 — Filters and noise control

> **Goal:** answer the problem's hardest questions: *How to minimise false alarms? How to tell docs-changes from changes that need docs? How to stay useful without excessive warnings?* Filters run in a **fixed, documented order** and every suppressed finding records *why*, which feeds eval and `--debug`.
>
> **Exit criteria:** filter order test passes; eval shows filters raise precision without losing more than 5% recall.

Order (in `filters/__init__.py`):

```
1 markers      (<!-- drift-ignore --> regions/lines)
2 driftignore  (.driftignore fingerprints)
3 same_pr      (PR already edits that sentence / adds new name nearby)
4 threshold    (per-tier confidence)
5 verifier     (Tier 2 rejected by verify → suppressed)
6 dedupe       (merge findings on the same sentence)
7 severity     (rank)
8 cap          (max inline annotations / comments)
```

### P5.1.1 — Filter framework + markers
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `filters/__init__.py`, `filters/markers.py`, `tests/test_filters_order.py`, `tests/test_markers.py`
- **Build:** `FilterContext(pr_doc_diff: list[FileChange], driftignore: DriftIgnore, cfg)`. `apply_filters()` runs filters in order; each returns `(kept, suppressed)` and sets `suppressed_by`. Markers: sentence `ignored=True` (set by parsers) → suppressed. Also support an inline trailing `<!-- drift-ignore: --timeout -->` that only ignores a specific symbol.
- **Tests:** order is exactly as listed; marker variants.

### P5.1.2 — Same-PR edit skip
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P5.1.1
- **Files:** `filters/same_pr.py`, `tests/test_same_pr.py`
- **Build:** suppress a finding when the PR's own diff (a) modifies any line in `[sentence.line_start, sentence.line_end]` of that doc file, or (b) adds the fact's **new** name/value within ±3 lines of the sentence (the author is mid-update). Note: the doc index is built at **head**, so line numbers match the head side of the PR diff.
- **Tests:** both cases; edit elsewhere in same file → not suppressed.

### P5.1.3 — Threshold, dedupe, severity, cap
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P5.1.1
- **Files:** `filters/threshold.py`, `filters/dedupe.py`, `filters/severity.py`, `filters/cap.py`, `tests/test_filters_misc.py`
- **Build:**
  - **threshold:** Tier 1 always passes; Tier 2 needs `confidence ≥ cfg.tier2_min_confidence` **and** (if verified) `verification.decision != "reject"`.
  - **dedupe:** multiple findings on one sentence → keep highest severity as primary, merge others into its `message` ("also: default 30 → 60"), combine suggested fixes by applying edits sequentially when non-overlapping.
  - **severity rank:** sort by (severity, tier, confidence desc, path, line). Severity table in P3.2.1; Tier 2 LOW/MEDIUM.
  - **cap:** at most `cfg.max_annotations` (default 25) inline annotations and `cfg.max_findings_in_comment` (default 15) rows; overflow summarised as "+N more (see the JSON artifact)". Never cap CRITICAL.
- **Tests:** each filter; cap never drops critical.

---

# Phase 6 — Outputs

> **Goal:** findings people actually read and act on, with exact references both ways (doc line ↔ code change).
>
> **Exit criteria:** all formats generated from one `RunReport`; GitHub output verified on a real test PR.

## Part 6.1 — Local outputs

### P6.1.1 — Console reporter
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `output/console.py`, `tests/test_console.py`
- **Build:** `rich` output grouped by doc file, coloured severity badges, `path:line` (clickable in most terminals), quoted doc text with the drifted token highlighted, "Caused by `cli.py:42` (`--timeout` → `--request-timeout`)", suggested text in green. Footer: counts by severity, mode, timings, suppressed count (`--debug` lists suppressed with reasons). Exit code: `0` no findings, `1` findings at or above `cfg.fail_on` (default `high` for CI, `none` for hook-warn mode), `2` tool error.
- **Tests:** snapshot of rendered text (rich `Console(record=True, width=100)`).

### P6.1.2 — JSON and Markdown reporters
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `output/json_out.py`, `output/markdown.py`, `tests/test_md_json.py`
- **Build:** JSON = `RunReport.to_json()`. Markdown = the summary comment body (§1.1 shape): title with count, table (severity, doc permalink, "says", "code now", "caused by" permalink), collapsible suggested-fix diff, collapsible "suppressed (N)" when `--debug`, footer with mode and models. Starts with the hidden marker `<!-- driftcheck:summary -->`. Zero findings → short "✅ No documentation drift detected (checked N sentences against M code changes)".
- **Tests:** snapshot for 0, 1, many findings.

### P6.1.3 — SARIF reporter
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `output/sarif.py`, `tests/test_sarif.py`
- **Build:** SARIF 2.1.0, one `rule` per rule ID, `result.locations` = doc line, `relatedLocations` = code line, `level` from severity, `partialFingerprints.driftcheck/v1` = fingerprint. Enables GitHub code scanning upload as an option.
- **Tests:** validates against a minimal schema subset (required fields present).

### P6.1.4 — Permalink builder
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P0.3.1
- **Files:** `output/links.py`, `tests/test_links_out.py`
- **Build:**
  - Doc line: `https://github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}`.
  - Code change in PR: `https://github.com/{owner}/{repo}/pull/{n}/files#diff-{sha256(path)}R{line_new}` (or `L{line_old}` for removed lines); outside a PR: commit blob permalink at the relevant SHA.
  - Local runs (no remote): `path:line` text.
- **Tests:** sha256 anchor correctness; removed vs added line anchors.

## Part 6.2 — GitHub outputs

### P6.2.1 — GitHub context and API client
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `github/context.py`, `github/api.py`, `tests/test_github_context.py`
- **Build:** read `GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, `GITHUB_SHA`, `GITHUB_TOKEN`, `GITHUB_API_URL`; for `pull_request` events take `base.sha`, `head.sha`, `number`, and `head.repo.full_name` (fork detection). `GitHubAPI` with `httpx`, auth header, retry on 5xx/secondary rate limit.
- **Tests:** context parsing from sample event JSON fixtures (same-repo PR, fork PR, push).

### P6.2.2 — Check Run with annotations
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P6.2.1, P6.1.2
- **Files:** `github/checks.py`, `tests/test_checks.py`
- **Build:** `POST /repos/{o}/{r}/check-runs` (name `DriftCheck` or `DriftCheck (LLM)`), `head_sha`, status → `completed`, `conclusion` = `failure` if any finding ≥ `fail_on`, else `neutral` if findings, else `success`. `output.title`, `output.summary` (the Markdown), `annotations` in batches of 50 via `PATCH` (GitHub limit). Annotation: `path`, `start_line`, `end_line`, `annotation_level` (critical/high → `failure`, medium → `warning`, low/info → `notice`), `title` = rule, `message` = finding message + "Caused by …", `raw_details` = suggested text.
  **Important:** drifted docs are usually *not* in the PR's changed files, so GitHub shows those annotations in the **Checks tab**, not inline in "Files changed". That's why the sticky comment (P6.2.3) with permalinks is the primary surface.
  Requires `permissions: checks: write`. If 403 (fork PR), fall back to `$GITHUB_STEP_SUMMARY` + `::warning file=…,line=…::` workflow commands.
- **Tests:** request payloads with mocked httpx; batching > 50; 403 fallback.

### P6.2.3 — Sticky summary comment
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P6.2.1, P6.1.2
- **Files:** `github/comment.py`, `tests/test_comment.py`
- **Build:** list PR comments, find one starting with `<!-- driftcheck:summary -->` authored by the bot, `PATCH` it; else `POST`. If the LLM job runs after the fast job, it overwrites with the richer report (mode shown in footer). If a later push has zero findings and a comment exists, update it to the ✅ version (don't delete — keeps history readable). Requires `pull-requests: write`; on 403, write to step summary only.
- **Tests:** create vs update; zero-findings update.

### P6.2.4 — Fix patch artifact
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P9.1.1
- **Files:** `output/patch.py` (shared with P9.1.1), workflow step in `driftcheck.yml`
- **Build:** write `driftcheck-out/fix.patch`, `report.json`, `report.md`, `report.sarif` and upload with `actions/upload-artifact@v4` (name `driftcheck-report`). Comment links to the run's artifacts page.
- **Tests:** covered in P9.1.1.

---

# Phase 7 — Triggers: CLI, pre-push hook, GitHub Action

> **Goal:** one engine, three entry points.
>
> **Exit criteria:** the same fixture repo produces identical findings via CLI, hook (Tier 1), and Action.

## Part 7.1 — CLI

### P7.1.1 — `driftcheck check`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P3.2.3, P6.1.1
- **Files:** `cli.py`, `tests/test_cli_check.py`
- **Build:**
  ```
  driftcheck check [--base REF] [--head REF] [--diff FILE] [--repo PATH]
                   [--llm none|local|full] [--format console|json|markdown|sarif]
                   [--out DIR] [--fix] [--fail-on critical|high|medium|low|none]
                   [--config FILE] [--debug] [--no-cache]
  ```
  Defaults: `--head HEAD`, `--base` = merge-base with `origin/main` (fallback `HEAD~1`), `--llm` from config (default `none`). `--diff FILE` reads a diff (use head = working tree). `--out` writes all formats.
- **Tests:** CLI runner on tmp repo for each format; exit codes.

### P7.1.2 — `driftcheck ignore` and `driftcheck doctor`
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P9.3.1, P4.4.1
- **Files:** `cli.py`, `tests/test_cli_ignore.py`
- **Build:** `driftcheck ignore <fingerprint|finding-id> --reason "…"` appends to `.driftignore` (resolving finding IDs from the last run saved at `.driftcheck/last-run.json`). `doctor` as specified in P4.4.1.
- **Tests:** ignore by fingerprint and by `D2`.

## Part 7.2 — Pre-push hook

### P7.2.1 — Hook runner and installer
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P7.1.1
- **Files:** `hooks/pre_push.py`, `hooks/install.py`, `cli.py` (`hook install|uninstall|run`), `.pre-commit-hooks.yaml`, `tests/test_hook.py`
- **Build:**
  - `driftcheck hook install` writes `.git/hooks/pre-push` (backing up any existing one) that runs `driftcheck hook run "$@"`.
  - `hook run` reads stdin lines `<local_ref> <local_sha> <remote_ref> <remote_sha>`; for each, range = `remote_sha..local_sha` (new branch: `merge-base(local_sha, origin/main)..local_sha`; deletion: skip).
  - Default mode `--llm none` (fast, < 2 s target), configurable `hook.llm = "local"` if Qwen is running locally.
  - Non-blocking by default (prints findings, exits 0). `hook.block_on = "critical"` makes it exit 1. Bypass: `git push --no-verify` (documented).
  - Also ship `.pre-commit-hooks.yaml` with `stages: [pre-push]` for pre-commit framework users.
- **Tests:** simulate stdin for new branch, update, delete; blocking vs non-blocking.

## Part 7.3 — GitHub Action

### P7.3.1 — Composite action
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P7.1.1, P6.2.2, P6.2.3
- **Files:** `action.yml`, `cli.py` (`github` subcommand), `tests/test_action_entry.py`
- **Build:**
  ```yaml
  name: DriftCheck
  description: Detect documentation made outdated by code changes in a PR
  inputs:
    llm:            { default: "none", description: "none | local | full" }
    fail-on:        { default: "high" }
    qwen-base-url:  { default: "http://127.0.0.1:8080/v1" }
    nvidia-api-key: { default: "" }
    check-name:     { default: "DriftCheck" }
  runs:
    using: composite
    steps:
      - run: pip install "${{ github.action_path }}"
        shell: bash
      - run: driftcheck github --llm "${{ inputs.llm }}" --fail-on "${{ inputs.fail-on }}" --check-name "${{ inputs.check-name }}" --out driftcheck-out
        shell: bash
        env:
          GITHUB_TOKEN: ${{ github.token }}
          DRIFTCHECK_QWEN_BASE_URL: ${{ inputs.qwen-base-url }}
          NVIDIA_API_KEY: ${{ inputs.nvidia-api-key }}
  ```
  `driftcheck github` = read context → `pipeline.run(base, head)` → Check Run → sticky comment → write artifacts → exit code.
- **Tests:** `github` subcommand with sample event JSON and mocked API.

### P7.3.2 — `driftcheck.yml`: fast tier on GitHub, LLM tier on the laptop
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P7.3.1, P7.4.1
- **Files:** `.github/workflows/driftcheck.yml`
- **Build:**
  ```yaml
  name: driftcheck
  on:
    pull_request:
      types: [opened, synchronize, reopened, ready_for_review]
  permissions:
    contents: read
    checks: write
    pull-requests: write
  concurrency:
    group: driftcheck-${{ github.event.pull_request.number }}
    cancel-in-progress: true

  jobs:
    fast:
      name: Tier 1 (offline)
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
          with: { fetch-depth: 0 }
        - uses: actions/setup-python@v5
          with: { python-version: "3.11" }
        - uses: ./
          with: { llm: none, check-name: "DriftCheck" }
        - uses: actions/upload-artifact@v4
          if: always()
          with: { name: driftcheck-fast, path: driftcheck-out/ }

    llm:
      name: Tier 1 + Qwen3-4B + Nemotron
      needs: fast
      # Only on PRs from this repo (never run fork code on the laptop) and only
      # when the laptop runner is switched on (repo variable).
      if: >
        github.event.pull_request.head.repo.full_name == github.repository &&
        vars.DRIFTCHECK_LLM_RUNNER == 'on'
      runs-on: [self-hosted, driftcheck-qwen]
      timeout-minutes: 20
      steps:
        - uses: actions/checkout@v4
          with: { fetch-depth: 0 }
        - name: Qwen health check
          id: qwen
          run: |
            if curl -sf http://127.0.0.1:8080/v1/models > /dev/null; then echo "up=true" >> "$GITHUB_OUTPUT";
            else echo "up=false" >> "$GITHUB_OUTPUT"; echo "::warning::Qwen server not reachable, skipping LLM tier"; fi
        - uses: ./
          if: steps.qwen.outputs.up == 'true'
          with:
            llm: full
            check-name: "DriftCheck (LLM)"
            nvidia-api-key: ${{ secrets.NVIDIA_API_KEY }}
        - uses: actions/upload-artifact@v4
          if: always()
          with: { name: driftcheck-llm, path: driftcheck-out/ }
  ```
  **Why this shape:** the `fast` job always gives a result in ~1 minute. The `llm` job is **not** a required check, so a sleeping laptop never blocks merging. Toggle with repo variable `DRIFTCHECK_LLM_RUNNER` (`on`/`off`) in Settings → Secrets and variables → Actions → Variables — flip it off when the laptop is offline so jobs don't queue for hours.
- **Done when:** a test PR shows both check runs and one sticky comment updated by the LLM job.

## Part 7.4 — Self-hosted runner on your mate's laptop

### P7.4.1 — Runner setup and hardening (runbook)
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P4.4.1
- **Files:** `docs/self-hosted-runner.md`
- **Build:** a runbook covering:
  1. Repo → Settings → Actions → Runners → **New self-hosted runner**; follow the OS-specific commands; add label **`driftcheck-qwen`**.
  2. Run the runner as a **non-admin user**, as a service (`./svc.sh install && ./svc.sh start` on Linux/macOS; service option on Windows) so it survives reboots.
  3. Start `scripts/serve_qwen.sh` as a service too (systemd unit / launchd plist / NSSM on Windows samples included). The runner and Qwen must be on the same machine (the workflow calls `127.0.0.1:8080`).
  4. **Security (must do):** Settings → Actions → General → *"Require approval for all external contributors"* (or all outside collaborators); the workflow's `if:` already blocks fork PRs; never put secrets other than `NVIDIA_API_KEY` in this repo; keep the laptop runner registered to **this repo only**.
  5. Add repo secret `NVIDIA_API_KEY` (from build.nvidia.com) and variable `DRIFTCHECK_LLM_RUNNER=on`.
  6. Laptop power settings: no sleep while plugged in during the hackathon.
  7. Smoke test: open a PR from `examples/01-renamed-flag` changes; confirm both checks.
- **Done when:** a real PR got a `DriftCheck (LLM)` check from the laptop.

---

# Phase 8 — Replay, mining and evaluation

> **Goal:** prove it works the way the judges will test it: on real histories where a doc-fix commit came shortly after a code change. Detect the drift **at the code commit**, before the doc fix existed.
>
> **Exit criteria:** `driftcheck eval` prints precision/recall/F1 per mode on ≥ 4 real repos with ≥ 60 labelled cases total; results committed in `eval/results/`.

## Part 8.1 — Replay

### P8.1.1 — `driftcheck replay`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P3.2.3
- **Files:** `eval/replay.py`, `cli.py` (`replay`), `tests/test_replay.py`
- **Build:** `driftcheck replay --commit <sha> [--repo PATH] [--llm …] [--format …]` runs the pipeline with `base = sha^`, `head = sha`, docs read **at `sha`** via `RepoView` (no checkout, no working-tree changes). `--range a..b` for PR-like ranges. Merge commits: use first parent.
- **Done when:** replaying the code commit in a tmp repo whose next commit fixes docs reports the drift.
- **Tests:** tmp repo history test.

## Part 8.2 — Mining labelled cases

### P8.2.1 — `driftcheck mine`
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P8.1.1, P1.*
- **Files:** `eval/mine.py`, `cli.py` (`mine`), `tests/test_mine.py`
- **Build:**
  1. Walk `git log --first-parent --no-merges` (optionally `--since`).
  2. **Doc-fix commit** `D`: ≥ 70% of changed lines are in doc files, and it **modifies or removes** existing doc lines (not only additions).
  3. For each removed/modified doc line in `D`, extract tokens (flags, env vars, code spans, numbers next to symbols).
  4. Look back up to `--window` commits (default 30) or `--days` (default 60) for a **code commit** `C` whose extracted facts (run Phase 1 on `C`) have `old` values/names that appear in those removed doc lines. Prefer the most recent such `C`.
  5. Commit-message boost: `D` messages matching `/(fix|update|correct|sync).*(doc|readme)|docs?:/i` raise confidence.
  6. Emit JSONL rows:
     ```json
     {"repo": "owner/name", "code_commit": "abc123", "doc_fix_commit": "def456",
      "labels": [{"path": "docs/usage.md", "line_start": 12, "line_end": 12,
                  "old_text": "Use `--timeout` …", "new_text": "Use `--request-timeout` …",
                  "tokens": ["--timeout"]}],
      "match_confidence": 0.9, "kind": "hard|soft"}
     ```
     `kind = hard` if a token is a flag/env/key/value match; `soft` when linked only by message + same PR/author + BM25 similarity (`--include-soft`).
  7. Deterministic split by hash of `code_commit`: 60% `dev`, 40% `test`.
- **Done when:** on a tmp repo with a known pair it finds exactly that pair.
- **Tests:** positive pair; doc-only additions ignored; window respected.

### P8.2.2 — Repo list and dataset build
- **Priority:** 🟥 MVP · **Owner:** 🧑🤖 · **Depends on:** P8.2.1
- **Files:** `eval/repos.txt`, `scripts/build_dataset.sh`, `eval/datasets/*.jsonl`, `eval/datasets/README.md`
- **Build:** pick 4–8 active open-source Python projects with real `docs/` folders and lots of CLI/config surface (candidates to vet: CLI tools, web servers, static-site generators, linters/formatters written in Python). Script clones with `--filter=blob:none`, runs `mine`, writes one JSONL per repo. Hand-review a sample of 20 cases and record the precision of the miner itself in the README (honesty points with judges).
- **Done when:** ≥ 60 cases total, reviewed sample documented.

## Part 8.3 — Evaluation

### P8.3.1 — Matching and metrics
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P8.2.1
- **Files:** `eval/match.py`, `eval/metrics.py`, `tests/test_eval_metrics.py`
- **Build:**
  - A finding **hits** a label if same `path` and line ranges overlap (±1 line tolerance).
  - Per case: TP = labels hit; FN = labels not hit; FP = findings that hit no label **and** whose sentence was not changed by the doc-fix commit **and** not in any later doc change within the window (report "unlabelled findings" separately, since some may be real drift the project never fixed).
  - Metrics: precision, recall, F1 (micro over labels), plus per-rule and per-tier breakdowns, mean findings per case (noise), latency p50/p95, LLM calls per case.
- **Tests:** synthetic hit/miss/overlap cases.

### P8.3.2 — `driftcheck eval` and report
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P8.3.1, P8.1.1
- **Files:** `eval/report.py`, `cli.py` (`eval`), `tests/test_eval_cli.py`
- **Build:** `driftcheck eval --dataset eval/datasets/*.jsonl --split test --modes none,local,full --out eval/results/`. Needs local clones (`--repos-dir`). Writes `results-<date>.md`:
  ```
  | Mode                         | Precision | Recall | F1   | Findings/case | p50 latency |
  |------------------------------|-----------|--------|------|---------------|-------------|
  | Tier 1 only (--llm none)     | 0.93      | 0.58   | 0.71 | 0.7           | 1.1 s       |
  | + Qwen3-4B                   | 0.81      | 0.74   | 0.77 | 1.2           | 14 s        |
  | + Qwen3-4B + Nemotron verify | 0.90      | 0.71   | 0.79 | 0.9           | 19 s        |
  ```
  (numbers above are placeholders — real ones come from the run.) Also a per-repo table and the 5 best and 5 worst cases with links.
- **Tests:** eval on a tiny synthetic dataset with tmp repos.

### P8.3.3 — Eval workflow
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P8.3.2
- **Files:** `.github/workflows/eval.yml`
- **Build:** `workflow_dispatch` with input `modes`; `fast` mode on ubuntu (Tier 1); LLM modes on `[self-hosted, driftcheck-qwen]`. Uploads results as artifact.

### P8.4.1 — Run eval and tune (human)
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** P8.3.2, P4.3.3
- **Files:** `eval/results/*.md`, README results section
- **Build:** run on `dev`, tune thresholds/rules/prompts, freeze, run once on `test`, commit results. Write 3–5 bullet "what fails and why" (honest error analysis wins judges).

---

# Phase 9 — Extras that win

> **Goal:** the features competitors won't have: hand over the fix, rank by importance, remember dismissals, work offline.

## Part 9.1 — Auto-fix

### P9.1.1 — Patch generator and `--fix`
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P3.2.2, P5.1.3
- **Files:** `output/patch.py`, `cli.py` (`--fix`, `--fix-dry-run`), `tests/test_patch.py`
- **Build:** for findings with `suggested_text` (Tier 1 always when not a removal; Tier 2 only if verified `confirm`/`revise`), replace the sentence's exact character span in the file at head; group by file; produce a unified diff with `difflib.unified_diff` (`a/` `b/` prefixes, applies with `git apply`). `--fix` writes the changes to the working tree (refuses if those doc files have uncommitted changes, unless `--force`); `--fix-dry-run` prints the patch. Overlapping edits on one sentence handled by dedupe (P5.1.3).
- **Done when:** `git apply --check fix.patch` passes in tests.
- **Tests:** single/multi-file patch applies cleanly; removals produce no edits.

### P9.1.2 — "Apply suggestion" blocks in the PR comment
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P9.1.1, P6.2.3
- **Files:** `github/review.py`, `tests/test_review.py`
- **Build:** for drifted docs that **are** in the PR diff (rare but possible), post a PR review comment with a GitHub ```` ```suggestion ```` block so the author can click "Commit suggestion". Others stay in the patch.

## Part 9.2 — Severity

### P9.2.1 — Severity model refinements
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P5.1.3
- **Files:** `filters/severity.py`, `tests/test_severity.py`
- **Build:** base severity from rule; **+1 level** when the sentence is in a CODE block or a quick-start / install / getting-started page (path or heading matches `cfg.high_traffic_patterns`) — users copy-paste those; **−1 level** when in a FAQ/blog/changelog-like page. Never below INFO, never above CRITICAL.

## Part 9.3 — Dismissal memory

### P9.3.1 — `.driftignore` format and loader
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** Contracts
- **Files:** `filters/driftignore.py`, `tests/test_driftignore.py`, `.driftignore` (example)
- **Build:** TOML-ish lines, human-editable:
  ```
  # fingerprint      | rule              | symbol      | path:line (at dismissal) | reason | by | date
  3f9a1c2b7d4e5f60   R3_default_changed  --workers     docs/tuning.md:88   "doc describes recommended value, not default"  aryan  2026-11-01
  path:docs/blog/**                      # glob: never check these docs
  symbol:--legacy-mode                   # never report this symbol
  ```
  Supports fingerprint, `path:` glob, `symbol:` entries. Loader + `add()` writer.
- **Tests:** parse/write round trip; each entry type suppresses correctly.

### P9.3.2 — Dismiss from GitHub
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P9.3.1, P6.2.3
- **Files:** `.github/workflows/driftcheck-dismiss.yml`, `github/dismiss.py`, `tests/test_dismiss.py`
- **Build:** a PR comment `/driftcheck ignore D2 <reason>` by a user with write access triggers an `issue_comment` workflow that appends the fingerprint (from the last report artifact or by re-running Tier 1) to `.driftignore` and pushes a commit to the PR branch (same-repo PRs only) with the required commit trailers. Reacts 👍 on success.

## Part 9.4 — Offline mode polish

### P9.4.1 — `--llm none` guarantees
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P3.2.3
- **Files:** `tests/test_offline_guarantee.py`
- **Build:** test that runs a full check with sockets disabled (monkeypatch `socket.socket` to raise) and `NVIDIA_API_KEY` unset → completes with Tier 1 findings, zero network attempts.

## Part 9.5 — Doc gaps

### P9.5.1 — Undocumented new public options (info)
- **Priority:** 🟨 Stretch · **Owner:** 🤖 · **Depends on:** P1.4.2, P2.3.2
- **Files:** `tier1/gaps.py`, `tests/test_gaps.py`
- **Build:** when `cfg.report_gaps = true` (default false): an `ADDED` public CLI flag/env var/config key with zero mentions in docs, while sibling options of the same parser/class **are** documented → INFO finding anchored at the page where siblings are documented ("`--retries` added in cli.py:51 is not documented; siblings are documented in docs/usage.md:30–44").

---

# Phase 10 — Examples, docs, demo, ship

> **Goal:** make it obvious in 60 seconds that the tool works.

### P10.1.1 — Examples generator
- **Priority:** 🟥 MVP · **Owner:** 🤖 · **Depends on:** P7.1.1, P9.1.1
- **Files:** `scripts/make_examples.py`, `examples/*/`, `Makefile` (`examples` target), `tests/test_examples_fresh.py`
- **Build:** each example folder contains `input/` (a tiny repo snapshot: `before/`, `after/` or a `change.diff` plus docs), `run.sh` (the exact command), and **real outputs** written by the script: `output.console.txt`, `report.json`, `report.md`, `fix.patch`. Examples: `01-renamed-flag`, `02-changed-default`, `03-removed-env-var`, `04-prose-behaviour` (LLM output, generated on the laptop, committed with mode noted), `05-no-drift-refactor` (proves silence). CI test regenerates the Tier 1 examples and fails if output differs (stale examples = broken proof).
- **Done when:** `make examples` reproduces committed outputs byte-for-byte (Tier 1 ones).

### P10.1.2 — Real-world example
- **Priority:** 🟧 Core · **Owner:** 🧑 · **Depends on:** P8.4.1
- **Files:** `examples/06-real-world/`
- **Build:** one mined case from a real open-source repo: commit links, our report at the code commit, and the project's actual later doc fix side by side.

### P10.2.1 — README
- **Priority:** 🟥 MVP · **Owner:** 🧑🤖 · **Depends on:** P7.*, P8.4.1
- **Files:** `README.md`
- **Build:** sections: one-line pitch + GIF/screenshot of the PR comment · Why (the 4 drift kinds from the problem statement) · How it works (the §1 diagram) · Quick start (pip install, `driftcheck check`, `hook install`, Action snippet) · Modes table (`none`/`local`/`full`) · Models (Qwen3-4B local, Nemotron-3-Ultra-550B NIM verifier) · Results table from eval · Noise control (filter order) · Config reference link · Limitations · AI disclosure (coding agent: OpenCode with Nemotron-3-Ultra-550B, plus any other agents used).

### P10.2.2 — Docs folder (and dogfooding)
- **Priority:** 🟧 Core · **Owner:** 🤖 · **Depends on:** P10.2.1
- **Files:** `docs/configuration.md`, `docs/how-it-works.md`, `docs/local-model.md`, `docs/self-hosted-runner.md`, `.driftcheck.toml`
- **Build:** document every config key and CLI flag. **Dogfood:** DriftCheck runs on its own PRs, so renaming one of our own flags without updating `docs/configuration.md` gets flagged — show this in the demo.

### P10.3.1 — Demo script and pitch
- **Priority:** 🟥 MVP · **Owner:** 🧑 · **Depends on:** everything MVP
- **Files:** `docs/demo.md`
- **Build:** a 3-minute script:
  1. (20 s) Problem: show a real project's doc-fix commit that came days after the code change.
  2. (60 s) Live: open a PR on this repo renaming a flag + changing a default → fast check in ~1 min, sticky comment with permalinks both ways; download `fix.patch`, `git apply`, push, check turns green.
  3. (40 s) Prose drift caught by Qwen3-4B, a false candidate rejected by Nemotron (show `--debug` suppressed list).
  4. (30 s) Offline: `driftcheck check --llm none` with Wi-Fi off; `git push` triggers the pre-push hook.
  5. (30 s) Eval table: precision/recall per tier on real histories; honest failure cases.
- **Done when:** rehearsed twice; a backup screen recording exists in case the laptop runner is down.

### P10.3.2 — Release
- **Priority:** 🟧 Core · **Owner:** 🧑 · **Depends on:** P10.*
- **Files:** `CHANGELOG.md` (ours), git tag `v0.1.0`
- **Build:** final PR green on CI; tag; confirm the last commit on `main` has green `ci / test`; confirm `HACKATHON.md` untouched (guard passes).

---

## Appendix A — Prompts

Prompt version constant: `PROMPT_VERSION = "t2-v1/verify-v1"` (bump on any change; invalidates the cache).

### A.1 Tier 2 — system (`tier2_system.md`)

```
You are a meticulous documentation reviewer. You check whether specific documentation
sentences became incorrect because of a specific code change.

Rules:
- Judge ONLY the sentences marked with an ID like [S17]. Lines marked (context) are for
  understanding only.
- A sentence is "outdated" only if, after this code change, a reader following it would be
  misled: wrong name, wrong default, wrong behaviour, or a feature that no longer exists.
- General advice that is still true is "still_accurate". Sentences about something else are
  "unrelated".
- When unsure, choose "still_accurate" with low confidence. False alarms are costly.
- doc_quote must be copied EXACTLY from the sentence (the shortest span that is wrong).
- code_quote must be copied EXACTLY from the code change.
- suggested_fix is the full corrected sentence, changing as little as possible, keeping the
  original formatting (backticks, markdown).
- Output only JSON matching the schema. No explanations outside JSON.
```

### A.2 Tier 2 — user (`tier2_user.md`)

````
/no_think
CODE CHANGE [F{fact_id}]
- What: {kind} `{symbol}` — {change_type}
- Before: {old}
- After: {new}
- Where: {path}:{line}
- Help/doc text: {help_text}

Diff excerpt:
```diff
{code_snippet}
```

DOCUMENTATION SENTENCES TO JUDGE
{for each candidate:}
(context) {previous_sentence}
[{sentence_id}] ({path}, section "{heading_path}") {text}
(context) {next_sentence}

Return JSON:
{"results": [{"sentence_id": "S..", "fact_id": "F..",
  "verdict": "outdated|still_accurate|unrelated", "confidence": 0.0-1.0,
  "doc_quote": "...", "code_quote": "...", "reason": "<= 25 words",
  "suggested_fix": "... or null"}]}
````

### A.3 Verify — system (`verify_system.md`)

```
You are a senior reviewer double-checking another model's claims that documentation is
outdated. For each claim, decide:
- "confirm": the sentence is genuinely wrong after this code change, and the fix is right.
- "revise": the sentence is wrong, but the fix needs changing (give revised_fix).
- "reject": the sentence is still accurate, unrelated, or the claim misreads the code.
Be strict: reject anything speculative. Output only JSON matching the schema.
````

### A.4 Verify — user (`verify_user.md`)

```
{for each finding:}
CLAIM {finding_id}
Code change: {kind} `{symbol}` {change_type}: {old} → {new} at {path}:{line}
```diff
{code_snippet}
```
Doc ({doc_path}:{line}): "{sentence_text}"
Context: "{prev}" … "{next}"
Claimed wrong part: "{doc_quote}"
Claimed fix: "{suggested_fix}"

Return JSON:
{"results": [{"finding_id": "D..", "decision": "confirm|revise|reject",
  "confidence": 0.0-1.0, "reason": "<= 25 words", "revised_fix": "... or null"}]}
````

---

## Appendix B — Config reference

`.driftcheck.toml` (all keys optional; env override `DRIFTCHECK_<SECTION>_<KEY>`, e.g. `DRIFTCHECK_LLM_MODE=local`):

```toml
[general]
fail_on = "high"                 # critical|high|medium|low|none
report_gaps = false

[docs]
globs = ["docs/**/*.md", "docs/**/*.mdx", "docs/**/*.rst", "docs/**/*.txt", "README*"]
exclude = ["**/CHANGELOG*", "**/HISTORY*", "**/RELEASE*", "node_modules/**", ".venv/**", "site/**", "_build/**"]
high_traffic_patterns = ["quickstart", "getting-started", "install", "README"]

[code]
ignore_globs = ["tests/**", "**/migrations/**", "**/vendor/**"]
config_globs = [".env.example", "**/*.example.*", "**/config*.{yml,yaml,toml,json,ini}", "**/defaults*.*", "**/settings*.*"]

[search]
max_candidates_per_fact = 12
bm25_top_k = 5
bm25_min_score = 0.35
weak_words = ["timeout", "name", "path", "debug", "port", "host", "verbose", "config", "output", "mode"]

[llm]
mode = "none"                    # none|local|full
tier2_base_url = "http://127.0.0.1:8080/v1"
tier2_model = "qwen3-4b"         # name as served by llama.cpp / ollama ("qwen3:4b")
tier2_min_confidence = 0.6
tier2_max_sentences = 6
tier2_max_calls = 40
verify_base_url = "https://integrate.api.nvidia.com/v1"
verify_model = "nvidia/nemotron-3-ultra-550b-a55b"
verify_concurrency = 2
timeout_s = 60
cache = true

[output]
max_annotations = 25
max_findings_in_comment = 15

[hook]
llm = "none"
block_on = "none"                # none|critical|high
```

Secrets are **never** in the file: `NVIDIA_API_KEY` and `GITHUB_TOKEN` come from the environment only.

---

## Appendix C — Glossary

| Term | Meaning |
|---|---|
| **Drift** | A doc sentence that became wrong because of a code change. |
| **Fact** (`F#`) | One structured code change: symbol, kind, change type, old → new, location. |
| **Sentence** (`S#`) | One addressable unit of docs (sentence, table row, heading, or code line). |
| **Candidate** | A (fact, sentence) pair worth checking. |
| **Finding** (`D#`) | A confirmed drift with severity, quotes, fix, and links. |
| **Tier 1** | Deterministic rules, certain, no LLM. |
| **Tier 2** | Qwen3-4B judgement on prose/behaviour. |
| **Verify** | Nemotron-3-Ultra-550B (or Qwen self-check offline) confirming Tier 2 findings. |
| **Fingerprint** | Stable hash identifying a finding across runs, used by `.driftignore`. |
| **Gate** | The "does this change need a doc update?" filter on facts. |
| **Replay** | Running DriftCheck on a historical commit as if it were a PR. |
| **Mining** | Automatically finding (code commit → later doc-fix commit) pairs to evaluate on. |

---

*Built for Hacktoberfest 2026 Hack Day · Coding agent: OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM) · Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)*