# plannerbench

Benchmark language models as the planner behind BioCosmos agent search
(`GET /search/agent`). The planner turns a query such as *"blue from brazil"*
into tool calls (`search_by_color` + `search_by_location(BR)`). The backend
runs those tools, so a wrong or missing call gives wrong results, and a
different plan for the same query gives inconsistent ones.

`plannerbench` replays the **production** planner request against any
OpenAI-compatible model and grades the tool calls it returns. No database,
embedding model, or running backend is needed.

## How it stays faithful to production

The backend exports the exact request it sends to the planner: the router
system prompt, the tool definitions generated from its typed argument models,
`tool_choice`, `max_tokens`, and the timeout. The benchmark reads that export
and validates tool calls the same way the backend's `parse_tool_calls` does.
Unknown tools, undecodable or schema-invalid arguments, and repeat calls to a
tool all count as invalid.

```bash
cd backend && uv run python scripts/export_planner_spec.py
# -> reports/planner/planner_spec.json
```

Re-export after changing a prompt in `backend/app/configs/prompts/` or a tool
argument model. Each run records the spec fingerprint, so two runs are
comparable only when their fingerprints match.

## Running

```bash
uv sync --all-packages

# Compare models on the UF endpoint (credentials from backend/.env)
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

uv run plannerbench cases        # list the packaged cases
uv run plannerbench run --help
```

| Option | Default | Meaning |
| --- | --- | --- |
| `-m/--model` | required | Model id; repeat to compare several |
| `--spec` | `reports/planner/planner_spec.json` | Exported planner spec |
| `--cases` | packaged `cases.toml` | Case file |
| `--case` | all | Run only these case ids |
| `-n/--repeats` | 3 | Calls per case and model; needed to measure consistency |
| `-j/--concurrency` | 4 | Requests in flight. Latency grows with load on a shared endpoint |
| `--temperature` | provider default | The backend sets none, so the default matches production |
| `--base-url` | `$LLM_API_URL` | OpenAI-compatible endpoint |
| `--api-key-env` | `LLM_API_KEY` | Variable holding the key. The key is never written out |
| `--max-retries` | 0 | Off, so provider failures count as errors instead of hiding in latency |
| `--no-write` | | Print only, do not save the run |

Models are interleaved within each case and repeat, so load changes on the
shared endpoint affect every model alike. The configured API team must be
authorized for every requested model; authorization failures are recorded as
benchmark errors rather than model-quality results.

## Metrics

| Metric | Meaning |
| --- | --- |
| accuracy | Correct trials over all trials. An API error counts as a miss |
| consistent | Cases where every repeat succeeded with the same accepted plan |
| no-tool | Successful responses with no valid tool call. The backend then falls back to a plain text search |
| invalid | Share of returned tool calls the backend would reject |
| errors | Failed requests: timeouts, HTTP errors, empty responses |
| p50 / p95 / max | Planner latency of successful calls |
| prompt / completion / total | Tokens consumed by successful calls, as reported by the provider |

A per-case table follows, and `--misses` (on by default) prints every wrong
plan, invalid argument, and error.

## Cases

[`src/plannerbench/resources/cases.toml`](src/plannerbench/resources/cases.toml)
lists each query with every plan that counts as correct. A trial is correct
when its valid tool calls match one plan exactly: a missing tool and an extra
tool are both wrong. Argument values can be exact (case-insensitive), a list of
alternatives, or `"*"` for "present with any value":

```toml
[[cases]]
id = "descriptive-country"
query = "owl-like butterfly from brazil"
accept = [
  { search_by_color = {}, search_by_location = { location = "BR" } },
  { search_by_image_similarity = { reference_species = ["Caligo", "Caligo eurilochus"] }, search_by_location = { location = "BR" } },
]
```

Pass your own file with `--cases`.

## Output

With `--write` (the default) each run goes to `reports/planner/<run_id>/`, and
`reports/latest.json` points to it (see [`reports/README.md`](../../reports/README.md)):

- `run.json`: the manifest, with settings, spec fingerprint, and per-model summaries.
- `trials.jsonl`: one line per call, with the raw and validated tool calls,
  latency, tokens, and any text the model returned instead of calling a tool.

## Tests

```bash
uv run --package plannerbench pytest packages/plannerbench/tests -q
```

The tests use a scripted fake client and make no network calls.
