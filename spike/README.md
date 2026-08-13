# Spikes

Throwaway, time-boxed experiments that ratify or overturn a spike-gated decision.
A spike is not part of the build. It is evidence: it runs, it produces a result,
and that result settles a decision recorded in `DECISIONS.md`. The code is kept in
the tree so the decision can be audited, not because it ships.

## Contents

- `substrate/`: the D25 / D38 substrate ratification spike (Phase 2). Tests whether
  a property graph can maintain Gjoll's action-critical label incrementally, with
  sound edge-deletion retraction (D32), without an authorisation-time traversal.
  Result: ratifies D25 and D38. See `substrate/OUTCOME.md`. `harness.py` is the
  substrate-neutral proof (the reference). `memgraph_harness.py` binds the same
  algorithm to a live Memgraph store and re-checks it (D57); it is optional and
  skips when Memgraph is not reachable.

## Running

The core spike reuses the PoC virtual environment and needs no third-party dependency:

```
poc/.venv/bin/python spike/substrate/harness.py
```

The optional Memgraph binding test needs the `neo4j` Bolt client (in the venv) and a
reachable Memgraph. Start one via podman, then run the binding test; it skips cleanly
if Memgraph is absent:

```
podman run -d --name heimdall-memgraph -p 7687:7687 docker.io/memgraph/memgraph-mage:latest
poc/.venv/bin/python spike/substrate/memgraph_harness.py
podman stop heimdall-memgraph && podman rm heimdall-memgraph
```
