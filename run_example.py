"""Run one inspection-reminder handoff without starting the HTTP service."""

import json
import os
import uuid
from dataclasses import asdict

from property_media import PropertyImageRequest, PropertyMediaAgent


def main() -> None:
    agent = PropertyMediaAgent(
        api_key=os.environ["INFRAI_API_KEY"], bucket=os.environ["INFRAI_STORAGE_BUCKET"]
    )
    result = agent.create_private_image(
        PropertyImageRequest(
            kind="inspection_reminder",
            property_name="Riverside Court",
            subject="Annual smoke-alarm inspection on Tuesday",
            request_id=f"inspection-{uuid.uuid4().hex}",
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
