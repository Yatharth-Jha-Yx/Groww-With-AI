"""Log in to Groww and give back a ready-to-use GrowwAPI object.

All method names used in this project come from Groww's official Python SDK
`growwapi` (PyPI package, version 1.5.0, file growwapi/groww/client.py).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


class LoginError(RuntimeError):
    pass


def get_access_token() -> str:
    """Work out an access token from whatever is set in `.env`.

    Three options (same three that Groww's API-key page offers):
      A. GROWW_ACCESS_TOKEN                 -> used as-is
      B. GROWW_API_KEY + GROWW_TOTP_SECRET  -> 6-digit code made with pyotp
      C. GROWW_API_KEY + GROWW_API_SECRET   -> checksum "approval" flow
    """
    load_dotenv()
    token = os.getenv("GROWW_ACCESS_TOKEN", "").strip()
    if token:
        return token

    api_key = os.getenv("GROWW_API_KEY", "").strip()
    totp_secret = os.getenv("GROWW_TOTP_SECRET", "").strip()
    api_secret = os.getenv("GROWW_API_SECRET", "").strip()
    if not api_key:
        raise LoginError(
            "No Groww login found. Copy .env.example to .env and fill in "
            "GROWW_ACCESS_TOKEN, or GROWW_API_KEY with a TOTP secret / API secret."
        )

    from growwapi import GrowwAPI

    if totp_secret:
        import pyotp

        return GrowwAPI.get_access_token(api_key=api_key, totp=pyotp.TOTP(totp_secret).now())
    if api_secret:
        return GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
    raise LoginError("GROWW_API_KEY is set but neither GROWW_TOTP_SECRET nor GROWW_API_SECRET is.")


def connect():
    """Return a logged-in `growwapi.GrowwAPI` client."""
    from growwapi import GrowwAPI

    return GrowwAPI(get_access_token())
