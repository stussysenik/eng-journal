from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateCard:
    input_per_million: float
    output_per_million: float
    cached_input_per_million: float
    cache_write_per_million: float


CLAUDE_RATE_CARDS: dict[str, RateCard] = {
    "claude-opus-4-5-20251101": RateCard(5.0, 25.0, 0.50, 6.25),
    "claude-opus-4.5": RateCard(5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-20250514": RateCard(15.0, 75.0, 1.50, 18.75),
    "claude-opus-4": RateCard(15.0, 75.0, 1.50, 18.75),
    "claude-sonnet-4-20250514": RateCard(3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4.5": RateCard(3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4.6": RateCard(3.0, 15.0, 0.30, 3.75),
    "claude-haiku-3-5-20241022": RateCard(0.8, 4.0, 0.08, 1.0),
    "claude-haiku-4.5": RateCard(1.0, 5.0, 0.10, 1.25),
    "default": RateCard(3.0, 15.0, 0.30, 3.75),
}

OPENAI_RATE_CARDS: dict[str, RateCard] = {
    "gpt-5.4": RateCard(2.50, 15.00, 0.25, 2.50),
    "gpt-5.4-mini": RateCard(0.750, 4.500, 0.075, 0.750),
    "gpt-5.4-nano": RateCard(0.20, 1.25, 0.02, 0.20),
    "default": RateCard(2.50, 15.00, 0.25, 2.50),
}


def rate_card_for_claude(model: str) -> RateCard:
    return CLAUDE_RATE_CARDS.get(model or "", CLAUDE_RATE_CARDS["default"])


def rate_card_for_openai(model: str) -> RateCard:
    return OPENAI_RATE_CARDS.get(model or "", OPENAI_RATE_CARDS["default"])


def calculate_claude_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, float]:
    rates = rate_card_for_claude(model)
    input_cost = (input_tokens / 1_000_000) * rates.input_per_million
    output_cost = (output_tokens / 1_000_000) * rates.output_per_million
    cache_read_cost = (cache_read_tokens / 1_000_000) * rates.cached_input_per_million
    cache_write_cost = (cache_write_tokens / 1_000_000) * rates.cache_write_per_million
    actual = input_cost + output_cost + cache_read_cost + cache_write_cost
    no_cache = (
        input_cost
        + output_cost
        + (cache_read_tokens / 1_000_000) * rates.input_per_million
        + cache_write_cost
    )
    return {
        "actual": round(actual, 6),
        "without_cache": round(no_cache, 6),
        "cache_savings": round(no_cache - actual, 6),
    }


def estimate_codex_cost(total_tokens: int, model: str) -> dict[str, float]:
    rates = rate_card_for_openai(model)
    low = (total_tokens / 1_000_000) * rates.input_per_million
    high = (total_tokens / 1_000_000) * rates.output_per_million
    mid = (total_tokens / 1_000_000) * (
        (rates.input_per_million * 0.8) + (rates.output_per_million * 0.2)
    )
    return {
        "low": round(low, 6),
        "mid": round(mid, 6),
        "high": round(high, 6),
    }

