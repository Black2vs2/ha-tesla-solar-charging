"""Pure charging logic — no Home Assistant dependencies.

Priority: home battery fills first, car only gets grid export (wasted energy).
As sun fades, car amps ramp down gracefully until stop.
By sunset, home battery is full — car never steals from it.
"""

from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    """Actions the controller can take."""
    NONE = "none"
    START = "start"
    STOP = "stop"
    ADJUST = "adjust"


@dataclass
class SensorState:
    """Current state of all sensors."""
    grid_power: float        # W, negative = exporting
    grid_voltage: float      # V
    battery_soc: float       # %, inverter battery
    battery_power: float     # W, positive = discharging
    is_charging: bool
    current_amps: float
    low_amp_count: int
    tesla_battery: float | None = None      # %, None if unavailable
    tesla_charge_limit: float | None = None # %, None if unavailable


@dataclass
class Config:
    """Charging configuration parameters."""
    min_export_power: float = 1200.0   # W of export needed to start
    max_charging_amps: int = 32
    safety_buffer_amps: float = 3.0    # amps reserved (never use for car)
    battery_soc_threshold: float = 80.0  # min home battery % to even consider starting
    low_amp_stop_count: int = 3        # consecutive low readings before stop
    min_charging_amps: int = 5
    battery_discharge_threshold: float = 100.0  # W, threshold for "meaningful drain"


@dataclass
class Decision:
    """Result of charging logic evaluation."""
    action: Action
    target_amps: int = 0
    reason: str = ""
    new_low_amp_count: int = 0


MAX_REASONABLE_EXPORT_AMPS = 50.0


def calculate_net_available(
    grid_power: float,
    grid_voltage: float,
    battery_power: float,
    safety_buffer: float,
    current_charging_amps: float = 0.0,
) -> float:
    """Calculate net available amps for car charging.

    Total solar available = what the car is using + what's exported + what
    the battery is absorbing. The inverter splits solar between battery,
    car, house, and grid — we want to know the total budget the car could
    use if the battery shared.

    Formula: solar_for_car = car_draw + grid_export + battery_charge_power
    Then subtract safety buffer and any battery discharge.
    """
    if grid_voltage <= 0:
        return 0.0

    # Ignore small grid import noise when battery is active
    effective_grid = grid_power
    if grid_power > 0 and abs(battery_power) > 0 and grid_power < 150:
        effective_grid = 0.0

    car_power = current_charging_amps * grid_voltage
    grid_export = abs(effective_grid) if effective_grid < 0 else 0.0
    battery_charge = abs(battery_power) if battery_power < 0 else 0.0
    battery_discharge = max(0, battery_power)

    # Total solar available for the car = what it's using + export + battery absorbing
    total_solar_for_car = car_power + grid_export + battery_charge
    total_amps = total_solar_for_car / grid_voltage

    return min(total_amps, MAX_REASONABLE_EXPORT_AMPS) - safety_buffer - (battery_discharge / grid_voltage)


