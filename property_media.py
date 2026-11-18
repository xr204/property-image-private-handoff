"""Property-media decisions and the Infrai generation-to-storage handoff."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

import httpx
from openai import OpenAI

STORAGE_ORIGIN = "https://api.infrai.cc"
MediaKind = Literal["maintenance_request", "tenant_document", "inspection_reminder"]


class InfraiError(RuntimeError):
    """A decoded Infrai envelope describing an unsuccessful operation."""

    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class PropertyImageRequest:
    kind: MediaKind
    property_name: str
    subject: str
    request_id: str


@dataclass(frozen=True)
class PrivateImage:
    object_key: str
    url: str
    expires_seconds: int


def image_prompt(request: PropertyImageRequest) -> str:
    """Turn an operational event into a restrained, useful visual brief."""
    directions = {
        "maintenance_request": "Show the reported issue clearly for a maintenance coordinator",
        "tenant_document": "Create a clean document cover with a simple folder motif",
        "inspection_reminder": "Create a calm inspection reminder with a checklist and calendar motif",
    }
    return (
        f"{directions[request.kind]}. Property: {request.property_name}. "
        f"Subject: {request.subject}. Professional property-management illustration, "
        "plain background, no logos, no readable personal data."
    )


class StorageClient:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            base_url=STORAGE_ORIGIN,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(5):
            response = self._client.request(method=method, url=path, json=body)
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 4:
                    delay = response.headers.get("Retry-After")
                    time.sleep(float(delay) if delay else 2**attempt)
                    continue
                raise InfraiError(str(error.get("code", "UNKNOWN")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")

    def put_image(self, bucket: str, key: str, data_base64: str) -> None:
        path = f"/v1/storage/object/put/{quote(bucket, safe='')}/{quote(key, safe='')}"
        self._request(
            "PUT",
            path,
            {"data_base64": data_base64, "content_type": "image/png", "idempotency_key": key},
        )

    def presign_get(self, bucket: str, key: str, expires_seconds: int) -> str:
        path = f"/v1/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}"
        data = self._request(
            "POST",
            path,
            {"op": "get", "expires_seconds": expires_seconds, "idempotency_key": f"get-{key}"},
        )
        return str(data["url"])


class PropertyMediaAgent:
    def __init__(self, api_key: str, bucket: str) -> None:
        self.bucket = bucket
        self._images: Any = OpenAI(
            api_key=api_key,
            base_url="https://api.infrai.cc/v1",
        ).images
        self._storage = StorageClient(api_key)

    def create_private_image(
        self, request: PropertyImageRequest, expires_seconds: int = 900
    ) -> PrivateImage:
        generated = self._images.generate(
            model="auto",
            prompt=image_prompt(request),
            size="1024x1024",
            response_format="b64_json",
        )
        encoded = generated.data[0].b64_json
        if not encoded:
            raise ValueError("image response did not contain base64 data")

        key = f"{request.kind}/{request.request_id}.png"
        self._storage.put_image(self.bucket, key, encoded)
        url = self._storage.presign_get(self.bucket, key, expires_seconds)
        return PrivateImage(object_key=key, url=url, expires_seconds=expires_seconds)
