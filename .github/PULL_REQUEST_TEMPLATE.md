## What changed

<!-- One logical change. Say what, and why the taxonomy or the spec calls for it. -->

## Fixtures

<!-- Classifier change: name the fixture pair (belongs-in-tier + near-miss). Real-server
     capture: which file under tests/fixtures/real_servers/. Neither: say "none" and why. -->

## Exit-code semantics

<!-- "Unchanged", or which rows were added to tests/test_diff_table.py /
     tests/test_exit_code_contract.py before the change. -->

## Checklist

- [ ] No code path calls `tools/call` (the AST guard passes)
- [ ] `pytest`, `ruff check`, `ruff format --check`, `mypy src/` all clean
- [ ] Coverage on `src/` is still at or above 85%
- [ ] If `tests/fixtures/mock_server_manifest.json` changed, the reason is stated above
- [ ] If a rule changed, `docs/TAXONOMY.md` changed with it
