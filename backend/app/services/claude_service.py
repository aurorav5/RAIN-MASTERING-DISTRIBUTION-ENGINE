"""
RAIN Claude AI Co-Master Engineer Service

Provides AI-powered mastering suggestions via Anthropic's Claude API.
Tier gating: Creator tier and above (10/mo for Creator, unlimited for Studio Pro+).

Error codes:
  RAIN-E900: Claude API authentication failure
  RAIN-E901: Claude API timeout or network error
  RAIN-E902: Claude response parsing failure (invalid JSON)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

import anthropic
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# The 7 macro controls and their DSP mapping
MACRO_SYSTEM_PROMPT = """\
You are RAIN's AI Co-Master Engineer — an expert audio mastering assistant built into \
the RAIN mastering platform by ARCOVEL Technologies International.

You help users refine their masters by suggesting adjustments to 7 macro controls. \
Each macro maps to underlying DSP parameters in the RainDSP engine.

## The 7 Macro Controls

1. **BRIGHTEN** (0–10): Controls high-frequency shelf EQ and air band presence.
   - 0 = no HF boost, 10 = +4 dB shelf at 8 kHz + 3 dB peak at 16 kHz.
   - Use for adding clarity, presence, and air. Be cautious with already-bright mixes.

2. **GLUE** (0–10): Controls multiband compression ratios and thresholds across all bands.
   - 0 = no compression, 10 = aggressive bus-style glue (ratios up to 4:1).
   - Higher values reduce dynamic range and create cohesion. Too much kills transients.

3. **WIDTH** (0–10): Controls stereo width via M/S processing and side-channel gain.
   - 0 = narrowed stereo (mono-ish), 5 = unchanged, 10 = maximum stereo enhancement.
   - Bass remains mono below 200 Hz regardless of setting. Excessive width hurts mono compat.

4. **PUNCH** (0–10): Controls mid-band transient shaping via attack/release times.
   - 0 = soft attack (transparent), 10 = fast attack with aggressive transient emphasis.
   - Affects snare, kick, and vocal presence. Genre-dependent — rock/hip-hop want more.

5. **WARMTH** (0–10): Controls low-shelf EQ at 200 Hz and analog saturation drive.
   - 0 = clean/neutral, 10 = +3 dB low shelf + tube saturation at 30% drive.
   - Adds body and harmonic richness. Too much muddies the low-mids.

6. **SPACE** (0–10): Controls stereo decorrelation and mid/side balance for depth.
   - 0 = dry/forward, 10 = spacious with enhanced side content and depth cues.
   - Interacts with WIDTH. High SPACE + high WIDTH can cause phase issues.

7. **REPAIR** (0–10): Controls spectral repair intensity and noise floor management.
   - 0 = no repair, 10 = aggressive spectral repair, de-essing, and rumble removal.
   - Higher values apply stronger HPF, sibilance reduction, and spectral smoothing.

## Response Format

Always respond with valid JSON in this exact structure:
```json
{
  "macros": {
    "BRIGHTEN": <float 0-10>,
    "GLUE": <float 0-10>,
    "WIDTH": <float 0-10>,
    "PUNCH": <float 0-10>,
    "WARMTH": <float 0-10>,
    "SPACE": <float 0-10>,
    "REPAIR": <float 0-10>
  },
  "explanation": "<2-4 sentences explaining the reasoning behind the suggested settings>",
  "confidence": <float 0.0-1.0>
}
```

## Decision Guidelines

- Base suggestions on the audio features provided (LUFS, spectral balance, dynamics, stereo width).
- Consider the detected genre — each genre has established mastering conventions.
- Consider the target platform(s) — Spotify normalizes to -14 LUFS, Apple Music to -16, etc.
- Factor in the user's intent as expressed in their query.
- Only suggest changes that address actual issues in the analysis data.
- If the mix is already well-balanced for the target, suggest minimal changes with high confidence.
- Prefer subtle adjustments (changes of 1-3) over dramatic ones unless the user requests otherwise.
- Never suggest REPAIR > 5 unless the analysis shows clear issues (rumble, sibilance, clipping).
- confidence should reflect how certain you are: >0.8 for clear cases, 0.5-0.8 for subjective \
choices, <0.5 when the request is ambiguous or contradictory.

