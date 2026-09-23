# Repository Guidelines

## Project Structure & Module Organization

BioCosmos is a full-stack biodiversity image platform. The Next.js App Router frontend lives in `src/app/`; reusable React components belong in `src/components/`, and API/data helpers in `src/lib/`. Static assets and generated public metadata live under `public/`. The FastAPI service is in `backend/app/`, organized into `routers/` (HTTP endpoints), `query/` (data access), `services/` (external and ML integrations), and `database/`. Backend tests are in `backend/tests/`. Use `colharmonize`, `geoharmonize`, and scripts under `backend/scripts/` for data preparation, and `scripts/` for local launch helpers. Everything under the root `tools/` directory is outdated and unused; do not use it for data preparation or recommend it in setup instructions. `packages/` holds the Python harmonization tools (`harmonize-core`, `colharmonize`, `geoharmonize`, `instharmonize`) and `plannerbench`, which benchmarks LLMs as the agent-search planner; `reports/` holds their generated run artifacts, which are gitignored.

## Build, Test, and Development Commands

- `bun install`: install the pinned frontend dependencies.
- `bun run dev`: start Next.js with Turbopack on port 3000.
- `bun run build`: create a production frontend build and catch type/build errors.
- `bun run lint`: run ESLint over the repository (`bun run lint:fix` applies the fixable subset). `next lint` was removed in Next 16, so this calls the ESLint CLI against the flat config in `eslint.config.mjs`.
- `uv sync --all-packages`: install every member of the root uv workspace (`backend` and `packages/*`) against the single root `uv.lock`. Python 3.12+.
- `./scripts/run_backend.sh`: start FastAPI in development mode using `backend/.env`.
- `cd backend && uv run pytest -q`: run the backend suite exactly as CI does. It must run from `backend/`, which resolves `static/` relatively.
- `uv run --package <name> pytest packages/<name>/tests -q`: run one harmonization package's suite.
- `uv run colharmonize --help` / `uv run geoharmonize --help`: the harmonization CLIs, for tuning and for the CSV/plot exports. The backend harmonizes taxonomy itself at startup, so `colharmonize` is not needed for the site to work. `geoharmonize integrate` is: it writes the coordinate-validation table the backend only reads. Stop the backend before running either against the live DuckDB: DuckDB allows a single writer, so the CLI cannot attach — even read-only — while the API holds the file open. See [`reports/README.md`](reports/README.md).
- `cd backend && uv run python scripts/export_planner_spec.py`, then `uv run --env-file backend/.env plannerbench run -m <model> -m <model>`: compare planner models for agent search against the production prompt. Re-export the spec after changing a planner prompt or tool argument model. See [`packages/plannerbench/README.md`](packages/plannerbench/README.md).
- `docker-compose up --build`: build and run both services together.

## Coding Style & Naming Conventions

TypeScript is strict. Follow the existing two-space indentation, use `PascalCase` for React components and interfaces, `camelCase` for functions and variables, and Next.js route conventions such as `[speciesName]/page.tsx`. Prefer the `@/` alias for imports from `src/`. Python uses four spaces, `snake_case` modules/functions, and typed FastAPI/Pydantic interfaces. Run ESLint for frontend changes and `cd backend && uv run ruff check . && uv run ruff format --check .` for backend changes. For `packages/`, run `uv run ruff check packages/ && uv run ruff format --check packages/`; those packages use a 100-character line length and target Python 3.12. Keep route handlers thin; place reusable domain logic in `query/` or `services/`.

## Testing Guidelines

Pytest is the active test framework. Name files `test_<feature>.py`, keep shared fixtures in `backend/tests/conftest.py`, and add regression coverage for changed routers, queries, or services. CI runs the backend and `packages/` suites for changes under `backend/**`, `packages/**`, or the root `pyproject.toml`/`uv.lock`; there is no configured frontend test harness or coverage threshold, so at minimum run lint and build for UI work and describe manual verification in the PR.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects such as `Fix image rendering.` and `Reduce caching.` Keep each commit focused and avoid mixing generated datasets with code changes. PRs should explain the problem and solution, link relevant issues, list commands run, and include screenshots for visible UI changes. Never commit `.env`, `.env.local`, API keys, local DuckDB/LanceDB files, model artifacts, bulk images, or anything generated under `reports/`.

## Git Restrictions for Agents

Agents must not stage changes or create, amend, or otherwise write commits. Do not run commands such as `git add`, `git commit`, or `git commit --amend`, even when requested as part of a larger task. Agents may use read-only Git commands such as `git status`, `git diff`, and `git log` to inspect and report repository state. Leave all working-tree changes unstaged for the user to review and commit.
