# Repository Guidelines

## Project Structure & Module Organization

BioCosmos is a full-stack biodiversity image platform. The Next.js App Router frontend lives in `src/app/`; reusable React components belong in `src/components/`, and API/data helpers in `src/lib/`. Static assets and generated public metadata live under `public/`. The FastAPI service is in `backend/app/`, organized into `routers/` (HTTP endpoints), `query/` (data access), `services/` (external and ML integrations), and `database/`. Backend tests are in `backend/tests/`. Use `tools/` for offline data-processing utilities and `scripts/` for local launch helpers.

## Build, Test, and Development Commands

- `bun install`: install the pinned frontend dependencies.
- `bun run dev`: start Next.js with Turbopack on port 3000.
- `bun run build`: create a production frontend build and catch type/build errors.
- `bun run lint`: run the configured Next.js/TypeScript ESLint checks.
- `cd backend && uv sync --dev`: install Python 3.10+ runtime and test dependencies.
- `./scripts/run_backend.sh`: start FastAPI in development mode using `backend/.env`.
- `cd backend && uv run pytest -q`: run the backend suite exactly as CI does.
- `docker-compose up --build`: build and run both services together.

## Coding Style & Naming Conventions

TypeScript is strict. Follow the existing two-space indentation, use `PascalCase` for React components and interfaces, `camelCase` for functions and variables, and Next.js route conventions such as `[speciesName]/page.tsx`. Prefer the `@/` alias for imports from `src/`. Python uses four spaces, `snake_case` modules/functions, and typed FastAPI/Pydantic interfaces. Run ESLint for frontend changes and `cd backend && uv run ruff check . && uv run ruff format --check .` for backend changes. Keep route handlers thin; place reusable domain logic in `query/` or `services/`.

## Testing Guidelines

Pytest is the active test framework. Name files `test_<feature>.py`, keep shared fixtures in `backend/tests/conftest.py`, and add regression coverage for changed routers, queries, or services. CI runs backend tests for changes under `backend/**`; there is no configured frontend test harness or coverage threshold, so at minimum run lint and build for UI work and describe manual verification in the PR.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects such as `Fix image rendering.` and `Reduce caching.` Keep each commit focused and avoid mixing generated datasets with code changes. PRs should explain the problem and solution, link relevant issues, list commands run, and include screenshots for visible UI changes. Never commit `.env`, `.env.local`, API keys, local DuckDB/LanceDB files, model artifacts, or bulk images.

## Git Restrictions for Agents

Agents must not stage changes or create, amend, or otherwise write commits. Do not run commands such as `git add`, `git commit`, or `git commit --amend`, even when requested as part of a larger task. Agents may use read-only Git commands such as `git status`, `git diff`, and `git log` to inspect and report repository state. Leave all working-tree changes unstaged for the user to review and commit.
