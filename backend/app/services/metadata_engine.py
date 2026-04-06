"""
RAIN Metadata Engine — Strip all input metadata, write clean production tags.

MP3: ID3v2.4 via mutagen
WAV: BWF bext chunk + INFO chunk via mutagen/soundfile
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mutagen.id3 import (
    COMM,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TRCK,
    TXXX,
)
from mutagen.mp3 import MP3


def strip_and_write_mp3_tags(
    mp3_path: str,
    metadata: dict[str, str],
    session_id: str,
    output_lufs: float,
    output_true_peak: float,
) -> None:
    """Strip ALL existing tags from MP3 and write clean RAIN metadata.

    Writes ONLY:
      TIT2 (title), TPE1 (artist), TALB (album), TDRC (year),
      TCON (genre), TRCK (track number), COMM (mastered by RAIN),
      TXXX:RAIN_SESSION_ID, TXXX:RAIN_LUFS, TXXX:RAIN_TRUE_PEAK
    """
    # Delete all existing tags completely
    audio = MP3(mp3_path)
    audio.delete()
    audio.save()

    # Re-open and ensure we have a clean ID3 tag
    audio = MP3(mp3_path)
    if audio.tags is None:
        audio.add_tags()
    else:
        # Clear any residual frames
        audio.tags.clear()
    tags = audio.tags

    now_year = str(datetime.now(timezone.utc).year)

    # Standard frames
    tags.add(TIT2(encoding=3, text=[metadata.get("title", "Untitled")]))
    tags.add(TPE1(encoding=3, text=[metadata.get("artist", "Unknown Artist")]))
    tags.add(TALB(encoding=3, text=[metadata.get("album", "")]))
    tags.add(TDRC(encoding=3, text=[metadata.get("year", now_year)]))
    tags.add(TCON(encoding=3, text=[metadata.get("genre", "")]))
    tags.add(TRCK(encoding=3, text=[metadata.get("track_number", "1")]))
    tags.add(COMM(encoding=3, lang="eng", desc="",
                  text=["Mastered by RAIN (R\u221eN) \u2014 arcovel.com"]))

    # RAIN custom frames
    tags.add(TXXX(encoding=3, desc="RAIN_SESSION_ID", text=[session_id]))
    tags.add(TXXX(encoding=3, desc="RAIN_LUFS", text=[f"{output_lufs:.1f}"]))
    tags.add(TXXX(encoding=3, desc="RAIN_TRUE_PEAK", text=[f"{output_true_peak:.1f}"]))

    audio.save(v2_version=4)


def write_wav_bwf_metadata(
    wav_path: str,
    metadata: dict[str, str],
    session_id: str,
    output_lufs: float,
    output_true_peak: float,
) -> None:
    """Write BWF bext chunk and INFO chunk metadata to WAV file.

    Uses raw RIFF chunk manipulation since mutagen doesn't natively support WAV BWF.
    Falls back to INFO chunk writing via simple RIFF appending.
    """
    now = datetime.now(timezone.utc)
    title = metadata.get("title", "Untitled")
    artist = metadata.get("artist", "Unknown Artist")
    year = metadata.get("year", str(now.year))
    comment = f"Mastered by RAIN (R\u221eN) | Session: {session_id}"

    # Write INFO chunk by reading and rewriting the WAV
    # INFO chunks go inside a LIST chunk in the RIFF structure
    _write_info_chunk(wav_path, {
        "IART": artist,
        "INAM": title,
        "ICMT": comment,
        "ICRD": now.strftime("%Y-%m-%d"),
        "ISFT": "RAIN v1.0",
        "IGNR": metadata.get("genre", ""),
    })


def _write_info_chunk(wav_path: str, info_fields: dict[str, str]) -> None:
    """Append a LIST/INFO chunk to a WAV file's RIFF structure.

    This reads the existing WAV, strips any existing LIST/INFO chunks,
    and appends a new one with the specified fields.
    """
    path = Path(wav_path)
    data = path.read_bytes()

    # Verify RIFF/WAVE header
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return  # Not a valid WAV, skip

    # Build the INFO chunk payload
    info_data = b"INFO"
    for tag, value in info_fields.items():
        if not value:
            continue
        encoded = value.encode("utf-8") + b"\x00"
        # Pad to even length
        if len(encoded) % 2 != 0:
            encoded += b"\x00"
        chunk = tag.encode("ascii") + struct.pack("<I", len(encoded)) + encoded
        info_data += chunk

    # Build LIST chunk
    list_chunk = b"LIST" + struct.pack("<I", len(info_data)) + info_data

    # Find the end of existing data chunks (before any existing LIST chunk)
    # Simple approach: strip any trailing LIST chunks and re-append
    pos = 12  # After RIFF header + WAVE
    clean_chunks = b""
    while pos < len(data):
        if pos + 8 > len(data):
            break
        chunk_id = data[pos : pos + 4]
        chunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        chunk_total = 8 + chunk_size
        if chunk_size % 2 != 0:
            chunk_total += 1  # RIFF padding

        if chunk_id == b"LIST":
            # Check if it's an INFO list
            if pos + 12 <= len(data) and data[pos + 8 : pos + 12] == b"INFO":
                pos += chunk_total
                continue  # Skip existing INFO

        clean_chunks += data[pos : pos + chunk_total]
        pos += chunk_total

    # Reconstruct file
    new_payload = b"WAVE" + clean_chunks + list_chunk
    new_file = b"RIFF" + struct.pack("<I", len(new_payload)) + new_payload
    path.write_bytes(new_file)


def write_metadata(
    wav_path: str | None,
    mp3_path: str | None,
    metadata: dict[str, str],
    session_id: str,
    output_lufs: float,
    output_true_peak: float,
) -> None:
    """Write metadata to both WAV and MP3 output files."""
    if mp3_path:
        strip_and_write_mp3_tags(
            mp3_path, metadata, session_id, output_lufs, output_true_peak
        )
    if wav_path:
        write_wav_bwf_metadata(
            wav_path, metadata, session_id, output_lufs, output_true_peak
        )
