"""DDEX ERN 4.3 XML generator for DSP delivery."""
from __future__ import annotations
from xml.etree.ElementTree import Element, SubElement, tostring, indent
from datetime import datetime, timezone
from typing import Optional
import structlog

logger = structlog.get_logger()
import uuid


def generate_ddex_ern43(
    release_id: str,
    title: str,
    artist_name: str,
    isrc: str,
    upc: str,
    audio_file_path: str,
    audio_sha256: str,
    duration_seconds: int,
    genre: str,
    release_date: str,
    territory: str = "Worldwide",
    ai_generated: bool = False,
    ai_source: Optional[str] = None,
    explicit: bool = False,
    label_name: str = "ARCOVEL RAIN Distribution",
    ai_involvement: dict[str, bool] | None = None,
) -> str:
    """Generate DDEX ERN 4.3 compliant XML string for DSP delivery."""

    ern = Element("ernm:NewReleaseMessage")
    ern.set("xmlns:ernm", "http://ddex.net/xml/ern/43")
    ern.set("xmlns:avs", "http://ddex.net/xml/avs/avs")
    ern.set("MessageSchemaVersionId", "ern/43")
    ern.set("LanguageAndScriptCode", "en")

    # MessageHeader
    header = SubElement(ern, "MessageHeader")
    SubElement(header, "MessageThreadId").text = str(uuid.uuid4())
    SubElement(header, "MessageId").text = str(uuid.uuid4())
    SubElement(header, "MessageSender").text = "RAIN"
    SubElement(header, "MessageCreatedDateTime").text = datetime.now(timezone.utc).isoformat()

    # ResourceList — SoundRecording
    resources = SubElement(ern, "ResourceList")
    sr = SubElement(resources, "SoundRecording")
    sr_id = SubElement(sr, "SoundRecordingId")
    SubElement(sr_id, "ISRC").text = isrc
    SubElement(sr, "SoundRecordingType").text = "MusicalWorkSoundRecording"

    details = SubElement(sr, "SoundRecordingDetailsByTerritory")
    SubElement(details, "TerritoryCode").text = "Worldwide"
    SubElement(details, "Title").text = title
    SubElement(details, "DisplayArtist").text = artist_name
    SubElement(details, "PLine").text = f"℗ {datetime.now().year} {label_name}"
    SubElement(details, "Genre").text = genre
    SubElement(details, "ParentalWarningType").text = "Explicit" if explicit else "NotExplicit"
    SubElement(details, "Duration").text = f"PT{duration_seconds}S"

    if ai_generated:
        ai_flag = SubElement(details, "AdditionalInformation")
        SubElement(ai_flag, "Type").text = "AIGenerated"
        SubElement(ai_flag, "Value").text = "true"
        if ai_source:
            SubElement(ai_flag, "Source").text = ai_source

    # DDEX ERN 4.3 AI Involvement per September 2025 standard
    # RAIN mastering always constitutes post_production AI involvement
    effective_ai_involvement: dict[str, bool] = {"post_production": True}
    if ai_involvement:
        effective_ai_involvement.update(ai_involvement)

    ai_inv_block = SubElement(details, "AIInvolvementDescription")
    SubElement(ai_inv_block, "AIInvolvementType").text = "PostProduction"
    SubElement(ai_inv_block, "AITool").text = "RAIN v6.0.0 by ARCOVEL Technologies International"
    SubElement(ai_inv_block, "AIInvolvementCategory").text = "Mastering"
    SubElement(ai_inv_block, "AIInvolvementDisclosure").text = "true"
    SubElement(ai_inv_block, "AIInvolvementVocals").text = (
        "true" if effective_ai_involvement.get("vocals") else "false"
    )
    SubElement(ai_inv_block, "AIInvolvementInstrumentation").text = (
        "true" if effective_ai_involvement.get("instrumentation") else "false"
    )
    SubElement(ai_inv_block, "AIInvolvementComposition").text = (
        "true" if effective_ai_involvement.get("composition") else "false"
    )
    SubElement(ai_inv_block, "AIInvolvementLyrics").text = (
        "true" if effective_ai_involvement.get("lyrics") else "false"
    )

    # EU AI Act Article 50 compliance disclosure
    eu_ai_act = SubElement(details, "AdditionalInformation")
    SubElement(eu_ai_act, "Type").text = "EUAIActCompliant"
    SubElement(eu_ai_act, "Value").text = "true"
    SubElement(eu_ai_act, "Description").text = (
        "Article 50 — AI-generated/processed audio disclosure"
    )

    # TechnicalSoundRecordingDetails
    tech_details = SubElement(sr, "TechnicalSoundRecordingDetails")
    SubElement(tech_details, "TechnicalResourceDetailsReference").text = "T1"
    SubElement(tech_details, "AudioCodecType").text = "WAV"
    SubElement(tech_details, "BitDepth").text = "24"
    SubElement(tech_details, "SamplingRate").text = "48000"
    file_ref = SubElement(tech_details, "File")
    SubElement(file_ref, "FileName").text = audio_file_path
    SubElement(file_ref, "HashSum").text = audio_sha256
    SubElement(file_ref, "HashSumAlgorithmType").text = "SHA256"

    # ReleaseList
    releases = SubElement(ern, "ReleaseList")
    release = SubElement(releases, "Release")
    rel_id = SubElement(release, "ReleaseId")
    SubElement(rel_id, "GRid").text = upc
    SubElement(release, "ReleaseType").text = "Single"
    rel_details = SubElement(release, "ReleaseDetailsByTerritory")
    SubElement(rel_details, "TerritoryCode").text = territory
    SubElement(rel_details, "Title").text = title
    SubElement(rel_details, "DisplayArtist").text = artist_name
    SubElement(rel_details, "LabelName").text = label_name
    SubElement(rel_details, "ReleaseDate").text = release_date

    indent(ern, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(ern, encoding="unicode")
