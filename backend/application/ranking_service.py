"""Ranking application service."""

from backend.application.strategy.calendar import validate_date
from backend.domain.ports import RankingRepository

_DIRECTION_ALIASES = {
    "": "range",
    "range": "range",
    "amplitude": "range",
    "up": "up",
    "rise": "up",
    "gain": "up",
    "zhang": "up",
    "涨": "up",
    "down": "down",
    "fall": "down",
    "drop": "down",
    "die": "down",
    "跌": "down",
}


class RankingService:
    """Read-only ranking use cases."""

    def __init__(self, ranking_repository: RankingRepository):
        self.ranking_repository = ranking_repository

    def list_high_low_gain_rank(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        direction: str | None = None,
        min_gain_percent: float | None = None,
    ) -> list[dict]:
        validate_date(start_date)
        validate_date(end_date)
        if start_date > end_date:
            raise ValueError("start must be less than or equal to end")
        normalized_direction = _normalize_direction(direction)
        if min_gain_percent is not None and min_gain_percent < 0:
            raise ValueError("min_gain_percent must be greater than or equal to 0")
        ranks = self.ranking_repository.list_high_low_gain_rank(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            direction=normalized_direction,
            min_gain_percent=min_gain_percent,
        )
        return [rank.to_dict() for rank in ranks]


def _normalize_direction(direction: str | None) -> str:
    normalized = _DIRECTION_ALIASES.get((direction or "").strip().lower())
    if normalized is None:
        raise ValueError("direction must be one of range, up, down")
    return normalized
