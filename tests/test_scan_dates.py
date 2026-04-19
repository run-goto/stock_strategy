from backend.application.scan_service import resolve_scan_dates


def test_resolve_scan_dates_normalizes_calendar_target_to_previous_trade_date():
    config = _config_with_trade_calendar(["20260415", "20260416", "20260417"])

    start_date, end_date, target_dates = resolve_scan_dates(
        app_config=config,
        start_date="20260401",
        end_date="20260418",
        target_dates=["20260418"],
    )

    assert start_date == "20260401"
    assert end_date == "20260418"
    assert target_dates == ["20260417"]


def test_resolve_scan_dates_deduplicates_targets_that_map_to_same_trade_date():
    config = _config_with_trade_calendar(["20260415", "20260416", "20260417"])

    _, _, target_dates = resolve_scan_dates(
        app_config=config,
        start_date="20260401",
        end_date="20260418",
        target_dates=["20260417", "20260418"],
    )

    assert target_dates == ["20260417"]


def _config_with_trade_calendar(dates):
    return {
        "defaults": {"check_days": 60},
        "trade_calendar": {"dates": dates},
    }
