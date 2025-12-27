# Audio Files Tagging Installation Guide

Welcome to the **Audio Files Tagging (AFT)** project installation guide! This guide will walk you through setting up the environment, installing necessary dependencies, and configuring essential tools to ensure a smooth development experience.

---

## Prerequisites

Make sure you have the following installed before proceeding:

- **Python**: Version >= 3.9
- **Poetry**: Latest version (for dependency management)

To install Poetry, follow the [official installation guide](https://python-poetry.org/docs/#installation).

---

## 1. Clone and Set Up the Project

First, clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd {{ cookiecutter.project_slug }}
```

---

## 2. Install Dependencies with Poetry

Poetry will automatically create a virtual environment and install all dependencies. Run the following command in your project root:

```bash
poetry install
```

This will install all dependencies defined in `pyproject.toml`, including:

- Core dependencies
- Development tools (black, ruff, mypy, etc.)

### Optional: Install Specific Groups

You can install specific dependency groups if needed:

```bash
# Install only development dependencies
poetry install --with dev
```

### Installing Additional Libraries

If you need to install additional libraries, you can do so with:

```bash
poetry add <package-name>
```

---

## 3. Activate the Poetry Environment

To activate the Poetry virtual environment:

```bash
poetry env activate
```

Or run commands directly using:

```bash
poetry run <command>
```

---

## 4. Set Up Development Tools

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
poetry run pre-commit install
```

### Jupyter and JupyterLab

If you plan to use Jupyter notebooks, install the notebook group:

```bash
poetry install --with notebook
```

To launch JupyterLab:

```bash
poetry run jupyter lab
```

---

## 6. Managing Project Tasks with Invoke

We use **[Invoke](http://www.pyinvoke.org/)** as a task runner for common project management tasks.

### List Available Tasks

```bash
poetry run invoke -l
```

### Get Help on a Specific Task

```bash
poetry run invoke --help <task-name>
```

### Adding Custom Tasks

To add your own tasks, edit the `tasks.py` file in your project root.

---

## 7. Testing

Run the test suite using pytest:

```bash
poetry run pytest
```

For coverage reports:

```bash
poetry run pytest --cov=src
```

---

## 8. Documentation

Build the documentation:

```bash
poetry run mkdocs build
```

Serve the documentation locally:

```bash
poetry run mkdocs serve
```

---

## Final Notes

- Always use `poetry run` to execute commands within the project's virtual environment
- Use `poetry add <package>` to add new dependencies
- Use `poetry update` to update dependencies
- Check `pyproject.toml` for all available dependency groups and their purposes

You're now all set to start developing with **{{ cookiecutter.project_name }}**!
