"""Phase 2 detection-layer tests: Fenrir structure, Huginn canary monitoring, the
attempt-introspection tripwire, and the false-inert catch (D67-fix direction d).

The deterministic tests here prove the pipeline LOGIC against mock emissions: a steered
emission trips the wire and is quarantined, a benign emission is clean, each canary hard
signal is detected, and fresh context holds. They are fast, deterministic and always
run. What they do NOT prove is that real models actually get steered by these payloads;
that is the separate, optional real-model demonstration (`real_model_demo.py`), which
provides the evidence the mocks cannot.
"""
