from types import SimpleNamespace

import pytest

from property_media import PropertyImageRequest, PropertyMediaAgent, image_prompt


@pytest.mark.parametrize(
    ("kind", "decision"),
    [
        ("maintenance_request", "maintenance coordinator"),
        ("tenant_document", "document cover"),
        ("inspection_reminder", "checklist and calendar"),
    ],
)
def test_each_property_event_gets_its_operational_visual(kind: str, decision: str) -> None:
    request = PropertyImageRequest(kind, "Riverside Court", "Smoke alarm", "req-17")
    prompt = image_prompt(request)
    assert decision in prompt
    assert "Riverside Court" in prompt


def test_generated_bytes_are_stored_before_private_link_is_signed() -> None:
    calls: list[tuple] = []

    class Images:
        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            return SimpleNamespace(data=[SimpleNamespace(b64_json="encoded-png")])

    class Storage:
        def put_image(self, bucket, key, data_base64):
            calls.append(("put", bucket, key, data_base64))

        def presign_get(self, bucket, key, expires_seconds):
            calls.append(("presign", bucket, key, expires_seconds))
            return "https://signed.example/private"

    agent = object.__new__(PropertyMediaAgent)
    agent.bucket = "property-agent-media"
    agent._images = Images()
    agent._storage = Storage()
    result = agent.create_private_image(
        PropertyImageRequest("maintenance_request", "Riverside Court", "Leaking tap", "req-17"),
        expires_seconds=600,
    )

    assert [call[0] for call in calls] == ["generate", "put", "presign"]
    assert calls[1] == (
        "put",
        "property-agent-media",
        "maintenance_request/req-17.png",
        "encoded-png",
    )
    assert result.url == "https://signed.example/private"
    assert result.expires_seconds == 600
