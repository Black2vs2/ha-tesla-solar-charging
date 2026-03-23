"""Lightweight Octopus Energy Italy API client for smart charge control."""

import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

OCTOPUS_IT_URL = "https://api.oeit-kraken.energy/v1/graphql/"


class OctopusItalyClient:
    """Minimal client for Octopus Energy Italy smart charge control."""

    def __init__(self, email: str, password: str, device_id: str) -> None:
        self._email = email
        self._password = password
        self._device_id = device_id
        self._token = None

    async def _ensure_token(self) -> None:
        """Login and get a JWT token."""
        if self._token is not None:
            return

        query = '''mutation {
            obtainKrakenToken(input: { email: "%s", password: "%s" }) {
                token
            }
        }''' % (self._email, self._password)

        async with aiohttp.ClientSession() as session:
            async with session.post(OCTOPUS_IT_URL, json={"query": query}) as resp:
                body = await resp.json()
                if "data" in body and body["data"]["obtainKrakenToken"]:
                    self._token = body["data"]["obtainKrakenToken"]["token"]
                else:
                    _LOGGER.error("Octopus Italy login failed")

    async def _graphql(self, query: str) -> dict | None:
        """Execute a GraphQL query with auth."""
        await self._ensure_token()
        if not self._token:
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"JWT {self._token}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(OCTOPUS_IT_URL, json={"query": query}, headers=headers) as resp:
                body = await resp.json()
                if "errors" in body:
                    _LOGGER.error("Octopus GraphQL error: %s", body["errors"][0].get("message"))
                    # Token might be expired, clear it
                    self._token = None
                    return None
                return body.get("data")

    async def enable_smart_charge(self) -> bool:
        """Enable smart charging (UNSUSPEND)."""
        query = '''mutation {
            updateDeviceSmartControl(input: { deviceId: "%s", action: UNSUSPEND }) {
                id
            }
        }''' % self._device_id

        result = await self._graphql(query)
        if result:
            _LOGGER.info("Octopus smart charge enabled")
            return True
        return False

    async def disable_smart_charge(self) -> bool:
        """Disable smart charging (SUSPEND)."""
        query = '''mutation {
            updateDeviceSmartControl(input: { deviceId: "%s", action: SUSPEND }) {
                id
            }
        }''' % self._device_id

        result = await self._graphql(query)
        if result:
            _LOGGER.info("Octopus smart charge disabled")
            return True
        return False
