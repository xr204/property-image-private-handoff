"""Typed FastAPI boundary for private property-management images."""

import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from property_media import InfraiError, PropertyImageRequest, PropertyMediaAgent


class ImageRequest(BaseModel):
    kind: Literal["maintenance_request", "tenant_document", "inspection_reminder"]
    property_name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=500)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    expires_seconds: int = Field(default=900, ge=60, le=86400)


class ImageResponse(BaseModel):
    object_key: str
    private_url: str
    expires_seconds: int


agent = PropertyMediaAgent(
    api_key=os.environ["INFRAI_API_KEY"], bucket=os.environ["INFRAI_STORAGE_BUCKET"]
)


app = FastAPI(title="Property image handoff")

@app.post("/property-images", response_model=ImageResponse)
def create_property_image(body: ImageRequest) -> ImageResponse:
    try:
        result = agent.create_private_image(
            PropertyImageRequest(
                kind=body.kind,
                property_name=body.property_name,
                subject=body.subject,
                request_id=body.request_id,
            ),
            expires_seconds=body.expires_seconds,
        )
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, **exc.detail}) from exc
    return ImageResponse(
        object_key=result.object_key,
        private_url=result.url,
        expires_seconds=result.expires_seconds,
    )
