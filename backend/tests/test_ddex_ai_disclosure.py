"""Tests for DDEX ERN 4.3 Sept 2025 AI Disclosure emission."""
import os
import xml.etree.ElementTree as ET

# Env setup to match other tests (so importing the service doesn't fail)
os.environ.setdefault("RAIN_ENV", "test")
os.environ.setdefault("RAIN_VERSION", "6.0.0")
os.environ.setdefault("RAIN_LOG_LEVEL", "error")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rain:rain@localhost:5432/rain_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("S3_BUCKET", "rain-test")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")

from app.services.ddex import generate_ddex_ern43, AIDisclosure  # noqa: E402

# ERN 4.3 namespace for XPath
_NS = {"ernm": "http://ddex.net/xml/ern/43"}


def _base_kwargs() -> dict:
    return dict(
        release_id="rel-123",
        title="Test Track",
        artist_name="Test Artist",
        isrc="USRAN2500001",
        upc="000000000001",
        audio_file_path="users/u/s/out.wav",
        audio_sha256="a" * 64,
        duration_seconds=180,
        genre="Electronic",
        release_date="2026-04-05",
    )


def _parse_details(xml_str: str) -> ET.Element:
    """Parse and return the SoundRecordingDetailsByTerritory element."""
    # Strip the XML declaration line so ET can parse
    root = ET.fromstring(xml_str.split("?>\n", 1)[1])
    details = root.find(".//SoundRecordingDetailsByTerritory")
    assert details is not None, "SoundRecordingDetailsByTerritory missing"
    return details


def test_no_disclosure_emits_no_ai_elements():
    xml = generate_ddex_ern43(ai_disclosure=None, **_base_kwargs())
    details = _parse_details(xml)
    assert details.findall("AIContributor") == []
    assert details.find("AIInvolvementSummary") is None


def test_mixing_mastering_only_emits_one_contributor():
    disclosure = AIDisclosure(
        mixing_mastering_ai=True,
        mixing_mastering_tool="RAIN",
        mixing_mastering_model_version="rainnet-v2.1",
        overall_ai_involvement="partial",
    )
    xml = generate_ddex_ern43(ai_disclosure=disclosure, **_base_kwargs())
    details = _parse_details(xml)

    contributors = details.findall("AIContributor")
    assert len(contributors) == 1
    assert contributors[0].find("Area").text == "MixingAndMastering"
    assert contributors[0].find("ToolName").text == "RAIN"
    assert contributors[0].find("ModelVersion").text == "rainnet-v2.1"
    assert contributors[0].find("AIInvolvement").text == "Partial"

    summary = details.find("AIInvolvementSummary")
    assert summary is not None
    assert summary.text == "partial"


def test_all_five_areas_emits_full():
    disclosure = AIDisclosure(
        vocals_ai=True,
        vocals_tool="Suno",
        instrumentation_ai=True,
        instrumentation_tool="Suno",
        composition_ai=True,
        composition_tool="Suno",
        post_production_ai=True,
        post_production_tool="RAIN",
        post_production_model_version="spectralrepair-v1",
        mixing_mastering_ai=True,
        mixing_mastering_tool="RAIN",
        mixing_mastering_model_version="rainnet-v2.1",
        overall_ai_involvement="full",
    )
    xml = generate_ddex_ern43(ai_disclosure=disclosure, **_base_kwargs())
    details = _parse_details(xml)

    contributors = details.findall("AIContributor")
    assert len(contributors) == 5
    areas = sorted(c.find("Area").text for c in contributors)
    assert areas == sorted([
        "Vocals",
        "Instrumentation",
        "Composition",
        "PostProduction",
        "MixingAndMastering",
    ])
    for c in contributors:
        assert c.find("AIInvolvement").text == "Full"

    summary = details.find("AIInvolvementSummary")
    assert summary is not None
    assert summary.text == "full"


def test_from_session_rainnet_sets_mixing_mastering():
    class FakeSession:
        rainnet_model_version = "rainnet-v2.1"
        spectral_repair_applied = False

    disclosure = AIDisclosure.from_session(FakeSession())
    assert disclosure.mixing_mastering_ai is True
    assert disclosure.mixing_mastering_tool == "RAIN"
    assert disclosure.mixing_mastering_model_version == "rainnet-v2.1"
    assert disclosure.overall_ai_involvement == "partial"  # 1 flag set


def test_from_session_none_when_heuristic_fallback():
    class FakeSession:
        rainnet_model_version = None
        spectral_repair_applied = False

    disclosure = AIDisclosure.from_session(FakeSession())
    assert disclosure.mixing_mastering_ai is False
    assert disclosure.overall_ai_involvement == "none"
