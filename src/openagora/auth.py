"""Wallet-based authentication for the Open Agora SDK."""

from typing import Optional
from eth_account import Account
from eth_account.messages import encode_defunct
import httpx


class WalletAuth:
    """Handles wallet-based authentication with the Open Agora API."""

    def __init__(self, private_key: str, api_url: str):
        """Initialize wallet auth.

        Args:
            private_key: Ethereum private key (with or without 0x prefix)
            api_url: Base URL of the Open Agora API
        """
        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"
        self.account = Account.from_key(private_key)
        self.wallet = self.account.address.lower()
        self.api_url = api_url.rstrip("/")
        self._session_token: Optional[str] = None

    @property
    def session_token(self) -> Optional[str]:
        """Get the current session token."""
        return self._session_token

    async def authenticate(self) -> str:
        """Authenticate with the API and get a session token.

        Returns:
            Session token string
        """
        async with httpx.AsyncClient() as client:
            # Get challenge
            resp = await client.get(
                f"{self.api_url}/api/auth/challenge",
                params={"wallet": self.wallet},
            )
            resp.raise_for_status()
            challenge = resp.json()

            # Sign the challenge
            nonce = challenge["nonce"]
            message = challenge["message"]
            signable = encode_defunct(text=message)
            signed = self.account.sign_message(signable)
            signature = signed.signature.hex()

            # Verify and get session
            resp = await client.post(
                f"{self.api_url}/api/auth/verify",
                json={
                    "wallet": self.wallet,
                    "signature": f"0x{signature}" if not signature.startswith("0x") else signature,
                    "nonce": nonce,
                },
            )
            resp.raise_for_status()
            result = resp.json()

            self._session_token = result["session_token"]
            return self._session_token

    def get_headers(self) -> dict:
        """Get authorization headers for API requests.

        Returns:
            Dict with Authorization header
        """
        if not self._session_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {"Authorization": f"Bearer {self._session_token}"}

    async def ensure_authenticated(self) -> str:
        """Ensure we have a valid session, re-authenticating if needed.

        Returns:
            Session token
        """
        if not self._session_token:
            await self.authenticate()
        return self._session_token
