"""Decide whether a number a guest typed in is safe to dial — locally, free.

No Lookup API call. The real financial risk is a premium-rate or satellite
destination billed at several euro a minute, and that is decided entirely by
the dialling prefix, which we can check ourselves.

What this does not do is detect burner numbers — that needed Lookup. The
access code covers it instead: only people who were sent a code can get here,
and each code allows a fixed number of calls.
"""

import re

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

# Allowlist, longest prefix first so +353 wins over +3.
ALLOWED_PREFIXES: dict[str, str] = {
    "+353": "Ireland", "+44": "UK", "+1": "US/Canada",
    "+33": "France", "+49": "Germany", "+34": "Spain", "+39": "Italy",
    "+31": "Netherlands", "+32": "Belgium", "+351": "Portugal",
    "+48": "Poland", "+46": "Sweden", "+45": "Denmark", "+358": "Finland",
    "+47": "Norway", "+43": "Austria", "+41": "Switzerland",
    "+91": "India", "+61": "Australia", "+64": "New Zealand",
}

# Premium / revenue-share ranges inside otherwise allowed countries. These
# are the ones that actually cost money, so they are refused explicitly.
BLOCKED_PREFIXES: tuple[str, ...] = (
    "+1900", "+1976",                              # US premium
    "+4487", "+4490", "+4491", "+4498", "+4470",   # UK premium & personal numbering
    "+353155", "+353156", "+353157", "+353158",    # Irish premium
    "+3531890",
    "+3399",                                       # FR premium
    "+49900",                                      # DE premium
    "+39899",                                      # IT premium
    "+3519",                                       # PT premium
    "+61190",                                      # AU premium
)


def normalise(raw: str) -> str | None:
    cleaned = re.sub(r"[\s()\-.]", "", (raw or "").strip())
    return cleaned if E164_RE.match(cleaned) else None


def country_for(number: str) -> str | None:
    for prefix in sorted(ALLOWED_PREFIXES, key=len, reverse=True):
        if number.startswith(prefix):
            return ALLOWED_PREFIXES[prefix]
    return None


def check_number(raw: str) -> tuple[str | None, str]:
    """Returns (dialable_number, refusal). Refusal is a sentence to say."""
    number = normalise(raw)
    if not number:
        return None, (
            "That doesn't look like a full international number — include the "
            "country code, like +353 87 123 4567."
        )

    for bad in BLOCKED_PREFIXES:
        if number.startswith(bad):
            return None, "That's a premium-rate number, which I can't dial."

    country = country_for(number)
    if not country:
        return None, (
            "I can only call a short list of countries at the moment, and that "
            "one isn't on it. Happy to email instead."
        )

    return number, ""


def _demo() -> None:
    ok, _ = check_number("+353 87 123 4567")
    assert ok == "+353871234567"
    assert check_number("  +1 (555) 010-1234 ")[0] == "+15550101234"

    # Malformed input is refused.
    for bad in ["", "0871234567", "+0871234567", "+353", "abc", "+12345678901234567"]:
        n, why = check_number(bad)
        assert n is None and why, bad

    # Premium ranges inside allowed countries are refused.
    for premium in ["+19005550123", "+448712345678", "+353155012345", "+3989912345"]:
        n, why = check_number(premium)
        assert n is None and "premium" in why.lower(), premium

    # Satellite and high-risk destinations fall outside the allowlist.
    for foreign in ["+8811234567", "+6781234567", "+2399999999"]:
        n, why = check_number(foreign)
        assert n is None, foreign

    assert country_for("+353871234567") == "Ireland"
    assert country_for("+15550101234") == "US/Canada"
    print("ok")


if __name__ == "__main__":
    _demo()
