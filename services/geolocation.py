import logging
import ipaddress

import httpx

import config


def is_valid_ip(ip_str: str) -> bool:
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


async def lookup_ip(ip: str) -> dict:
    url = config.IP_API_URL.format(ip=ip)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def lookup_zip(country_code: str, postal_code: str) -> dict | None:
    """Returns the parsed dict, or None if 404/not found."""
    url = config.ZIP_API_URL.format(
        country_code=country_code, postal_code=postal_code
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise
    except httpx.HTTPError:
        raise