# Spikes

Throwaway, time-boxed experiments that ratify or overturn a spike-gated decision.
A spike is not part of the build. It is evidence: it runs, it produces a result,
and that result settles a decision recorded in `DECISIONS.md`. The code is kept in
the tree so the decision can be audited, not because it ships.

## Contents

- `substrate/`: the D25 / D38 substrate ratification spike (Phase 2). Tests whether
  a property graph can maintain Gjoll's action-critical label incrementally, with
  sound edge-deletion retraction (D32), without an authorisation-time traversal.
  Result: ratifies D25 and D38. See `substrate/OUTCOME.md`.

## Running

The spikes reuse the PoC virtual environment and need no third-party dependency:

```
poc/.venv/bin/python spike/substrate/harness.py
```
