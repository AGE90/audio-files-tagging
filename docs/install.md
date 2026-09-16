# Audio Files Tagging Installation Guide

Welcome to the **Audio Files Tagging (AFT)** project installation guide! This guide walks you through setting up the environment and installing dependencies.

---

## Prerequisites

- **Python**: Version >= 3.12
- **uv**: Latest version (for dependency management)

To install uv, follow the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

---

## 1. Clone and Set Up the Project

```bash
git clone <repository-url>
cd audio-files-tagging
```

---

## 2. Install Dependencies with uv

`uv sync` creates a virtual environment (`.venv`) and installs all dependencies (including dev tools like black, ruff, mypy) from `pyproject.toml`/`uv.lock`:

```bash
uv sync
```

### Adding a Dependency

```bash
uv add <package-name>
```

### Adding a Dev-Only Dependency

```bash
uv add --dev <package-name>
```

---

## 3. Run Commands in the Environment

Prefix any command with `uv run` to execute it inside the project's virtual environment, without activating it manually:

```bash
uv run python -m aft.scripts.ingest --help
```

To activate the environment directly instead:

```bash
source .venv/bin/activate   # macOS/Linux
.\.venv\Scripts\activate    # Windows
```

---

## 4. Configure Discogs API (Optional)

Metadata enrichment via Discogs requires a user token. Get one from https://www.discogs.com/settings/developers, then create a `.env` file in the project root:

```
DISCOGS_USER_TOKEN=your_token_here
```

This is loaded automatically via `python-dotenv` (see `aft.credentials`).

---

## 5. Testing

Run the test suite using pytest (configured via `pyproject.toml` to always run with coverage on `src`):

```bash
uv run pytest tests/ -v
```

---

## 6. Lint, Format, Type-Check

```bash
uv run ruff check src tests
uv run black src tests
uv run mypy src
```

---

## Final Notes

- Always use `uv run` to execute commands within the project's virtual environment (or activate it directly).
- There is no `aft` console command — invoke via `python -m aft.scripts.*` (see `CLAUDE.md`).
- Check `pyproject.toml` for the full dependency list.
