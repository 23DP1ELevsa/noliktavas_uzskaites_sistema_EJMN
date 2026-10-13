"""Fetch bounded JSON offers over HTTP, then use shared atomic persistence."""

from io import BytesIO
from http.client import HTTPException
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .json_import import read_json_offers
from .offer_import import MAX_FILE_BYTES, OfferImportError, save_imported_offers


DEFAULT_TIMEOUT = 5


class APIImportError(OfferImportError):
    pass


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch_api_offers(url, *, timeout=DEFAULT_TIMEOUT):
    """URL comes from server configuration, never from a submitted form."""
    try:
        parsed = urlsplit(url) if isinstance(url, str) else None
        valid = (parsed is not None and parsed.scheme in {"http", "https"} and parsed.hostname
                 and not parsed.username and not parsed.password and not parsed.fragment
                 and not any(char.isspace() or ord(char) < 32 for char in url)
                 and (parsed.port is None or 1 <= parsed.port <= 65535))
    except ValueError:
        valid = False
    if not valid:
        raise APIImportError("TEST_API_URL jābūt pilnai HTTP vai HTTPS adresei bez lietotājvārda un paroles.")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise APIImportError("API gaidīšanas laikam jābūt no 0 līdz 30 sekundēm (neieskaitot 0).")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "StockFlow/1.0"}, method="GET")
    # Keep requests direct; redirects must not silently change the configured source.
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise APIImportError(f"API atgrieza HTTP statusu {response.status}; nepieciešams 200.")
            content_type = response.headers.get_content_type()
            if content_type != "application/json" and not (
                    content_type.startswith("application/") and content_type.endswith("+json")):
                raise APIImportError("API atbilde nav JSON (Content-Type).")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise APIImportError("API atbildes saspiešanas formāts nav atbalstīts.")
            body = response.read(MAX_FILE_BYTES + 1)
    except HTTPError as error:
        error.close()
        raise APIImportError(f"API atgrieza HTTP statusu {error.code}; nepieciešams 200. Pāradresācijas netiek pieņemtas.") from error
    except (TimeoutError, socket.timeout) as error:
        raise APIImportError("API atbildes gaidīšanas laiks ir pārsniegts. Mēģiniet vēlreiz.") from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise APIImportError("API atbildes gaidīšanas laiks ir pārsniegts. Mēģiniet vēlreiz.") from error
        raise APIImportError("Neizdevās savienoties ar API. Pārbaudiet adresi un API pieejamību.") from error
    except (OSError, ValueError, HTTPException) as error:
        if isinstance(error, APIImportError):
            raise
        raise APIImportError("API atbildi neizdevās saņemt pilnībā. Mēģiniet vēlreiz.") from error
    try:
        return read_json_offers(BytesIO(body))
    except OfferImportError as error:
        prefix = f"Rinda {error.row}: " if error.row is not None else ""
        raise APIImportError("API atbildes dati nav derīgi: " + str(error).removeprefix(prefix),
                             row=error.row, field=error.field) from error


def import_api_offers(url, *, admin_id, timeout=DEFAULT_TIMEOUT):
    records = fetch_api_offers(url, timeout=timeout)
    return save_imported_offers(records, source="API", admin_id=admin_id)
