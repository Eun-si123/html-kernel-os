# Cross-agent feature-to-regression map

A small, machine-readable review aid inspired by the TeamForge and BetterNet-App approach. This is useful to Codex, Claude Code, ChatGPT, Copilot and humans alike.

```sh
python3 scripts/agent_feature_map.py validate
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/agent_feature_map.py impact --base origin/main --head HEAD
```

The feature contract points at **existing source and regression test files**. An `impact` result recommends the tests to review; it **does not execute them**, guarantee completeness, or prove a bootable OS. Files that are not mapped remain subject to code review and testing. Never synthesize a PASS from a feature-map count.

For changes to HTML parser semantics, use [tests/test_compiler.py](../tests/test_compiler.py). For the static site, use [tests/test_site.py](../tests/test_site.py). Status and evidence belong in [docs/STATUS.md](../docs/STATUS.md) and [docs/VALIDATION.md](../docs/VALIDATION.md). No model or agent quality leaderboard is implied.