Respond ONLY with the JSON object. No markdown fences, no preamble, no trailing text.\
"""

REPORT_SYSTEM_PROMPT = """\
You are RAIN's AI Co-Master Engineer. Generate a concise, professional before/after \
mastering report for the user. Write in plain language that both audio professionals and \
informed amateurs can understand.

Structure:
1. **Summary** — One sentence describing what was done.
2. **Before** — Key characteristics of the input audio (loudness, dynamics, spectral balance, \
stereo image) using the provided measurements.
3. **After** — How the mastered output differs, citing specific improvements and the macro \
settings that achieved them.
4. **QC Results** — Summarize any quality check findings. Highlight critical issues that were \
auto-remediated and any advisory warnings.
5. **Recommendation** — One sentence of actionable advice for the next mix or revision.

Keep the report under 300 words. Use dB, LUFS, and Hz values where relevant. \
Do not invent measurements — use only the data provided. Do not use markdown headers — \
use the bold labels shown above.\
"""

VALID_MACROS = frozenset({"BRIGHTEN", "GLUE", "WIDTH", "PUNCH", "WARMTH", "SPACE", "REPAIR"})

# Retry configuration per CLAUDE.md execution discipline
_MAX_RETRIES = 3
_BASE_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_TIMEOUT_S = 30.0


class ClaudeService:
    """Claude AI Co-Master Engineer — macro suggestion and reporting service."""

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=_TIMEOUT_S,
        )
        self.model = "claude-sonnet-4-6"

    async def _call_with_retry(
        self,
        *,
        system: str,
        user_message: str,
        max_tokens: int = 1024,
        session_id: str | None = None,
        user_id: str | None = None,
        stage: str = "claude_inference",
    ) -> str:
        """Call the Anthropic API with exponential backoff retry.

        Returns the text content of the response.
        Raises on exhausted retries or authentication errors (no retry).
        """
        last_exception: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            start_ms = time.monotonic()
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user_message}],
                )
                duration_ms = int((time.monotonic() - start_ms) * 1000)
                logger.info(
                    "claude_api_success",
                    session_id=session_id,
                    user_id=user_id,
                    stage=stage,
                    attempt=attempt,
                    duration_ms=duration_ms,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
                # Extract text from content blocks
                text_parts = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
                return "".join(text_parts)

            except anthropic.AuthenticationError as exc:
                # Auth errors are not retryable
                duration_ms = int((time.monotonic() - start_ms) * 1000)
                logger.error(
                    "claude_api_auth_failure",
                    error_code="RAIN-E900",
                    session_id=session_id,
                    user_id=user_id,
                    stage=stage,
                    duration_ms=duration_ms,
                    detail=str(exc),
                )
                raise

            except (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
                anthropic.InternalServerError,
            ) as exc:
                duration_ms = int((time.monotonic() - start_ms) * 1000)
                last_exception = exc
                backoff = min(_BASE_BACKOFF_S * (2 ** (attempt - 1)), _MAX_BACKOFF_S)
                logger.warning(
                    "claude_api_retry",
                    error_code="RAIN-E901",
                    session_id=session_id,
                    user_id=user_id,
                    stage=stage,
                    attempt=attempt,
                    max_retries=_MAX_RETRIES,
                    duration_ms=duration_ms,
                    backoff_s=backoff,
                    error_type=type(exc).__name__,
                    detail=str(exc),
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)

        # All retries exhausted
        logger.error(
            "claude_api_exhausted",
            error_code="RAIN-E901",
            session_id=session_id,
            user_id=user_id,
            stage=stage,
            max_retries=_MAX_RETRIES,
            detail=str(last_exception),
        )
        raise last_exception  # type: ignore[misc]

    def _parse_macro_response(
        self,
        raw: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> Dict[str, Any]:
        """Parse and validate Claude's JSON macro response.

        Returns a validated dict with macros, explanation, and confidence.
        Raises ValueError with RAIN-E902 on parse or validation failure.
        """
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language tag)
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].rstrip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error(
                "claude_response_parse_failure",
                error_code="RAIN-E902",
                session_id=session_id,
                user_id=user_id,
                stage="claude_inference",
                detail=f"JSON decode error: {exc}",
                raw_response=raw[:500],
            )
            raise ValueError(f"RAIN-E902: Failed to parse Claude response as JSON: {exc}") from exc

        # Validate structure
        if "macros" not in data or not isinstance(data["macros"], dict):
            logger.error(
                "claude_response_validation_failure",
                error_code="RAIN-E902",
                session_id=session_id,
                user_id=user_id,
                stage="claude_inference",
                detail="Missing or invalid 'macros' key",
            )
            raise ValueError("RAIN-E902: Claude response missing 'macros' dict")

        macros = data["macros"]

        # Validate all 7 macros present and in range
        for macro_name in VALID_MACROS:
            if macro_name not in macros:
                logger.error(
                    "claude_response_validation_failure",
                    error_code="RAIN-E902",
                    session_id=session_id,
                    user_id=user_id,
                    stage="claude_inference",
                    detail=f"Missing macro: {macro_name}",
                )
                raise ValueError(f"RAIN-E902: Claude response missing macro '{macro_name}'")
            val = macros[macro_name]
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"RAIN-E902: Macro '{macro_name}' must be numeric, got {type(val).__name__}"
                )
            # Clamp to valid range
            macros[macro_name] = float(max(0.0, min(10.0, val)))

        # Reject unexpected macro names
        unexpected = set(macros.keys()) - VALID_MACROS
        if unexpected:
            for key in unexpected:
                del macros[key]

        # Validate explanation
        explanation = data.get("explanation", "")
        if not isinstance(explanation, str) or not explanation.strip():
            explanation = "No explanation provided."

        # Validate confidence
        confidence = data.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = float(max(0.0, min(1.0, confidence)))

        return {
            "macros": macros,
            "explanation": explanation.strip(),
            "confidence": confidence,
        }

    async def analyze_and_suggest(
        self,
        features: Dict[str, Any],
        current_macros: Dict[str, float],
        genre: Dict[str, float],
        style: str,
        platform_targets: List[str],
        user_query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> Dict[str, Any]:
        """Get macro suggestions from Claude based on audio analysis and user query.

        Args:
            features: 43-dimensional feature vector from FeatureVector.to_dict()
            current_macros: Current macro values (BRIGHTEN, GLUE, WIDTH, etc.)
            genre: Genre classification probabilities {genre_name: confidence}
            style: User-selected style preset name
            platform_targets: List of target platform slugs (e.g. ["spotify", "apple_music"])
            user_query: Natural language request from the user
            session_id: Session ID for structured logging
            user_id: User ID for structured logging

        Returns:
            Dict with keys: macros (dict), explanation (str), confidence (float)

        Raises:
            anthropic.AuthenticationError: On invalid API key (RAIN-E900)
            anthropic.APITimeoutError: On exhausted retries (RAIN-E901)
            ValueError: On response parsing failure (RAIN-E902)
        """
        if not settings.ANTHROPIC_API_KEY:
            logger.error(
                "claude_api_not_configured",
                error_code="RAIN-E900",
                session_id=session_id,
                user_id=user_id,
                stage="claude_inference",
                detail="ANTHROPIC_API_KEY is not set",
            )
            raise anthropic.AuthenticationError(
                message="RAIN-E900: ANTHROPIC_API_KEY is not configured",
                response=None,  # type: ignore[arg-type]
                body=None,
            )

        # Build the user message with all context
        top_genres = sorted(genre.items(), key=lambda x: x[1], reverse=True)[:3]
        genre_str = ", ".join(f"{g} ({c:.0%})" for g, c in top_genres) if top_genres else "unknown"

        user_message = json.dumps({
            "audio_features": features,
            "current_macros": current_macros,
            "detected_genre": genre_str,
            "style_preset": style,
            "target_platforms": platform_targets,
            "user_request": user_query,
        }, indent=2)

        start_ms = time.monotonic()
        try:
            raw_response = await self._call_with_retry(
                system=MACRO_SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=1024,
                session_id=session_id,
                user_id=user_id,
                stage="claude_macro_suggestion",
            )
        except anthropic.AuthenticationError:
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            logger.error(
                "claude_suggest_failed",
                error_code="RAIN-E901",
                session_id=session_id,
                user_id=user_id,
                stage="claude_macro_suggestion",
                duration_ms=duration_ms,
                detail=str(exc),
            )
            raise

        result = self._parse_macro_response(
            raw_response,
            session_id=session_id,
            user_id=user_id,
        )

        duration_ms = int((time.monotonic() - start_ms) * 1000)
        logger.info(
            "claude_macro_suggestion_complete",
            session_id=session_id,
            user_id=user_id,
            stage="claude_macro_suggestion",
            duration_ms=duration_ms,
            confidence=result["confidence"],
            macros=result["macros"],
        )

        return result

    async def generate_before_after_report(
        self,
        before_features: Dict[str, Any],
        after_features: Dict[str, Any],
        applied_macros: Dict[str, float],
        qc_results: List[Dict[str, Any]],
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Generate a plain-language before/after mastering report.

        Args:
            before_features: Feature vector of the input audio
            after_features: Feature vector of the mastered output
            applied_macros: The macro settings that were applied
            qc_results: List of QC check result dicts from QCReport.to_dict()["checks"]
            session_id: Session ID for structured logging
            user_id: User ID for structured logging

        Returns:
            Plain-text mastering report string

        Raises:
            anthropic.AuthenticationError: On invalid API key (RAIN-E900)
            anthropic.APITimeoutError: On exhausted retries (RAIN-E901)
        """
        if not settings.ANTHROPIC_API_KEY:
            logger.error(
                "claude_api_not_configured",
                error_code="RAIN-E900",
                session_id=session_id,
                user_id=user_id,
                stage="claude_report",
                detail="ANTHROPIC_API_KEY is not set",
            )
            raise anthropic.AuthenticationError(
                message="RAIN-E900: ANTHROPIC_API_KEY is not configured",
                response=None,  # type: ignore[arg-type]
                body=None,
            )

        # Summarize QC for the prompt
        qc_summary = []
        for check in qc_results:
            status = "PASS" if check.get("passed") else "FAIL"
            remediated = " (auto-remediated)" if check.get("auto_remediated") else ""
            qc_summary.append(
                f"[{status}] {check.get('name', 'Unknown')}: {check.get('detail', '')}{remediated}"
            )

        user_message = json.dumps({
            "before": before_features,
            "after": after_features,
            "applied_macros": applied_macros,
            "qc_checks": qc_summary,
        }, indent=2)

        start_ms = time.monotonic()
        try:
            report = await self._call_with_retry(
                system=REPORT_SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=2048,
                session_id=session_id,
                user_id=user_id,
                stage="claude_report",
            )
        except anthropic.AuthenticationError:
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            logger.error(
                "claude_report_failed",
                error_code="RAIN-E901",
                session_id=session_id,
                user_id=user_id,
                stage="claude_report",
                duration_ms=duration_ms,
                detail=str(exc),
            )
            raise

        duration_ms = int((time.monotonic() - start_ms) * 1000)
        logger.info(
            "claude_report_complete",
            session_id=session_id,
            user_id=user_id,
            stage="claude_report",
            duration_ms=duration_ms,
            report_length=len(report),
        )

        return report.strip()


claude_service = ClaudeService()
