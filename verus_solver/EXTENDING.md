# Extending Strategies

Add a new strategy in `verus_solver/strategies/`:

1. Create a class implementing `Strategy.generate(code, result) -> List[Candidate]`.
2. Keep patches narrow: one repair hypothesis per candidate.
3. Register strategy in `verus_solver/solver.py::_build_strategies`.
4. Add a regression fixture and unit test under `tests/`.

Recommended safety checks for new strategies:

- avoid generating unsupported Verus syntax
- avoid edits outside relevant function regions
- preserve existing `requires`/`ensures` unless strategy is explicitly spec-focused

