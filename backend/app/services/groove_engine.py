"""
RAIN Groove Engine — Microtiming, Swing, and Rhythmic Feel Analysis

This engine analyzes and enhances the rhythmic feel of audio tracks.
It detects transients, calculates swing ratios, measures timing variance,
and provides groove enhancement for genre-specific rhythmic characteristics.

Critical for afropop_house, hiphop, and dance genres where groove is paramount.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.signal import find_peaks
from dataclasses import dataclass


@dataclass
class GrooveAnalysisResult:
    """Complete groove analysis output."""
    swing_ratio: float           # Ratio of odd/even intervals (0.5-2.0 typical)
    timing_variance: float       # Standard deviation of intervals (0.0-1.0 normalized)
    transient_sharpness: float   # Average transient attack steepness (0.0-1.0)
    rhythmic_consistency: float  # How consistent the rhythm is (0.0-1.0)
    groove_score: float          # Composite score (0.0-1.0)
    tempo_bpm: float             # Estimated tempo in BPM
    transient_count: int         # Number of detected transients
    intervals: NDArray[np.float64] = None  # Raw interval array


class GrooveEngine:
    """
    Analyze and enhance rhythmic groove in audio.
    
    The groove engine operates on two levels:
    1. Analysis: Detect transients, measure timing patterns, calculate metrics
    2. Enhancement: Apply microtiming adjustments to improve feel
    """
    
    def __init__(self, sample_rate: int = 48000):
        self.sr = sample_rate
        self.min_transient_interval = 0.02  # 20ms minimum between transients
        
    def detect_transients(self, audio: NDArray[np.float64]) -> NDArray[np.int64]:
        """
        Detect transient positions in audio.
        
        Uses energy-based detection with adaptive thresholding.
        Returns sample indices of transient onsets.
        """
        # Convert to mono if stereo
        if audio.ndim > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio.flatten()
        
        # Compute envelope using Hilbert transform
        analytic_signal = np.abs(np.hilbert(mono))
        
        # Smooth envelope
        window_size = int(0.01 * self.sr)  # 10ms window
        if len(analytic_signal) > window_size:
            envelope = np.convolve(analytic_signal, np.ones(window_size)/window_size, mode='same')
        else:
            envelope = analytic_signal
        
        # Adaptive threshold
        threshold = np.mean(envelope) + 0.5 * np.std(envelope)
        
        # Find peaks in envelope
        min_distance = int(self.min_transient_interval * self.sr)
        peaks, _ = find_peaks(envelope, height=threshold, distance=min_distance)
        
        return peaks
    
    def calculate_swing_ratio(self, transients: NDArray[np.int64]) -> float:
        """
        Calculate swing ratio from transient intervals.
        
        Swing ratio = mean(odd intervals) / mean(even intervals)
        Perfect even timing = 1.0
        Swung timing typically 1.2-1.8
        """
        if len(transients) < 3:
            return 1.0
        
        intervals = np.diff(transients)
        
        if len(intervals) < 2:
            return 1.0
        
        even_intervals = intervals[::2]   # 1st, 3rd, 5th...
        odd_intervals = intervals[1::2]   # 2nd, 4th, 6th...
        
        if len(even_intervals) == 0 or len(odd_intervals) == 0:
            return 1.0
        
        mean_even = np.mean(even_intervals)
        mean_odd = np.mean(odd_intervals)
        
        if mean_even < 1e-10:
            return 1.0
        
        return float(mean_odd / mean_even)
    
    def calculate_timing_variance(self, transients: NDArray[np.int64]) -> float:
        """
        Calculate normalized timing variance.
        
        Measures how much intervals deviate from perfect grid.
        Lower = more quantized, Higher = more human/loose
        Returns 0.0-1.0 normalized value.
        """
        if len(transients) < 2:
            return 0.0
        
        intervals = np.diff(transients)
        
        if len(intervals) < 2:
            return 0.0
        
        # Expected interval (median is more robust than mean)
        expected = np.median(intervals)
        
        if expected < 1e-10:
            return 0.0
        
        # Coefficient of variation
        std_dev = np.std(intervals)
        cv = std_dev / expected
        
        # Normalize to 0.0-1.0 (typical range 0.0-0.5 for most music)
        normalized = min(cv / 0.5, 1.0)
        
        return float(normalized)
    
    def calculate_transient_sharpness(self, audio: NDArray[np.float64], 
                                       transients: NDArray[np.int64]) -> float:
        """
        Calculate average transient sharpness.
        
        Sharpness = steepness of attack (samples to reach peak)
        Higher = punchier, more defined transients
        """
        if len(transients) == 0:
            return 0.5
        
        if audio.ndim > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio.flatten()
        
        sharpness_values = []
        window_size = int(0.005 * self.sr)  # 5ms analysis window
        
        for idx in transients:
            start = max(0, idx)
            end = min(len(mono), idx + window_size)
            
            if end - start < 10:
                continue
            
            segment = mono[start:end]
            
            # Find time to peak
            peak_idx = np.argmax(np.abs(segment))
            
            if peak_idx < 1:
                continue
            
            # Sharpness inverse to time-to-peak (normalized)
            sharpness = 1.0 - (peak_idx / window_size)
            sharpness_values.append(max(0.0, min(1.0, sharpness)))
        
        if len(sharpness_values) == 0:
            return 0.5
        
        return float(np.mean(sharpness_values))
    
    def estimate_tempo(self, transients: NDArray[np.int64]) -> float:
        """
        Estimate tempo in BPM from transient intervals.
        """
        if len(transients) < 2:
            return 120.0
        
        intervals = np.diff(transients)
        
        if len(intervals) == 0:
            return 120.0
        
        # Median interval in seconds
        median_interval_sec = np.median(intervals) / self.sr
        
        if median_interval_sec < 0.1:
            return 120.0
        
        # Convert to BPM (assuming quarter notes)
        bpm = 60.0 / median_interval_sec
        
        # Clamp to reasonable range
        bpm = max(60.0, min(200.0, bpm))
        
        return float(bpm)
    
    def analyze(self, audio: NDArray[np.float64]) -> GrooveAnalysisResult:
        """
        Perform complete groove analysis on audio.
        """
        # Detect transients
        transients = self.detect_transients(audio)
        
        # Calculate metrics
        swing = self.calculate_swing_ratio(transients)
        variance = self.calculate_timing_variance(transients)
        sharpness = self.calculate_transient_sharpness(audio, transients)
        tempo = self.estimate_tempo(transients)
        
        # Calculate rhythmic consistency (inverse of variance, scaled)
        consistency = 1.0 - min(variance, 1.0)
        
        # Composite groove score
        # For afropop_house: swing and consistency are most important
        groove_score = (
            0.3 * min(abs(swing - 1.0) / 0.5, 1.0) +  # Deviation from even (swing presence)
            0.3 * consistency +                         # Rhythmic stability
            0.2 * sharpness +                           # Transient definition
            0.2 * (1.0 - variance)                      # Timing tightness
        )
        
        groove_score = min(1.0, max(0.0, groove_score))
        
        # Store intervals for downstream use
        intervals = np.diff(transients) if len(transients) > 1 else np.array([])
        
        return GrooveAnalysisResult(
            swing_ratio=swing,
            timing_variance=variance,
            transient_sharpness=sharpness,
            rhythmic_consistency=consistency,
            groove_score=groove_score,
            tempo_bpm=tempo,
            transient_count=len(transients),
            intervals=intervals
        )
    
    def apply_microtiming(self, audio: NDArray[np.float64], 
                          groove_score: float,
                          genre: str = "afropop_house") -> NDArray[np.float64]:
        """
        Apply microtiming adjustments to enhance groove feel.
        
        This introduces subtle timing variations that make the track
        feel more human and less quantized.
        """
        if groove_score >= 0.7:
            # Already good groove, minimal adjustment
            return audio
        
        # Genre-specific microtiming strategies
        if genre == "afropop_house":
            # Introduce slight swing and looseness
            swing_amount = 0.1 * (1.0 - groove_score)
            humanize_variance = 0.005 * (1.0 - groove_score)
        elif genre == "hiphop":
            # More pronounced swing
            swing_amount = 0.15 * (1.0 - groove_score)
            humanize_variance = 0.008 * (1.0 - groove_score)
        else:
            # Generic gentle adjustment
            swing_amount = 0.05 * (1.0 - groove_score)
            humanize_variance = 0.003 * (1.0 - groove_score)
        
        # Note: True microtiming requires transient-level manipulation
        # This is a simplified version that prepares the signal
        # Full implementation would shift individual transient positions
        
        # For now, we mark this as a placeholder for C++ DSP implementation
        # The actual time-stretching happens in RainDSP
        return audio
    
    def enhance_groove(self, audio: NDArray[np.float64], 
                       analysis: GrooveAnalysisResult,
                       target_groove: float = 0.75) -> NDArray[np.float64]:
        """
        Enhance groove based on analysis and target state.
        
        Applies transient shaping and dynamic adjustments to improve feel.
        """
        delta = target_groove - analysis.groove_score
        
        if delta <= 0:
            # Already at or above target
            return audio
        
        # Enhance transient sharpness if low
        if analysis.transient_sharpness < 0.5:
            audio = self._enhance_transients(audio, amount=delta * 0.3)
        
        # Adjust dynamics for better rhythmic flow
        if analysis.timing_variance > 0.3:
            audio = self._tighten_dynamics(audio, amount=delta * 0.2)
        
        return audio
    
    def _enhance_transients(self, audio: NDArray[np.float64], 
                            amount: float = 0.3) -> NDArray[np.float64]:
        """
        Enhance transient attack using simple transient shaper.
        """
        if audio.ndim > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio.flatten()
        
        # Simple transient detection and enhancement
        # Full implementation would use dedicated transient shaper DSP
        attack_gain = 1.0 + amount * 0.5
        
        # Apply gain to transient regions (simplified)
        # In production, this uses envelope followers and targeted gain
        enhanced = audio * attack_gain
        
        return enhanced
    
    def _tighten_dynamics(self, audio: NDArray[np.float64], 
                          amount: float = 0.2) -> NDArray[np.float64]:
        """
        Apply light compression to tighten rhythmic elements.
        """
        # Simplified dynamic tightening
        # Full implementation uses multiband compression tuned for rhythm
        threshold = -20.0
        ratio = 2.0 + amount * 2.0
        
        # Placeholder for actual compression
        return audio


# Convenience function for standalone use
def analyze_groove(audio: NDArray[np.float64], sr: int = 48000) -> GrooveAnalysisResult:
    """Analyze groove in audio file."""
    engine = GrooveEngine(sample_rate=sr)
    return engine.analyze(audio)
