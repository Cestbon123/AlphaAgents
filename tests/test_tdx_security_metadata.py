from app.local_data.tdx_security import parse_tdx_security_file


def _record(code: str, name: str) -> bytes:
    data = bytearray(96)
    data[:6] = code.encode("ascii")
    data[31 : 31 + len(name.encode("gbk"))] = name.encode("gbk")
    return bytes(data)


def test_parse_tdx_security_file_reads_gbk_names(tmp_path):
    path = tmp_path / "shs.tnf"
    path.write_bytes(b"header" + _record("000001", "上证指数") + _record("600519", "贵州茅台"))

    rows = parse_tdx_security_file(path, "SH")

    assert {"symbol": "000001.SH", "name": "上证指数", "market": "SH"} in rows
    assert {"symbol": "600519.SH", "name": "贵州茅台", "market": "SH"} in rows


def test_parse_tdx_security_file_ignores_codes_without_chinese_name(tmp_path):
    path = tmp_path / "szs.tnf"
    path.write_bytes(_record("000001", "平安银行") + b"123456" + bytes(64))

    rows = parse_tdx_security_file(path, "SZ")

    assert rows == [{"symbol": "000001.SZ", "name": "平安银行", "market": "SZ"}]
