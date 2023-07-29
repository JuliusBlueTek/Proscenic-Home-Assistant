from copy import deepcopy
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries, core
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_API_TOKEN, CONF_DEVICES, CONF_LOCATION
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry
)
import voluptuous as vol

from .const import DOMAIN
from .proscenicapis import *

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_LOCATION, default="US",): vol.In(["US", "EU", "CN"])
    }
)

class ProscenicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                proscenic_home = ProscenicHome(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                await proscenic_home.connect()
            except ValueError:
                errors["base"] = "auth"
            if not errors:
                self.data = {}
                self.data[CONF_USERNAME] = user_input[CONF_USERNAME]
                self.data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                self.data[CONF_LOCATION] = user_input[CONF_LOCATION]
                return self.async_create_entry(title="Proscenic", data=self.data)



        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

