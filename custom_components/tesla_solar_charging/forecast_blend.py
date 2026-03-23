"""Multi-source forecast blending — weighted average with accuracy tracking."""
from dataclasses import dataclass

@dataclass
class ForecastSource:
    name: str
    production_kwh: float
    weight: float = 1.0
    pessimistic_kwh: float | None = None

@dataclass
class BlendedForecast:
    blended_kwh: float
    pessimistic_kwh: float
    sources: list[ForecastSource]

def blend_forecasts(sources: list[ForecastSource]) -> BlendedForecast:
    if not sources:
        return BlendedForecast(blended_kwh=0.0, pessimistic_kwh=0.0, sources=[])
    total_weight = sum(max(0, s.weight) for s in sources)
    if total_weight <= 0:
        return BlendedForecast(blended_kwh=0.0, pessimistic_kwh=0.0, sources=sources)
    blended = sum(s.production_kwh * max(0, s.weight) for s in sources) / total_weight
    pessimistic_values = [s.pessimistic_kwh for s in sources if s.pessimistic_kwh is not None]
    pessimistic = min(pessimistic_values) if pessimistic_values else blended * 0.8
    return BlendedForecast(
        blended_kwh=round(blended, 1),
        pessimistic_kwh=round(pessimistic, 1),
        sources=sources,
    )