def decide(state: SensorState, config: Config, force: bool = False) -> Decision:
    """Decide what charging action to take (solar mode).

    Core principle: car only gets energy that would otherwise be exported
    to grid (wasted). Home battery always fills first.

    If force=True, skip the battery SOC threshold — charge from any export.
    Still won't pull from grid (only uses actual export).
    """
    net_available = calculate_net_available(
        state.grid_power,
        state.grid_voltage,
        state.battery_power,
        config.safety_buffer_amps,
        current_charging_amps=state.current_amps if state.is_charging else 0.0,
    )

    # Tesla already full?
    if state.tesla_battery is not None and state.tesla_charge_limit is not None:
        if state.tesla_battery >= state.tesla_charge_limit:
            if state.is_charging:
                return Decision(
                    action=Action.STOP,
                    reason=f"Tesla at {state.tesla_battery}% — reached limit {state.tesla_charge_limit}%",
                )
            return Decision(
                action=Action.NONE,
                reason=f"Tesla at {state.tesla_battery}% — at limit {state.tesla_charge_limit}%",
            )

    # --- NOT CHARGING ---
    if not state.is_charging:
        # Don't start if home battery is too low (unless force charge)
        # But allow early start if export is so high we can charge both
        if not force and state.battery_soc < config.battery_soc_threshold:
            # Allow if exporting well above minimum (2x) — plenty for both
            export_w = abs(state.grid_power) if state.grid_power < 0 else 0
            if export_w < config.min_export_power * 2:
                return Decision(
                    action=Action.NONE,
                    reason=f"Home battery {state.battery_soc}% below {config.battery_soc_threshold}% — filling first (export {export_w:.0f}W)",
                )

        # Battery at threshold but inverter still absorbing — start at minimum,
        # the ramp logic will adjust once export kicks in.
        # Only if battery is absorbing enough to sustain min charging — otherwise
        # starting at 5A (~1150W) would immediately overwhelm what's available
        # and cause a start/stop oscillation loop.
        if (
            state.battery_soc >= config.battery_soc_threshold
            and state.battery_power < 0
            and abs(state.battery_power) >= config.min_export_power
        ):
            return Decision(
                action=Action.START,
                target_amps=config.min_charging_amps,
                reason=f"Battery {state.battery_soc}% at threshold, still charging at {abs(state.battery_power):.0f}W — starting at min amps",
            )

        # Don't start if not exporting enough
        if state.grid_power >= -(config.min_export_power):
            return Decision(
                action=Action.NONE,
                reason=f"Export {abs(state.grid_power):.0f}W below {config.min_export_power:.0f}W threshold",
            )

        # Exporting enough and battery is healthy — start
        start_amps = max(
            config.min_charging_amps,
            min(int(net_available), config.max_charging_amps),
        )
        return Decision(
            action=Action.START,
            target_amps=start_amps,
            reason=f"Exporting {abs(state.grid_power):.0f}W, battery {state.battery_soc}%, starting at {start_amps}A",
        )

    # --- CURRENTLY CHARGING ---

    # If home battery starts discharging, reduce car charge immediately
    # (means solar dropped and inverter is pulling from battery)
    if state.battery_power > config.battery_discharge_threshold:
        # SOC below threshold — stop immediately, don't waste cycles counting
        if state.battery_soc < config.battery_soc_threshold:
            return Decision(
                action=Action.STOP,
                reason=f"Battery {state.battery_soc}% below {config.battery_soc_threshold}% and discharging {state.battery_power:.0f}W — stopping",
                new_low_amp_count=0,
            )
        target = max(int(state.current_amps - 2), config.min_charging_amps)
        if target <= config.min_charging_amps:
            new_count = state.low_amp_count + 1
            if new_count >= config.low_amp_stop_count:
                return Decision(
                    action=Action.STOP,
                    reason=f"Home battery discharging {state.battery_power:.0f}W, stopping car",
                    new_low_amp_count=0,
                )
            return Decision(
                action=Action.ADJUST,
                target_amps=config.min_charging_amps,
                reason=f"Battery discharging, holding minimum, count {new_count}/{config.low_amp_stop_count}",
                new_low_amp_count=new_count,
            )
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Battery discharging {state.battery_power:.0f}W, reducing to {target}A",
            new_low_amp_count=0,
        )

    # When battery is actively charging, the car and battery are sharing solar.
    # Don't reduce/stop based on headroom — the battery absorbing power is fine.
    # Only the battery-discharging check above should trigger reductions.
    battery_is_charging = state.battery_power < -50  # absorbing > 50W
    real_grid_import = state.grid_power > 150  # ignore sensor noise

    # Ramp up/down based on headroom (net_available vs current draw)
    headroom = net_available - state.current_amps
    if headroom >= 4:
        target = min(int(state.current_amps + 2), int(net_available), config.max_charging_amps)
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Headroom {headroom:.1f}A (net {net_available:.1f}A), ramping to {target}A",
            new_low_amp_count=0,
        )
    elif headroom >= 2:
        target = min(int(state.current_amps + 1), int(net_available), config.max_charging_amps)
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Headroom {headroom:.1f}A (net {net_available:.1f}A), increasing to {target}A",
            new_low_amp_count=0,
        )
    elif headroom <= -2 and not battery_is_charging:
        # Actually importing from grid (battery not helping) — reduce car
        target = max(int(state.current_amps - 1), config.min_charging_amps)
        if target <= config.min_charging_amps and state.current_amps <= config.min_charging_amps:
            new_count = state.low_amp_count + 1
            if new_count >= config.low_amp_stop_count:
                return Decision(
                    action=Action.STOP,
                    reason=f"No excess for {new_count} checks, stopping",
                    new_low_amp_count=0,
                )
            return Decision(
                action=Action.ADJUST,
                target_amps=config.min_charging_amps,
                reason=f"At minimum, low count {new_count}/{config.low_amp_stop_count}",
                new_low_amp_count=new_count,
            )
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Importing {state.grid_power:.0f}W, reducing to {target}A",
            new_low_amp_count=0,
        )
    elif real_grid_import and not battery_is_charging:
        # Grid importing and battery not charging — reduce
        target = max(int(state.current_amps - 1), config.min_charging_amps)
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Grid importing {state.grid_power:.0f}W, reducing to {target}A",
            new_low_amp_count=0,
        )
    else:
        # Stable — battery is charging, car is fine where it is
        return Decision(
            action=Action.NONE,
            target_amps=int(state.current_amps),
            reason=f"Stable at {int(state.current_amps)}A, battery charging {abs(state.battery_power):.0f}W, grid {state.grid_power:.0f}W",
            new_low_amp_count=0,
        )


def decide_night_amps(
    grid_power: float,
    grid_voltage: float,
    current_amps: float,
    grid_power_limit: float,
    max_charging_amps: int,
) -> Decision:
    """Decide charging amps for night mode (grid limit protection)."""
    if grid_voltage <= 0:
        return Decision(action=Action.NONE, reason="Grid voltage unavailable")

    headroom_w = grid_power_limit - grid_power
    headroom_amps = headroom_w / grid_voltage

    if headroom_amps <= -1:
        target = max(int(current_amps + headroom_amps), 0)
        if target < MIN_CHARGING_AMPS:
            return Decision(
                action=Action.STOP,
                reason=f"Grid at {grid_power:.0f}W, over {grid_power_limit:.0f}W limit — pausing",
            )
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Grid at {grid_power:.0f}W, reducing to {target}A to stay under limit",
        )

    if headroom_amps >= 2:
        target = min(int(current_amps + 1), max_charging_amps)
        return Decision(
            action=Action.ADJUST,
            target_amps=target,
            reason=f"Grid at {grid_power:.0f}W, {headroom_amps:.1f}A headroom — increasing to {target}A",
        )

    return Decision(
        action=Action.NONE,
        target_amps=int(current_amps),
        reason=f"Grid at {grid_power:.0f}W, maintaining {int(current_amps)}A",
    )


MIN_CHARGING_AMPS = 5
