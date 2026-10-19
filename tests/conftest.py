import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def read_data():
    def read(relative):
        return json.loads((ROOT / "data" / relative).read_text())

    return read


@pytest.fixture
def client_factory():
    def make(data, records=(), task="industry", *, status="completed", output=None):
        hits = []
        for row in records:
            attrs = {"taxonomy": task}
            if task == "event":
                attrs["event_type"] = row["event_type"]
            else:
                attrs.update(industry=row["Industry"], sub_category=row["Sub-category"])
            hits.append(
                SimpleNamespace(
                    attributes=attrs,
                    score=0.9,
                    file_id="file_test",
                    content=[SimpleNamespace(type="text", text="A non-JSON search chunk.")],
                )
            )
        response = SimpleNamespace(
            id="resp_test",
            status=status,
            output=output or [],
            output_text=json.dumps(data),
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 100, "output_tokens": 20}),
        )
        return SimpleNamespace(
            vector_stores=SimpleNamespace(search=Mock(return_value=SimpleNamespace(data=hits))),
            responses=SimpleNamespace(create=Mock(return_value=response)),
        )

    return make
