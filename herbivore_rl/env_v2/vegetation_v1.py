"""soil-v1 leaf model mirrored from EcoVegetationV3.h.

Explicit opt-in integration helper, not automatically enabled by training configs.
Food remains the caller's existing grid balance. No policy/schema/weights change.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Config:
    enabled: bool = False
    infiltration: float = .018
    evaporation: float = .002
    drainage: float = .010
    uptake: float = .001
    stress_loss: float = .004


@dataclass(frozen=True)
class Weather:
    rain: float = .2
    temperature: float = 20.
    light: float = 1.


@dataclass(frozen=True)
class Habitat:
    plant: int = 0
    drainage: float = .5
    shade: float = 0.
    water_supply: float = 0.
    flood: float = 0.
    ground_usable: bool = True


@dataclass
class Cell:
    moisture: float = .5
    stress: float = 0.


def _unit(value):
    return min(1., max(0., value))


def advance(config, weather, habitat, state, food, capacity, regen_per_step, dt):
    """Return (food_after, growth, loss), mutating only a valid cell's moisture/stress.

    regen_per_step already includes the native 2/15s step rate. Do not multiply
    it by dt a second time. Invalid inputs fail closed, matching native behavior.
    """
    result = (food, 0., 0.)
    unit_values = (config.infiltration, config.evaporation, config.drainage,
                   config.uptake, config.stress_loss, weather.rain, weather.light,
                   habitat.drainage, habitat.shade, habitat.water_supply, habitat.flood,
                   state.moisture, state.stress)
    if (not config.enabled or any(not math.isfinite(v) or not 0 <= v <= 1 for v in unit_values)
            or habitat.plant not in (0, 1, 2) or not math.isfinite(weather.temperature)
            or not -100 <= weather.temperature <= 100 or not math.isfinite(dt) or not 0 < dt <= .25
            or not all(math.isfinite(v) for v in (food, capacity, regen_per_step))
            or not 0 <= food <= capacity or regen_per_step < 0):
        return result
    heat = min(2., max(0., (weather.temperature + 5) / 25))
    density = food / capacity if capacity > 0 else 0
    rate = (config.infiltration * weather.rain * (1 - .5 * habitat.drainage)
            + .01 * habitat.water_supply + .03 * habitat.flood
            - config.evaporation * heat * (.25 + .75 * weather.light) * (1 - .5 * habitat.shade)
            - config.drainage * habitat.drainage * state.moisture - config.uptake * density)
    state.moisture = _unit(state.moisture + rate * dt)
    lo, hi = ((.45, .95) if habitat.plant == 1 else (.18, .65) if habitat.plant == 2 else (.30, .75))
    dry = _unit((lo - state.moisture) / lo)
    wet = _unit((state.moisture - hi) / (1 - hi))
    flood_stress = habitat.flood * (.1 if habitat.plant == 1 else 1.)
    target = max(dry, wet, flood_stress, 0. if habitat.ground_usable else 1.)
    state.stress = _unit(state.stress + (target - state.stress) * (1 - math.exp(-dt / 8.)))
    loss = food * (1 - math.exp(-config.stress_loss * state.stress * dt)) if habitat.ground_usable else food
    remaining = food - loss
    suitability = (1 - target) * (.2 + .8 * weather.light) * _unit(1 - abs(weather.temperature - 20) / 30)
    growth = min(capacity - remaining, regen_per_step * suitability * (capacity - remaining)) if habitat.ground_usable else 0.
    return remaining + growth, growth, loss
