from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.const import CONF_USERNAME, CONF_API_TOKEN, CONF_DEVICES, CONF_PASSWORD

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
    vacuum = [ProscenicMapCamera(config['device'])]
    async_add_entities(vacuum, update_before_add=True)

class ProscenicMapCamera(Camera):
    """Representation of a local file camera."""
    _attr_frame_interval = 5 # seconds

    def __init__(self, proscenic_home):
        """Initialize Local File Camera component."""
        super().__init__()

        self.proscenic_home = proscenic_home
        self.vacuum = proscenic_home.vacuums[0]
        self.content_type = 'image/png'

    async def async_camera_image(self, width = None, height = None):
        """Return image response."""
        
        await self.vacuum.get_paths()
        return self.vacuum.get_map()

    @property
    def name(self):
        """Return the name of this camera."""
        return self.vacuum.uid + '_map'

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {}

    @property
    def device_info(self):
        """Return the device info."""
        return {"identifiers": {(DOMAIN, self.vacuum.uid)}}

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "camera" + self.vacuum.uid