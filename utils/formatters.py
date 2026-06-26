"""Centralized message formatters with professional emoji-section layout."""

from __future__ import annotations


def _safe(v, default="N/A") -> str:
    if v is None:
        return default
    if isinstance(v, str) and not v.strip():
        return default
    return str(v)


def format_ip_result(ip: str, r: dict, risk: dict) -> str:
    """Professional /ip output with Location, Network, ISP, ASN, Coordinates,
    Risk Analysis, Maps and Notes sections."""
    lat = r.get("lat")
    lon = r.get("lon")
    as_str = r.get("as") or "N/A"
    asname = r.get("asname") or ""
    reverse = r.get("reverse") or ""

    lines: list[str] = []
    lines.append("🌍 *IP Intelligence Report*\n")

    lines.append("━━━ 🌍 *Location* ━━━")
    lines.append(f"🏳️ Country: {_safe(r.get('country'))} ({_safe(r.get('countryCode'))})")
    lines.append(f"🗺️ Region: {_safe(r.get('regionName'))}")
    lines.append(f"🏙️ City: {_safe(r.get('city'))}")
    lines.append(f"📮 Postal: {_safe(r.get('zip'))}")
    lines.append(f"🕐 Timezone: {_safe(r.get('timezone'))}")

    lines.append("\n━━━ 🛰️ *Network* ━━━")
    lines.append(f"📡 IP: `{ip}`")
    if reverse:
        lines.append(f"🔁 Reverse DNS: `{reverse}`")
    if r.get("mobile"):
        lines.append("📱 Mobile network: yes")
    if r.get("proxy"):
        lines.append("🛡️ Proxy/VPN: yes")
    if r.get("hosting"):
        lines.append("🖥️ Hosting/Datacenter: yes")

    lines.append("\n━━━ 🏢 *ISP* ━━━")
    lines.append(f"🛰️ ISP: {_safe(r.get('isp'))}")
    lines.append(f"🏢 Org: {_safe(r.get('org'))}")

    lines.append("\n━━━ 📡 *ASN* ━━━")
    lines.append(f"🔢 AS: `{as_str}`")
    if asname:
        lines.append(f"📛 AS name: `{asname}`")

    lines.append("\n━━━ 📍 *Coordinates* ━━━")
    lines.append(f"🌐 Lat: `{_safe(lat)}`")
    lines.append(f"🌐 Lon: `{_safe(lon)}`")

    lines.append("\n━━━ ⚠️ *Risk Analysis* ━━━")
    lines.append(f"{risk['emoji']} Risk Level: *{risk['level']}*")
    if risk.get("flags"):
        lines.append(f"🏷️ Flags: {', '.join(risk['flags'])}")
    for reason in risk.get("reasons", []):
        lines.append(f"  • {reason}")

    # Maps
    if lat is not None and lon is not None:
        lines.append("\n━━━ 🗺️ *Maps* ━━━")
        lines.append(f"📍 Google Maps: https://maps.google.com/?q={lat},{lon}")
        lines.append(f"🗺 OpenStreetMap: https://www.openstreetmap.org/?mlat={lat}&mlon={lon}")

    lines.append("\n━━━ 📝 *Notes* ━━━")
    lines.append(
        "⚠️ _IP geolocation is approximate (city-level) and does not reveal "
        "an exact street address._"
    )
    return "\n".join(lines)


