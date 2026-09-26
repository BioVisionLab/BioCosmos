# Repository Guidelines

## Project Structure & Module Organization

BioCosmos is a full-stack biodiversity image platform. The Next.js App Router frontend lives in `src/app/`; reusable React components belong in `src/components/`, and API/data helpers in `src/lib/`. Static assets and generated public metadata live under `public/`. The FastAPI service is in `backend/app/`, organized into `routers/` (HTTP endpoints), `query/` (data access), `services/` (external and ML integrations), and `database/`. Backend tests are in `backend/tests/`. Use `colharmonize`, `geoharmonize`, and scripts under `backend/scripts/` for data preparation, and `scripts/` for local launch helpers. Everything under the root `tools/` directory is outdated and unused; do not use it for data preparation or recommend it in setup instructions. `packages/` holds the Python harmonization tools (`harmonize-core`, `colharmonize`, `geoharmonize`, `instharmonize`), `morphospace`, which precomputes the dorso-ventral morphospaces of the UNICOM embeddings that the species, genus and family pages draw, `similarity`, which precomputes the visually similar species the species pages list, and `plannerbench`, which benchmarks LLMs as the agent-search planner; `reports/` holds their generated run artifacts, which are gitignored.

### Excluded families

`image_meta` is a view, not a table. The backend ingests the raw metadata into `image_meta_source` and, at every startup, publishes `image_meta` as a view without the families in `image_metadata.exclude_families` (`backend/app/configs/config.yaml`; currently Castniidae, moths imaged with the butterflies). Every reader (API queries, the derived taxonomy/locality/provenance/trait tables, `similarity`, `morphospace`, and the `analyses/` notebooks) queries `image_meta`, so excluded records never reach a query or analysis while their images and embeddings stay in place. Never point a reader at `image_meta_source`. After changing the list, restart the backend, then re-run `similarity run`, `morphospace run`/`integrate`, and the notebooks.

## Build, Test, and Development Commands

- `bun install`: install the pinned frontend dependencies.
- `bun run dev`: start Next.js with Turbopack on port 3000.
- `bun run build`: create a production frontend build and catch type/build errors.
- `bun run lint`: run ESLint over the repository, then `prettier --check .`. `bun run lint:fix` applies ESLint's fixable subset and formats with Prettier. `next lint` was removed in Next 16, so this calls the ESLint CLI against the flat config in `eslint.config.mjs`, which ends with `eslint-config-prettier` so the two never conflict.
- `bun run format` / `bun run format:check`: format, or check, the frontend with Prettier (default settings in `.prettierrc.json`). `.prettierignore` leaves out the Python side, `public/`, Markdown and CI config.
- `uv sync --all-packages`: install every member of the root uv workspace (`backend` and `packages/*`) against the single root `uv.lock`. Python 3.12+.
- `./scripts/run_backend.sh`: start FastAPI in development mode using `backend/.env`.
- `cd backend && uv run pytest -q`: run the backend suite exactly as CI does. It must run from `backend/`, which resolves `static/` relatively.
- `uv run --package <name> pytest packages/<name>/tests -q`: run one harmonization package's suite.
- `uv run colharmonize --help` / `uv run geoharmonize --help`: the harmonization CLIs, for tuning and for the CSV/plot exports. The backend harmonizes taxonomy itself at startup, so `colharmonize` is not needed for the site to work. `geoharmonize integrate` is: it writes the coordinate-validation table the backend only reads. Stop the backend before running either against the live DuckDB: DuckDB allows a single writer, so the CLI cannot attach — even read-only — while the API holds the file open. See [`reports/README.md`](reports/README.md).
- `uv run morphospace run --db <duckdb> --lance-dir <lance>`, then `uv run morphospace integrate --db <duckdb> --replace` with the backend stopped: rebuild the morphospace tables after the embeddings or the taxonomy change. See [`packages/morphospace/README.md`](packages/morphospace/README.md).
- `uv run similarity run --db <duckdb> --lance-dir <lance>` with the backend stopped: rebuild the `species_similarity` table after the embeddings or the image metadata change. See [`packages/similarity/README.md`](packages/similarity/README.md).
- `cd backend && uv run --env-file .env python scripts/migrate_lance.py` with the backend stopped: dry-run the LanceDB image-collection migration (v2 manifests, `img_path`, compaction, `img_id` BTREE index); add `--apply` to run it, `--drop-legacy-columns` to drop the stored image bytes (refused unless every image is on disk), and `--reindex` to retrain the vector indexes. Startup logs a warning while the collection needs it. `table.restore(<version>)` undoes a run for seven days.
- `cd backend && uv run python scripts/export_planner_spec.py`, then `uv run --env-file backend/.env plannerbench run -m <model> -m <model>`: compare planner models for agent search against the production prompt. Re-export the spec after changing a planner prompt or tool argument model. See [`packages/plannerbench/README.md`](packages/plannerbench/README.md).
- `docker-compose up --build`: build and run both services together.

