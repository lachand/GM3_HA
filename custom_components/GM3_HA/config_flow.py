import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class PlumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère l'étape de configuration (Demande de l'IP)."""
    
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Première étape : l'utilisateur clique sur ajouter."""
        errors = {}

        if user_input is not None:
            # L'utilisateur a validé le formulaire
            # On crée l'entrée de configuration
            return self.async_create_entry(
                title=f"Chaudière ({user_input[CONF_IP_ADDRESS]})", 
                data=user_input
            )

        # Formulaire par défaut
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS, default="192.168.1.38"): str,
            }),
            errors=errors,
        )
