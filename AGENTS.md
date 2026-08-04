# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python teaching project that builds a university-services RAG pipeline in ten stages. Implement task logic in `src/task1_*.py` through `src/task10_*.py`; later tasks compose earlier retrieval, reranking, and generation modules. `app.py` is the Streamlit chat interface. Raw documents belong under `data/landing/{legal,news}/`, and converted Markdown belongs under `data/standardized/{legal,news}/`. Automated grading lives in `tests/test_individual.py`. Group evaluation assets are under `group_project/evaluation/`, while `README.md` and `LAB_GUIDE.md` define deliverables and checkpoints.

## Build, Test, and Development Commands

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Use `pytest tests/ -v` for the full task suite, or target one stage with `pytest tests/test_individual.py::TestTask5 -v`. Run task modules from the repository root, for example `python -m src.task3_convert_markdown`, so relative imports resolve correctly. Start the UI with `streamlit run app.py`. Run the optional evaluation pipeline with `python -m group_project.evaluation.eval_pipeline` after implementing one supported framework.

## Coding Style & Naming Conventions

Follow the existing PEP 8-style Python: four-space indentation, `snake_case` functions and variables, `UPPER_SNAKE_CASE` configuration constants, and `PascalCase` test classes. Keep public function signatures and result dictionaries compatible with the tests. Add type hints and short docstrings to pipeline-facing functions. Preserve the task-based filenames (`taskN_description.py`) and avoid introducing abstractions that span tasks unless they remove clear duplication. No formatter or linter is configured; keep imports grouped standard-library first, then third-party, then local.

## Testing Guidelines

Tests use `unittest.TestCase` assertions and are collected by pytest. Add behavior-focused methods named `test_<expected_behavior>` to the matching `TestTaskN` class. Test both return structure and meaningful content, while isolating network/API behavior where possible. There is no formal coverage threshold; passing all relevant task tests is the baseline.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive subjects, usually in Vietnamese, with occasional prefixes such as `docs:`. Use an imperative summary focused on one change, for example `docs: clarify Task 8 fallback setup`. Pull requests should explain the affected tasks, list validation commands and results, link the issue or lab requirement, and include screenshots for Streamlit UI changes. Call out API-dependent or skipped checks explicitly.

## Security & Configuration

Copy `.env.example` to `.env` and supply only the keys needed locally. Never commit `.env`, API keys, generated caches, `chroma_db/`, or temporary conversion outputs. Prefer environment variables for OpenRouter, OpenAI, Gemini, PageIndex, and Jina credentials.