## Coding Style & Naming Conventions

TypeScript is strict. Follow the existing two-space indentation, use `PascalCase` for React components and interfaces, `camelCase` for functions and variables, and Next.js route conventions such as `[speciesName]/page.tsx`. Prefer the `@/` alias for imports from `src/`. Python uses four spaces, `snake_case` modules/functions, and typed FastAPI/Pydantic interfaces. Run `bun run lint` (ESLint and Prettier) for frontend changes and `cd backend && uv run ruff check . && uv run ruff format --check .` for backend changes. For `packages/`, run `uv run ruff check packages/ && uv run ruff format --check packages/`; those packages use a 100-character line length and target Python 3.12. Keep route handlers thin; place reusable domain logic in `query/` or `services/`.

Never define a function inside another function in Python, and don't use a lambda to get around the rule. Make a helper a module-level function or a method, and pass state as arguments or bind it with `functools.partial`. Some nested functions predate this rule; don't add new ones.

Python must type-check with zero errors under Pyright, the engine behind Pylance, in its default `standard` mode. Check backend changes with `cd backend && uvx pyright --pythonpath ../.venv/bin/python app scripts tests`. Fix errors rather than suppress them: narrow Optionals, correct annotations, and in tests use `typing.cast` where a fake stands in for a real client. Use `# pyright: ignore[<rule>]`, naming the rule and giving the reason in a comment, only for a gap in a third-party library's typing. Never use a bare `# type: ignore`.

Always use American English spelling and usage (for example, `color`, `harmonize`, `behavior`) in code, identifiers, comments, docstrings, UI copy, documentation, and commit or PR text.

## Testing Guidelines

Pytest is the active test framework. Name files `test_<feature>.py`, keep shared fixtures in `backend/tests/conftest.py`, and add regression coverage for changed routers, queries, or services. CI runs the backend and `packages/` suites for changes under `backend/**`, `packages/**`, or the root `pyproject.toml`/`uv.lock`; there is no configured frontend test harness or coverage threshold, so at minimum run lint and build for UI work and describe manual verification in the PR.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects such as `Fix image rendering.` and `Reduce caching.` Keep each commit focused and avoid mixing generated datasets with code changes. PRs should explain the problem and solution, link relevant issues, list commands run, and include screenshots for visible UI changes. Never commit `.env`, `.env.local`, API keys, local DuckDB/LanceDB files, model artifacts, bulk images, or anything generated under `reports/`.

## Git Restrictions for Agents

Agents must not stage changes or create, amend, or otherwise write commits. Do not run commands such as `git add`, `git commit`, or `git commit --amend`, even when requested as part of a larger task. Agents may use read-only Git commands such as `git status`, `git diff`, and `git log` to inspect and report repository state. Leave all working-tree changes unstaged for the user to review and commit.
