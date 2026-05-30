from types import SimpleNamespace

import pytest

from app.local_data.tdxquant_daily import TdxQuantDailyBarProvider, TdxQuantUnavailable


def test_tdxquant_provider_reports_windows_runtime_requirement_on_linux(tmp_path):
    pyplugins = tmp_path / "PYPlugins"
    pyplugins.mkdir()
    provider = TdxQuantDailyBarProvider(
        SimpleNamespace(tdxquant_pyplugins=str(pyplugins), tdxquant_seed_file="")
    )

    with pytest.raises(TdxQuantUnavailable, match="Windows Tongdaxin DLL runtime"):
        provider.get_daily_bars("000001.SZ", 5)
