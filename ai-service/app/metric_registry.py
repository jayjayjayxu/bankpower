"""Program-owned registry for public electricity statistics metrics.

The registry is deliberately finite: a question may only trigger a calculation
whose operands, unit and formula have been reviewed here.  No model chooses a
formula or silently substitutes a statistical scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MetricType = Literal["DIRECT_METRIC", "DERIVED_METRIC"]


@dataclass(frozen=True)
class MetricSpec:
    code: str
    label: str
    aliases: tuple[str, ...]
    metric_type: MetricType
    energy_type_code: str | None = None
    numerator: str | None = None
    denominator: str | None = None


METRIC_REGISTRY: tuple[MetricSpec, ...] = (
    MetricSpec("total_generation", "发电总量", ("发电总量", "总发电量", "年发电量", "发电量"), "DIRECT_METRIC", "TOTAL"),
    MetricSpec("thermal_generation", "火力发电量", ("火力发电量", "火电发电量", "火电量"), "DIRECT_METRIC", "THERMAL"),
    MetricSpec("wind_generation", "风力发电量", ("风力发电量", "风电发电量", "风电量"), "DIRECT_METRIC", "WIND"),
    MetricSpec("hydro_generation", "水力发电量", ("水力发电量", "水电发电量", "水电量"), "DIRECT_METRIC", "HYDRO"),
    MetricSpec("nuclear_generation", "核电发电量", ("核电发电量", "核电量"), "DIRECT_METRIC", "NUCLEAR"),
    MetricSpec("solar_generation", "太阳能发电量", ("太阳能发电量", "光伏发电量", "光伏发电量"), "DIRECT_METRIC", "SOLAR"),
    MetricSpec("thermal_generation_share", "火力发电占比", ("火力发电占比", "火电占比", "火电发电占比"), "DERIVED_METRIC", numerator="thermal_generation", denominator="total_generation"),
    MetricSpec("wind_generation_share", "风力发电占比", ("风力发电占比", "风电占比", "风电发电占比"), "DERIVED_METRIC", numerator="wind_generation", denominator="total_generation"),
    MetricSpec("hydro_generation_share", "水力发电占比", ("水力发电占比", "水电占比", "水电发电占比"), "DERIVED_METRIC", numerator="hydro_generation", denominator="total_generation"),
    MetricSpec("nuclear_generation_share", "核电发电占比", ("核电发电占比", "核电占比"), "DERIVED_METRIC", numerator="nuclear_generation", denominator="total_generation"),
    MetricSpec("solar_generation_share", "太阳能发电占比", ("太阳能发电占比", "光伏发电占比", "光伏占比"), "DERIVED_METRIC", numerator="solar_generation", denominator="total_generation"),
)


def find_metric(question: str) -> MetricSpec | None:
    folded = question.casefold()
    # Derived aliases must win where one phrase also contains a direct alias.
    return next((item for item in METRIC_REGISTRY if item.metric_type == "DERIVED_METRIC" and any(alias in folded for alias in item.aliases)), None) or next(
        (item for item in METRIC_REGISTRY if any(alias in folded for alias in item.aliases)), None
    )


def metric_by_code(code: str) -> MetricSpec:
    return next(item for item in METRIC_REGISTRY if item.code == code)


def related_metric_for(question: str, active_metric_code: str) -> MetricSpec | None:
    """Resolve terse substitutions such as ``那风电呢`` from verified context."""
    source = next((
        code for alias, code in (
            ("火电", "thermal_generation"), ("火力", "thermal_generation"),
            ("风电", "wind_generation"), ("风力", "wind_generation"),
            ("水电", "hydro_generation"), ("水力", "hydro_generation"),
            ("核电", "nuclear_generation"), ("光伏", "solar_generation"),
            ("太阳能", "solar_generation"),
        ) if alias in question.casefold()
    ), None)
    if source is None:
        return None
    target = f"{source}_share" if active_metric_code.endswith("_share") else source
    try:
        return metric_by_code(target)
    except StopIteration:
        return None
