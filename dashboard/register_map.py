# register_map.py
# Diagnostic register map for FORT FCN300-3E4Y.
#
# IMPORTANT:
#   - This is NOT the production decoder.
#   - Every entry carries explicit confidence and evidence.
#   - Old production mappings and additive CORRECTIONS in /home/ais/ais-energy
#     are NOT treated as truth here.
#   - All raw values come from a single controlled snapshot taken from the
#     physical meter at the warehouse. No /dev/powermeter polling happens here.

from __future__ import annotations

# ---- Snapshot metadata --------------------------------------------------------

SNAPSHOT = {
    "device": "FORT FCN300-3E4Y",
    "connection": "RS485 / Modbus RTU",
    "slave_id": 1,
    "baud": 9600,
    "serial_port_known": "/dev/powermeter",
    "production_owner_note": (
        "Production poller already owns /dev/powermeter. "
        "This diagnostic app does NOT touch the serial port."
    ),
    "cabling_note": (
        "Cabling currently appears to be UTP rather than STP/SFTP. "
        "This is a hypothesis that MAY affect RS485 robustness; "
        "interference is NOT proven."
    ),
    "snapshot_timestamp": "2026-09-07 (controlled capture, exact time not preserved)",
    "snapshot_source": "controlled raw Modbus scan, manual capture",
    "comm_problem": "UNKNOWN (no live capture here)",
    "decode_problem": (
        "KNOWN: production decoder used wrong register offsets and "
        "applied large additive CORRECTIONS to hide the bad mapping."
    ),
}

# ---- Raw controlled capture (the only ground truth used here) -----------------
#
# Each item: (register_hex_address, raw_unsigned_16bit_low_register)
# The two-register uint32 values were captured as a low word followed by
# the high word. To reconstruct the 32-bit value we OR them together
# in the decoder (big-endian word order, matching Modbus holding register
# convention).
#
# Voltage group (HIGH confidence):
#   0x0042 / 0x0043 -> voltage A   raw 2351668 -> 235.1668 V  panel ~235.5 V
#   0x0044 / 0x0045 -> voltage B   raw 2369622 -> 236.9622 V  panel ~236.3 V
#   0x0046 / 0x0047 -> voltage C   raw 2353836 -> 235.3836 V  panel ~235.7 V
#   0x0048 / 0x0049 -> average V   raw 2358375 -> 235.8375 V  (sanity check)
#
# Line-to-line group (VALIDATED 2026-09-08 live sweep, MEDIUM):
#   0x004C / 0x004D -> ~399.9 V  vs 398.5 V derived from field 230.1 V avg
#   0x004E / 0x004F -> ~399.8 V  (same rule: Modbus-order uint32 /10000)
#   0x0050 / 0x0051 -> ~399.5 V
#   0x0052 / 0x0053 -> ~399.7 V  (note: 0x0053 low-word misread by
#     production as energy_kwh — proven wrong, see evidence)
# AB/BC/CA assignment still unknown; same-instant photo pending.
#
# Current candidates (MEDIUM confidence):
#   0x0070 / 0x0071 signed = -1440  -> -0.1440 A  panel 0.000 A
#   0x0072 / 0x0073 signed = -1440  -> -0.1440 A  panel 0.000 A
#   0x0074 / 0x0075 raw    = 20840  ->  2.0840 A  panel 2.148 A

