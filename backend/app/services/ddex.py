"""DDEX ERN 4.3 XML generator for DSP delivery.

Implements the September 2025 DDEX AI Disclosure standard (coordinated with
Spotify, adopted by 15+ distributors). Granular per-area AI disclosure is
emitted as <AIContributor> elements inside SoundRecordingDetailsByTerritory,
with an <AIInvolvementSummary> sibling element.
"""
from __future__ import annotations
from xml.etree.ElementTree import Element, SubElement, tostring, indent
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Tuple
import structlog

logger = structlog.get_logger()
import uuid


# Canonical DDEX Area names (Sept 2025 AI Disclosure standard)
_AREA_VOCALS = "Vocals"
_AREA_INSTRUMENTATION = "Instrumentation"
_AREA_COMPOSITION = "Composition"
_AREA_POST_PRODUCTION = "PostProduction"
_AREA_MIXING_MASTERING = "MixingAndMastering"

# Canonical involvement levels
_VALID_INVOLVEMENT = ("none", "partial", "substantial", "full")


@dataclass
class AIDisclosure:
    """Sept 2025 DDEX AI Disclosure — granular per-area AI usage declaration."""

    vocals_ai: bool = False
    vocals_tool: Optional[str] = None
    instrumentation_ai: bool = False
    instrumentation_tool: Optional[str] = None
    composition_ai: bool = False
    composition_tool: Optional[str] = None
    post_production_ai: bool = False
    post_production_tool: Optional[str] = None
    mixing_mastering_ai: bool = False
    mixing_mastering_tool: Optional[str] = None
    overall_ai_involvement: str = "none"
    # Per-area model versions (optional, keyed to tool_name)
    vocals_model_version: Optional[str] = None
    instrumentation_model_version: Optional[str] = None
    composition_model_version: Optional[str] = None
    post_production_model_version: Optional[str] = None
    mixing_mastering_model_version: Optional[str] = None

    def _enabled_areas(self) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """Return list of (area_name, tool_name, model_version) for areas with AI=True."""
        areas: List[Tuple[str, Optional[str], Optional[str]]] = []
        if self.vocals_ai:
            areas.append((_AREA_VOCALS, self.vocals_tool, self.vocals_model_version))
        if self.instrumentation_ai:
            areas.append((_AREA_INSTRUMENTATION, self.instrumentation_tool, self.instrumentation_model_version))
        if self.composition_ai:
            areas.append((_AREA_COMPOSITION, self.composition_tool, self.composition_model_version))
        if self.post_production_ai:
            areas.append((_AREA_POST_PRODUCTION, self.post_production_tool, self.post_production_model_version))
        if self.mixing_mastering_ai:
            areas.append((_AREA_MIXING_MASTERING, self.mixing_mastering_tool, self.mixing_mastering_model_version))
        return areas

    @staticmethod
    def from_session(session) -> "AIDisclosure":
        """Build an AIDisclosure by inspecting a mastering Session.

        - mixing_mastering_ai=True if session.rainnet_model_version is set
          (i.e. RainNet actually ran, not the heuristic fallback)
        - post_production_ai=True if SpectralRepairNet or any neural restoration
          was used (TODO: wire to session fields once restoration flags exist)
        - vocals/instrumentation/composition default False (RAIN does not
          generate these)
        - overall_ai_involvement computed from True-flag count:
            0 -> "none", 1-2 -> "partial", 3 -> "substantial", 4-5 -> "full"
        """
        disclosure = AIDisclosure()

        rainnet_version = getattr(session, "rainnet_model_version", None)
        if rainnet_version:
            disclosure.mixing_mastering_ai = True
            disclosure.mixing_mastering_tool = "RAIN"
            disclosure.mixing_mastering_model_version = rainnet_version

        # TODO: populate post_production_ai when SpectralRepairNet /
        # neural restoration session flags are added to the Session model.
        spectral_repair_used = getattr(session, "spectral_repair_applied", False)
        if spectral_repair_used:
            disclosure.post_production_ai = True
            disclosure.post_production_tool = "RAIN"
            disclosure.post_production_model_version = getattr(
                session, "spectral_repair_model_version", None
            )

        # Compute overall involvement from true-flag count
        flags = [
            disclosure.vocals_ai,
            disclosure.instrumentation_ai,
            disclosure.composition_ai,
            disclosure.post_production_ai,
            disclosure.mixing_mastering_ai,
        ]
        count = sum(1 for f in flags if f)
        if count == 0:
            disclosure.overall_ai_involvement = "none"
        elif count <= 2:
            disclosure.overall_ai_involvement = "partial"
        elif count == 3:
            disclosure.overall_ai_involvement = "substantial"
        else:
            disclosure.overall_ai_involvement = "full"

        return disclosure


def _emit_ai_disclosure(details: Element, ai_disclosure: AIDisclosure) -> None:
    """Emit DDEX Sept 2025 AI disclosure elements into SoundRecordingDetailsByTerritory."""
    for area_name, tool_name, model_version in ai_disclosure._enabled_areas():
        contributor = SubElement(details, "AIContributor")
        SubElement(contributor, "Area").text = area_name
        # Per-area AIInvolvement defaults to the overall level, capitalized
        SubElement(contributor, "AIInvolvement").text = (
            ai_disclosure.overall_ai_involvement.capitalize()
        )
        if tool_name:
            SubElement(contributor, "ToolName").text = tool_name
        if model_version:
            SubElement(contributor, "ModelVersion").text = model_version

    summary = SubElement(details, "AIInvolvementSummary")
    summary.text = ai_disclosure.overall_ai_involvement


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
    ai_disclosure: Optional[AIDisclosure] = None,
    explicit: bool = False,
    label_name: str = "ARCOVEL RAIN Distribution",
    ai_involvement: dict[str, bool] | None = None,
) -> str:
    """Generate DDEX ERN 4.3 compliant XML string for DSP delivery.

    ai_disclosure: Sept 2025 DDEX AI disclosure (granular per-area fields).
        If None, no AI elements are emitted (fully human release).
    """

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
    SubElement(details, "PLine").text = f"\u2117 {datetime.now().year} {label_name}"
    SubElement(details, "Genre").text = genre
    SubElement(details, "ParentalWarningType").text = "Explicit" if explicit else "NotExplicit"
    SubElement(details, "Duration").text = f"PT{duration_seconds}S"

    # Sept 2025 DDEX AI Disclosure — emit only if provided
    if ai_disclosure is not None:
        _emit_ai_disclosure(details, ai_disclosure)

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
