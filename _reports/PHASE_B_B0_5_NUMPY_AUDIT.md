# Phase B / B0.5 — numpy 2.x migration audit

> **Batch.** B0.5 — Audit gate for Plan v2 / D6 (numpy 2.x migration).
> **HEAD at start.** `c80778a` (post B0.3).
> **HEAD at end.** `c80778a` — uncommitted; this batch produces no code change.
> **Date.** 2026-05-17.
> **Decision gate.** ≤ 10 application-level breakage points → continue D6=α. > 10 → fall back to D6=β (isolated service).

## Verdict

**🟢 GREEN. Application-level breakage points = 0. D6 = α (migrate Core to numpy 2.x) is GO.**

The migration requires coordinated upgrades of **5 transitive dependencies** (audit-level findings F1–F5 below) but **zero application code changes**. Phase A's 217 tests pass unchanged under numpy 2.4.5.

## §1 venv rebuild

- **Path.** `backend/.venv-numpy2-audit/`
- **Python.** 3.12.7 (system).
- **Reason for rebuild.** The pre-existing `backend/.venv-backend-tests/` has mojibake (`���ĵİ�ľľ`) in its `pyvenv.cfg` `home =` field from a different user-dir encoding; it can't be invoked from the current host.

### Final dependency set under audit

| Package | Plan v2 requested | Audit-final | Δ vs `requirements.txt` |
|---|---|---|---|
| numpy | `>=2.0,<3.0` | **2.4.5** | bumped from 1.26.4 |
| scipy | `>=1.15` | **1.17.1** | bumped from 1.12.0 (forced) |
| pandas | (not in BOS reqs) | not installed | not needed without dowhy/econml |
| pyarrow | — | **24.0.0** | bumped from 15.0.0 (forced) |
| sqlalchemy | unchanged | 2.0.27 | identical |
| fastapi | unchanged | 0.109.2 | identical |
| pydantic | unchanged target | **2.13.4** | bumped from 2.6.1 (forced by langchain-core) |
| langchain-core | (in `agent/requirements.txt`) | **1.4.0** | bumped from spec `>=0.3` |
| langgraph | (in `agent/requirements.txt`) | **1.2.0** | bumped from spec `>=0.2` |
| anthropic | implicit | 0.102.0 | newly explicit |
| aiosqlite | **MISSING** from `requirements.txt` | 0.22.1 | newly explicit |

## §2 Static numpy usage scan

`grep '^(import numpy|from numpy)'` over `backend/app/` + `backend/agent/`:

- **21 files** import numpy. All in `app/engine/` (none in `agent/` runtime).
- **0 files** in `backend/agent/` import numpy — agent isolation preserved.

### Usage depth

| Pattern | Hits | numpy 2.x risk |
|---|---|---|
| Type hints (`np.ndarray`, `NDArray[np.float64]`, `np.random.Generator`) | dominant | **none** — type aliases stable |
| Modern PRNG (`np.random.default_rng(seed)`) | 12 sites | **none** — PCG64 generator |
| `np.isnan` / `np.isinf` (functions, not constants) | 7 sites | **none** — canonical |
| `np.frombuffer(..., dtype=np.uint8)` | 1 site (`bos_native_runtime.py:283`) | **none** — supported in 2.x |
| Removed-in-2.0 aliases (`np.bool`, `np.int`, `np.float`, `np.object`, `np.complex`, `np.NaN`, `np.Inf`) | **0** | **none** — BOS doesn't use any |
| Structured arrays / `np.cast` / `np.fromfile` / `np.byteswap` | **0** | **none** |

**Static-scan prediction.** 0–2 application-level breakage points expected. **Actual: 0.**

## §3 Regression results — apples-to-apples

| Metric | B0.3 (numpy 1.26.4) | B0.5 (numpy 2.4.5) | Δ |
|---|---|---|---|
| Tests collected | 925 | 925 | 0 |
| **Passed** | 754 | **754** | **0** ✓ |
| **Failed** | 0 | **0** | **0** ✓ |
| Skipped | 171 | 171 | 0 |
| Wall-clock | 369.63 s | 352.08 s | -17.55 s (numpy 2.x mildly faster) |
| Phase A subset (`-k phase_a`) | 217 PASS | **217 PASS** | **0** ✓ |

