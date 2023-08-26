"""Support for Ecovacs Ecovacs Vacuums."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, PROSCENICHOME
from .proscenicapis import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    vacuum = [ProscenicVacuum(config['device'])]
    async_add_entities(vacuum, update_before_add=True)

class ProscenicVacuum(StateVacuumEntity):
    """Ecovacs Vacuums such as Deebot."""
    _attr_should_poll = False
    _attr_fan_speed_list = ['quiet', 'auto', 'strong']
    _attr_fan_speed = 'auto'
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.SEND_COMMAND
    )

    def __init__(self, proscenic_home) -> None:
        """Initialize the Ecovacs Vacuum."""
        self.proscenic_home = proscenic_home
        self.vacuum = proscenic_home.vacuums[0]
        self._attr_name = self.vacuum.get_name()
        self._error = None
        self.vacuum.subcribe(lambda vacuum: self.schedule_update_ha_state(True))

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        return

    async def async_update(self) -> None:
        if not await self.vacuum.connect():
            await self.proscenic_home.connect()
        await self.vacuum.update_state()
        if not self.vacuum.status:
            return
        if 'mode' in self.vacuum.status:
            self._attr_status = self.vacuum.status['mode']
        if 'elec' in self.vacuum.status:
            self._attr_battery_level = self.vacuum.status['elec']
        if 'workNoisy' in self.vacuum.status:
            self._attr_fan_speed = self.vacuum.status['workNoisy']
        if 'errorState' in self.vacuum.status:
            if len(self.vacuum.status['errorState']) > 0:
                self._error = self.vacuum.status['errorState'][0]

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self.vacuum.uid

    @property
    def is_on(self) -> bool:
        """Return true if vacuum is currently cleaning."""
        return self._attr_status == 'sweep'

    @property
    def is_charging(self) -> bool:
        """Return true if vacuum is currently charging."""
        return self._attr_status == 'charge'

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
        return super().fan_speed

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the vacuum cleaner."""
        await self.vacuum.pause_cleaning()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.vacuum.return_to_dock()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self.vacuum.proscenic_powermode(fan_speed)

    async def async_start(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        if self._attr_status == 'pause':
            await self.vacuum.continue_cleaning()
        else:
            await self.vacuum.start_clean()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.async_pause()

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        if command == 'app_segment_clean':
            duplicates_removed = list(dict.fromkeys(params))
            string_list = ','.join(str(e) for e in duplicates_removed)
            await self.vacuum.clean_segment(string_list)
            self.vacuum.status['mode'] = 'sweep'
            


