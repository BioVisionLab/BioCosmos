# Contributing to BioCosmos

First off, thank you for considering contributing to BioCosmos! It's people like you that make open source such a great community. We welcome any and all contributions.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

There are many ways to contribute to BioCosmos, from writing code and documentation to reporting bugs and suggesting new features.

- **Reporting Bugs:** If you find a bug, please open an issue on our GitHub issue tracker.
- **Suggesting Enhancements:** If you have an idea for a new feature, open an issue to discuss it.
- **Pull Requests:** We welcome pull requests! Please follow the steps below.

## Development Environment Setup

To get started with local development, you'll need to set up both the frontend and backend environments.

### 1. Fork and Clone the Repository

First, fork the repository on GitHub, then clone it to your local machine:

```bash
git clone https://github.com/your-username/BioCosmos.git
cd BioCosmos
```

### 2. Frontend Setup (Next.js)

The frontend is a [Next.js](https://nextjs.org/) application. We use `fnm` to manage Node.js versions and `yarn` for package management.

**A. Install and Set Up `fnm`**

If you don't have `fnm` (Fast Node Manager) installed, you can install it using the instructions in its [repository](https://github.com/Schniz/fnm).

Once `fnm` is installed, use it to install and use the Node.js version specified in the `.nvmrc` or `.node-version` file (if present), or the latest LTS version.

Briefly, you can install `fnm` and `Node.js` using the following command:

```bash
# installs fnm (Fast Node Manager)
curl -fsSL https://fnm.vercel.app/install | bash

# activate fnm
source ~/.bashrc

# download and install Node.js
fnm use --install-if-missing 22

# verifies the correct Node.js version is in the environment
node -v # should print `v22.11.0`

# verifies the correct npm version is in the environment
npm -v # should print `10.9.0`
```

Follow the instructions on the [Node.js website](https://nodejs.org/en/download/) for other installation methods.

#### B. Install Dependencies with `yarn`

With the correct Node.js version active, install the frontend dependencies using `yarn`.

```bash
# Install yarn if you don't have it
corepack enable

# Install project dependencies
yarn install
```

### 3. Backend Setup (FastAPI)

The backend is a [FastAPI](https://fastapi.tiangolo.com/) application. We use `uv` for Python package management.

#### A. Install `uv`

If you don't have `uv`, you can install it with:

```bash
pip install uv
```

### B. Create a Virtual Environment and Install Dependencies**

From the `backend` directory, create a virtual environment and install the dependencies listed in `pyproject.toml`.

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cd ..
```

## Running the Application

The easiest way to run the full application stack for development is using Docker Compose.

```bash
docker-compose up --build
```

This command will build the images for the frontend and backend services and start the containers.

- The frontend will be available at [http://localhost:3000](http://localhost:3000).
- The backend API will be available at [http://localhost:8000](http://localhost:8000).

## Project Structure

- **`src/`**: The Next.js frontend application.
  - `src/app/`: Main application pages and layouts (App Router).
  - `src/components/`: Shared React components.
  - `src/lib/`: Utility functions, configurations, and shared code.
- **`backend/`**: The FastAPI backend application.
  - `backend/app/`: Core application code (main entrypoint, routers, services).
  - `backend/tests/`: Tests for the backend.
- **`tools/`**: Standalone scripts for data processing and other tasks.

## Coding Standards

### Frontend

- We use [ESLint](https://eslint.org/) for linting. Please run `yarn lint` before committing.
- Code is formatted automatically on commit using pre-commit hooks.

### Backend

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.
- Please run `ruff check .` and `ruff format .` in the `backend` directory before committing.

## Testing

### Frontend Tests

- We use [Playwright](https://playwright.dev/) for end-to-end testing. Please add tests for any new features or bug fixes.

### Backend Tests

- We use [Pytest](https://docs.pytest.org/en/stable/). Run tests from the `backend` directory: `pytest`. Please add tests for any new contributions.

We look forward to your contributions!
