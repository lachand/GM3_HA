"""Shared helpers for Home Assistant repair issues (Settings -> Repairs).

Every problem this integration surfaces as a repair issue -- an active
alarm bit (binary_sensor.py), a write the boiler explicitly rejected, or
the connection to the boiler being down (both coordinator.py) -- goes
through the same create/clear pattern. Centralizing it here means each
call site is one line instead of repeating async_create_issue's full
kwarg list, and the full set of issue types this integration can raise is
discoverable from one place instead of scattered across platforms.
"""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def raise_issue(
    hass: HomeAssistant,
    issue_id: str,
    translation_key: str,
    *,
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Creates a repair issue for this integration, or refreshes it if
    already open (e.g. updated placeholders) -- safe to call on every
    poll/check without tracking prior state yourself.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=severity,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


def clear_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Clears a repair issue if one is currently open. A no-op if it
    isn't -- safe to call unconditionally on every "things are fine" check.
    """
    ir.async_delete_issue(hass, DOMAIN, issue_id)
