"""BOS Engine package.

Phase 0.5 (2026-05-16) split the 42 engine modules into two subpackages
(``app.engine.core``: 19 paper-core engines + species/feedstock data tables;
``app.engine.extended``: 23 satellite engines). To preserve every existing
``from app.engine.<name> import ...`` call site without touching business
code, this package installs a ``MetaPathFinder`` that transparently
redirects legacy dotted paths to their real location.

Why a MetaPathFinder and not PEP 562 ``__getattr__``:
  PEP 562 only fires on attribute access (``app.engine.ser_engine``).
  ``from app.engine.ser_engine import compute_ser`` goes through the
  import system, which consults ``sys.meta_path`` and never reaches the
  package ``__getattr__``. Only a ``MetaPathFinder`` can intercept it.

Do NOT add business logic here.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec

_ENGINE_LOCATION: dict[str, str] = {
    # ---- core (19) ----
    "ser_engine": "core",
    "ser_calculator": "core",
    "monte_carlo_engine": "core",
    "monte_carlo": "core",
    "flight_envelope": "core",
    "digital_twin_engine": "core",
    "controller_engine": "core",
    "kinetics_engine": "core",
    "mass_balance": "core",
    "stoichiometry_engine": "core",
    "sensitivity_engine": "core",
    "tea_engine": "core",
    "lca_engine": "core",
    "risk_engine": "core",
    "ghg_engine": "core",
    "water_engine": "core",
    "energy_engine": "core",
    "species_db": "core",
    "feedstock_db": "core",
    # ---- Phase A additions (core) ----
    "sfi_engine": "core",
    "relay_engine": "core",
    # ---- extended (23) ----
    "bayesian_engine": "extended",
    "bayesian_ab": "extended",
    "automl_engine": "extended",
    "nn_surrogate": "extended",
    "pareto_engine": "extended",
    "anomaly_engine": "extended",
    "outlier_engine": "extended",
    "arima_engine": "extended",
    "forecast": "extended",
    "calibration_engine": "extended",
    "did_engine": "extended",
    "consistency_engine": "extended",
    "data_validator": "extended",
    "sensitivity": "extended",
    "schema_engine": "extended",
    "feed_optimizer": "extended",
    "scheduling_engine": "extended",
    "manuscript_reference_db": "extended",
    "external_knowledge_candidates": "extended",
    "bos_supervisor_engine": "extended",
    "bos_simulation_lab": "extended",
    "bos_closed_loop_simulation": "extended",
    "bos_mechanistic_engine": "extended",
}


class _EngineAliasFinder(MetaPathFinder):
    """Intercept ``app.engine.<name>`` and redirect to the real submodule.

    The finder kicks in only for the legacy flat names listed in
    ``_ENGINE_LOCATION``. Real subpackage imports
    (``app.engine.core.ser_engine``) bypass this finder entirely.
    """

    _PREFIX = "app.engine."

    def find_spec(
        self,
        fullname: str,
        path,
        target=None,
    ) -> ModuleSpec | None:
        if not fullname.startswith(self._PREFIX):
            return None
        suffix = fullname[len(self._PREFIX):]
        if "." in suffix or suffix in ("core", "extended"):
            return None
        location = _ENGINE_LOCATION.get(suffix)
        if location is None:
            return None

        real_fullname = f"app.engine.{location}.{suffix}"
        real_module = importlib.import_module(real_fullname)
        sys.modules[fullname] = real_module
        return real_module.__spec__


if not any(isinstance(f, _EngineAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _EngineAliasFinder())