RAW_SCAN = {
    # voltages (high confidence phase-to-neutral candidates)
    # 0x0042/0x0043 = 2351668 -> hi=0x0023, lo=0xE234
    "0x0042": 0xE234,
    "0x0043": 0x0023,
    # 0x0044/0x0045 = 2369622 -> hi=0x0024, lo=0x2856
    "0x0044": 0x2856,
    "0x0045": 0x0024,
    # 0x0046/0x0047 = 2353836 -> hi=0x0023, lo=0xEAAC
    "0x0046": 0xEAAC,
    "0x0047": 0x0023,
    # 0x0048/0x0049 = 2358375 -> hi=0x0023, lo=0xFC67
    "0x0048": 0xFC67,
    "0x0049": 0x0023,

    # line-to-line candidate group (NOT used for headline values)
    # 0x004C/0x004D = 4088766 -> hi=0x003E, lo=0x63BE
    "0x004C": 0x63BE,
    "0x004D": 0x003E,
    # 0x004E/0x004F = 4090642 -> hi=0x003E, lo=0x6B12
    "0x004E": 0x6B12,
    "0x004F": 0x003E,
    # 0x0050/0x0051 = 4078292 -> hi=0x003E, lo=0x3AD4
    "0x0050": 0x3AD4,
    "0x0051": 0x003E,
    # 0x0052/0x0053 = 4086967 -> hi=0x003E, lo=0x5CB7
    "0x0052": 0x5CB7,
    "0x0053": 0x003E,

    # current candidates
    # 0x0070/0x0071 signed = -1440 -> 0xFFFFFA60
    "0x0070": 0xFA60,
    "0x0071": 0xFFFF,
    # 0x0072/0x0073 signed = -1440 -> 0xFFFFFA60
    "0x0072": 0xFA60,
    "0x0073": 0xFFFF,
    # 0x0074/0x0075 = 20840 -> 0x00005168
    "0x0074": 0x5168,
    "0x0075": 0x0000,
}

# ---- Decode definitions ------------------------------------------------------
#
# Each DECODE entry describes a single physical quantity we want to expose
# on the diagnostic page. The decoder combines the raw scan words according
# to the rules here. Nothing here is allowed to invent register addresses.

from dataclasses import dataclass


@dataclass(frozen=True)
class Decode:
    name: str            # human label
    unit: str            # "V", "A", "kWh", "kvarh"
    addr_lo: str         # low word register (e.g. "0x0042")
    addr_hi: str         # high word register
    signed: bool         # interpret as signed int32 if True
    divide: int          # scale factor (divide raw by this)
    confidence: str      # HIGH / MEDIUM / LOW / INVALID
    evidence: str        # one-line reason for the confidence rating
    panel_ref: str       # text describing panel comparison, "" if unknown


