import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import OpenAI

from orcalytics_experiments.experiments import run_experiment
from orcalytics_experiments.retrieval import prepare_store


def test_store_and_classification_with_real_sdk_and_offline_http_transport():
    """Exercise serialization, polling, metadata, search, and response parsing offline."""
    row = {
        "Industry": "Technology",
        "Sub-category": "Software",
        "Description": "Software services.",
    }
    expected = {
        "shortlisted_industries": [
            {
                "sector": "Technology",
                "sub_category": "Software",
                "relevance": "HIGH",
                "reason": "Central topic.",
            }
        ],
        "emergent_industry_candidate": None,
    }
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/v1/vector_stores":
            payload = {
                "id": "vs_mock",
                "object": "vector_store",
                "status": "completed",
                "created_at": 0,
            }
        elif path == "/v1/files":
            assert b"industry_001.txt" in request.content
            payload = {
                "id": "file_mock",
                "object": "file",
                "bytes": 20,
                "created_at": 0,
                "filename": "industry_001.txt",
                "purpose": "assistants",
            }
        elif path in (
            "/v1/vector_stores/vs_mock/files",
            "/v1/vector_stores/vs_mock/files/file_mock",
        ):
            if request.method == "POST":
                assert json.loads(request.content)["attributes"]["industry"] == "Technology"
            payload = {
                "id": "file_mock",
                "object": "vector_store.file",
                "status": "completed",
                "created_at": 0,
                "vector_store_id": "vs_mock",
                "usage_bytes": 20,
            }
        elif path == "/v1/vector_stores/vs_mock/search":
            assert json.loads(request.content)["filters"]["value"] == "industry"
            payload = {
                "object": "vector_store.search_results.page",
                "data": [
                    {
                        "file_id": "file_mock",
                        "filename": "industry_001.txt",
                        "score": 0.9,
                        "attributes": {
                            "taxonomy": "industry",
                            "industry": "Technology",
                            "sub_category": "Software",
                        },
                        "content": [{"type": "text", "text": "A partial chunk, not JSON."}],
                    }
                ],
                "has_more": False,
                "next_page": None,
                "search_query": ["Software demand grew."],
            }
        elif path == "/v1/responses":
            request_json = json.loads(request.content)
            assert request_json["text"]["format"]["strict"] is True
            payload = {
                "id": "resp_mock",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-5.1",
                "output": [
                    {
                        "id": "msg_mock",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": json.dumps(expected), "annotations": []}
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            }
        else:
            raise AssertionError(f"Unexpected request: {request.method} {path}")
        return httpx.Response(200, json=payload)

    with OpenAI(
        api_key="offline-test-placeholder",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        manifest = prepare_store(client, "industry", [row])
        result = run_experiment(
            client,
            "industry",
            "Software demand grew.",
            [row],
            vector_store_id=manifest["vector_store_id"],
        )
    assert result["data"] == expected
    assert result["usage"]["total_tokens"] == 30
    assert ("GET", "/v1/vector_stores/vs_mock/files/file_mock") in calls
    assert all(method != "DELETE" for method, _ in calls)


def test_partial_store_failure_reports_id_without_deleting_anything():
    store_files = SimpleNamespace(
        create_and_poll=Mock(return_value=SimpleNamespace(status="failed"))
    )
    client = SimpleNamespace(
        vector_stores=SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="vs_partial")), files=store_files
        ),
        files=SimpleNamespace(create=Mock(return_value=SimpleNamespace(id="file_partial"))),
    )
    taxonomy = [
        {"Industry": "Industry", "Sub-category": "Subcategory", "Description": "Description."}
    ]
    with pytest.raises(RuntimeError, match="vs_partial after 0 files"):
        prepare_store(client, "industry", taxonomy)
