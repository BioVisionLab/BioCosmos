# plannerbench

Compare language models as the planner for BioCosmos agent search
(`GET /search/agent`). A query such as _"blue from brazil"_ becomes tool calls
for color and location (`search_by_color` and `search_by_location(BR)`). The
backend executes those calls, so their accuracy and consistency determine the
search results.

`plannerbench` sends the production planner request to OpenAI-compatible models
and grades their returned tool calls. It needs an LLM endpoint, but no database,
embedding model, or running backend.

## Production request

The backend exports the exact request it sends to the planner: the router system
prompt, the tool definitions generated from its typed argument models,
`tool_choice`, `max_tokens`, and the timeout. The benchmark reads that export
and applies the same validation as the backend's `parse_tool_calls`. Unknown
tools, arguments that cannot be decoded or fail schema validation, and duplicate
calls to a tool are invalid.

```bash
cd backend
uv run python scripts/export_planner_spec.py
cd ..
# Writes reports/planner/planner_spec.json
```

Re-export after changing a planner prompt in `backend/app/configs/prompts/` or a
tool argument model. Each run records the spec fingerprint. Compare model
results across runs only when the fingerprints match.

## Usage

Run from the repository root. Sync the workspace, then use `uv run` to select
its environment and `--env-file backend/.env` to load the endpoint settings. If
another virtual environment is active, prefix the commands with
`env -u VIRTUAL_ENV` to use the root `.venv`.

```bash
uv sync --all-packages

# Compare models on the UF endpoint
uv run --env-file backend/.env plannerbench run \
    -m mistral-small-3.1 \
    -m gemma-4-31b-it \
    -m gpt-oss-20b \
    -m meta-muse-glimmer-30b \
    -m nemotron-3-nano-30b-a3b \
    --repeats 5

# A subset of cases, one repeat, greedy decoding
uv run --env-file backend/.env plannerbench run -m gemma-4-31b-it \
    --case color-country --case similar-common-name -n 1 --temperature 0

uv run plannerbench cases
uv run plannerbench run --help
```

Set `LLM_API_URL` and `LLM_API_KEY` in `backend/.env`, or use the options below
to select another endpoint and key variable.

| Option                 | Default                             | Meaning                                                       |
| ---------------------- | ----------------------------------- | ------------------------------------------------------------- |
| `-m/--model`           | required                            | Model ID; repeat to compare several                           |
| `--spec`               | `reports/planner/planner_spec.json` | Exported planner spec                                         |
| `--cases`              | packaged `cases.toml`               | Case file                                                     |
| `--case`               | all                                 | Run only these case IDs                                       |
| `-n/--repeats`         | 5                                   | Calls per case and model; needed to measure consistency       |
| `-j/--concurrency`     | 4                                   | Requests in flight, at most 10                                |
| `--rpm`                | 100                                 | Request budget per minute across all calls; 0 disables pacing |
| `--rate-limit-retries` | 3                                   | Retries for an HTTP 429 before it counts as an error          |
| `--temperature`        | provider default                    | The backend sets none, so the default matches production      |
| `--base-url`           | `$LLM_API_URL`                      | OpenAI-compatible endpoint                                    |
| `--api-key-env`        | `LLM_API_KEY`                       | Variable holding the key. The key is never written out        |
| `--max-retries`        | 0                                   | Client retries; 0 records provider failures as errors         |
| `--no-write`           |                                     | Print only, do not save the run                               |

Requests are interleaved by model within each case and repeat to reduce bias
from changing endpoint load. The API credentials must allow access to every
requested model. Access failures are recorded as benchmark errors and should be
checked before interpreting accuracy.

The default `--rpm 100` spaces calls 0.6 seconds apart. Adjust pacing and
concurrency to your endpoint's limits, allowing for backend requests if it
shares the key. HTTP 429 responses are retried using `Retry-After` or
exponential backoff, up to `--rate-limit-retries`; latency covers only the final
attempt. Eighteen cases × five repeats × three models require 270 calls, or
about 2.7 minutes at the default request rate before accounting for latency and
retries.

## Metrics

| Metric                      | Meaning                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------ |
| accuracy                    | Correct trials over all trials. An API error counts as a miss                                    |
| consistent                  | Cases where every repeat succeeded with the same accepted plan                                   |
| no-tool                     | Successful responses with no valid tool call. The backend then falls back to a plain text search |
| invalid                     | Share of returned tool calls the backend would reject                                            |
| errors                      | Failed requests: timeouts, HTTP errors, empty responses                                          |
| p50 / p95 / max             | Planner latency of successful calls                                                              |
| prompt / completion / total | Tokens consumed by successful calls, as reported by the provider                                 |

The summary includes a per-case table. `--misses`, enabled by default, prints
incorrect plans, invalid arguments, and request errors.

## Cases

[`src/plannerbench/resources/cases.toml`](src/plannerbench/resources/cases.toml)
lists each query with every plan that counts as correct. A trial is correct when
its valid tool calls match one accepted plan exactly. Missing or extra tools
make the trial incorrect. Argument expectations can be an exact value
(case-insensitive), a list of alternatives, `"*"` for any supplied value, or
`"-"` for an omitted argument. Include `"-"` in a list to allow omission as an
alternative.

Only listed arguments are checked. To reject an argument the model should omit,
specify `"-"`. This case allows `state_province` to be `"Amazonas"` or omitted,
while rejecting other values:

```toml
[[cases]]
id = "adm1-not-city"
query = "butterflies near Manaus"
accept = [
  { search_by_location = { country = "BR", state_province = ["Amazonas", "-"] } },
]
```

Use `--cases` to supply a custom case file.

## Output

Each run saves outputs to `reports/planner/<run_id>/` and updates
`reports/latest.json` by default. Pass `--no-write` to print results without
saving them. See the [report format](../../reports/README.md).

- `run.json`: the manifest, with settings, spec fingerprint, and per-model
  summaries.
- `trials.jsonl`: one line per call, with the raw and validated tool calls,
  latency, tokens, and any text the model returned instead of calling a tool.

## Development

```bash
uv run --package plannerbench pytest packages/plannerbench/tests -q
```

The tests use a scripted fake client and make no network calls.
