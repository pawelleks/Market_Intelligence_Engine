Why ---
title: Contributing Guide
version: 1.0.0
last_updated: 2025-11-14
status: active
owner: development
---

# Contributing to Market Intelligence Engine

Thank you for your interest in contributing to the Market Intelligence Engine (MIE)! This guide outlines the process for contributing code, documentation, and other improvements.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Code Standards](#code-standards)
4. [Commit Conventions](#commit-conventions)
5. [Testing Requirements](#testing-requirements)
6. [Pull Request Process](#pull-request-process)
7. [Documentation](#documentation)
8. [Project Architecture](#project-architecture)

---

## Getting Started

### Prerequisites

- Python 3.10+ (currently using 3.13)
- Git
- Virtual environment tool (venv, conda, etc.)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Market_Intelligence_Engine
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   # or
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -U pip
   pip install -e .
   pip install -r requirements.txt
   ```

4. **Verify installation**:
   ```bash
   python -c "import mie_lib; print('mie_lib OK')"
   pytest -q
   ```

5. **Read core documentation**:
   - `docs/CORE/ARCHITECT_BIBLE.md` — System architecture and constraints
   - `docs/DEVELOPMENT/DEV_GUIDE.md` — Development workflows
   - `docs/README.md` — Documentation navigation

---

## Development Workflow

### Branch Strategy

- **main**: Stable production code
- **feature/<name>**: New features
- **fix/<name>**: Bug fixes
- **docs/<name>**: Documentation updates
- **refactor/<name>**: Code refactoring without feature changes

### Typical Workflow

1. **Create a branch**:
   ```bash
   git checkout -b feature/add-new-analytics
   ```

2. **Make changes**:
   - Write code following [Code Standards](#code-standards)
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests locally**:
   ```bash
   pytest -v
   # or use Makefile
   make test
   ```

4. **Commit with conventional format** (see [Commit Conventions](#commit-conventions))

5. **Push and create Pull Request**:
   ```bash
   git push origin feature/add-new-analytics
   ```

---

## Code Standards

### Python Style

- **PEP 8 Compliance**: Follow Python's official style guide
- **Line Length**: Max 100 characters (soft limit), 120 (hard limit)
- **Imports**: Organize using `isort` or manually:
  ```python
  # Standard library
  import os
  from pathlib import Path
  
  # Third-party
  import numpy as np
  import pandas as pd
  
  # Local
  from mie_lib.utils.paths import features_parquet_path
  ```

### Type Hints

- **Required for all public functions**:
  ```python
  def calculate_returns(prices: pd.Series, periods: int = 1) -> pd.Series:
      """Calculate returns over specified periods."""
      return prices.pct_change(periods)
  ```

- **Use modern syntax** (Python 3.10+):
  ```python
  from __future__ import annotations  # Use for forward references
  
  def process(data: list[dict[str, int]]) -> pd.DataFrame:
      ...
  ```

### Docstrings

- **Required for all public modules, classes, and functions**
- **Format**: Google-style or NumPy-style
- **Example**:
  ```python
  def train_hmm(
      data: pd.DataFrame,
      n_states: int = 3,
      random_state: int = 42
  ) -> GaussianHMM:
      """Train a Gaussian Hidden Markov Model on financial data.
      
      Args:
          data: DataFrame with returns and volatility features
          n_states: Number of hidden states (2 or 3)
          random_state: Random seed for reproducibility
          
      Returns:
          Trained GaussianHMM model
          
      Raises:
          ValueError: If data has insufficient rows (<400)
      """
      ...
  ```

### Naming Conventions

- **Variables/Functions**: `snake_case`
  - `calculate_transition_matrix()`, `hmm_result`, `train_window_years`
- **Classes**: `PascalCase`
  - `HMMRunResult`, `MarkovChainAnalyzer`
- **Constants**: `UPPER_SNAKE_CASE`
  - `MIN_TRAIN_ROWS`, `STATE_COLORS`, `DEFAULT_RANDOM_SEED`
- **Private functions**: Prefix with underscore
  - `_map_state_names()`, `_validate_input()`

### Code Organization

- **Keep functions focused**: Single Responsibility Principle
- **Avoid deep nesting**: Max 3-4 levels
- **Use early returns** to reduce nesting:
  ```python
  def process(data: pd.DataFrame) -> pd.DataFrame:
      if data.empty:
          return pd.DataFrame()
      
      # Main logic here
      ...
  ```

---

## Commit Conventions

Use **Conventional Commits** format for clear, semantic version history.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring (no feature or bug fix)
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, build, etc.)
- **perf**: Performance improvements

### Examples

```bash
# Feature addition
git commit -m "feat(hmm): add regime duration statistics to HMM page"

# Bug fix
git commit -m "fix(markov): correct transition matrix normalization for sparse contexts"

# Documentation
git commit -m "docs(dev-guide): add section on HMM model training specifications"

# Refactor
git commit -m "refactor(analytics): extract state mapping logic into helper function"

# Multiple paragraphs
git commit -m "feat(analytics): implement multi-horizon Markov forecasts

Add P^h exact computation for horizons 1-5.
Display results in probability table and chart.
Update PAGE_SPEC_MARKOV_v2.md with new section.

Closes #123"
```

### Scope Guidelines

Common scopes:
- `hmm`: Hidden Markov Model features
- `markov`: Markov chain analytics
- `seasonality`: Seasonality analysis
- `features`: Feature engineering
- `ui`: Streamlit UI components
- `cli`: Command-line interface
- `tests`: Test infrastructure
- `docs`: Documentation

---

## Testing Requirements

### Test Coverage

- **Required for all new features**: Minimum 80% line coverage
- **Required for bug fixes**: Add regression test

### Running Tests

```bash
# All tests
pytest -v

# Specific module
pytest tests/test_hmm.py -v

# With coverage report
pytest --cov=src --cov-report=html

# Fast fail (stop on first failure)
pytest -x

# Re-run last failures
pytest --lf
```

### Writing Tests

- **Location**: `tests/test_<module>.py`
- **Naming**: `test_<function_name>_<scenario>`
- **Structure**: Arrange-Act-Assert
- **Use fixtures** for common setup (see `tests/conftest.py`)

**Example**:
```python
def test_train_hmm_with_sufficient_data(sample_features_df):
    """Test HMM training succeeds with 400+ rows."""
    # Arrange
    df = sample_features_df.iloc[:500]  # Sufficient data
    
    # Act
    result = train_hmm(df, n_states=3)
    
    # Assert
    assert result is not None
    assert len(result.state_name_map) == 3
    assert "Bull" in result.state_name_map.values()

def test_train_hmm_with_insufficient_data(sample_features_df):
    """Test HMM training fails with <400 rows."""
    # Arrange
    df = sample_features_df.iloc[:300]  # Insufficient data
    
    # Act & Assert
    with pytest.raises(ValueError, match="Not enough training data"):
        train_hmm(df, n_states=3)
```

### Test Types

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test component interactions
3. **Smoke Tests**: Basic functionality checks (used in CI)

See `docs/DEVELOPMENT/TESTING.md` for comprehensive testing guide.

---

## Pull Request Process

### Before Submitting

1. **Run full test suite**:
   ```bash
   pytest -v
   ```

2. **Check for type errors** (if using mypy/pyright):
   ```bash
   mypy src/
   ```

3. **Update documentation**:
   - Add docstrings to new functions
   - Update relevant docs in `docs/`
   - Update `CHANGELOG.md` if significant change

4. **Ensure clean commits**:
   - Follow commit conventions
   - Squash work-in-progress commits if needed
   - Write descriptive commit messages

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of changes and motivation.

## Changes Made
- Added X feature to Y module
- Fixed Z bug in A component
- Updated B documentation

## Testing
- [ ] All existing tests pass
- [ ] Added new tests for new functionality
- [ ] Manually tested in UI (if UI changes)

## Documentation
- [ ] Updated relevant docs in docs/
- [ ] Added/updated docstrings
- [ ] Updated CHANGELOG.md (if applicable)

## Related Issues
Closes #123
Relates to #456
```

### Review Process

1. **Automated Checks**: CI runs tests (if configured)
2. **Code Review**: Maintainer reviews code for:
   - Correctness and functionality
   - Code quality and style
   - Test coverage
   - Documentation completeness
3. **Address Feedback**: Make requested changes
4. **Approval & Merge**: Once approved, maintainer merges

### Merge Strategy

- **Squash and Merge**: Preferred for feature branches (clean history)
- **Rebase and Merge**: For small, clean commits
- **Merge Commit**: For large feature branches with meaningful history

---

## Documentation

### When to Update Documentation

- **Always** for new features or breaking changes
- **Always** for public API changes
- **Recommended** for significant refactors
- **Optional** for internal implementation details

### Documentation Structure

See `docs/README.md` for full structure. Key locations:

- **Core System**: `docs/CORE/`
  - Architecture, analytics, data models, CLI
- **Development**: `docs/DEVELOPMENT/`
  - Developer guides, testing, contributing
- **UI System**: `docs/UI_SYSTEM/`
  - Page specs, chart specs, design guidelines

### Writing Style

- **Clear and concise**: Avoid jargon where possible
- **Examples**: Include code examples for API usage
- **Audience-aware**: Tag sections for quants vs. general users
- **Up-to-date**: Remove outdated information promptly

---

## Project Architecture

### Directory Structure

```
.
├── app/                    # Streamlit UI application
│   ├── pages/             # Multi-page app pages
│   └── ui/                # UI components and themes
├── cli/                   # Command-line interface
├── config/                # Configuration files (YAML)
├── data/                  # Data storage (features, analytics, logs)
├── docs/                  # Documentation
│   ├── CORE/             # Core system docs
│   ├── DEVELOPMENT/      # Developer docs
│   └── UI_SYSTEM/        # UI specifications
├── src/                   # Core library code
│   ├── analytics/        # Analytics modules (HMM, Markov, etc.)
│   ├── data_ingest/      # Data ingestion
│   ├── features/         # Feature engineering
│   └── mie_lib/          # Shared utilities
├── tests/                 # Test suite
└── scripts/              # Automation scripts
```

### Key Principles

From `docs/CORE/ARCHITECT_BIBLE.md`:

1. **Offline-First**: Heavy computation in CLI/scripts, not UI
2. **Reproducibility**: Deterministic outputs, versioned artifacts
3. **Testability**: High test coverage, clear contracts
4. **Modularity**: Loosely coupled components
5. **Documentation**: Specs define behavior, code implements

### Adding New Features

1. **Analytics Module** (e.g., new indicator):
   - Implement in `src/analytics/`
   - Add CLI command in `cli/mie.py`
   - Save outputs to `data/analytics/`
   - Create UI page in `app/pages/`
   - Write page spec in `docs/UI_SYSTEM/`

2. **UI Page** (e.g., new visualization):
   - Create page file: `app/pages/NN_PageName.py`
   - Follow `docs/UI_SYSTEM/UI_README_v2.md` structure
   - Write page spec: `docs/UI_SYSTEM/PAGE_SPEC_<name>_v2.md`
   - Add tests: `tests/test_<module>.py`

---

## Questions or Issues?

- **Documentation**: Start with `docs/README.md`
- **Development Setup**: See `docs/DEVELOPMENT/DEV_GUIDE.md`
- **Architecture Questions**: Refer to `docs/CORE/ARCHITECT_BIBLE.md`
- **Testing Help**: See `docs/DEVELOPMENT/TESTING.md`
- **Bugs/Features**: Open an issue (if using issue tracker)

---

Thank you for contributing to MIE! 🚀
