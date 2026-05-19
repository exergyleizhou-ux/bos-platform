"""Agent-side mirror of backend/app/schemas/causal/.

Six modules: ``common`` + the five endpoint schemas (``identify``,
``estimate``, ``refute``, ``mediation``, ``sensitivity``).
``SCHEMA_VERSION`` constants mirror backend (B.1 - B.5) verbatim;
parity is verified at test time by ``test_schema_parity.py``
(B4 v2 Step 4 will extend that test to cover causal mirrors).

Isolation: these mirrors MUST NOT import ``app.*``. The only
cross-file import inside this subpackage is
``from agent.schemas.causal.common import X``.
"""
