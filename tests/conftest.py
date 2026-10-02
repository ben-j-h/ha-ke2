"""Test harness: an in-memory fake KE2 LDA behind HA's aiohttp mocker."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.ke2.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
IP = "192.168.30.165"
BASE = f"http://{IP}"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


class FakeLDA:
    """Serves GETs from captured samples; PUT /Setpoints mutates the state."""

    def __init__(self) -> None:
        self.all = load("modbus_COM1_all.json")
        self.limits = load("modbus_COM1_1_limits.json")
        self.writes: list[dict[str, Any]] = []
        self.write_ok = True
        self.online = True

    def install(self, mock: AiohttpClientMocker) -> None:
        async def get_all(method, url, data):
            if not self.online:
                return AiohttpClientMockResponse(method, url, exc=TimeoutError())
            return AiohttpClientMockResponse(method, url, json=copy.deepcopy(self.all))

        async def put_setpoints(method, url, data):
            self.writes.append(dict(data))
            if self.write_ok:
                self.all[0]["Setpoints"].update(data)
                body = {"Status": 200, "Message": "Success", "Details": "Data Successfully written"}
            else:
                body = {"Status": 500, "Message": "Failed"}
            return AiohttpClientMockResponse(method, url, json=body)

        mock.get(f"{BASE}/modbus", json=["COM1"])
        mock.get(f"{BASE}/modbus/COM1/all", side_effect=get_all)
        mock.get(f"{BASE}/modbus/COM1/1", side_effect=lambda m, u, d: _one(self, m, u))
        mock.get(f"{BASE}/modbus/COM1/1/limits", json=self.limits)
        mock.get(f"{BASE}/version.json", json=load("version.json"))
        mock.get(
            f"{BASE}/smartaccess/client/exec/networkInfo.lua",
            json=load("smartaccess_client_exec_networkInfo.lua.json"),
        )
        mock.post(
            f"{BASE}/auth/login",
            json={"status": "success", "message": "logged in", "sessionID": "sid"},
        )
        mock.post(f"{BASE}/auth/logout", json={"status": "success"})
        mock.put(f"{BASE}/modbus/COM1/1/Setpoints", side_effect=put_setpoints)


async def _one(fake: FakeLDA, method, url):
    return AiohttpClientMockResponse(method, url, json=copy.deepcopy(fake.all[0]))


@pytest.fixture
def fake_lda(aioclient_mock: AiohttpClientMocker) -> FakeLDA:
    fake = FakeLDA()
    fake.install(aioclient_mock)
    return fake


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="KE2LDA-431CA2",
        title="KE2 Temp (KE2LDA-431CA2)",
        data={"host": IP, "username": "ke2admin", "password": "ke2admin"},
    )
