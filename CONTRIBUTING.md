# Contributing to BioCosmos

First off, thank you for considering contributing to BioCosmos! It's people like you that make open source such a great community. We welcome any and all contributions.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

There are many ways to contribute to BioCosmos, from writing code and documentation to reporting bugs and suggesting new features.

### Reporting Bugs

If you find a bug, please open an issue on our [GitHub issue tracker](https://github.com/your-repo/issues). When you are creating a bug report, please include as many details as possible. Fill out the required template, the information it asks for helps us resolve issues faster.

### Suggesting Enhancements

If you have an idea for a new feature or an enhancement to an existing one, please open an issue on our [GitHub issue tracker](https://github.com/your-repo/issues). Please provide a clear and detailed explanation of the feature you are suggesting.

### Pull Requests

We welcome pull requests! If you'd like to contribute code, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix: `git checkout -b feature/your-feature-name` or `git checkout -b bugfix/your-bug-fix`.
3. Make your changes.
4. Commit your changes with a clear and descriptive commit message.
5. Push your changes to your fork.
6. Open a pull request to the `main` branch of the BioCosmos repository.

## Getting Started

To get started with local development, please refer to the **Local Development Setup** section in the [README.md](README.md) file. It provides detailed instructions on how to set up the development environment, including prerequisites and how to run the application.

## Project Structure

Here's a more detailed look at the project structure to help you navigate the codebase:

### Frontend (`src/`)

The frontend is a [Next.js](https://nextjs.org/) application.

- `src/app/`: This is where the main application pages and layouts are located. We use the Next.js App Router.
  - `src/app/api/`: API routes for the frontend.
  - `src/app/family/`, `src/app/genus/`, `src/app/species/`: Pages for the different taxonomic levels.
  - `src/app/search/`: The main search page.
  - `src/app/visualization/`: The t-SNE visualization page.
- `src/components/`: Contains all the React components used throughout the application.
- `src/lib/`: Utility functions, configuration, and other shared code.
- `public/`: Static assets like images, fonts, and icons.

**Key Files:**

- `next.config.ts`: Configuration for Next.js.
- `tailwind.config.ts`: Configuration for Tailwind CSS.
- `package.json`: Lists the frontend dependencies and scripts.

### Backend (`backend/`)

The backend is a [FastAPI](https://fastapi.tiangolo.com/) application.

- `backend/app/`: The core application code.
  - `backend/app/main.py`: The entry point for the FastAPI application.
  - `backend/app/database/`: Code for interacting with the databases (ChromaDB, DuckDB, LanceDB).
  - `backend/app/routers/`: API endpoint definitions.
  - `backend/app/searches/`: The logic for the different search modalities.
  - `backend/app/services/`: Services for machine learning models and other external services.
- `backend/unicom/`: Contains the UNICOM model for computer vision tasks.
- `backend/tests/`: Tests for the backend.

**Key Files:**

- `backend/pyproject.toml`: Lists the backend dependencies.
- `backend/Dockerfile`: The Dockerfile for the backend service.

## Coding Standards

### Frontend

- We use [ESLint](https://eslint.org/) for linting and [Prettier](https://prettier.io/) for code formatting. Please make sure to run `yarn lint` before committing your changes.
- We follow the [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript).

### Backend

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting. Please make sure to run `ruff check .` and `ruff format .` before committing your changes.
- We follow the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide for Python code.

## Testing

### Frontend

- We use [Jest](https://jestjs.io/) and [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) for testing. Please add tests for any new features or bug fixes.

### Backend

- We use [Pytest](https://docs.pytest.org/en/stable/) for testing. Please add tests for any new features or bug fixes. You can run the tests with `pytest`.

We look forward to your contributions!
