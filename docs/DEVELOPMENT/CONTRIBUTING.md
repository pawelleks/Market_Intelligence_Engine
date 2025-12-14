# Contributing to Market Intelligence Engine (MIE)

## 1. Development Principles

-   **Offline First**: All analytics (Markov, HMM) must be pre-computable. The UI reads static artifacts (Parquet/JSON).
-   **Dockerized**: Run everything via Docker Compose.
-   **Clean Code**: Use `black` formatting and strict typing (`mypy`).

## 2. Pull Request Process

1.  **Branching**: Use `feat/description` or `fix/description`.
2.  **Testing**: Run `pytest` before submitting.
3.  **Docs**: Update relevant documentation in `docs/` if you change architecture or API.

## 3. Style Guide

-   **Python**: PEP8, strict type hints.
-   **React**: Functional components, strict TypeScript.
-   **Commits**: Conventional Commits (e.g., `feat: add new signal scanner`).

## 4. Coding Agents

If you are an AI coding agent:
-   Read `docs/CORE/ARCHITECT_BIBLE.md` first.
-   Respect the "Offline First" constraint.
-   Do not modify `_deprecated_v1` files.
