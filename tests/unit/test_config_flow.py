"""Unit tests for config_flow.py: connection validation (Family: config
flow validation, mocked PlumDevice).

`_validate_connection()` and `_build_data_schema()` are free functions
(not ConfigFlow methods), so they can be exercised directly without a real
FlowManager/hass -- only `hass.config.path()` is used, stubbed with a
plain MagicMock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from custom_components.plum_ecomax import config_flow as config_flow_module
from custom_components.plum_ecomax.config_flow import (
    PlumConfigFlow,
    PlumOptionsFlow,
    _build_data_schema,
    _validate_connection,
)
from custom_components.plum_ecomax.const import (
    CONF_ACTIVE_CIRCUITS,
    CONF_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)


def _fake_hass():
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda p: f"/config/{p}")
    return hass


def _patch_device(monkeypatch, *, load_map_error=None, get_value_return=42, get_value_error=None):
    fake_device = MagicMock()
    fake_device.load_map = MagicMock(side_effect=load_map_error)
    if get_value_error is not None:
        fake_device.get_value = AsyncMock(side_effect=get_value_error)
    else:
        fake_device.get_value = AsyncMock(return_value=get_value_return)
    monkeypatch.setattr(config_flow_module, "PlumDevice", lambda *a, **k: fake_device)
    return fake_device


class TestValidateConnection:
    @pytest.mark.asyncio
    async def test_successful_probe_returns_no_error(self, monkeypatch):
        _patch_device(monkeypatch, get_value_return=42)

        error = await _validate_connection(_fake_hass(), {
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PORT: 8899, CONF_PASSWORD: "0000",
        })

        assert error is None

    @pytest.mark.asyncio
    async def test_map_load_failure_returns_cannot_load_map(self, monkeypatch):
        _patch_device(monkeypatch, load_map_error=OSError("no such file"))

        error = await _validate_connection(_fake_hass(), {
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000",
        })

        assert error == "cannot_load_map"

    @pytest.mark.asyncio
    async def test_no_value_returned_means_cannot_connect(self, monkeypatch):
        _patch_device(monkeypatch, get_value_return=None)

        error = await _validate_connection(_fake_hass(), {
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000",
        })

        assert error == "cannot_connect"

    @pytest.mark.asyncio
    async def test_exception_during_read_means_cannot_connect(self, monkeypatch):
        _patch_device(monkeypatch, get_value_error=OSError("connection refused"))

        error = await _validate_connection(_fake_hass(), {
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000",
        })

        assert error == "cannot_connect"


class TestBuildDataSchema:
    def test_schema_validates_full_input(self):
        schema = _build_data_schema({})
        result = schema({
            CONF_IP_ADDRESS: "192.168.1.38",
            CONF_PORT: 8899,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "0000",
            CONF_ACTIVE_CIRCUITS: ["2"],
        })
        assert result[CONF_IP_ADDRESS] == "192.168.1.38"
        assert result[CONF_ACTIVE_CIRCUITS] == ["2"]

    def test_password_field_is_masked(self):
        from homeassistant.helpers.selector import TextSelector, TextSelectorType

        schema = _build_data_schema({})
        password_validator = next(
            v for k, v in schema.schema.items() if getattr(k, "schema", k) == CONF_PASSWORD
        )
        assert isinstance(password_validator, TextSelector)
        assert password_validator.config["type"] == TextSelectorType.PASSWORD

    def test_password_defaults_when_omitted(self):
        # vol.Required + a default means the key is auto-filled, not
        # enforced as "must be present" -- omitting it must not raise.
        schema = _build_data_schema({})
        result = schema({CONF_IP_ADDRESS: "192.168.1.38", CONF_ACTIVE_CIRCUITS: ["2"]})
        assert result[CONF_PASSWORD] == "0000"

    def test_ip_address_default_reflects_prior_input(self):
        schema = _build_data_schema({CONF_IP_ADDRESS: "10.0.0.5"})
        # Applying the schema to an empty dict pulls in the field defaults,
        # which is how the options flow pre-fills the form from entry.data.
        result = schema({CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"]})
        assert result[CONF_IP_ADDRESS] == "10.0.0.5"

    def test_update_interval_defaults_when_omitted(self):
        schema = _build_data_schema({})
        result = schema({
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"],
        })
        assert result[CONF_UPDATE_INTERVAL] == UPDATE_INTERVAL

    def test_update_interval_default_reflects_prior_input(self):
        schema = _build_data_schema({CONF_UPDATE_INTERVAL: 60})
        result = schema({
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"],
        })
        assert result[CONF_UPDATE_INTERVAL] == 60

    def test_update_interval_accepts_value_within_bounds(self):
        schema = _build_data_schema({})
        result = schema({
            CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"],
            CONF_UPDATE_INTERVAL: 90,
        })
        assert result[CONF_UPDATE_INTERVAL] == 90

    def test_update_interval_rejects_value_below_minimum(self):
        schema = _build_data_schema({})
        with pytest.raises(vol.Invalid):
            schema({
                CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"],
                CONF_UPDATE_INTERVAL: MIN_UPDATE_INTERVAL - 1,
            })

    def test_update_interval_rejects_value_above_maximum(self):
        schema = _build_data_schema({})
        with pytest.raises(vol.Invalid):
            schema({
                CONF_IP_ADDRESS: "192.168.1.38", CONF_PASSWORD: "0000", CONF_ACTIVE_CIRCUITS: ["2"],
                CONF_UPDATE_INTERVAL: MAX_UPDATE_INTERVAL + 1,
            })


class TestOptionsFlowConstruction:
    """Regression for a real bug reported by the user: opening the options
    flow returned "500 Internal Server Error" in production. Cause: on
    current Home Assistant, OptionsFlow.config_entry is a read-only
    property (computed from self.hass/self.handler, unavailable until
    after init) -- PlumOptionsFlow.__init__ used to do `self.config_entry
    = config_entry`, which raises AttributeError ("can't set attribute")
    the moment the flow manager constructs the flow, before any HTTP
    response can be built. Confirmed against the real installed
    homeassistant.config_entries.OptionsFlow (not a mock), which is the
    only way to catch this class of bug -- it wouldn't show up against a
    hand-rolled stub.
    """

    def test_async_get_options_flow_does_not_raise(self):
        mock_entry = MagicMock()
        # This call alone used to raise AttributeError under the old
        # PlumOptionsFlow(config_entry) pattern.
        flow = PlumConfigFlow.async_get_options_flow(mock_entry)
        assert isinstance(flow, PlumOptionsFlow)

    def test_config_entry_resolves_after_framework_style_init(self):
        # Mimics how FlowManager actually wires up a flow: construct with
        # no arguments, then set hass/handler afterward.
        flow = PlumOptionsFlow()
        mock_entry = MagicMock()
        mock_hass = MagicMock()
        mock_hass.config_entries.async_get_known_entry.return_value = mock_entry
        flow.hass = mock_hass
        flow.handler = "some-entry-id"

        assert flow.config_entry is mock_entry
