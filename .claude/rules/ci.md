---
paths:
  - ".github/**"
---

# .github/: CI workflows

- Workflow-level keys (`concurrency`, `permissions`, `defaults`, `env`, `jobs`) are top-level siblings of `on:`/`jobs:`, never nested under `on:`: YAML parses either shape, but GitHub reads a nested `concurrency:` as an unknown trigger and every run fails at once with a workflow file issue and no jobs. `yaml.safe_load` can't tell the two apart; `scripts/check_docs.py` checks the structure of every workflow file.
