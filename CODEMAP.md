# HTML Kernel OS — code map

Locate the smallest source and test surface. This is a navigation index, **not evidence of implemented functionality**.

| Question | Source of truth | Verification / review |
| --- | --- | --- |
| What is released, planned, or blocked? | [docs/STATUS.md](docs/STATUS.md) | [docs/VALIDATION.md](docs/VALIDATION.md), live CI |
| What is the compiler grammar? | [compiler/htmlk.py](compiler/htmlk.py) | [tests/test_compiler.py](tests/test_compiler.py) |
| What example is accepted? | [examples/kernel.html](examples/kernel.html) | Compiler CLI / object compilation |
| Where does the generated C come from? | [compiler/htmlk.py](compiler/htmlk.py) | `build/kernel.c` generated, not committed |
| Is it actually bootable? | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/STATUS.md](docs/STATUS.md) | QEMU boot test **not yet implemented** |
| Where is the static site? | [site/index.html](site/index.html), [site/styles.css](site/styles.css), [site/app.js](site/app.js) | [tests/test_site.py](tests/test_site.py), browser checks if available |
| What does CI verify? | [.github/workflows/ci.yml](.github/workflows/ci.yml) | Exact GitHub Actions run |
| Which regressions map to changed source? | [agent-evals/feature-contracts.json](agent-evals/feature-contracts.json) | `python3 scripts/agent_feature_map.py impact ...` |
| What should agents read first? | [AGENTS.md](AGENTS.md), [docs/README.md](docs/README.md) | Routing / docs-link check |
| Who owns status / open decisions? | [docs/STATUS.md](docs/STATUS.md), [docs/DECISIONS.md](docs/DECISIONS.md) | Source and current GitHub state |

## Boundaries worth keeping separate

- `site/`: static web UI, **not** kernel runtime or a web compiler.
- `compiler/`: build-time parser and code generator, currently Python-based.
- `examples/`: examples for language syntax, not hardware acceptance evidence.
- `tests/`: source/unit/static regression checks.
- `agent-evals/`: advisory mapping of source paths to existing tests; never a release gate by itself.
- `docs/`: status, evidence standards, architecture, decisions, and agent navigation.

Do not introduce a long-running agent service, database, or synthetic feature count simply because another larger repository has one.
