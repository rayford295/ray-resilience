"""Agent gateway: the Steward Harness wrapped around an LLM.

The harness stands guard on both sides of the model. Deterministic code —
never the LLM — decides authorization (policy pre-check) and verifies the
output (claim post-check). The LLM only drafts prose from evidence it was
handed; everything else is checkable, audited, and fail-closed.
"""
