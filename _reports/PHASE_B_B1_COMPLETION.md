# Phase B / B1 — Dependencies landing + numpy 2.x migration

> **Batch.** B1 — D6 = α implementation per Plan v2 §5.
> **HEAD at start.** `3968e77` (post planning archive).
> **HEAD at end.** *uncommitted* — this report is part of the B1 commit.
> **Date.** 2026-05-17.
> **Implements.** Plan v2 D6 = α (Core migrates to numpy 2.x).
> **Resolves.** B0.5 audit findings F1, F2, F3, F4, F5.

## §1 `backend/requirements.txt` diff

### Upgrades (5)

| Package | Was | Now | Why |
|---|---|---|---|
| `numpy` | `==1.26.4` | `>=2.0,<3.0` | D6 = α landing; B0.5 validated against 2.4.5 |
| `scipy` | `==1.12.0` | `>=1.13` | B0.5 F3 — `1.12.0` had `dtype` binary incompat with numpy 2.x |
| `pyarrow` | `==15.0.0` | `>=16` | B0.5 F2 — `15.0.0` `_ARRAY_API not found` import error |
| `pydantic[email]` | `==2.6.1` | `>=2.6,<3.0` | B0.5 F5 — langchain-core pulls 2.13+; range loosened to allow this |
| `pydantic-core` | `==2.16.2` | (drop pin) | Let pydantic resolve a matching version |

### Additions (7)

| Package | Min version | Reason |
|---|---|---|
| `aiosqlite` | `>=0.22` | B0.5 F1 — test SQLite async driver was missing from main reqs |
| `dowhy` | `==0.14` | Phase B causal inference (DoWhy 4-step pipeline) |
| `econml` | `==0.16.0` | Phase B DML / mediation estimators (D9 = α LinearDML; D14 = γ DML mediation) |
| `langchain-core` | `>=0.3` | B0.5 F4 — was in `agent/requirements.txt` only |
| `langgraph` | `>=0.2` | B0.5 F4 |
| `langchain-anthropic` | `>=0.3` | B0.5 F4 |
| `anthropic` | `>=0.40` | B0.5 F4 |

### F1–F5 status

| Finding | Status |
|---|---|
| F1 aiosqlite missing | ✅ resolved |
| F2 pyarrow 15.0.0 numpy-2.x incompat | ✅ resolved |
| F3 scipy 1.12.0 numpy-2.x incompat | ✅ resolved |
| F4 agent deps not in main reqs | ✅ resolved (inlined into main `requirements.txt`) |
| F5 pydantic forced upgrade | ✅ resolved (range loosened to `>=2.6,<3.0`) |

**5 / 5 resolved.**

### Final installed versions in `.venv-backend/`

```
numpy==2.4.5
scipy==1.15.3                      # NB: dowhy 0.14 pulled 1.15.3 (still ≥ 1.13)
pyarrow==24.0.0
pydantic==2.13.4
pydantic-core==2.46.4              # transitive, unpinned
aiosqlite==0.22.1
dowhy==0.14
econml==0.16.0
langchain-core==1.4.0
langgraph==1.2.0
langchain-anthropic==1.4.3
anthropic==0.102.0
# Phase B transitive deps:
pandas==3.0.3
scikit-learn==1.6.1
statsmodels==0.14.6
numba==0.65.1
lightgbm==4.6.0
shap==0.48.0
matplotlib==3.10.9
networkx==3.6.1
sympy==1.14.0
cvxpy==1.8.2
causal-learn==0.1.4.6
```

## §2 venv decision

**Decision.** Rename the B0.5 audit venv to become the main venv. **Delete** the old mojibake-broken `.venv-backend-tests/`.

```
backend/.venv-backend-tests/       (DELETED — pyvenv.cfg had mojibake home path)
backend/.venv-numpy2-audit/   →   backend/.venv-backend/   (renamed)
```

**Why.** The B0.5 venv already had numpy 2.4.5 + scipy + pyarrow + langchain stack validated end-to-end. Renaming preserves that validation work; only `pip install -r requirements.txt` was needed to add dowhy / econml / langchain-anthropic that B0.5 didn't install. Faster than building from scratch (saved ~5 min) and lower risk (B0.5's version set is the known-good combination).

