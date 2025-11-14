> **⚠️ DEPRECATED as of 2025-11-14**
> This file is superseded by:
> - **[developer_commands_cheatsheet.md](../../developer_commands_cheatsheet.md)** for command reference
> - **[docs/DEVELOPMENT/DEV_GUIDE.md](../DEVELOPMENT/DEV_GUIDE.md)** for development workflows
> 
> See [legacy/README.md](./README.md) for migration guide. This file will be deleted after **2026-05-14**.
>
> ---

# COMMANDS (Quick Index)

Short, friendly index to your most used commands. For details and more examples, see **developer_commands_cheatsheet.md**.

## TL;DR

### Tests
```bash
make test               # default pytest
make test-fast          # fail fast
make test-lastfail      # last failures only
```

### Pipeline
```bash
make pipeline TICKER=SPY WINDOW=2Y LOOKBACK=90
# Log will be in ./logs/pipeline_20251105_1121.log (timestamped)
```

### Features & Analytics
```bash
make features
make update-features LOOKBACK=30
make markov TICKER=QQQ WINDOW=1Y
make analytics
```

### Streamlit
```bash
make streamlit ARGS="-- --ticker SPY --window 2Y --mode full"
```

### Logging patterns
```bash
{ cmd1; cmd2; } > out.txt 2>&1      # group + log
your_cmd 2>&1 | tee out.txt           # see + save
```

---

> Place the files like so:
>
> ```
> scripts/run_pipeline.sh
> scripts/validate.sh
> Makefile
> developer_commands_cheatsheet.md
> COMMANDS.md
> ```
>
> Then:
>
> ```bash
> chmod +x scripts/*.sh
> ```