def format_domain_result(d: dict) -> str:
    """Professional /domain output."""
    geo = d.get("geo") or {}
    risk = d.get("risk") or {}
    lines: list[str] = []
    lines.append(f"🌐 *Domain Intelligence Report*\n")
    lines.append("━━━ 🌐 *Domain* ━━━")
    lines.append(f"🔖 Domain: `{d.get('domain', 'N/A')}`")
    lines.append(f"📡 Primary IP: `{_safe(d.get('ip'))}`")

    ipv4 = d.get("ipv4") or []
    ipv6 = d.get("ipv6") or []
    if ipv4:
        lines.append(f"🔢 IPv4: {', '.join(f'`{x}`' for x in ipv4)}")
    if ipv6:
        lines.append(f"🔢 IPv6: {', '.join(f'`{x}`' for x in ipv6)}")

    if d.get("reverse"):
        lines.append(f"🔁 Reverse DNS: `{d['reverse']}`")

    if geo.get("status") == "success":
        lines.append("\n━━━ 🌍 *Location* ━━━")
        lines.append(f"🏳️ Country: {_safe(geo.get('country'))} ({_safe(geo.get('countryCode'))})")
        lines.append(f"🗺️ Region: {_safe(geo.get('regionName'))}")
        lines.append(f"🏙️ City: {_safe(geo.get('city'))}")
        lines.append(f"🕐 Timezone: {_safe(geo.get('timezone'))}")

        lines.append("\n━━━ 🏢 *ISP* ━━━")
        lines.append(f"🛰️ ISP: {_safe(geo.get('isp'))}")
        lines.append(f"🏢 Org: {_safe(geo.get('org'))}")
        lines.append(f"📡 AS: `{_safe(geo.get('as'))}`")

        lat = geo.get("lat")
        lon = geo.get("lon")
        lines.append("\n━━━ 📍 *Coordinates* ━━━")
        lines.append(f"🌐 Lat: `{_safe(lat)}`  Lon: `{_safe(lon)}`")
        if lat is not None and lon is not None:
            lines.append("\n━━━ 🗺️ *Maps* ━━━")
            lines.append(f"📍 Google Maps: https://maps.google.com/?q={lat},{lon}")
            lines.append(f"🗺 OpenStreetMap: https://www.openstreetmap.org/?mlat={lat}&mlon={lon}")
    else:
        lines.append("\n━━━ 🌍 *Location* ━━━")
        lines.append(f"⚠️ Geolocation unavailable: {_safe(geo.get('message'), 'unknown error')}")

    lines.append("\n━━━ ⚠️ *Risk Analysis* ━━━")
    lines.append(f"{risk.get('emoji', '🟢')} Risk Level: *{risk.get('level', 'N/A')}*")
    if risk.get("flags"):
        lines.append(f"🏷️ Flags: {', '.join(risk['flags'])}")
    for reason in risk.get("reasons", []):
        lines.append(f"  • {reason}")
    return "\n".join(lines)


def format_whois_result(query: str, w: dict, is_domain: bool = False) -> str:
    lines: list[str] = []
    title = "Domain" if is_domain else "IP"
    lines.append(f"📇 *WHOIS / RDAP Report ({title})*\n")
    lines.append(f"🔍 Query: `{query}`")
    lines.append("")
    lines.append(f"🏢 Organization: {_safe(w.get('organization'))}")
    lines.append(f"📛 Netname: {_safe(w.get('netname'))}")
    lines.append(f"🔢 ASN: {_safe(w.get('asn'))}")
    lines.append(f"🌐 CIDR: {_safe(w.get('cidr'))}")
    lines.append(f"📧 Abuse Contact: {_safe(w.get('abuse_email'))}")
    lines.append(f"🏳️ Country: {_safe(w.get('country'))}")
    lines.append(f"🗄️ Registry: {_safe(w.get('registry'))}")
    lines.append(f"📅 Creation Date: {_safe(w.get('created'))}")
    lines.append("\n⚠️ _Fields not returned by the registry are marked N/A; data is never fabricated._")
    return "\n".join(lines)


def format_rdns_result(ip: str, hostname: str | None) -> str:
    lines = ["🔁 *Reverse DNS Lookup*\n", f"📡 IP: `{ip}`"]
    if hostname:
        lines.append(f"🏷️ PTR: `{hostname}`")
    else:
        lines.append("🏷️ PTR: _No PTR record found for this IP._")
    return "\n".join(lines)


def format_zip_result(country_code: str, postal_code: str, result: dict) -> str:
    country = result.get("country", "N/A")
    country_abbrev = result.get("country abbreviation", country_code.upper())
    places = result.get("places", [])

    lines = [
        "📮 *Postal Code Lookup Result*",
        f"📮 Code: `{postal_code}`",
        f"🌍 Country: {country} ({country_abbrev})",
    ]

    if len(places) == 1:
        p = places[0]
        lines.append(f"🏙️ City/Place: {p.get('place name', 'N/A')}")
        lines.append(f"🗺️ State: {p.get('state', 'N/A')}")
        lines.append(f"📍 Coordinates: {p.get('latitude', 'N/A')}, {p.get('longitude', 'N/A')}")
    else:
        lines.append("\n*Multiple places found:*")
        for i, p in enumerate(places, 1):
            lines.append(f"\n{i}. {p.get('place name', 'N/A')}")
            lines.append(f"   🗺️ State: {p.get('state', 'N/A')}")
            lines.append(f"   📍 {p.get('latitude', 'N/A')}, {p.get('longitude', 'N/A')}")

    return "\n".join(lines)