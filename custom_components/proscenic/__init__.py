"""Proscenic Custom Component."""
import asyncio
import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_USERNAME, CONF_DEVICES, CONF_PASSWORD, CONF_LOCATION

from .const import DOMAIN, PROSCENICHOME
from .proscenicapis import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(config_entry.data)
    hass.data[DOMAIN][config_entry.entry_id] = hass_data

    proscenic_home = ProscenicHome(config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD], config_entry.data[CONF_LOCATION])
    await proscenic_home.connect()
    hass.data[DOMAIN][config_entry.entry_id]['device'] = proscenic_home

    if 1 > len(proscenic_home.vacuums):
        return False

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "vacuum")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "camera")
    )
    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    hass.data[DOMAIN][config_entry.entry_id]['device'].disconnect()
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(config_entry, "vacuum")]
        )
    )
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(config_entry, "camera")]
        )
    )

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok