import logging
import ipaddress
import asyncio
import socket
import re

import httpx

import config


# ---------------------------------------------------------------------------
# IP validation
# ---------------------------------------------------------------------------

def is_valid_ip(ip_str: str) -> bool:
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def is_private_ip(ip_str: str) -> bool:
    try:
        return ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return False


def is_loopback_ip(ip_str: str) -> bool:
    try:
        return ipaddress.ip_address(ip_str).is_loopback
    except ValueError:
        return False


def is_reserved_ip(ip_str: str) -> bool:
    try:
        return ipaddress.ip_address(ip_str).is_reserved
    except ValueError:
        return False


def is_multicast_ip(ip_str: str) -> bool:
    try:
        return ipaddress.ip_address(ip_str).is_multicast
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Domain validation & DNS resolution
# ---------------------------------------------------------------------------

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Z\d-]{1,63}(?<!-)(\.(?!-)[A-Z\d-]{1,63}(?<!-))+\.?$",
    re.IGNORECASE,
)


def is_valid_domain(domain: str) -> bool:
    domain = domain.strip().lower().rstrip(".")
    if not domain or len(domain) > 253:
        return False
    return bool(_DOMAIN_RE.match(domain))


async def resolve_domain(domain: str) -> dict:
    """Resolve a domain name to its IPv4 and IPv6 addresses.

    Returns ``{"ipv4": list[str], "ipv6": list[str], "ip": str}`` where ``ip``
    is the first resolved IPv4 (or IPv6 if no A records).
    Raises ``socket.gaierror`` on DNS failure.
    """
    domain = domain.strip().lower().rstrip(".")
    loop = asyncio.get_event_loop()

    ipv4: list[str] = []
    ipv6: list[str] = []

    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(domain, None, family=socket.AF_INET),
            timeout=config.DNS_TIMEOUT,
        )
        ipv4 = sorted({i[4][0] for i in infos})
    except asyncio.TimeoutError:
        pass
    except socket.gaierror:
        pass

    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(domain, None, family=socket.AF_INET6),
            timeout=config.DNS_TIMEOUT,
        )
        ipv6 = sorted({i[4][0] for i in infos})
    except asyncio.TimeoutError:
        pass
    except socket.gaierror:
        pass

    if not ipv4 and not ipv6:
        raise socket.gaierror(8, "Domain name resolution failed")

    ip = ipv4[0] if ipv4 else ipv6[0]
    return {"ipv4": ipv4, "ipv6": ipv6, "ip": ip}


# ---------------------------------------------------------------------------
# Reverse DNS
# ---------------------------------------------------------------------------

async def reverse_dns(ip: str) -> str | None:
    """Return the PTR hostname for *ip* or ``None`` if no PTR record exists."""
    loop = asyncio.get_event_loop()
    try:
        name, _ = await asyncio.wait_for(
            loop.getnameinfo((ip, 0), socket.NI_NAMEREQD),
            timeout=config.DNS_TIMEOUT,
        )
        return name if name else None
    except (asyncio.TimeoutError, socket.gaierror, socket.herror, OSError):
        # Fallback: try gethostbyaddr via executor
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, socket.gethostbyaddr, ip),
                timeout=config.DNS_TIMEOUT,
            )
            return result[0] if result and result[0] != ip else None
        except (asyncio.TimeoutError, socket.herror, socket.gaierror, OSError):
            return None


# ---------------------------------------------------------------------------
# IP geolocation (ip-api.com)
# ---------------------------------------------------------------------------

async def lookup_ip(ip: str) -> dict:
    url = config.IP_API_URL.format(ip=ip)
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def lookup_zip(country_code: str, postal_code: str) -> dict | None:
    """Returns the parsed dict, or None if 404/not found."""
    url = config.ZIP_API_URL.format(
        country_code=country_code, postal_code=postal_code
    )
    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise
    except httpx.HTTPError:
        raise


# ---------------------------------------------------------------------------
# WHOIS via RDAP
# ---------------------------------------------------------------------------

async def lookup_whois_ip(ip: str) -> dict | None:
    """Fetch WHOIS/RDAP data for an IP address.

    Returns a normalized dict with keys: asn, organization, netname, cidr,
    abuse_email, country, registry, created.  Missing fields are ``None``.
    Returns ``None`` if all RDAP endpoints fail.
    """
    for url_template in (config.RDAP_BOOTSTRAP_URL, config.RDAP_IP_URL):
        url = url_template.format(ip=ip)
        try:
            async with httpx.AsyncClient(
                timeout=config.HTTP_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers={"Accept": "application/rdap+json"})
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                return _parse_rdap(resp.json())
        except httpx.TimeoutException:
            logging.warning("RDAP timeout for %s via %s", ip, url)
            continue
        except httpx.HTTPError as e:
            logging.warning("RDAP HTTP error for %s via %s: %s", ip, url, e)
            continue
    return None


async def lookup_whois_domain(domain: str) -> dict | None:
    """Fetch WHOIS/RDAP data for a domain name via rdap.org."""
    domain = domain.strip().lower().rstrip(".")
    url = f"https://rdap.org/domain/{domain}"
    try:
        async with httpx.AsyncClient(
            timeout=config.HTTP_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url, headers={"Accept": "application/rdap+json"})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_rdap_domain(resp.json(), domain)
    except httpx.TimeoutException:
        logging.warning("RDAP timeout for domain %s", domain)
    except httpx.HTTPError as e:
        logging.warning("RDAP HTTP error for domain %s: %s", domain, e)
    return None


def _parse_rdap(data: dict) -> dict:
    """Normalize RDAP JSON into a flat dict."""
    result = {
        "asn": None,
        "organization": None,
        "netname": None,
        "cidr": None,
        "abuse_email": None,
        "country": None,
        "registry": None,
        "created": None,
    }

    result["netname"] = data.get("name") or None
    result["registry"] = data.get("port43") or None

    cidrs = data.get("cidr0_cidrs") or []
    if cidrs:
        first = cidrs[0]
        prefix = first.get("v4prefix") or first.get("v6prefix")
        length = first.get("length")
        if prefix and length is not None:
            result["cidr"] = f"{prefix}/{length}"

    for ev in data.get("events") or []:
        if ev.get("eventAction") == "registration":
            result["created"] = ev.get("eventDate")
            break

    for entity in data.get("entities") or []:
        roles = entity.get("roles") or []
        vcard = (entity.get("vcardArray") or [None, []])[1]
        if not vcard:
            vcard = []
        if "registrant" in roles:
            for v in vcard:
                if v[0] == "fn":
                    result["organization"] = v[3]
                    break
        # Nested entities (abuse/tech/admin)
        for sub in entity.get("entities") or []:
            sub_roles = sub.get("roles") or []
            if "abuse" in sub_roles:
                for v in (sub.get("vcardArray") or [None, []])[1]:
                    if v[0] == "email" and not result["abuse_email"]:
                        result["abuse_email"] = v[3]
        # Top-level abuse
        if "abuse" in roles:
            for v in vcard:
                if v[0] == "email" and not result["abuse_email"]:
                    result["abuse_email"] = v[3]

    return result


def _parse_rdap_domain(data: dict, domain: str) -> dict:
    result = {
        "asn": None,
        "organization": None,
        "netname": domain,
        "cidr": None,
        "abuse_email": None,
        "country": None,
        "registry": data.get("port43") or None,
        "created": None,
    }
    for ev in data.get("events") or []:
        if ev.get("eventAction") == "registration":
            result["created"] = ev.get("eventDate")
            break
    for entity in data.get("entities") or []:
        roles = entity.get("roles") or []
        vcard = (entity.get("vcardArray") or [None, []])[1]
        if not vcard:
            vcard = []
        if "registrar" in roles:
            for v in vcard:
                if v[0] == "fn":
                    result["organization"] = v[3]
                    break
        if "abuse" in roles:
            for v in vcard:
                if v[0] == "email" and not result["abuse_email"]:
                    result["abuse_email"] = v[3]
        for sub in entity.get("entities") or []:
            if "abuse" in (sub.get("roles") or []):
                for v in (sub.get("vcardArray") or [None, []])[1]:
                    if v[0] == "email" and not result["abuse_email"]:
                        result["abuse_email"] = v[3]
    return result


