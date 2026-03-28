"""
Hybrid severity engine: rule-based keyword tiers + lightweight 'ML-style' feature scoring.

The feature vector is hand-crafted (no external model file) so the stack stays portable.
Production teams can swap `score_from_features` with a trained classifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SeverityResult:
    severity_level: int  # 1–5
    priority_score: float  # higher = more urgent
    explanation: str
    feature_vector: dict[str, float]


# Keyword tiers (case-insensitive)
CRITICAL_PATTERNS = [
    r"\bcardiac arrest\b",
    r"\bnot breathing\b",
    r"\bno pulse\b",
    r"\bunconscious\b",
    r"\bsevere bleeding\b",
    r"\bunresponsive\b",
]
HIGH_PATTERNS = [
    r"\bchest pain\b",
    r"\bstroke\b",
    r"\bcan't breathe\b",
    r"\bcannot breathe\b",
    r"\bdifficulty breathing\b",
    r"\bchoking\b",
    r"\banaphylaxis\b",
]
MEDIUM_PATTERNS = [
    r"\bfracture\b",
    r"\bbroken bone\b",
    r"\bmoderate bleeding\b",
    r"\bsevere pain\b",
    r"\bburn\b",
]
LOW_PATTERNS = [
    r"\bfever\b",
    r"\bcough\b",
    r"\bmild\b",
    r"\bsore throat\b",
    r"\bnausea\b",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _max_tier_from_keywords(text: str) -> int:
    t = _normalize(text)
    if any(re.search(p, t) for p in CRITICAL_PATTERNS):
        return 5
    if any(re.search(p, t) for p in HIGH_PATTERNS):
        return 4
    if any(re.search(p, t) for p in MEDIUM_PATTERNS):
        return 3
    if any(re.search(p, t) for p in LOW_PATTERNS):
        return 2
    return 2


def _feature_scores(text: str) -> dict[str, float]:
    """Simple bag-of-keywords features in [0,1]."""
    t = _normalize(text)
    features = {
        "len_norm": min(1.0, len(t) / 400.0),
        "critical_kw": 1.0 if any(re.search(p, t) for p in CRITICAL_PATTERNS) else 0.0,
        "high_kw": 1.0 if any(re.search(p, t) for p in HIGH_PATTERNS) else 0.0,
        "medium_kw": 1.0 if any(re.search(p, t) for p in MEDIUM_PATTERNS) else 0.0,
        "low_kw": 1.0 if any(re.search(p, t) for p in LOW_PATTERNS) else 0.0,
    }
    return features


def score_from_features(fv: dict[str, float]) -> float:
    """
    Weighted linear model (interpretable pseudo-ML).
    Weights chosen so outcomes align with triage intuition.
    """
    w = {
        "critical_kw": 50.0,
        "high_kw": 35.0,
        "medium_kw": 20.0,
        "low_kw": 8.0,
        "len_norm": 5.0,
    }
    return sum(fv[k] * w[k] for k in w)


def severity_from_score(score: float, keyword_floor: int) -> int:
    """Map continuous score to 1–5, never below keyword-driven floor."""
    if score >= 55:
        level = 5
    elif score >= 40:
        level = 4
    elif score >= 25:
        level = 3
    elif score >= 12:
        level = 2
    else:
        level = 1
    return max(keyword_floor, min(5, max(level, 1)))


def predict_severity_and_priority(
    symptoms: str,
    user_reported_severity: int | None = None,
) -> SeverityResult:
    """
    If user_reported_severity (1–5) is provided, blend with AI estimate (max for safety).
    """
    symptoms = symptoms or ""
    fv = _feature_scores(symptoms)
    base_score = score_from_features(fv)
    kw_floor = _max_tier_from_keywords(symptoms)

    ai_level = severity_from_score(base_score, keyword_floor=min(kw_floor, 3))
    ai_level = max(ai_level, kw_floor)

    if user_reported_severity is not None:
        ur = max(1, min(5, int(user_reported_severity)))
        final_level = max(ai_level, ur)
        blended = "User-reported severity was blended with the AI estimate (max taken for safety)."
    else:
        final_level = ai_level
        blended = "Severity predicted from symptoms only."

    priority = 10.0 * final_level + min(20.0, base_score / 3.0)
    priority = round(priority, 2)

    explanation = (
        f"{blended} Keyword tier floor={kw_floor}, model score={base_score:.1f} → "
        f"level {final_level}."
    )

    return SeverityResult(
        severity_level=final_level,
        priority_score=priority,
        explanation=explanation,
        feature_vector=fv,
    )
