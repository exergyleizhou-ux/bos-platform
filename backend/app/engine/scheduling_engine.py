"""
BOS Pipeline v9.0 �� Batch Scheduling Optimizer

Optimizes batch scheduling for a bioconversion facility, considering:
  - Available capacity (number of rearing containers)
  - Batch cycle time (species-dependent)
  - Substrate availability windows
  - Labor constraints
  - Staggered harvest for continuous output

Uses constraint satisfaction and simple heuristic scheduling.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import numpy as np

ENGINE_VERSION = "9.0.0"


@dataclass
class ScheduleConstraints:
    """Facility constraints for scheduling."""

    n_containers: int = 20  # Number of rearing containers
    batch_cycle_days: float = 14.0  # Days per batch
    setup_days: float = 1.0  # Cleaning/setup between batches
    max_simultaneous_harvests: int = 3  # Labor constraint
    substrate_available_per_day: float = 500.0  # kg/day
    substrate_per_batch: float = 200.0  # kg per batch
    planning_horizon_days: int = 90  # Days to plan


@dataclass
class ScheduledBatch:
    """A single scheduled batch."""

    batch_number: int
    container_id: int
    start_day: int
    end_day: int
    harvest_day: int
    substrate_kg: float
    status: str = "scheduled"  # scheduled, active, completed


@dataclass
class ScheduleResult:
    """Scheduling optimization results."""

    schedule: List[ScheduledBatch] = field(default_factory=list)
    total_batches: int = 0
    batches_per_container: float = 0.0
    container_utilization: float = 0.0  # %
    throughput_kg_per_day: float = 0.0
    harvest_calendar: Dict[int, int] = field(default_factory=dict)  # day �� n_harvests
    substrate_demand_profile: List[float] = field(default_factory=list)

    # Gantt chart data
    gantt_data: List[Dict] = field(default_factory=list)

    feasible: bool = True
    warnings: List[str] = field(default_factory=list)
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION


def optimize_schedule(constraints: ScheduleConstraints) -> ScheduleResult:
    """
    Generate an optimized batch schedule.

    Uses a staggered-start heuristic to maximize throughput while
    respecting capacity and labor constraints.

    Parameters
    ----------
    constraints : ScheduleConstraints
        Facility constraints.

    Returns
    -------
    ScheduleResult
        Batch schedule with utilization metrics.
    """
    start_time = time.perf_counter()
    result = ScheduleResult()

    c = constraints
    total_cycle = c.batch_cycle_days + c.setup_days
    horizon = c.planning_horizon_days

    # ���� Staggered scheduling ����
    # Calculate ideal stagger interval to spread harvests
    stagger_interval = max(total_cycle / c.n_containers, 1.0)

    # Track container availability
    container_available_day = [0] * c.n_containers  # Day each container becomes free
    harvest_days: Dict[int, int] = {}  # day �� count of harvests
    daily_substrate_demand = [0.0] * (horizon + int(total_cycle) + 1)

    batch_number = 0
    day = 0

    while day < horizon:
        # Find available containers on this day
        available = [
            (i, container_available_day[i])
            for i in range(c.n_containers)
            if container_available_day[i] <= day
        ]

        if not available:
            day += 1
            continue

        # Check substrate availability
        remaining_substrate_today = c.substrate_available_per_day
        for i, _ in sorted(available, key=lambda x: x[1]):
            if remaining_substrate_today < c.substrate_per_batch:
                break

            # Check harvest constraint
            harvest_day = int(day + c.batch_cycle_days)
            if harvest_day < len(daily_substrate_demand):
                current_harvests = harvest_days.get(harvest_day, 0)
                if current_harvests >= c.max_simultaneous_harvests:
                    # Try next day
                    continue

            # Schedule batch
            batch_number += 1
            batch = ScheduledBatch(
                batch_number=batch_number,
                container_id=i,
                start_day=int(day),
                end_day=int(day + total_cycle),
                harvest_day=harvest_day,
                substrate_kg=c.substrate_per_batch,
            )
            result.schedule.append(batch)

            # Update tracking
            container_available_day[i] = day + total_cycle
            remaining_substrate_today -= c.substrate_per_batch

            if int(day) < len(daily_substrate_demand):
                daily_substrate_demand[int(day)] += c.substrate_per_batch

            harvest_days[harvest_day] = harvest_days.get(harvest_day, 0) + 1

            # Gantt data
            result.gantt_data.append({
                "batch": batch_number,
                "container": i,
                "start": int(day),
                "end": int(day + c.batch_cycle_days),
                "setup_end": int(day + total_cycle),
            })

        day += max(stagger_interval, 1)

    # ���� Metrics ����
    result.total_batches = batch_number
    result.batches_per_container = round(batch_number / max(c.n_containers, 1), 2)

    # Container utilization
    total_container_days = c.n_containers * horizon
    busy_days = sum(total_cycle for _ in result.schedule)
    result.container_utilization = round(min(busy_days / max(total_container_days, 1) * 100, 100), 2)

    # Throughput
    total_substrate = batch_number * c.substrate_per_batch
    result.throughput_kg_per_day = round(total_substrate / max(horizon, 1), 2)

    # Harvest calendar
    result.harvest_calendar = {k: v for k, v in sorted(harvest_days.items())}

    # Substrate demand profile
    result.substrate_demand_profile = [round(v, 2) for v in daily_substrate_demand[:horizon]]

    # Warnings
    if result.container_utilization < 70:
        result.warnings.append(
            f"Container utilization is low ({result.container_utilization:.1f}%). "
            "Consider reducing number of containers or increasing substrate supply."
        )

    max_harvest_day = max(harvest_days.values()) if harvest_days else 0
    if max_harvest_day >= c.max_simultaneous_harvests:
        peak_days = sum(1 for v in harvest_days.values() if v >= c.max_simultaneous_harvests)
        result.warnings.append(
            f"{peak_days} days at maximum harvest capacity ({c.max_simultaneous_harvests}). "
            "Consider staggering further or adding labor."
        )

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
