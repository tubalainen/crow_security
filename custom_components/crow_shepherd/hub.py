"""Hub for Crow Shepherd — thin wrapper around crow_security_ng Session/Panel."""
from __future__ import annotations

import logging

from crow_security_ng import Session
from crow_security_ng.exceptions import AuthenticationError, ConnectionError, PanelNotFoundError
from crow_security_ng.models import Panel

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_PANEL_CODE, CONF_PANEL_MAC

_LOGGER = logging.getLogger(__name__)


class CrowHub:
    """Holds the authenticated Session and the resolved Panel object."""

    def __init__(
        self,
        email: str,
        password: str,
        mac: str,
        panel_code: str | None = None,
    ) -> None:
        """Initialise hub; does NOT connect yet."""
        self._mac = mac
        self._panel_code = panel_code or None
        self._session = Session(email, password)
        self._panel: Panel | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def mac(self) -> str:
        """Return the normalised panel MAC address."""
        return self._mac

    @property
    def session(self) -> Session:
        """Return the authenticated session."""
        return self._session

    @property
    def panel(self) -> Panel:
        """Return the resolved Panel.  Raises if async_connect not yet called."""
        if self._panel is None:
            raise RuntimeError("CrowHub.async_connect() has not been called yet")
        return self._panel

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_connect(self) -> None:
        """Login and resolve the panel.  Raises HA exceptions on failure."""
        try:
            self._panel = await self._session.get_panel(self._mac)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Crow Cloud authentication failed — check email/password"
            ) from err
        except PanelNotFoundError as err:
            raise ConfigEntryNotReady(
                f"Panel {self._mac!r} not found on Crow Cloud"
            ) from err
        except ConnectionError as err:
            raise ConfigEntryNotReady(
                f"Could not reach Crow Cloud: {err}"
            ) from err

        # Wire the user code so arm/disarm headers are sent automatically.
        if self._panel_code:
            self._panel.user_code = self._panel_code

        _LOGGER.debug("Panel connected: %s (id=%s)", self._panel.name, self._panel.id)

    async def async_close(self) -> None:
        """Close the underlying session."""
        try:
            await self._session.close()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Session close returned: %s", err)

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @classmethod
    def from_config_entry(cls, data: dict, options: dict) -> "CrowHub":
        """Build a CrowHub from config entry data + options dicts."""
        panel_code = options.get(CONF_PANEL_CODE) or data.get(CONF_PANEL_CODE) or None
        return cls(
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            mac=data[CONF_PANEL_MAC],
            panel_code=panel_code,
        )
