# plannerbench

Benchmark language models as the tool-calling planner for BioCosmos agentic search (`GET /search/agent`).

When a user searches for a phrase like *"blue from brazil"*, the planner translates the query into structured tool calls (`search_by_color` and `search_by_location(country="BR")`). `plannerbench` sends the exact production system prompt and tool schemas to OpenAI-compatible models and grades their returned tool plans against curated test cases. It requires an LLM API endpoint, but no database, embeddings, or running backend.

## 1. Export the Production Planner Spec

The benchmark reads `reports/planner/planner_spec.json`, which captures the backend's router prompt, Pydantic-generated tool schemas, `tool_choice`, `max_tokens`, and timeout. Export (or re-export after editing `backend/app/configs/prompts/` or tool argument models):

```bash
cd backend
uv run python scripts/export_planner_spec.py
cd ..
```

Each benchmark run records the spec's SHA-256 fingerprint so runs are only compared when evaluated against the exact same prompt and tool definitions.

## 2. Run the Benchmark

Run from the repository root using `--env-file backend/.env` to load `LLM_API_URL` and `LLM_API_KEY` (prefix with `env -u VIRTUAL_ENV` if another virtualenv is active):

```bash
uv sync --all-packages

# Compare candidate models across 5 repeats per test case
uv run --env-file backend/.env plannerbench run \
    -m mistral-small-3.1 \
    -m gemma-4-31b-it \
    -m gpt-oss-20b \
    -m meta-muse-glimmer-30b \
    -m nemotron-3-nano-30b-a3b \
    --repeats 5

# Run specific test cases with a single repeat and temperature 0
uv run --env-file backend/.env plannerbench run -m gemma-4-31b-it \
    --case color-country --case similar-common-name -n 1 --temperature 0

# List all packaged benchmark cases
uv run plannerbench cases
```

### CLI Options (`plannerbench run`)

| Option | Default | Description |
| :--- | :--- | :--- |
| `-m`, `--model` | required | Model ID to evaluate (repeat `-m` to compare multiple models) |
| `--spec` | `reports/planner/planner_spec.json` | Exported production planner specification |
| `--cases` | packaged `cases.toml` | Benchmark test-case TOML file |
| `--case` | all cases | Filter to specific case IDs (repeatable) |
| `-n`, `--repeats` | `5` | Trials per case and model (measures plan consistency) |
| `-j`, `--concurrency` | `4` | Maximum concurrent requests in flight (`1`–`10`) |
| `--rpm` | `100` | Request rate limit per minute across all calls (`0` disables pacing) |
| `--rate-limit-retries` | `3` | Automatic retries on HTTP `429` (`Retry-After` / exponential backoff) |
| `--temperature` | provider default | Sampling temperature (omitted by default to match production) |
| `--base-url` | `$LLM_API_URL` | OpenAI-compatible API base URL |
| `--api-key-env` | `LLM_API_KEY` | Environment variable name holding the API key (never written to disk) |
| `--max-retries` | `0` | OpenAI client retries (`0` records provider failures directly) |
| `--write / --no-write` | `--write` | Save run artifacts under `reports/planner/<run_id>/` |
| `--misses / --no-misses` | `--misses` | Print failed plans, invalid arguments, and request errors |

Requests are interleaved across models within each case and repeat to minimize bias from fluctuating endpoint load.

## 3. Metrics

| Metric | Meaning |
| :--- | :--- |
| `accuracy` | Share of trials producing an accepted tool plan (API errors count as misses) |
| `consistent` | Share of cases where all repeats succeeded with the same accepted plan |
| `no-tool` | Successful responses with no valid tool call (triggers text-search fallback in production) |
| `invalid` | Share of returned tool calls rejected by `parse_tool_calls` (unknown tool, bad JSON/schema, or duplicate tool call) |
| `errors` | Failed API requests (timeouts, HTTP errors, empty responses) |
| `p50 / p95 / max` | Latency distribution across successful calls |
| `prompt / completion / total` | Token usage across successful calls as reported by the provider |

## 4. Test Cases (`cases.toml`)

[`src/plannerbench/resources/cases.toml`](src/plannerbench/resources/cases.toml) defines each natural-language query and the list of tool plans (`accept`) that count as correct. A trial passes when its validated tool calls match one accepted plan with no missing or extra tools:

- **Exact string** (case-insensitive): `"BR"`
- **List of allowed values**: `["Amazonas", "-"]`
- **Wildcard (`"*"`)**: Any non-empty argument value is accepted
- **Omitted (`"-"`)**: The argument must be omitted (or may be omitted when included in a list)

```toml
[[cases]]
id = "adm1-not-city"
query = "butterflies near Manaus"
accept = [
  { search_by_location = { country = "BR", state_province = ["Amazonas", "-"] } },
]
```

## 5. Outputs

Each saved run writes two files to `reports/planner/<run_id>/` and updates `reports/latest.json` (see [`reports/README.md`](../../reports/README.md) and [`analyses/notebooks/model_performance.ipynb`](../../analyses/notebooks/model_performance.ipynb)):

- `run.json`: Run settings, spec fingerprint, and aggregate per-model metrics.
- `trials.jsonl`: One JSON record per trial containing raw and validated tool calls, latency, token counts, and any fallback text.

## Development

```bash
uv run --package plannerbench pytest packages/plannerbench/tests -q
uv run ruff check packages/plannerbench && uv run ruff format --check packages/plannerbench
```
