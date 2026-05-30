from app.local_data.repository import LocalMarketRepository
from app.local_data.tdx_sector import (
    import_tdx_local_metadata,
    parse_tdx_industry_members,
    parse_tdx_infoharbor_blocks,
    parse_tdx_sector_metadata,
)


def test_parse_tdx_sector_metadata_maps_industry_keys(tmp_path):
    hq_cache = tmp_path / "hq_cache"
    hq_cache.mkdir()
    (hq_cache / "tdxzs3.cfg").write_text(
        "\n".join(
            [
                "银行|880471|2|1|1|T1001",
                "股份制银行|881388|12|1|1|X500102",
                "锂电池概念|880534|4|2|0|锂电池",
            ]
        ),
        encoding="gbk",
    )

    metadata, key_map = parse_tdx_sector_metadata(hq_cache)

    assert {"sector_code": "880471.SH", "sector_name": "银行", "sector_type": "行业"} in metadata
    assert {"sector_code": "880534.SH", "sector_name": "锂电池概念", "sector_type": "概念"} in metadata
    assert key_map["T1001"] == "880471.SH"
    assert key_map["X500102"] == "881388.SH"


def test_parse_tdx_industry_members_uses_tdxhy_mapping(tmp_path):
    hq_cache = tmp_path / "hq_cache"
    hq_cache.mkdir()
    (hq_cache / "tdxhy.cfg").write_text(
        "0|000001|T1001|||X500102\n1|600000|T1001|||X500101\n",
        encoding="gbk",
    )

    members = parse_tdx_industry_members(
        hq_cache,
        {"T1001": "880471.SH", "X500102": "881388.SH"},
    )

    assert {"sector_code": "880471.SH", "symbol": "000001.SZ"} in members
    assert {"sector_code": "881388.SH", "symbol": "000001.SZ"} in members
    assert {"sector_code": "880471.SH", "symbol": "600000.SH"} in members


def test_parse_tdx_infoharbor_blocks_reads_concept_members(tmp_path):
    hq_cache = tmp_path / "hq_cache"
    hq_cache.mkdir()
    (hq_cache / "infoharbor_block.dat").write_text(
        "#GN_锂电池,2,880534,20050610,20260522,,\n"
        "0#300750,1#600519,\n",
        encoding="gbk",
    )

    metadata, members = parse_tdx_infoharbor_blocks(hq_cache)

    assert metadata == [
        {"sector_code": "880534.SH", "sector_name": "锂电池", "sector_type": "概念"}
    ]
    assert {"sector_code": "880534.SH", "symbol": "300750.SZ"} in members
    assert {"sector_code": "880534.SH", "symbol": "600519.SH"} in members


def test_import_tdx_local_metadata_persists_sectors_and_members(tmp_path):
    tdx_root = tmp_path / "new_tdx"
    hq_cache = tdx_root / "T0002" / "hq_cache"
    hq_cache.mkdir(parents=True)
    (hq_cache / "tdxzs3.cfg").write_text(
        "银行|880471|2|1|1|T1001\n股份制银行|881388|12|1|1|X500102\n",
        encoding="gbk",
    )
    (hq_cache / "tdxhy.cfg").write_text(
        "0|000001|T1001|||X500102\n",
        encoding="gbk",
    )
    (hq_cache / "infoharbor_block.dat").write_text(
        "#GN_锂电池,1,880534,20050610,20260522,,\n0#300750,\n",
        encoding="gbk",
    )
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    report = import_tdx_local_metadata(tdx_root, repository)

    assert report == {"profiles": 0, "sectors": 3, "sector_members": 3}
    assert repository.list_sector_members("880471.SH") == ["000001.SZ"]
    assert repository.list_sector_members("880534.SH") == ["300750.SZ"]
