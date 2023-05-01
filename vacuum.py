"""Support for Ecovacs Ecovacs Vacuums."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout

from homeassistant.components.vacuum import VacuumEntity, VacuumEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.const import CONF_USERNAME, CONF_API_TOKEN, CONF_DEVICES, CONF_PASSWORD

from .const import DOMAIN
from .proscenicapis import *

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    proscenic_home = ProscenicHome(config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD], None)
    await proscenic_home.connect()
    vacuum = [ProscenicVacuum(proscenic_home)]
    async_add_entities(vacuum, update_before_add=True)

class ProscenicVacuum(VacuumEntity):
    """Ecovacs Vacuums such as Deebot."""
    _attr_should_poll = True
    _attr_fan_speed_list = ['quiet', 'strong']
    _attr_supported_features = (
        VacuumEntityFeature.TURN_ON
        | VacuumEntityFeature.TURN_OFF
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATUS
        | VacuumEntityFeature.START
    )

    def __init__(self, proscenic_home) -> None:
        """Initialize the Ecovacs Vacuum."""
        self.proscenic_home = proscenic_home
        self.vacuum = proscenic_home.vacuums[0]
        self._attr_name = self.vacuum.get_name()
        self._error = None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        return

    async def async_update(self) -> None:
        await self.vacuum.update_state()
        if self.vacuum.status and 'mode' in self.vacuum.status:
            self._attr_status = self.vacuum.status['mode']
        if self.vacuum.status and 'elec' in self.vacuum.status:
            self._attr_battery_level = self.vacuum.status['elec']

    def on_error(self, error):
        """Handle an error event from the robot.
        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error == "no_error":
            self._error = None
        else:
            self._error = error
        
    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self.vacuum.uid

    @property
    def is_on(self) -> bool:
        """Return true if vacuum is currently cleaning."""
        if self.vacuum.status and 'mode' in self.vacuum.status:
            return self.vacuum.status['mode'] == 'sweep'
        return False

    @property
    def is_charging(self) -> bool:
        """Return true if vacuum is currently charging."""
        if self.vacuum.status and 'mode' in self.vacuum.status:
            return self.vacuum.status['mode'] == 'charge'
        return True

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return super().status

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.is_charging
        )

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return super().battery_level

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if self.vacuum.status and 'workNoisy' in self.vacuum.status:
            return self.vacuum.status['workNoisy']
        return 'strong'

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self.vacuum.proscenic_powermode(fan_speed)
        self.vacuum.status['workNoisy'] = fan_speed
        self.schedule_update_ha_state()

    async def async_start(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        if self.vacuum.status['mode'] == 'pause':
            await self.vacuum.continue_cleaning()
        else:
            await self.vacuum.start_clean()
        self.vacuum.status['mode'] = 'sweep'
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on and start cleaning."""
        await self.async_start()

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the vacuum cleaner."""
        await self.vacuum.pause_cleaning()
        self.vacuum.status['mode'] = 'pause'
        self.schedule_update_ha_state()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.async_pause()

    async def async_start_pause(self, **kwargs: Any) -> None:
        mode = self.vacuum.status['mode']
        if mode == None or mode == '' or mode == 'pause':
            await self.async_start()
        elif mode == 'sweep':
            await self.async_pause()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.vacuum.return_to_dock()
        self.vacuum.status['mode'] = 'returning home'
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off stopping the cleaning and returning home."""
        await self.async_return_to_base()

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        return