DECODES = [
    # -------- Screen 1: voltage + energy --------------------------------------
    Decode(
        name="Voltage A",
        unit="V",
        addr_lo="0x0042", addr_hi="0x0043",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "uint32 /10000; live 230.74 V vs site-confirmed field photo "
            "image1 230.1 V (+0.28%). Snapshot 235.1668 V was a prior "
            "load point."
        ),
        panel_ref="Field photo image1 (site-confirmed): 230.1 V",
    ),
    Decode(
        name="Voltage B",
        unit="V",
        addr_lo="0x0044", addr_hi="0x0045",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "uint32 /10000; live 231.06 V vs field photo image1 230.3 V "
            "(+0.33%). Snapshot 236.9622 V was a prior load point."
        ),
        panel_ref="Field photo image1 (site-confirmed): 230.3 V",
    ),
    Decode(
        name="Voltage C",
        unit="V",
        addr_lo="0x0046", addr_hi="0x0047",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "uint32 /10000; live 230.57 V vs field photo image1 229.9 V "
            "(+0.29%). Snapshot 235.3836 V was a prior load point."
        ),
        panel_ref="Field photo image1 (site-confirmed): 229.9 V",
    ),
    Decode(
        name="Total kWh",
        unit="kWh",
        addr_lo="", addr_hi="",
        signed=False, divide=1,
        confidence="LOW",
        evidence=(
            "register not identified in 0x00-0x55 sweep. Field image1 "
            "bottom shows 1055.20 kWh; production 0x0053 value proven to "
            "be a line-voltage low-word, not energy."
        ),
        panel_ref="Field photo image1 bottom: 1055.20 kWh",
    ),

    # -------- Screen 2: current + reactive energy -----------------------------
    Decode(
        name="Rejected Current A (0x0070)",
        unit="A",
        addr_lo="0x0070", addr_hi="0x0071",
        signed=True, divide=10000,
        confidence="LOW",
        evidence=(
            "REJECTED as phase-A at this load: live int32 /10000 gives "
            "~14.0 A vs field image2 93.5 A (-85%). No uniform rescale, "
            "swap, or phase permutation fixes all three phases."
        ),
        panel_ref="Field photo image2 (site: ours wrong): 93.5 A",
    ),
    Decode(
        name="Rejected Current B (0x0072)",
        unit="A",
        addr_lo="0x0072", addr_hi="0x0073",
        signed=True, divide=10000,
        confidence="LOW",
        evidence=(
            "REJECTED as phase-B at this load: live int32 /10000 gives "
            "~43.4 A vs field image2 104.0 A (-58%). Register block wrong."
        ),
        panel_ref="Field photo image2 (site: ours wrong): 104.0 A",
    ),
    Decode(
        name="Rejected Current C (0x0074)",
        unit="A",
        addr_lo="0x0074", addr_hi="0x0075",
        signed=False, divide=10000,
        confidence="LOW",
        evidence=(
            "REJECTED as phase-C at this load: live uint32 /10000 gives "
            "~21.7 A vs field image2 93.1 A (-77%). Register block wrong."
        ),
        panel_ref="Field photo image2 (site: ours wrong): 93.1 A",
    ),
    Decode(
        name="Total kvarh",
        unit="kvarh",
        addr_lo="", addr_hi="",
        signed=False, divide=1,
        confidence="LOW",
        evidence=(
            "register not identified in 0x00-0x55 sweep. Field image2 "
            "bottom shows 000726.52 Kvarh (reactive energy, NOT kWh)."
        ),
        panel_ref="Field photo image2 bottom: 000726.52 Kvarh",
    ),
    Decode(
        name="Line-to-line 1",
        unit="V",
        addr_lo="0x004C", addr_hi="0x004D",
        signed=False, divide=10000,
        confidence="MEDIUM",
        evidence=(
            "uint32 /10000 gives ~399.9 V vs 398.5 V derived from field "
            "phase avg 230.1 V (+0.3%). AB/BC/CA assignment unknown; "
            "same-instant confirmation pending. Pair reads are non-atomic: "
            "torn reads spike +-2% (406.2 V seen once), L-L band 393-406 V."
        ),
        panel_ref="Derived from field image1 phases (230.1 V avg x sqrt(3))",
    ),
    Decode(
        name="Line-to-line 2",
        unit="V",
        addr_lo="0x004E", addr_hi="0x004F",
        signed=False, divide=10000,
        confidence="MEDIUM",
        evidence=(
            "uint32 /10000 gives ~399.8 V vs 398.5 V derived (+0.3%). "
            "Assignment unknown; same-instant confirmation pending. "
            "Non-atomic pair reads: torn-read spikes +-2% possible."
        ),
        panel_ref="Derived from field image1 phases (230.1 V avg x sqrt(3))",
    ),
    Decode(
        name="Line-to-line 3",
        unit="V",
        addr_lo="0x0050", addr_hi="0x0051",
        signed=False, divide=10000,
        confidence="MEDIUM",
        evidence=(
            "uint32 /10000 gives ~399.5 V vs 398.5 V derived (+0.2%). "
            "Assignment unknown; same-instant confirmation pending. "
            "Non-atomic pair reads: torn-read spikes +-2% possible."
        ),
        panel_ref="Derived from field image1 phases (230.1 V avg x sqrt(3))",
    ),
    Decode(
        name="Line-to-line 4",
        unit="V",
        addr_lo="0x0052", addr_hi="0x0053",
        signed=False, divide=10000,
        confidence="MEDIUM",
        evidence=(
            "uint32 /10000 gives ~399.7 V vs 398.5 V derived (+0.3%). "
            "Note: production reads 0x0053 alone as energy_kwh — that "
            "mapping is proven wrong (this pair is line voltage). "
            "Non-atomic pair reads: torn-read spikes +-2% possible."
        ),
        panel_ref="Derived from field image1 phases (230.1 V avg x sqrt(3))",
    ),
    # -------- Current candidates round 2 (2026-09-08 hunt) ----------------------
    # Quad 0x58-5F: BE-uint32 /10000, same convention as validated voltages.
    # H2 0x64-69: BE-uint32 with FITTED divisor 1790 (two live samples <1%,
    # common scale, B-highest, A~=C). Divisor unattested — needs manual or
    # same-instant photo before any promotion. Neither touches production.
    Decode(
        name="Current A",
        unit="A",
        addr_lo="0x0058", addr_hi="0x0059",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "Production-validated BE-uint32 /10000; 14 live samples over "
            "15 min: A~=C in all, co-moves +-15 A with load; ramp sample "
            "93.74 A vs field 93.5 A (+0.3%)."
        ),
        panel_ref="Field photo image2: 93.5 A",
    ),
    Decode(
        name="Current B",
        unit="A",
        addr_lo="0x005A", addr_hi="0x005B",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "Production-validated BE-uint32 /10000; highest phase in all "
            "14 samples, matching "
            "field B-highest; ramp sample 104.95 A vs field 104.0 A "
            "(+0.9%)."
        ),
        panel_ref="Field photo image2: 104.0 A",
    ),
    Decode(
        name="Current C",
        unit="A",
        addr_lo="0x005C", addr_hi="0x005D",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "Production-validated BE-uint32 /10000; 14 live samples track "
            "field 93.1 A; ramp sample 93.04 A (-0.1%)."
        ),
        panel_ref="Field photo image2: 93.1 A",
    ),
    Decode(
        name="Current avg (quad)",
        unit="A",
        addr_lo="0x005E", addr_hi="0x005F",
        signed=False, divide=10000,
        confidence="HIGH",
        evidence=(
            "Equals mean(A2,B2,C2): 14 samples, min 0.000% / mean 0.06% "
            "/ max 0.54% error (13/14 under 0.09%; max = meter-side avg "
            "lag during a fast B excursion, avg caught up next sample)."
        ),
        panel_ref="Mean of quad channels (no direct panel equivalent)",
    ),
    Decode(
        name="Current A3 (H2)",
        unit="A",
        addr_lo="0x0064", addr_hi="0x0065",
        signed=False, divide=1790,
        confidence="LOW",
        evidence=(
            "BE-uint32 with FITTED divisor 1790: two samples 93.6/94.4 A "
            "vs field 93.5 A (+0.1%/+1.0%). Divisor unattested; do NOT "
            "promote without manual or same-instant confirmation."
        ),
        panel_ref="Field photo image2: 93.5 A (divisor fitted, unvalidated)",
    ),
    Decode(
        name="Current B3 (H2)",
        unit="A",
        addr_lo="0x0066", addr_hi="0x0067",
        signed=False, divide=1790,
        confidence="LOW",
        evidence=(
            "Fitted divisor 1790: two samples 104.4/104.3 A vs field "
            "104.0 A (+0.4%/+0.3%), highest phase both times. "
            "Divisor unattested."
        ),
        panel_ref="Field photo image2: 104.0 A (divisor fitted, unvalidated)",
    ),
    Decode(
        name="Current C3 (H2)",
        unit="A",
        addr_lo="0x0068", addr_hi="0x0069",
        signed=False, divide=1790,
        confidence="LOW",
        evidence=(
            "Fitted divisor 1790: two samples 92.2/93.0 A vs field 93.1 A "
            "(-1.0%/-0.1%). Divisor unattested."
        ),
        panel_ref="Field photo image2: 93.1 A (divisor fitted, unvalidated)",
    ),
]


# ---- Sanity helpers -----------------------------------------------------------


def to_signed32(u: int) -> int:
    """Convert unsigned 32-bit to signed 32-bit (two's complement)."""
    if u >= 0x80000000:
        return u - 0x100000000
    return u
