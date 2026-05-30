import pytest

from app.strategies.filters import should_exclude_from_strategy_by_default


@pytest.mark.parametrize("name", ["ST测试", "*ST测试", "SST测试", "S*ST测试", "st测试"])
def test_default_strategy_filter_excludes_st_names(name):
    assert should_exclude_from_strategy_by_default(name) is True


@pytest.mark.parametrize("name", ["贵州茅台", "测试ST概念", "", None])
def test_default_strategy_filter_keeps_non_st_names(name):
    assert should_exclude_from_strategy_by_default(name) is False


@pytest.mark.parametrize("market_category", ["创业板", "科创板", "北交所"])
def test_default_strategy_filter_excludes_tdxquant_market_categories(market_category):
    profile = {
        "symbol": "300001.SZ",
        "name": "测试股票",
        "market_category": market_category,
        "is_st": False,
    }

    assert should_exclude_from_strategy_by_default(profile["name"], profile=profile) is True


def test_default_strategy_filter_excludes_tdxquant_st_profile():
    profile = {
        "symbol": "600001.SH",
        "name": "测试股票",
        "market_category": "沪市主板",
        "is_st": True,
    }

    assert should_exclude_from_strategy_by_default(profile["name"], profile=profile) is True


def test_default_strategy_filter_keeps_tdxquant_main_board_profile():
    profile = {
        "symbol": "600001.SH",
        "name": "测试股票",
        "market_category": "沪市主板",
        "is_st": False,
    }

    assert should_exclude_from_strategy_by_default(profile["name"], profile=profile) is False