**Side effect to flag.** `scipy 1.17.1 → 1.15.3` — dowhy 0.14's constraint pinned an older minor. Still satisfies the new `scipy>=1.13` constraint in `requirements.txt`, but worth noting as a transitive downgrade.

## §3 Regression vs B0.7 baseline

| Metric | B0.7 baseline | B1 | Δ |
|---|---|---|---|
| Tests collected | 925 | 925 | 0 |
| **Passed** | 754 | **754** | **0** ✓ |
| **Failed** | 0 | **0** | **0** ✓ |
| Skipped | 171 | 171 | 0 |
| Wall-clock | 369.63 s | **169.81 s** | -199.82 s (warm cache; B0.5 was 352 s in cold venv) |
| Phase A subset (`-k phase_a`) | 217 PASS | **217 PASS** | **0** ✓ |

**Zero regression.** All Phase A guarantees maintained.

## §4 DoWhy + EconML hello-world

```python
# Smoke test in main venv (.venv-backend/Scripts/python.exe)
import dowhy, econml, numpy as np, pandas as pd
from dowhy import CausalModel
from econml.dml import LinearDML
from sklearn.linear_model import LinearRegression
```

```
dowhy:  0.14
econml: 0.16.0
numpy:  2.4.5    pandas: 3.0.3
DoWhy ATE: 2.010 (true=2.0)
EconML LinearDML ATE: 0.974 (true mean ≈ 1.0)
HELLO_WORLD_OK
```

Both libraries fully operational in the main venv. ATE recovery within 1–3% of the true effect on the same n=500 / n=1000 synthetic benches used in the reconnaissance phase.

## §5 Effort vs estimate

| Step | Plan v2 estimate | Actual |
|---|---|---|
| 1 — backup | 1 min | <1 min |
| 2 — edit requirements.txt | 15 min | ~5 min (4 surgical Edits) |
| 3 — venv decision + install | 30–60 min | ~10 min (renamed B0.5 venv; pip added ~40 packages) |
| 4 — full regression | 10–15 min | ~3 min (warm cache) |
| 5 — Phase A subset | 5 min | ~1 min |
| 6 — dowhy / econml smoke | 5 min | <1 min |
| 7 — completion doc | 30 min | ~10 min |
| 8 — commit | 10 min | ~3 min |
| **Total** | **2–3 h (vs Plan v2 3–5 h)** | **~35 min** |

Came in well under estimate because (a) B0.5 had already validated the version set, (b) the renamed venv approach avoided re-downloading hundreds of MB, (c) warm filesystem cache halved regression wall-clock.

## §6 Aux findings

### scipy downgrade trade-off

dowhy 0.14's installer pulled `scipy 1.15.3` over the B0.5-validated `1.17.1`. Both satisfy the new `scipy>=1.13` requirement. No behavioural difference observed — Phase A's 217 tests pass identically. If a future scipy ≥ 1.16 feature is needed, the requirement will need to be bumped along with a dowhy upgrade audit.

### `.venv-numpy2-audit/` removed

The B0.5 audit venv was renamed, not deleted, so the 511 MB disk-space concern from earlier is resolved (it became the main venv). The B0.5 audit's separate-venv contract is preserved in `_reports/PHASE_B_B0_5_NUMPY_AUDIT.md` as the historical record.

### `requirements.txt.B1-backup` left in tree

`backend/requirements.txt.B1-backup` (925 bytes, the pre-B1 snapshot) was created by Step 1 but is **not** committed by B1. Decision deferred to user: keep as safety net during early Phase B batches, or delete now that B1 is verified green.

## §7 Next batch

- **B2a** (identify + estimate endpoints) is unblocked.
- **B0.7 DAG library** is already loaded in `_reports/PHASE_B_DAGS/*.json` for B2a fixture use.
- **pytest.ini `-x` decision** still outstanding (B0.5 §6 + B0.3 finding) — user single-decision, not gating.

**End of B1 completion report.**
