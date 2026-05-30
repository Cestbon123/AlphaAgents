from app.local_data.repository import LocalMarketRepository
from app.local_data.tdxquant_metadata import import_tdxquant_metadata


def test_import_tdxquant_metadata_persists_profiles_and_sectors(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    payload = {
        "stocks": [
            {"Code": "600519.SH", "Name": "贵州茅台", "ListType": 5},
            {"Code": "300001.SZ", "Name": "特锐德", "ListType": 51},
            {"Code": "688001.SH", "Name": "华兴源创", "ListType": 52},
            {"Code": "920001.BJ", "Name": "纬达光电", "ListType": 53},
            {"Code": "000004.SZ", "Name": "*ST国华", "ListType": 5},
        ],
        "sectors": [
            {"Code": "881355.SH", "Name": "软件服务", "BlockType": "行业"},
            {"Code": "880592.SH", "Name": "互联金融", "BlockType": "概念"},
        ],
        "sector_members": [
            {"sector_code": "881355.SH", "symbol": "688001.SH"},
            {"sector_code": "880592.SH", "symbol": "300001.SZ"},
        ],
        "relations": [
            {
                "symbol": "600519.SH",
                "BlockCode": "881355.SH",
                "BlockName": "软件服务",
                "BlockType": "行业",
            }
        ],
    }

    report = import_tdxquant_metadata(payload, repository)

    assert report == {
        "profiles": 5,
        "sectors": 2,
        "sector_members": 3,
    }
    assert repository.get_security_name("600519.SH") == "贵州茅台"
    assert repository.get_security_profile("300001.SZ")["market_category"] == "创业板"
    assert repository.get_security_profile("688001.SH")["market_category"] == "科创板"
    assert repository.get_security_profile("920001.BJ")["market_category"] == "北交所"
    assert repository.get_security_profile("000004.SZ")["is_st"] is True
    assert repository.get_security_sectors("600519.SH")[0]["sector_name"] == "软件服务"
    assert repository.list_sector_members("880592.SH") == ["300001.SZ"]


def test_import_tdxquant_metadata_accepts_normalized_export_payload(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    payload = {
        "stocks": [
            {
                "symbol": "600000.SH",
                "name": "浦发银行",
                "market": "SH",
                "market_category": "沪市主板",
                "is_st": False,
            }
        ],
        "sectors": [{"code": "880471.SH", "name": "银行", "type": "行业"}],
        "sector_members": [{"sector_code": "880471.SH", "symbol": "600000.SH"}],
    }

    import_tdxquant_metadata(payload, repository)

    assert repository.get_security_profile("600000.SH") == {
        "symbol": "600000.SH",
        "name": "浦发银行",
        "market": "SH",
        "market_category": "沪市主板",
        "is_st": False,
        "source": "tdxquant",
    }
    assert repository.get_security_sectors("600000.SH") == [
        {
            "sector_code": "880471.SH",
            "sector_name": "银行",
            "sector_type": "行业",
        }
    ]
