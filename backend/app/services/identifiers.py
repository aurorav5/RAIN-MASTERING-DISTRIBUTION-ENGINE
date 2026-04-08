"""ISRC and UPC identifier allocation per ISO 3901 and EAN-13/GS1.

CRITICAL: Random generation is a bug — globally unique identifiers must come from
allocated ranges via atomic sequential counters. Distributors reject collisions and
out-of-range codes. Use the DB-backed counter in `identifier_counters` table.
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = structlog.get_logger()


async def allocate_isrc(db: AsyncSession, country: str = "ZA") -> str:
    """
    Allocate next sequential ISRC per ISO 3901.
    Format: CCXXXYYNNNNN (12 chars, no hyphens).
      CC = country (2 alpha), XXX = registrant (3 alnum),
      YY = 2-digit year, NNNNN = designation (5 digits, sequential per year).
    Raises RuntimeError on counter overflow (>99999 per year — request new registrant range).
    """
    registrant = (settings.ISRC_REGISTRANT_CODE or "ARC")[:3].upper()
    year = datetime.now().year % 100
    scope = f"ISRC:{country}:{registrant}:{year:02d}"

    seq = await _next_counter(db, scope, maximum=99999)
    return f"{country}{registrant}{year:02d}{seq:05d}"


async def allocate_upc(db: AsyncSession) -> str:
    """
    Allocate next sequential UPC (EAN-13) from GS1 prefix.
    Format: PPPPPP-IIIIII-C (12-digit base + EAN-13 check digit).
    Raises RuntimeError on counter overflow (>999999 — request a new GS1 block).
    """
    prefix = (settings.UPC_GS1_PREFIX or "000000")[:6]
    scope = f"UPC:{prefix}"

    seq = await _next_counter(db, scope, maximum=999999)
    base = f"{prefix}{seq:06d}"  # 12 digits
    check = _ean13_check_digit(base)
    return base + str(check)


async def _next_counter(db: AsyncSession, scope: str, maximum: int) -> int:
    """
    Atomically increment the counter for `scope` and return the new value.
    Uses INSERT ... ON CONFLICT DO UPDATE RETURNING for single-roundtrip atomicity.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO identifier_counters (scope, next_value)
            VALUES (:scope, 1)
            ON CONFLICT (scope)
            DO UPDATE SET next_value = identifier_counters.next_value + 1
            RETURNING next_value
            """
        ),
        {"scope": scope},
    )
    row = result.first()
    if row is None:
        raise RuntimeError(f"identifier_counter_allocation_failed scope={scope}")
    seq: int = row[0]
    if seq > maximum:
        logger.error("identifier_range_exhausted", scope=scope, seq=seq, maximum=maximum)
        raise RuntimeError(
            f"RAIN-E710 identifier range exhausted scope={scope} — request new allocation"
        )
    return seq


def _ean13_check_digit(digits: str) -> int:
    """Compute EAN-13 check digit from 12-digit base (GS1 spec)."""
    if len(digits) != 12 or not digits.isdigit():
        raise ValueError(f"EAN-13 base must be 12 digits, got: {digits!r}")
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    return (10 - total % 10) % 10


# ---------------------------------------------------------------------------
# Lightweight in-memory ISRC generator (no DB required)
# Used for prototype / mock flows where the DB counter is unavailable.
# Format: CC-XXX-YY-NNNNN
#   CC    = country code (ZA for South Africa / ARCOVEL)
#   XXX   = registrant code (ARC for ARCOVEL)
#   YY    = 2-digit year
#   NNNNN = 5-digit sequential number
# ---------------------------------------------------------------------------
_isrc_in_memory_counter: int = 0


def generate_isrc(
    country: str = "ZA",
    registrant: str = "ARC",
    year: int | None = None,
) -> str:
    """Generate the next sequential ISRC without a database.

    Returns the ISRC in the canonical 12-character format (no hyphens)
    as required by ISO 3901: CCXXXYYNNNNN.

    Thread-safety note: adequate for single-process prototype use.
    Production should use :func:`allocate_isrc` with the DB counter.
    """
    global _isrc_in_memory_counter
    _isrc_in_memory_counter += 1

    if year is None:
        year = datetime.now().year % 100

    country = country[:2].upper()
    registrant = registrant[:3].upper()

    if _isrc_in_memory_counter > 99999:
        raise RuntimeError(
            "RAIN-E710 in-memory ISRC range exhausted (>99999) — "
            "use DB-backed allocate_isrc for production"
        )

    return f"{country}{registrant}{year:02d}{_isrc_in_memory_counter:05d}"


def format_isrc_display(isrc: str) -> str:
    """Format a 12-character ISRC into the human-readable CC-XXX-YY-NNNNN form."""
    if len(isrc) != 12:
        return isrc
    return f"{isrc[:2]}-{isrc[2:5]}-{isrc[5:7]}-{isrc[7:12]}"


def validate_isrc(isrc: str) -> bool:
    """Validate ISRC format per ISO 3901."""
    if len(isrc) != 12:
        return False
    return isrc[:2].isalpha() and isrc[2:5].isalnum() and isrc[5:].isdigit()


def validate_upc(upc: str) -> bool:
    """Validate UPC/EAN-13 check digit."""
    if len(upc) != 13 or not upc.isdigit():
        return False
    return _ean13_check_digit(upc[:12]) == int(upc[12])
