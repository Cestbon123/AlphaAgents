from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.domain.models import ResearchSupplementBundle
from app.external_data.cache import ExternalDataCache

USER_AGENT = "Mozilla/5.0 AlphaAgents/0.1"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"
PUSH2HIS_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={code}"
CNINFO_ANNOUNCEMENT_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"


class AStockDataUnavailable(Exception):
    """Raised when an external A-share endpoint cannot provide data."""


class AStockDataClient:
    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout

    def valuation(self, symbol: str) -> dict[str, Any]:
        raw_text = self._http_text(TENCENT_QUOTE_URL.format(code=_prefixed_code(symbol)), "gbk")
        return normalize_tencent_quote(raw_text, symbol)

    def money_flow(self, symbol: str) -> dict[str, Any]:
        payload = self._http_json(
            PUSH2HIS_URL,
            {
                "lmt": "1",
                "klt": "101",
                "secid": _eastmoney_secid(symbol),
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55",
            },
        )
        return normalize_eastmoney_money_flow(payload)

    def dragon_tiger(self, symbol: str) -> list[dict[str, Any]]:
        payload = self._eastmoney_datacenter(
            report_name="RPT_DAILYBILLBOARD_DETAILS",
            filter_str=f'(SECURITY_CODE="{_plain_code(symbol)}")',
            page_size=5,
        )
        return normalize_datacenter_rows(payload)

    def sectors(self, symbol: str) -> list[dict[str, Any]]:
        payload = self._http_json(
            PUSH2_URL,
            {
                "secid": _eastmoney_secid(symbol),
                "fields": "f58,f127,f128,f129,f140,f141",
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else {}
        names = [
            value
            for key, value in (data or {}).items()
            if key.startswith("f") and isinstance(value, str) and value and value != "-"
        ]
        return [
            {"sector_code": "", "sector_name": name, "sector_type": "外部标签"}
            for name in dict.fromkeys(names)
        ]

    def announcements(self, symbol: str) -> list[dict[str, Any]]:
        payload = self._http_json(
            CNINFO_ANNOUNCEMENT_URL,
            {
                "stock": _plain_code(symbol),
                "pageNum": "1",
                "pageSize": "5",
                "column": "szse" if _market_suffix(symbol) == "SZ" else "sse",
                "tabName": "fulltext",
            },
            method="POST",
        )
        rows = payload.get("announcements") if isinstance(payload, dict) else []
        return [
            {
                "title": str(row.get("announcementTitle", "")),
                "date": str(row.get("announcementTime", "")),
                "source": "cninfo",
            }
            for row in rows or []
            if row.get("announcementTitle")
        ]

    def news(self, symbol: str) -> list[dict[str, Any]]:
        payload = self._http_json(
            "https://search-api-web.eastmoney.com/search/jsonp",
            {
                "keyword": _plain_code(symbol),
                "pageIndex": "1",
                "pageSize": "5",
            },
        )
        rows = _extract_jsonp_result(payload).get("result", []) if isinstance(payload, dict) else []
        return normalize_datacenter_rows(rows)

    def _eastmoney_datacenter(
        self, *, report_name: str, filter_str: str = "", page_size: int = 50
    ) -> list[dict[str, Any]]:
        payload = self._http_json(
            DATACENTER_URL,
            {
                "reportName": report_name,
                "columns": "ALL",
                "filter": filter_str,
                "pageNumber": "1",
                "pageSize": str(page_size),
                "source": "WEB",
                "client": "WEB",
            },
        )
        result = payload.get("result") if isinstance(payload, dict) else {}
        rows = result.get("data") if isinstance(result, dict) else []
        return rows if isinstance(rows, list) else []

    def _http_json(
        self, url: str, params: dict[str, str], *, method: str = "GET"
    ) -> dict[str, Any]:
        body = None
        target_url = url
        if method == "GET":
            target_url = f"{url}?{urlencode(params)}"
        else:
            body = urlencode(params).encode("utf-8")

        text = self._http_text(target_url, "utf-8", data=body, method=method)
        return _json_from_text(text)

    def _http_text(
        self,
        url: str,
        encoding: str,
        *,
        data: bytes | None = None,
        method: str = "GET",
    ) -> str:
        request = Request(
            url,
            data=data,
            headers={"User-Agent": USER_AGENT},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read().decode(encoding, errors="ignore")
        except Exception as exc:
            raise AStockDataUnavailable(str(exc)) from exc


class ExternalResearchDataProvider:
    def __init__(
        self,
        *,
        cache: ExternalDataCache,
        client: AStockDataClient | None = None,
        live_enabled: bool = False,
    ) -> None:
        self.cache = cache
        self.client = client or AStockDataClient()
        self.live_enabled = live_enabled

    def supplement(self, symbol: str) -> ResearchSupplementBundle:
        gaps: list[str] = []
        return ResearchSupplementBundle(
            valuation=self._get_dict(symbol, "valuation", self.client.valuation, gaps),
            money_flow=self._get_dict(symbol, "money_flow", self.client.money_flow, gaps),
            dragon_tiger=self._get_list(symbol, "dragon_tiger", self.client.dragon_tiger, gaps),
            sectors=self._get_list(symbol, "sectors", self.client.sectors, gaps),
            announcements=self._get_list(symbol, "announcements", self.client.announcements, gaps),
            news=self._get_list(symbol, "news", self.client.news, gaps),
            data_gaps=gaps,
        )

    def _get_dict(
        self,
        symbol: str,
        data_key: str,
        loader: Any,
        gaps: list[str],
    ) -> dict[str, Any]:
        cached = self.cache.get(symbol, data_key)
        if isinstance(cached, dict):
            return cached
        if not self.live_enabled:
            gaps.append(f"{data_key}: 外部实时补充数据未启用，未命中本地缓存")
            return {}
        try:
            payload = loader(symbol)
        except Exception as exc:
            gaps.append(f"{data_key}: {exc}")
            return {}
        self.cache.set(symbol, data_key, payload)
        return payload

    def _get_list(
        self,
        symbol: str,
        data_key: str,
        loader: Any,
        gaps: list[str],
    ) -> list[dict[str, Any]]:
        cached = self.cache.get(symbol, data_key)
        if isinstance(cached, list):
            return cached
        if not self.live_enabled:
            gaps.append(f"{data_key}: 外部实时补充数据未启用，未命中本地缓存")
            return []
        try:
            payload = loader(symbol)
        except Exception as exc:
            gaps.append(f"{data_key}: {exc}")
            return []
        self.cache.set(symbol, data_key, payload)
        return payload


def normalize_tencent_quote(raw_text: str, symbol: str) -> dict[str, Any]:
    _, _, payload = raw_text.partition("=")
    fields = payload.strip().strip('";').split("~")
    if len(fields) < 46:
        raise AStockDataUnavailable("Tencent quote response has insufficient fields")

    def number(index: int) -> float | None:
        try:
            value = fields[index]
            return None if value in {"", "-"} else float(value)
        except (ValueError, IndexError):
            return None

    return {
        "symbol": symbol,
        "name": fields[1],
        "price": number(3),
        "pe_ttm": number(39),
        "pb": number(46),
        "turnover_rate": number(38),
        "market_cap": number(45),
        "source": "tencent",
    }


def normalize_eastmoney_money_flow(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    klines = data.get("klines") if isinstance(data, dict) else []
    if not klines:
        raise AStockDataUnavailable("Eastmoney money flow response is empty")
    fields = str(klines[-1]).split(",")
    return {
        "trade_date": fields[0] if fields else "",
        "main_net_inflow": _to_float(fields[1] if len(fields) > 1 else None),
        "small_net_inflow": _to_float(fields[4] if len(fields) > 4 else None),
        "source": "eastmoney",
    }


def normalize_datacenter_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("var "):
        _, _, cleaned = cleaned.partition("=")
    if not cleaned.startswith("{"):
        match = re.search(r"\((\{.*\})\)", cleaned, flags=re.S)
        if match:
            cleaned = match.group(1)
    try:
        payload = json.loads(cleaned.strip().strip(";"))
    except json.JSONDecodeError as exc:
        raise AStockDataUnavailable("External endpoint returned non-JSON payload") from exc
    return payload if isinstance(payload, dict) else {}


def _extract_jsonp_result(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _to_float(value: str | None) -> float | None:
    try:
        return None if value in {None, "", "-"} else float(value)
    except ValueError:
        return None


def _plain_code(symbol: str) -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value.split(".", 1)[0]
    if value.startswith(("SH", "SZ", "BJ")):
        return value[2:]
    return value


def _market_suffix(symbol: str) -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value.split(".", 1)[1]
    if value.startswith(("SH", "SZ", "BJ")):
        return value[:2]
    if _plain_code(value).startswith(("6", "9")):
        return "SH"
    if _plain_code(value).startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _prefixed_code(symbol: str) -> str:
    suffix = _market_suffix(symbol).lower()
    return f"{suffix}{_plain_code(symbol)}"


def _eastmoney_secid(symbol: str) -> str:
    suffix = _market_suffix(symbol)
    market_id = "1" if suffix == "SH" else "0"
    return f"{market_id}.{_plain_code(symbol)}"
