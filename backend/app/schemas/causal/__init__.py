"""Phase B causal-layer endpoint schemas.

One module per endpoint (mirrors Phase A's per-endpoint schema split):

- ``identify.py``       SCHEMA_VERSION = "B.1"
- ``estimate.py``       SCHEMA_VERSION = "B.2"
- ``refute.py``         SCHEMA_VERSION = "B.3"  (B2b)
- ``mediation.py``      SCHEMA_VERSION = "B.4"  (B2b)
- ``sensitivity.py``    SCHEMA_VERSION = "B.5"  (B2b)

Shared sub-models live in ``app.schemas.causal_common``.
"""
