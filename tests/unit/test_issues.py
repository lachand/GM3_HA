"""Unit tests for issues.py's shared repair-issue helpers.

Thin wrappers around homeassistant.helpers.issue_registry -- these tests
just pin the exact args passed through, since every call site (alarm
binary sensors, write-rejected/connection-lost in coordinator.py) relies
on this shape being consistent.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.helpers import issue_registry as ir

from custom_components.plum_ecomax.const import DOMAIN
from custom_components.plum_ecomax.issues import clear_issue, raise_issue


def test_raise_issue_forwards_expected_arguments():
    hass = MagicMock()
    with patch("custom_components.plum_ecomax.issues.ir.async_create_issue") as mock_create:
        raise_issue(hass, "my_issue", "my_translation_key", translation_placeholders={"x": "1"})

    mock_create.assert_called_once_with(
        hass,
        DOMAIN,
        "my_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="my_translation_key",
        translation_placeholders={"x": "1"},
    )


def test_raise_issue_defaults_translation_placeholders_to_none():
    hass = MagicMock()
    with patch("custom_components.plum_ecomax.issues.ir") as mock_ir:
        raise_issue(hass, "my_issue", "my_translation_key")

    assert mock_ir.async_create_issue.call_args.kwargs["translation_placeholders"] is None


def test_raise_issue_accepts_custom_severity():
    hass = MagicMock()
    from homeassistant.helpers import issue_registry as ir

    with patch("custom_components.plum_ecomax.issues.ir.async_create_issue") as mock_create:
        raise_issue(hass, "my_issue", "my_translation_key", severity=ir.IssueSeverity.ERROR)

    assert mock_create.call_args.kwargs["severity"] == ir.IssueSeverity.ERROR


def test_clear_issue_forwards_expected_arguments():
    hass = MagicMock()
    with patch("custom_components.plum_ecomax.issues.ir") as mock_ir:
        clear_issue(hass, "my_issue")

    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, "my_issue")
