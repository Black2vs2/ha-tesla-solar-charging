"""Telegram notification with actionable inline keyboard."""

import logging

from homeassistant.core import HomeAssistant

from .planner import ChargePlan, format_plan_message

_LOGGER = logging.getLogger(__name__)

# Callback data for Telegram inline keyboard
CALLBACK_CHARGE_TONIGHT = "/tsc_charge_tonight"
CALLBACK_SKIP_CHARGE = "/tsc_skip_charge"


async def send_plan_notification(
    hass: HomeAssistant,
    chat_id: int,
    plan: ChargePlan,
) -> None:
    """Send charge plan via Telegram with override buttons."""
    message = format_plan_message(plan)

    if plan.charge_tonight:
        keyboard = [
            [f"Charge tonight (auto in 30min):{CALLBACK_CHARGE_TONIGHT}"],
            [f"Skip — I'll use solar:{CALLBACK_SKIP_CHARGE}"],
        ]
    else:
        keyboard = [
            [f"Skip night charge (auto in 30min):{CALLBACK_SKIP_CHARGE}"],
            [f"Override — charge tonight:{CALLBACK_CHARGE_TONIGHT}"],
        ]

    try:
        await hass.services.async_call(
            "telegram_bot", "send_message",
            {
                "chat_id": chat_id,
                "message": message,
                "parse_mode": "markdown",
                "inline_keyboard": keyboard,
            },
            blocking=True,
        )
        _LOGGER.info("Sent charge plan notification via Telegram")
    except Exception as err:
        _LOGGER.error("Failed to send Telegram notification: %s", err)
        # Fallback to persistent notification
        await hass.services.async_call(
            "persistent_notification", "create",
            {
                "title": "Tesla Charging Plan",
                "message": message.replace("*", "**"),
            },
        )


async def send_action_notification(
    hass: HomeAssistant,
    chat_id: int,
    message: str,
) -> None:
    """Send a simple status notification via Telegram."""
    try:
        await hass.services.async_call(
            "telegram_bot", "send_message",
            {
                "chat_id": chat_id,
                "message": message,
            },
            blocking=True,
        )
    except Exception as err:
        _LOGGER.error("Failed to send Telegram notification: %s", err)


# ---------------------------------------------------------------------------
# Message formatters for critical events
# ---------------------------------------------------------------------------

def format_ble_alert(status: str, detail: str) -> str:
    """Format a BLE / ESP32 alert message."""
    if status == "esp32_offline":
        return (
            f"*ESP32 Offline*\n"
            f"The ESP32 BLE bridge appears to be offline.\n"
            f"Detail: {detail}"
        )
    # Generic BLE error fallback
    return (
        f"*BLE Error*\n"
        f"A Bluetooth Low Energy error was detected.\n"
        f"Detail: {detail}"
    )


def format_charge_stopped(reason: str) -> str:
    """Format a charge-stopped notification message."""
    return f"*Charging Stopped*\nReason: {reason}"


def format_charge_limit_reached(tesla_soc: float, limit: float) -> str:
    """Format a charge-limit-reached notification message."""
    return (
        f"*Charge Limit Reached*\n"
        f"Tesla SOC: {tesla_soc:.0f}% — limit is {limit:.0f}%.\n"
        f"Charging has been paused."
    )


def format_night_mode_change(entering: bool) -> str:
    """Format a night-mode transition notification message."""
    if entering:
        return (
            "*Night Mode Active*\n"
            "Solar charging is paused overnight. "
            "Cheap-rate / scheduled charging may run if configured."
        )
    return (
        "*Night Mode Ended*\n"
        "Solar charging window has resumed."
    )


def format_daily_report(
    solar_kwh: float,
    grid_kwh: float,
    total_kwh: float,
    peak_amps: float,
    hours_charged: float,
    forecast_kwh: float,
    actual_production_kwh: float,
) -> str:
    """Format a daily summary report message."""
    if forecast_kwh > 0:
        accuracy_pct = (actual_production_kwh / forecast_kwh) * 100
        accuracy_str = f"{accuracy_pct:.0f}%"
    else:
        accuracy_str = "N/A"

    return (
        f"*Daily Charging Report*\n"
        f"Solar charged: {solar_kwh:.1f} kWh\n"
        f"Grid charged:  {grid_kwh:.1f} kWh\n"
        f"Total charged: {total_kwh:.1f} kWh\n"
        f"Peak current:  {peak_amps:.0f} A\n"
        f"Hours charged: {hours_charged:.1f} h\n"
        f"Forecast: {forecast_kwh:.1f} kWh | Actual: {actual_production_kwh:.1f} kWh "
        f"(accuracy: {accuracy_str})"
    )


async def send_alert_notification(
    hass: HomeAssistant,
    chat_id: int,
    message: str,
) -> None:
    """Send a critical alert notification via Telegram with markdown."""
    try:
        await hass.services.async_call(
            "telegram_bot", "send_message",
            {
                "chat_id": chat_id,
                "message": message,
                "parse_mode": "markdown",
            },
            blocking=True,
        )
        _LOGGER.info("Sent alert notification via Telegram")
    except Exception as err:
        _LOGGER.error("Failed to send Telegram alert: %s", err)
