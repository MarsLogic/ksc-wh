# decoder.py
# Diagnostic decoder for FORT FCN300-3E4Y.
#
# Pure function: takes a raw scan dict + decode table -> list of results.
# No side effects, no serial port access, no production file writes.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from register_map import DECODES, RAW_SCAN, to_signed32


@dataclass
class DecodeResult:
    name: str
    unit: str
    addr_lo: str          # e.g. "0x0042"  or "" if unknown
    addr_hi: str
    width: int            # 2 for 32-bit, 0 for unknown
    signed: bool
    divide: int
    raw_hex: str          # 8-hex-char 32-bit big-endian, or "" if unknown
    raw_dec: str          # decimal string of the 32-bit value, or "" if unknown
    signed_dec: str       # signed interpretation if signed, else ""
    calc: str             # human-readable formula, e.g. "2351668 / 10000"
    decoded: str          # final number with unit, e.g. "235.1668 V"
    decoded_value: Optional[float]  # numeric value, None if unknown
    confidence: str       # HIGH / MEDIUM / LOW / INVALID
    confidence_text: str  # plain-language explanation
    evidence: str
    panel_ref: str
    status: str           # "decoded" or "unknown"


def _hex32_be(u: int) -> str:
    """Format unsigned 32-bit as 8 uppercase hex chars, big-endian."""
    return f"{(u & 0xFFFFFFFF):08X}"


def decode_one(d, raw):
    """Decode a single Decode definition against the raw scan dict."""
    if not d.addr_lo or not d.addr_hi:
        return DecodeResult(
            name=d.name,
            unit=d.unit,
            addr_lo="",
            addr_hi="",
            width=0,
            signed=d.signed,
            divide=d.divide,
            raw_hex="",
            raw_dec="",
            signed_dec="",
            calc="register not identified",
            decoded="UNKNOWN",
            decoded_value=None,
            confidence=d.confidence,
            confidence_text=(
                "Not identified in this snapshot. We are NOT inventing a "
                "register or factor."
            ),
            evidence=d.evidence,
            panel_ref=d.panel_ref,
            status="unknown",
        )

    lo = raw.get(d.addr_lo)
    hi = raw.get(d.addr_hi)
    if lo is None or hi is None:
        return DecodeResult(
            name=d.name,
            unit=d.unit,
            addr_lo=d.addr_lo,
            addr_hi=d.addr_hi,
            width=2,
            signed=d.signed,
            divide=d.divide,
            raw_hex="",
            raw_dec="",
            signed_dec="",
            calc="missing raw word",
            decoded="UNKNOWN",
            decoded_value=None,
            confidence="LOW",
            confidence_text="Raw word missing from snapshot.",
            evidence=d.evidence,
            panel_ref=d.panel_ref,
            status="unknown",
        )

    raw32 = (hi << 16) | lo
    signed32 = to_signed32(raw32) if d.signed else raw32
    if d.signed:
        # signed representation shown for the user
        if d.divide and d.divide != 1:
            numeric = signed32 / d.divide
        else:
            numeric = float(signed32)
        # raw_dec shows the unsigned raw as well, since that is what
        # the bus actually carries
        raw_dec_str = str(raw32)
        signed_dec_str = str(signed32)
        calc = f"{signed32} / {d.divide}"
        if numeric == int(numeric):
            decoded_str = f"{numeric:.4f} {d.unit}".rstrip("0").rstrip(".")
        else:
            decoded_str = f"{numeric:.4f} {d.unit}"
    else:
        if d.divide and d.divide != 1:
            numeric = raw32 / d.divide
        else:
            numeric = float(raw32)
        raw_dec_str = str(raw32)
        signed_dec_str = ""
        calc = f"{raw32} / {d.divide}"
        decoded_str = (
            f"{numeric:.4f} {d.unit}".rstrip("0").rstrip(".")
            if numeric == int(numeric)
            else f"{numeric:.4f} {d.unit}"
        )

    return DecodeResult(
        name=d.name,
        unit=d.unit,
        addr_lo=d.addr_lo,
        addr_hi=d.addr_hi,
        width=2,
        signed=d.signed,
        divide=d.divide,
        raw_hex=_hex32_be(raw32),
        raw_dec=raw_dec_str,
        signed_dec=signed_dec_str,
        calc=calc,
        # Re-build with explicit 4-decimal then trim to match snapshot
        decoded=f"{numeric:.4f} {d.unit}",
        decoded_value=numeric,
        confidence=d.confidence,
        confidence_text=_confidence_blurb(d.confidence, d.evidence),
        evidence=d.evidence,
        panel_ref=d.panel_ref,
        status="decoded",
    )


def _confidence_blurb(level: str, evidence: str) -> str:
    if level == "HIGH":
        return (
            "Strong support: register, data type and divide factor reproduce "
            "realistic 3-phase voltage that closely matches the physical panel."
        )
    if level == "MEDIUM":
        return (
            "Strong candidate: register and factor reproduce a plausible value, "
            "but same-instant panel confirmation is still missing."
        )
    if level == "LOW":
        return (
            "Weak / unknown: no register has been mapped to this quantity in "
            "this snapshot. We are NOT guessing an address or factor."
        )
    return "Invalid: decoded value is physically impossible."


def decode_all():
    """Decode every entry. Returns list[dict] ready for template / JSON."""
    results = [decode_one(d, RAW_SCAN) for d in DECODES]
    out = []
    for r in results:
        d = asdict(r)
        out.append(d)
    return out


def decode_all_from_raw(raw: dict) -> list[dict]:
    """Same as decode_all() but consumes an arbitrary raw-scan dict.

    Used by the live /api/live endpoint to merge freshly observed raw 16-bit
    words from the production side-channel with the same DECODES table that
    the controlled snapshot uses. Pure function — no serial access, no I/O.
    """
    results = [decode_one(d, raw) for d in DECODES]
    return [asdict(r) for r in results]


def raw_evidence_summary():
    """Compact listing of every raw word used, for the page footer."""
    items = []
    for key, val in sorted(RAW_SCAN.items()):
        items.append({"register": key, "hex": f"{val:04X}", "dec": str(val)})
    return items