**0 application-level breakage points.** Decision gate cleared with a wide margin (gate was ≤ 10; actual is 0).

## §4 Findings (infrastructure-level)

These are **not** application-level breakage points (counted against the gate). They are infrastructure-level fixes the B1 batch must apply to land the migration. None require BOS code changes.

### F1 — `aiosqlite` missing from `requirements.txt`

- **Symptom.** Fresh venv test collection fails with `ModuleNotFoundError: No module named 'aiosqlite'` (`tests/conftest.py:17` → `app/db.py:31` → SQLAlchemy's `sqlite+aiosqlite:///` URL).
- **Root cause.** The system Python had aiosqlite installed globally; the project requirements.txt never listed it. Phase A and prior worked because pytest used the global Python.
- **Fix for B1.** Add `aiosqlite==0.22.1` (or compatible) to `requirements.txt` under the "Database" section.
- **Severity.** Medium — invisible until someone uses an isolated venv. B0.5 surfaced it.

### F2 — `pyarrow 15.0.0` C-API incompatible with numpy 2.x

- **Symptom.** `AttributeError: _ARRAY_API not found` at `pyarrow.__init__` line 65.
- **Root cause.** pyarrow 15.0.0 was compiled against numpy 1.x C-API. The numpy 2.0 ABI break invalidated all such modules until pyarrow 16+ shipped numpy-2.x-compatible wheels.
- **BOS-level scope.** Used in 2 files:
  - `app/routers/batches.py` (Excel/Parquet export)
  - `app/routers/export.py` (general export)
- **Fix for B1.** Bump to `pyarrow>=16` (audit confirmed working on 24.0.0).
- **Severity.** **High if uncaught** — would block backend boot. Already audited.

### F3 — `scipy 1.12.0` binary-incompatible with numpy 2.x

- **Symptom.** `ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject` when importing `scipy.spatial._ckdtree` (transitively from `scipy.stats`).
- **Root cause.** scipy < 1.13 was compiled against the old numpy dtype struct layout (96 bytes); numpy 2.x changed it to 88 bytes.
- **BOS-level scope.** scipy is used across ~10 engines (`engine/extended/anomaly_engine.py`, `engine/core/sensitivity_engine.py`, `engine/core/monte_carlo_engine.py`, `engine/extended/calibration_engine.py`, etc.) for statistical functions, optimisation, special functions.
- **Fix for B1.** Bump to `scipy>=1.13` (audit confirmed working on 1.17.1).
- **Severity.** **Critical if uncaught** — would break every analytical engine. Already audited.

### F4 — Phase A agent deps not in main `requirements.txt`

- **Symptom.** `ModuleNotFoundError: No module named 'langchain_core'` when collecting `tests/e2e/test_phase_a_e2e.py` or `agent/tests/test_graph_boot.py`.
- **Root cause.** Phase A3 introduced `backend/agent/requirements.txt` as a separate file. The main `backend/requirements.txt` doesn't include `langchain-core`, `langgraph`, `langchain-anthropic`, or `anthropic`. CI on the system Python worked only because these were installed globally for an unrelated reason.
- **Fix for B1.** Either (a) inline the agent deps into main `requirements.txt`, or (b) document that running tests requires `pip install -r requirements.txt -r agent/requirements.txt`. Recommend (b) — preserves the explicit separation Phase A established.
- **Severity.** Medium — invisible until someone uses an isolated venv. B0.5 surfaced it.

### F5 — pydantic forced upgrade 2.6.1 → 2.13.4

- **Symptom.** `pip install langchain-core` un-installs pydantic 2.6.1 and installs 2.13.4. The version jump crosses two minor versions in the pydantic-2 series.
- **Risk.** Phase A's strict Pydantic schemas (SCHEMA_VERSION A.1–A.5) use `model_validator`, `ConfigDict`, `Field` with constraints. All these are stable in pydantic 2.x. The audit's 217-Phase-A-PASS confirms no behavioural drift on this codebase.
- **Observed warnings under 2.13.4** (2 instances, both pre-existing in BOS V9 baseline models):
  ```
  UserWarning: Field "model_version" has conflict with protected namespace "model_".
  UserWarning: Field "model_activation" has conflict with protected namespace "model_".
  ```
  These are *warnings*, not errors. They were already present before this audit (pydantic 2.0 introduced `model_` as a protected namespace; v9 baseline used `model_version` / `model_activation` field names). Fix is documented in the warning text itself: set `model_config['protected_namespaces'] = ()`.
- **Fix for B1.** Pin `pydantic>=2.6,<3.0` (or specifically `pydantic==2.13.4` to match audit). The two protected-namespace warnings are pre-existing and out of B0.5/B1 scope.
- **Severity.** Low — no functional break observed in 217 Phase A tests.

## §5 Decision gate

| Item | Value |
|---|---|
| **Application-level breakage points** | **0** |
| Gate threshold | ≤ 10 |
| Verdict | **PASS — continue D6 = α** |
| Phase A subset regression | 217 PASS / 0 FAIL ✓ |
| Full backend regression | 754 PASS / 0 FAIL / 171 SKIP ✓ |
| Distance from gate | 10 points of slack — large safety margin |

**Recommendation to user.** Proceed to B1 (deps + numpy migration landing) using the package set this audit validated. **No fallback to D6=β needed.**

## §6 Auxiliary findings

### `pytest.ini` has `addopts: -x`

The `addopts` block contains `-x` (exit on first failure). This is the root cause of the historic short-summary truncation that confused the B0.3 reconciliation pass (24 visible vs 36 actual fails). Phase B regressions are routinely run with `-o "addopts="` to override.

**Recommendation (separate decision, not B0.5 scope).** Either:
- (a) Remove `-x` from `pytest.ini` so the default reports every failure.
- (b) Keep `-x` but add a `Makefile` target `make test-full` that overrides it.

Option (a) is the simpler and more honest default; only `-x` users had a reason to keep it. Defer to user choice; this Plan v2 doesn't pre-commit either way.

### B0.5-only venv preserved

Per task brief: `backend/.venv-numpy2-audit/` is **kept** (not deleted) so B1 can reference it. Free disk space when B1 lands a new venv.

## §7 B1 prerequisites — concrete `requirements.txt` deltas

When B1 starts, the file at `backend/requirements.txt` must transition as follows:

```diff
- numpy==1.26.4
+ numpy>=2.0,<3.0          # B0.5 validated against 2.4.5
- scipy==1.12.0
+ scipy>=1.13              # B0.5 validated against 1.17.1
- pyarrow==15.0.0
+ pyarrow>=16              # B0.5 validated against 24.0.0
- pydantic[email]==2.6.1
+ pydantic[email]>=2.6,<3.0
- pydantic-core==2.16.2
- (drop pydantic-core pin — let pydantic pull a matching version)

# Add (currently missing — F1 + F4):
+ aiosqlite>=0.22          # test-time SQLite async driver
+ langchain-core>=0.3
+ langgraph>=0.2
+ langchain-anthropic>=0.3
+ anthropic>=0.40
```

The exact pin levels can be tightened during B1. The point is: **none of these changes touches BOS application code**. Phase B can proceed.

## §8 Effort vs estimate

| Step | Estimate (Plan v2) | Actual |
|---|---|---|
| 0 — venv rebuild | 30 min | ~12 min |
| 1 — static scan | 30 min | ~10 min |
| 2 — full regression | 10–15 min | ~25 min (3 retries: aiosqlite, then langchain, then green) |
| 3 — decision gate | 10 min | ~3 min (numbers were unambiguous) |
| 4 — pytest.ini note | 5 min | inline (already known from B0.3) |
| 5 — report | 30 min | ~20 min |
| **Total** | **3–5 h** | **~1.2 h** |

Came in under estimate because the static scan correctly predicted shallow numpy usage, and most "audit time" was waiting for pytest to print buffered output.

## §9 Next batch

B1 (deps + numpy migration landing) is now unblocked. **B0.7 (DAG library) is independent** and can start in parallel. Recommended order: B0.7 first (shorter; gates B2 by providing the starter DAGs the test fixtures need), then B1.

**End of B0.5 audit.**
