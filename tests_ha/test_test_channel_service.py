import asyncio

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from conftest import setup_integration
from fakebus import SimDevice


@pytest.fixture
async def relay(hass):
    device = SimDevice((1, 89), 0x01AC, "Rėlės", functions=[(1, 1, 4)], levels=[0, 100, 0, 0])
    curtains = SimDevice((1, 40), 0x02CF, curtains={1: 0})
    await setup_integration(hass, [device, curtains])
    return device, curtains


async def call(hass, data, **kwargs):
    return await hass.services.async_call("buspro", "test_channel", data, blocking=True, return_response=True,
                                          **kwargs)


async def test_on_off_and_level(hass, relay):
    device, _curtains = relay
    on = await call(hass, {"address": "1.89", "channel": 1, "action": "on"})
    level = await call(hass, {"address": "1.89", "channel": 3, "action": "level", "level": 40})

    assert on["confirmed"] is True and on["value"] == 100 and on["confirmed_by"] == "0x0032"
    assert level["value"] == 40
    assert device.levels == [100, 100, 40, 0]


async def test_pulse_restores_and_stop_restores_pending(hass, relay):
    device, _curtains = relay
    result = await call(hass, {"address": "1.89", "channel": 1, "action": "pulse", "duration": 0.5})
    assert result["previous"] == 0 and device.levels[0] == 100
    await asyncio.sleep(0.7)
    assert device.levels[0] == 0

    await call(hass, {"address": "1.89", "channel": 4, "action": "pulse", "duration": 30})
    assert device.levels[3] == 100
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert device.levels[3] == 0


async def test_curtain(hass, relay):
    _device, curtains = relay
    result = await call(hass, {"address": "1.40", "channel": 1, "target": "curtain", "action": "open"})
    assert result["confirmed"] is True and curtains.curtains == {1: 1}


async def test_invalid_requests(hass, relay):
    with pytest.raises(HomeAssistantError, match="not available"):
        await call(hass, {"address": "1.40", "channel": 1, "target": "curtain", "action": "pulse"})
    with pytest.raises(HomeAssistantError, match="needs a level"):
        await call(hass, {"address": "1.89", "channel": 1, "action": "level"})
    with pytest.raises(HomeAssistantError, match="Too many"):
        await call(hass, {"address": "1.89", "channel": 2, "action": "on"})
        await call(hass, {"address": "1.89", "channel": 2, "action": "off"})


async def test_admin_only(hass, relay, hass_read_only_user):
    with pytest.raises(Unauthorized):
        await call(hass, {"address": "1.89", "channel": 1, "action": "on"},
                   context=Context(user_id=hass_read_only_user.id))
    with pytest.raises(Unauthorized):
        await hass.services.async_call("buspro", "scan", {"rounds": 1, "interval": 0.2}, blocking=True,
                                       return_response=True, context=Context(user_id=hass_read_only_user.id))
