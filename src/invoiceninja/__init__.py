"""InvoiceNinja v5 REST client.

Thin wrapper around the InvoiceNinja ``/api/v1`` endpoints using only
the standard library. All HTTP calls are blocking — wrap them in
``asyncio.to_thread`` when calling from async code.

Configuration (read from the environment, see ``.env.example``):

* ``INVOICE_NINJA_TOKEN`` — pre-issued API token from
  ``User → API Tokens`` in the InvoiceNinja UI. Strongly preferred.
* ``INVOICENINJA_BASE_URL`` — base URL the API is reachable at, e.g.
  ``http://localhost/``. No trailing slash.
* ``IN_USER_EMAIL`` / ``IN_PASSWORD`` — admin credentials. Only used
  as a fallback when ``INVOICE_NINJA_TOKEN`` is empty: the client logs
  in once via ``POST /api/v1/login`` and reuses the returned token.

The current implementation only covers the three use cases the
project needs today — list clients, create a client, and create an
invoice for an existing or newly-created client. The transport layer
(``_request``) is shared so adding more endpoints later is a small,
mechanical change: add a typed method, call ``_request`` with the path
and payload, and return the parsed ``data`` field.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

DEFAULT_TIMEOUT = float(os.getenv("INVOICENINJA_TIMEOUT", "30"))
DEFAULT_BASE_URL = "http://localhost/"


class InvoiceNinjaError(RuntimeError):
    """Raised when the API returns a non-2xx response or unparseable JSON."""


@dataclass
class InvoiceNinjaClient:
    """Client for the InvoiceNinja ``/api/v1`` REST API.

    Either ``token`` or both ``email`` and ``password`` must be
    provided. If both are present, ``token`` wins.
    """

    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    email: str | None = None
    password: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    # Cached token obtained by logging in. Populated on first request
    # when no static token was configured.
    _session_token: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url is required")
        self.base_url = self.base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must include http:// or https://")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.token is None and not (self.email and self.password):
            raise ValueError(
                "either token or (email and password) must be provided"
            )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _ensure_token(self) -> str:
        """Return a usable bearer token, logging in if necessary."""
        if self.token:
            return self.token
        if self._session_token:
            return self._session_token
        if not (self.email and self.password):
            raise InvoiceNinjaError(
                "no API token configured and no login credentials available"
            )
        payload = {"email": self.email, "password": self.password}
        # Use _request without auth extraction: login response is
        # {"data": [{"token": "..."}]} and we want the list, not the
        # first element unwrapped.
        body = self._request("POST", "login", json_body=payload, auth=False)
        if isinstance(body, dict):
            data = body.get("data")
        else:
            data = body
        try:
            token = data[0]["token"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvoiceNinjaError(
                f"login response missing token: {body!r}"
            ) from exc
        self._session_token = token
        return token

    @classmethod
    def from_env(cls) -> "InvoiceNinjaClient":
        """Build a client from environment variables.

        Resolution:

        * ``INVOICENINJA_BASE_URL`` (default ``http://localhost/``).
        * ``INVOICE_NINJA_TOKEN`` if set, otherwise login is attempted
          with ``IN_USER_EMAIL`` / ``IN_PASSWORD`` on first use.
        """
        return cls(
            base_url=os.getenv("INVOICENINJA_BASE_URL", DEFAULT_BASE_URL),
            token=os.getenv("INVOICE_NINJA_TOKEN") or None,
            email=os.getenv("IN_USER_EMAIL") or None,
            password=os.getenv("IN_PASSWORD") or None,
        )

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        auth: bool = True,
    ) -> dict | list:
        """Issue a request and return the parsed JSON body.

        All successful InvoiceNinja API responses share the shape
        ``{"data": <object|list>}``. The caller is responsible for
        picking the right key out of that payload.
        """
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        data_bytes: bytes | None = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data_bytes = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            headers["X-Api-Token"] = self._ensure_token()

        request = urllib.request.Request(
            url, data=data_bytes, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise InvoiceNinjaError(
                f"HTTP {exc.code} {exc.reason} for {method} {url}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise InvoiceNinjaError(
                f"connection failed for {method} {url}: {exc.reason}"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvoiceNinjaError(
                f"non-JSON response from {method} {url}: {raw[:200]!r}"
            ) from exc

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------

    def list_clients(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict]:
        """Return all clients, optionally filtered by ``search``.

        The API caps ``per_page`` (InvoiceNinja default is 100). When
        more results are needed, walk pages — this helper only returns
        the requested page to keep memory bounded. Use ``page=0`` to
        ask for a single page of all results.
        """
        params: dict[str, str | int] = {
            "page": page,
            "per_page": per_page,
        }
        if search:
            params["filter"] = search
        body = self._request("GET", "clients", params=params)
        return self._extract_list(body, "clients")

    def get_client(self, client_id: str | int) -> dict:
        """Fetch a single client by id (the ``idata`` field, not the DB id)."""
        body = self._request("GET", f"clients/{client_id}")
        return self._extract_object(body, "client")

    def create_client(
        self,
        *,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        address1: str | None = None,
        address2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country_id: str | int | None = None,
        contacts: list[dict] | None = None,
    ) -> dict:
        """Create a client and return the created record.

        ``contacts`` lets you attach one or more contact persons to the
        client in the same request — InvoiceNinja requires at least
        one contact, so when you don't pass any, a minimal one derived
        from ``name`` + ``email`` is added automatically.
        """
        if not name:
            raise ValueError("name is required")
        if contacts is None:
            first_contact: dict[str, str] = {"first_name": name}
            if email:
                first_contact["email"] = email
            if phone:
                first_contact["phone"] = phone
            contacts = [first_contact]

        payload: dict = {"name": name, "contacts": contacts}
        optional = {
            "phone": phone,
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country_id": country_id,
        }
        for key, value in optional.items():
            if value is not None:
                payload[key] = value
        body = self._request("POST", "clients", json_body=payload)
        return self._extract_object(body, "client")

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def create_invoice(
        self,
        *,
        client_id: str | int,
        line_items: list[dict],
        number: str | None = None,
        date: str | None = None,
        due_date: str | None = None,
        po_number: str | None = None,
        public_notes: str | None = None,
        private_notes: str | None = None,
    ) -> dict:
        """Create an invoice for an existing client.

        ``line_items`` is the only required payload beyond the client.
        Each item accepts at least ``product_key`` (free-text label),
        ``description``, ``quantity`` (numeric), ``cost`` (unit cost),
        and ``tax_rate1`` (percentage, e.g. 10 for 10%). See the
        InvoiceNinja docs for the full set.
        """
        if not line_items:
            raise ValueError("at least one line item is required")

        payload: dict = {
            "client_id": str(client_id),
            "line_items": line_items,
        }
        optional = {
            "number": number,
            "date": date,
            "due_date": due_date,
            "po_number": po_number,
            "public_notes": public_notes,
            "private_notes": private_notes,
        }
        for key, value in optional.items():
            if value is not None:
                payload[key] = value

        body = self._request("POST", "invoices", json_body=payload)
        return self._extract_object(body, "invoice")

    def list_invoices(
        self,
        *,
        client_id: str | int | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict]:
        """Return invoices, optionally filtered by ``client_id``."""
        params: dict[str, str | int] = {"page": page, "per_page": per_page}
        if client_id is not None:
            params["client_id"] = str(client_id)
        body = self._request("GET", "invoices", params=params)
        return self._extract_list(body, "invoices")

    def get_invoice(self, invoice_id: str | int) -> dict:
        """Fetch a single invoice by id."""
        body = self._request("GET", f"invoices/{invoice_id}")
        return self._extract_object(body, "invoice")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_object(body: dict | list, what: str) -> dict:
        """Pull a single object out of a response ``{"data": ...}``.

        The API sometimes returns the object directly, sometimes inside
        ``{"data": {...}}`` or ``{"data": [{...}]}``. Tolerate all
        three; raise if we can't find anything useful.
        """
        if isinstance(body, dict):
            data = body.get("data")
        else:
            data = body

        if isinstance(data, list):
            if not data:
                raise InvoiceNinjaError(f"empty response, expected {what}")
            data = data[0]
        if not isinstance(data, dict):
            raise InvoiceNinjaError(
                f"unexpected response shape for {what}: {body!r}"
            )
        return data

    @staticmethod
    def _extract_list(body: dict | list, what: str) -> list[dict]:
        """Pull a list out of a response, tolerating a bare list body."""
        if isinstance(body, list):
            data = body
        elif isinstance(body, dict):
            data = body.get("data", [])
        else:
            data = []
        if not isinstance(data, list):
            raise InvoiceNinjaError(
                f"expected list for {what}, got {type(data).__name__}"
            )
        return data
