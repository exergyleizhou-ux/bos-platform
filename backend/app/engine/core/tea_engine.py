"""
BOS Pipeline v9.0 — TEA Engine (Techno-Economic Analysis)

Computes the techno-economic viability of insect bioconversion operations,
including:
  - Capital expenditures (CAPEX)
  - Operating expenditures (OPEX)
  - Revenue from products (larvae, frass, chitin)
  - Profitability metrics: NPV, IRR, payback period, LCOP
  - Sensitivity to key parameters
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

ENGINE_VERSION = "9.0.0"


@dataclass
class TEAInput:
    """Input parameters for techno-economic analysis."""

    # Production parameters
    annual_substrate_tonnes: float = 1000.0  # tonnes DM / year
    ser: float = 0.22  # System Efficiency Ratio
    operating_days: int = 340  # days / year
    batch_days: float = 14.0

    # Product prices ($/kg DM)
    price_larvae: float = 2.50
    price_frass: float = 0.30
    price_chitin: float = 25.00  # Extracted chitin
    price_oil: float = 1.20  # Extracted oil

    # Larval composition (% DM)
    protein_content: float = 42.0
    fat_content: float = 35.0
    chitin_content: float = 8.0

    # Product streams (fractions)
    fraction_whole_larvae: float = 0.60  # Sold as whole dried larvae
    fraction_defatted_meal: float = 0.20  # Defatted protein meal
    fraction_oil_extraction: float = 0.15  # Oil extraction
    fraction_chitin_extraction: float = 0.05  # Chitin extraction

    # CAPEX ($)
    capex_facility: float = 500_000.0
    capex_equipment: float = 300_000.0
    capex_processing: float = 200_000.0
    capex_other: float = 50_000.0

    # OPEX ($/year)
    opex_substrate: float = 50_000.0  # May be negative (paid to take waste)
    opex_labor: float = 150_000.0
    opex_energy: float = 40_000.0
    opex_maintenance: float = 30_000.0
    opex_packaging: float = 20_000.0
    opex_transport: float = 25_000.0
    opex_regulatory: float = 15_000.0
    opex_other: float = 10_000.0

    # Financial parameters
    project_lifetime_years: int = 15
    discount_rate: float = 0.10  # 10%
    tax_rate: float = 0.25  # 25%
    depreciation_years: int = 10  # Straight-line
    inflation_rate: float = 0.03  # 3% annual

    # Waste gate fee (negative opex_substrate means revenue from waste disposal)
    waste_gate_fee: float = 0.0  # $/tonne substrate


@dataclass
class TEAResult:
    """Techno-economic analysis results."""

    # Production volumes
    annual_larvae_tonnes: float = 0.0
    annual_frass_tonnes: float = 0.0
    batches_per_year: float = 0.0

    # Revenue ($/year)
    revenue_larvae: float = 0.0
    revenue_frass: float = 0.0
    revenue_chitin: float = 0.0
    revenue_oil: float = 0.0
    revenue_waste_gate: float = 0.0
    total_revenue: float = 0.0

    # Costs ($/year)
    total_capex: float = 0.0
    total_opex: float = 0.0
    annual_depreciation: float = 0.0

    # Profitability ($/year)
    gross_profit: float = 0.0
    ebitda: float = 0.0
    net_profit: float = 0.0
    gross_margin: float = 0.0  # %

    # Investment metrics
    npv: float = 0.0  # Net Present Value
    irr: Optional[float] = None  # Internal Rate of Return
    payback_years: Optional[float] = None  # Simple payback
    discounted_payback: Optional[float] = None  # Discounted payback
    lcop: float = 0.0  # Levelized Cost of Production ($/kg larvae)
    roi: float = 0.0  # Return on Investment (%)

    # Cash flows
    cash_flows: List[float] = field(default_factory=list)
    cumulative_cash_flows: List[float] = field(default_factory=list)

    # Breakdown
    revenue_breakdown: Dict[str, float] = field(default_factory=dict)
    opex_breakdown: Dict[str, float] = field(default_factory=dict)
    capex_breakdown: Dict[str, float] = field(default_factory=dict)

    engine_version: str = ENGINE_VERSION


def compute_tea(inp: TEAInput) -> TEAResult:
    """
    Compute techno-economic analysis for insect bioconversion.

    Parameters
    ----------
    inp : TEAInput
        Production, financial, and cost parameters.

    Returns
    -------
    TEAResult
        Detailed profitability analysis with investment metrics.
    """
    result = TEAResult()

    # ── Production Volumes ──
    result.annual_larvae_tonnes = round(inp.annual_substrate_tonnes * inp.ser, 4)
    result.annual_frass_tonnes = round(
        inp.annual_substrate_tonnes * (1 - inp.ser) * 0.85,  # ~85% of residue becomes frass
        4,
    )
    result.batches_per_year = round(inp.operating_days / inp.batch_days, 1)

    larvae_kg = result.annual_larvae_tonnes * 1000  # Convert to kg

    # ── Revenue ──
    # Whole larvae
    rev_whole = larvae_kg * inp.fraction_whole_larvae * inp.price_larvae
    # Defatted meal (higher protein value)
    rev_meal = larvae_kg * inp.fraction_defatted_meal * inp.price_larvae * 1.3  # 30% premium
    # Oil extraction
    oil_kg = larvae_kg * inp.fraction_oil_extraction * (inp.fat_content / 100)
    rev_oil = oil_kg * inp.price_oil
    # Chitin extraction
    chitin_kg = larvae_kg * inp.fraction_chitin_extraction * (inp.chitin_content / 100)
    rev_chitin = chitin_kg * inp.price_chitin

    result.revenue_larvae = round(rev_whole + rev_meal, 2)
    result.revenue_oil = round(rev_oil, 2)
    result.revenue_chitin = round(rev_chitin, 2)
    result.revenue_frass = round(result.annual_frass_tonnes * 1000 * inp.price_frass, 2)
    result.revenue_waste_gate = round(inp.annual_substrate_tonnes * inp.waste_gate_fee, 2)

    result.total_revenue = round(
        result.revenue_larvae
        + result.revenue_oil
        + result.revenue_chitin
        + result.revenue_frass
        + result.revenue_waste_gate,
        2,
    )

    # ── CAPEX ──
    result.total_capex = round(
        inp.capex_facility + inp.capex_equipment + inp.capex_processing + inp.capex_other,
        2,
    )
    result.capex_breakdown = {
        "Facility": inp.capex_facility,
        "Equipment": inp.capex_equipment,
        "Processing": inp.capex_processing,
        "Other": inp.capex_other,
    }

    # ── OPEX ──
    result.total_opex = round(
        inp.opex_substrate
        + inp.opex_labor
        + inp.opex_energy
        + inp.opex_maintenance
        + inp.opex_packaging
        + inp.opex_transport
        + inp.opex_regulatory
        + inp.opex_other,
        2,
    )
    result.opex_breakdown = {
        "Substrate": inp.opex_substrate,
        "Labor": inp.opex_labor,
        "Energy": inp.opex_energy,
        "Maintenance": inp.opex_maintenance,
        "Packaging": inp.opex_packaging,
        "Transport": inp.opex_transport,
        "Regulatory": inp.opex_regulatory,
        "Other": inp.opex_other,
    }

    # ── Depreciation ──
    result.annual_depreciation = round(result.total_capex / inp.depreciation_years, 2)

    # ── Profitability ──
    result.gross_profit = round(result.total_revenue - result.total_opex, 2)
    result.ebitda = result.gross_profit
    taxable_income = result.gross_profit - result.annual_depreciation
    tax = max(taxable_income * inp.tax_rate, 0)
    result.net_profit = round(result.gross_profit - tax, 2)

    if result.total_revenue > 0:
        result.gross_margin = round(result.gross_profit / result.total_revenue * 100, 2)

    # ── Revenue Breakdown ──
    result.revenue_breakdown = {
        "Larvae (whole + meal)": result.revenue_larvae,
        "Oil": result.revenue_oil,
        "Chitin": result.revenue_chitin,
        "Frass": result.revenue_frass,
        "Waste gate fees": result.revenue_waste_gate,
    }

    # ── Cash Flows ──
    cash_flows = [-result.total_capex]  # Year 0
    for year in range(1, inp.project_lifetime_years + 1):
        # Inflation-adjusted revenue and opex
        inflation_factor = (1 + inp.inflation_rate) ** (year - 1)
        annual_revenue = result.total_revenue * inflation_factor
        annual_opex = result.total_opex * inflation_factor
        annual_gross = annual_revenue - annual_opex
        annual_tax = max((annual_gross - result.annual_depreciation) * inp.tax_rate, 0)
        annual_net_cf = annual_gross - annual_tax
        cash_flows.append(round(annual_net_cf, 2))

    result.cash_flows = cash_flows

    # Cumulative cash flows
    cumulative = []
    running = 0.0
    for cf in cash_flows:
        running += cf
        cumulative.append(round(running, 2))
    result.cumulative_cash_flows = cumulative

    # ── NPV ──
    npv = 0.0
    for year, cf in enumerate(cash_flows):
        npv += cf / ((1 + inp.discount_rate) ** year)
    result.npv = round(npv, 2)

    # ── IRR ──
    try:
        irr = np.irr(cash_flows) if hasattr(np, "irr") else _compute_irr(cash_flows)
        result.irr = round(float(irr) * 100, 2) if irr is not None and not np.isnan(irr) else None
    except Exception:
        result.irr = None

    # ── Payback Period ──
    for i, cum_cf in enumerate(cumulative):
        if cum_cf >= 0 and i > 0:
            # Interpolate
            prev_cf = cumulative[i - 1]
            annual_cf = cash_flows[i]
            if annual_cf != 0:
                result.payback_years = round(i - 1 + abs(prev_cf) / annual_cf, 2)
            else:
                result.payback_years = float(i)
            break

    # ── Discounted Payback ──
    disc_cumulative = 0.0
    for year, cf in enumerate(cash_flows):
        disc_cf = cf / ((1 + inp.discount_rate) ** year)
        disc_cumulative += disc_cf
        if disc_cumulative >= 0 and year > 0:
            result.discounted_payback = float(year)
            break

    # ── LCOP (Levelized Cost of Production) ──
    if larvae_kg > 0:
        total_lifetime_cost = result.total_capex + result.total_opex * inp.project_lifetime_years
        total_lifetime_larvae = larvae_kg * inp.project_lifetime_years
        result.lcop = round(total_lifetime_cost / total_lifetime_larvae, 4)

    # ── ROI ──
    if result.total_capex > 0:
        total_net_profit = result.net_profit * inp.project_lifetime_years
        result.roi = round(total_net_profit / result.total_capex * 100, 2)

    return result


def _compute_irr(cash_flows: List[float], max_iter: int = 1000, tol: float = 1e-8) -> Optional[float]:
    """Compute IRR using Newton-Raphson method."""
    rate = 0.10  # Initial guess

    for _ in range(max_iter):
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))

        if abs(dnpv) < 1e-12:
            return None

        new_rate = rate - npv / dnpv

        if abs(new_rate - rate) < tol:
            return new_rate

        rate = new_rate

    return rate if abs(sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))) < 1.0 else None
