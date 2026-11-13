import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class FetchError(RuntimeError):
    pass


def request(url, *, method="GET", data=None, headers=None, retries=2, timeout=40):
    if urlsplit(url).scheme != "https":
        raise FetchError("仅允许 HTTPS 请求")
    headers = {"User-Agent": "XMPL-WeeklyReport/1.0 (+editorial research)", **(headers or {})}
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    # Writes are deliberately not retried: the server may have committed the request.
    attempts = retries + 1 if method == "GET" else 1
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, data=data, headers=headers, method=method), timeout=timeout) as response:
                raw = response.read(15_000_001)
                if len(raw) > 15_000_000:
                    raise FetchError("响应超过15MB")
                return raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise FetchError(f"HTTP {error.code} ({urlsplit(url).hostname})") from None
        except (URLError, TimeoutError, OSError):
            if attempt + 1 == attempts:
                raise FetchError(f"网络请求失败 ({urlsplit(url).hostname})") from None
        time.sleep(2 ** attempt)


def api(url, **kwargs):
    return json.loads(request(url, **kwargs))

