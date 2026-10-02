from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.components.climate import HVACAction
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from custom_components.ke2.const import DOMAIN

from .conftest import IP

CLIMATE = "climate.ke2_temp_com1_1"


async def _setup(hass: HomeAssistant, entry) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM  # the fixture controller reports °F
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_config_flow(hass: HomeAssistant, fake_lda) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": IP, "username": "ke2admin", "password": "ke2admin"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KE2 Temp (KE2LDA-431CA2)"
    assert result["result"].unique_id == "KE2LDA-431CA2"


async def test_config_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{IP}/modbus", exc=TimeoutError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": IP, "username": "ke2admin", "password": "ke2admin"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_setup_entities(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(CLIMATE)
    assert state is not None
    sp = fake_lda.all[0]["Setpoints"]["RoomTemperature"]
    assert state.attributes["temperature"] == sp
    assert state.attributes["current_temperature"] == fake_lda.all[0]["Status"]["RoomTemperature"]
    assert state.attributes["cut_in_temperature"] == sp + 5
    assert state.attributes["hvac_action"] in (HVACAction.COOLING, HVACAction.IDLE)
    assert state.attributes["min_temp"] == -50 and state.attributes["max_temp"] == 100

    ents = er.async_get(hass)
    ids = {e.entity_id for e in er.async_entries_for_config_entry(ents, config_entry.entry_id)}
    for expected in (
        "sensor.ke2_temp_com1_1_room_temperature",
        "sensor.ke2_temp_com1_1_mode",
        "sensor.ke2_temp_com1_1_alarms",
        "binary_sensor.ke2_temp_com1_1_cooling_relay",
        "binary_sensor.ke2_temp_com1_1_alarm_high_air_temp",
        "binary_sensor.ke2_temp_com1_1_room_probe_fault",
        "number.ke2_temp_com1_1_differential",
        "number.ke2_temp_com1_1_defrosts_per_day",
        "number.ke2_temp_com1_1_max_compressor_starts_per_hour",
        "time.ke2_temp_com1_1_controller_clock",
        "button.ke2_temp_com1_1_sync_controller_clock",
    ):
        assert expected in ids, expected
    # Advanced fields are not created unless the option is on.
    assert "number.ke2_temp_com1_1_modbus_address" not in ids
    assert "select.ke2_temp_com1_1_temperature_units" not in ids
    # No Manual Control on the KE2 Temp → no system switch.
    assert not any(i.startswith("switch.") for i in ids)

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    by_id = {ident: d for d in devices for ident in d.identifiers}
    hub = by_id.get((DOMAIN, "KE2LDA-431CA2"))
    ctrl = by_id.get((DOMAIN, "KE2LDA-431CA2-COM1-1"))
    assert hub is not None and ctrl is not None and ctrl.via_device_id == hub.id
    assert ctrl.model == "KE2 Temp" and hub.sw_version == "V1.3.2"


async def test_set_temperature_writes_and_confirms(
    hass: HomeAssistant, fake_lda, config_entry
) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 56}, blocking=True
    )
    assert fake_lda.writes == [{"RoomTemperature": 56}]
    assert hass.states.get(CLIMATE).attributes["temperature"] == 56


async def test_number_write_and_validation(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.ke2_temp_com1_1_differential", "value": 4},
        blocking=True,
    )
    assert fake_lda.writes[-1] == {"AirTempDiff": 4}
    # 3 starts/h is below the controller's 5..10 (0 = disabled) range → rejected locally.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.ke2_temp_com1_1_max_compressor_starts_per_hour", "value": 3},
            blocking=True,
        )
    assert len(fake_lda.writes) == 1


async def test_unconfirmed_write_raises(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    fake_lda.write_ok = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 57}, blocking=True
        )


async def test_raw_set_value_service(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "set_value",
        {"entity_id": CLIMATE, "field": "Start Time of Defrost 1", "value": "24:00"},
        blocking=True,
    )
    assert fake_lda.writes[-1] == {"Start Time of Defrost 1": "24:00"}


async def test_lda_offline_marks_unavailable(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    fake_lda.online = False
    await config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).state == "unavailable"
    fake_lda.online = True
    await config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).state == "cool"


async def test_unload(hass: HomeAssistant, fake_lda, config_entry) -> None:
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
