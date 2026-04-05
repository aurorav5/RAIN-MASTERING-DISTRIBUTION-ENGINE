# ADR-0005: C2PA + AudioSeal + Chromaprint + RAIN-CERT Provenance Stack

## Status
Accepted

## Context
The EU AI Act Article 50 enters application on 2026-08-02, mandating that AI-generated or AI-modified audiovisual content carry machine-readable disclosure of its AI provenance. Non-compliance carries fines up to 3% of global turnover for the deploying party. Separately, major streaming platforms (Spotify, Apple Music, YouTube) are rolling out AI-content labeling policies tied to DDEX ERN 4.3.2 signals and C2PA manifests.

RAIN outputs are AI-modified audio: RainNet predicts mastering parameters and RainDSP applies them. Every downloadable file must carry provenance that is:

1. **Manifest-attached** — structured metadata stating what AI did what, when, with which model hash.
2. **Detectable post-hoc** — if the manifest is stripped, the file should still be identifiable as RAIN-processed.
3. **Cryptographically signed** — the manifest and detection signals must be bound to ARCOVEL's identity, not forgeable.
4. **Fingerprint-linked** — to correlate the file back to RAIN's session database for takedown, attribution, and dispute resolution.

No single technology covers all four requirements.

## Decision
RAIN attaches a four-layer provenance stack to every render exported from the paid tiers:

1. **C2PA v2.2 manifest** — structured claims (software agent, model hash, render timestamp, WASM binary hash, processing params). Attached to the output file per the C2PA specification.
2. **AudioSeal 16-bit watermark** — imperceptible audio watermark embedded in the render. Survives transcoding, codec roundtrips, and mild time/pitch modification. Detectable even if the C2PA manifest is stripped.
3. **Chromaprint acoustic fingerprint** — computed over the final render and stored in the RAIN session database. Allows correlating a wild file back to the original session.
4. **RAIN-CERT signature** — Ed25519 signature by ARCOVEL's signing key, binding the C2PA manifest, AudioSeal payload, and Chromaprint fingerprint into one verifiable artifact.

The free tier renders in-browser without persistence and does not receive RAIN-CERT signing (no session to bind to).

## Consequences

**Positive:**
- EU AI Act Article 50 compliance by the 2026-08-02 deadline, on all paid-tier outputs.
- Defense-in-depth: if any one layer is stripped, the others remain. Manifest strip leaves the watermark; watermark laundering leaves the fingerprint; fingerprint evasion leaves the Ed25519 signature on the manifest.
- Takedown and attribution path: a wild MP3 claimed to be RAIN output can be verified or refuted in seconds via AudioSeal detection + Chromaprint lookup.
- DDEX ERN 4.3.2 AI disclosure fields can be populated directly from the C2PA claims.

**Negative:**
- Adds ~200-400 ms of post-render CPU time for watermark embedding and Chromaprint hashing.
- AudioSeal embedding alters samples imperceptibly but measurably; the watermarked render is NOT bit-identical to the unwatermarked WASM output. The canonical render manifest records both hashes.
- Ed25519 signing key management becomes a critical infrastructure concern (HSM or isolated signer service).
- C2PA tooling ecosystem is still maturing; manifest parsers on downstream platforms may lag the v2.2 spec.

**Neutral:**
- Establishes ARCOVEL as a signer identity in the C2PA ecosystem, which requires ongoing trust-list registration and key rotation hygiene.

## Alternatives Considered

1. **Watermark-only (AudioSeal alone).** Rejected. No manifest chain means no structured AI disclosure; fails EU AI Act Article 50 which requires machine-readable metadata, not just detectability.
2. **Manifest-only (C2PA alone).** Rejected. C2PA manifests can be stripped trivially (re-encode, re-mux). Without the watermark, stripped files are indistinguishable from non-AI audio, defeating the compliance goal.
3. **Fingerprint-only (Chromaprint alone).** Rejected. Fingerprints identify a specific rendered file but carry no claims about AI involvement. Not compliant with Article 50's disclosure requirement.
4. **Proprietary watermark instead of AudioSeal.** Rejected. AudioSeal is Meta-published with a documented 16-bit capacity and public detector. An open, inspectable watermark has stronger legal posture than a black-box proprietary one.
5. **Blockchain-based provenance.** Rejected. Solves no problem that C2PA + Ed25519 doesn't already solve, and adds gas costs, confirmation latency, and a hard dependency on external chain availability.