# ---------------------------------------------------------------------------
# IP risk analysis
# ---------------------------------------------------------------------------

async def analyze_ip_risk(ip: str, geo_result: dict | None = None) -> dict:
    """Analyze an IP and return a risk assessment.

    Returns a dict:
        {"level": "Low|Medium|High", "emoji": "🟢|🟡|🔴",
         "flags": [str], "reasons": [str]}

    Only uses reliable data: ip-api flags (proxy, hosting, mobile) and
    ipaddress classification (private, loopback, reserved, multicast).
    Never invents data.
    """
    flags: list[str] = []
    reasons: list[str] = []

    # 1) IANA allocation classification (always available, no API needed)
    if is_private_ip(ip):
        flags.append("Private")
        reasons.append("IP belongs to a private range (RFC 1918 / RFC 4193).")
    if is_loopback_ip(ip):
        flags.append("Loopback")
        reasons.append("IP is a loopback address (127.0.0.0/8 or ::1).")
    if is_reserved_ip(ip):
        flags.append("Reserved")
        reasons.append("IP is in an IANA-reserved range.")
    if is_multicast_ip(ip):
        flags.append("Multicast")
        reasons.append("IP is a multicast address.")

    # 2) ip-api flags (only if we have a successful geo_result)
    if geo_result and geo_result.get("status") == "success":
        if geo_result.get("proxy"):
            flags.append("Proxy/VPN")
            reasons.append("ip-api.com reports this IP as a proxy/VPN.")
        if geo_result.get("hosting"):
            flags.append("Datacenter/Hosting")
            reasons.append(
                "ip-api.com reports this IP as a hosting provider / datacenter."
            )
        if geo_result.get("mobile"):
            flags.append("Mobile network")
            reasons.append("ip-api.com reports this IP as a mobile network.")

        org = (geo_result.get("org") or "").lower()
        isp = (geo_result.get("isp") or "").lower()
        asname = (geo_result.get("asname") or "").lower()
        combined = f"{isp} {org} {asname}"
        for marker in ("tor", "exit", "relay"):
            if marker in combined:
                if "Tor exit node" not in flags:
                    flags.append("Tor exit node")
                    reasons.append("ISP/org/AS name contains a Tor marker.")

        for marker in ("vpn", "proxy", "anonymizer"):
            if marker in combined and "Proxy/VPN" not in flags:
                flags.append("Proxy/VPN")
                reasons.append(
                    f"ISP/org name contains '{marker}', suggesting anonymization."
                )

    # 3) Determine level
    if any(f in flags for f in ("Proxy/VPN", "Tor exit node")):
        level, emoji = "High", "🔴"
    elif any(f in flags for f in ("Datacenter/Hosting", "Mobile network")):
        level, emoji = "Medium", "🟡"
    elif flags:
        level, emoji = "Medium", "🟡"
    else:
        level, emoji = "Low", "🟢"
        reasons.append("No anonymization, hosting, or risk flags detected.")

    return {
        "level": level,
        "emoji": emoji,
        "flags": flags,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Domain lookup (composite: DNS + geolocation)
# ---------------------------------------------------------------------------

async def lookup_domain(domain: str) -> dict:
    """Resolve a domain and geolocate its primary IP.

    Returns:
        {"domain": str, "ip": str, "ipv4": [...], "ipv6": [...],
         "reverse": str|None, "geo": dict, "risk": dict}
    """
    resolved = await resolve_domain(domain)
    ip = resolved["ip"]

    # Reverse DNS for the resolved IP
    rdns = await reverse_dns(ip)

    # Geolocate (reuse ip-api)
    try:
        geo_result = await lookup_ip(ip)
    except Exception:
        geo_result = {"status": "fail", "message": "geolocation unavailable"}

    # Risk analysis
    risk = await analyze_ip_risk(ip, geo_result)

    return {
        "domain": domain,
        "ip": ip,
        "ipv4": resolved["ipv4"],
        "ipv6": resolved["ipv6"],
        "reverse": rdns,
        "geo": geo_result,
        "risk": risk,
    }