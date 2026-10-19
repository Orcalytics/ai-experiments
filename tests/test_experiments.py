import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from orcalytics_experiments.experiments import output_schema, run_experiment
from orcalytics_experiments.taxonomy import taxonomy_records


def industry_result(row):
    return {
        "shortlisted_industries": [
            {
                "sector": row["Industry"],
                "sub_category": row["Sub-category"],
                "relevance": "HIGH",
                "reason": "Central subject in the article.",
            }
        ],
        "emergent_industry_candidate": None,
    }


def test_explicit_retrieval_preserves_definitions_and_handles_non_json_chunks(
    read_data, client_factory
):
    taxonomy = read_data("taxonomies/industries.json")
    row = taxonomy[0]
    client = client_factory(industry_result(row), [row, row])
    result = run_experiment(
        client,
        "industry",
        "A business article.",
        taxonomy,
        vector_store_id="vs_industry",
        model="test-model",
    )
    payload = client.responses.create.call_args.kwargs
    supplied = json.loads(payload["input"][1]["content"])["taxonomy_evidence"]
    assert supplied == [row]  # Duplicate chunks become one complete definition.
    assert result["model"] == "test-model"
    assert result["retrieval"][0]["text"] == "A non-JSON search chunk."
    assert result["usage"]["input_tokens"] == 100


def test_file_search_is_forced_and_has_same_output_contract(read_data, client_factory):
    taxonomy = read_data("taxonomies/industries.json")
    client = client_factory(industry_result(taxonomy[0]))
    result = run_experiment(
        client,
        "industry",
        "An article.",
        taxonomy,
        strategy="file-search",
        vector_store_id="vs_test",
    )
    payload = client.responses.create.call_args.kwargs
    assert payload["tools"][0]["vector_store_ids"] == ["vs_test"]
    assert payload["tool_choice"] == "required"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["text"]["format"]["strict"] is True
    assert result["data"]["shortlisted_industries"]
    client.vector_stores.search.assert_not_called()


@pytest.mark.parametrize(
    "failure", ["unknown_pair", "duplicate", "invalid_json", "incomplete", "refusal"]
)
def test_invalid_model_responses_are_not_accepted(failure, read_data, client_factory):
    taxonomy = read_data("taxonomies/industries.json")
    data = industry_result(taxonomy[0])
    client = client_factory(data, [taxonomy[0]])
    response = client.responses.create.return_value
    if failure == "unknown_pair":
        data["shortlisted_industries"][0]["sector"] = "Invented industry"
        response.output_text = json.dumps(data)
    elif failure == "duplicate":
        data["shortlisted_industries"] *= 2
        response.output_text = json.dumps(data)
    elif failure == "invalid_json":
        response.output_text = "Not JSON"
    elif failure == "incomplete":
        response.status = "incomplete"
    else:
        response.output = [SimpleNamespace(content=[SimpleNamespace(type="refusal")])]
    with pytest.raises(ValueError):
        run_experiment(client, "industry", "An article.", taxonomy, vector_store_id="vs_test")


def event_case():
    context = {
        "shortlisted_industries": [{"sector": "Technology", "sub_category": "Software"}],
        "emergent_industry_candidate": None,
    }
    data = deepcopy(context)
    data["shortlisted_industries"][0].update(
        events=[
            {
                "event_type": "Earnings",
                "event_sentiment": "Positive",
                "event_significance": 0.6,
                "market_reaction_likelihood": 70,
                "confidence": 0.9,
                "evidence": "Revenue increased.",
            }
        ],
        event_frequency=1,
    )
    return context, data


def test_event_receives_same_article_industries_and_checks_quotes(read_data, client_factory):
    context, data = event_case()
    taxonomy = read_data("taxonomies/events.json")
    records = taxonomy_records("event", taxonomy)
    client = client_factory(data, records, "event")
    result = run_experiment(
        client,
        "event",
        "Revenue increased.",
        taxonomy,
        industries={"data": context},
        vector_store_id="vs_event",
    )
    assert result["data"] == data
    payload = json.loads(client.responses.create.call_args.kwargs["input"][1]["content"])
    assert payload["industries"] == context


@pytest.mark.parametrize(
    "failure", ["scale", "quote", "frequency", "unknown_event", "missing_row", "confidence"]
)
def test_event_contract_rejects_legacy_failure_modes(failure, read_data, client_factory):
    context, data = event_case()
    event = data["shortlisted_industries"][0]["events"][0]
    if failure == "scale":
        event["event_significance"] = 8
    elif failure == "quote":
        event["evidence"] = "An invented quote."
    elif failure == "frequency":
        data["shortlisted_industries"][0]["event_frequency"] = 0
    elif failure == "unknown_event":
        event["event_type"] = "Made up"
    elif failure == "missing_row":
        data["shortlisted_industries"] = []
    else:
        event["confidence"] = 0.2
    taxonomy = read_data("taxonomies/events.json")
    client = client_factory(data, taxonomy_records("event", taxonomy), "event")
    with pytest.raises((ValueError, ValidationError)):
        run_experiment(
            client,
            "event",
            "Revenue increased.",
            taxonomy,
            industries=context,
            vector_store_id="vs_event",
        )


def test_emotions_follow_real_taxonomy_and_receive_complete_descriptors(read_data, client_factory):
    taxonomy = read_data("taxonomies/emotions_healthcare.json")
    row = taxonomy_records("emotion", taxonomy)[0]
    emotion = row["Emotions"][1]  # Concern: absent from the old hard-coded six-label enum.
    data = {
        "shortlisted_emotions": [
            {
                "industry": row["Industry"],
                "sub_category": row["Sub-category"],
                "emotion_label": emotion["Name"],
                "intensity": emotion["Intensity"],
                "direction": emotion["Direction"],
                "confidence": emotion["Confidence"],
                "relevance": "HIGH",
                "reason": "The article expresses concern.",
            }
        ],
        "emergent_emotion_candidate": None,
    }
    client = client_factory(data)
    result = run_experiment(
        client, "emotion", "Concern about future claims.", taxonomy, industries=industry_result(row)
    )
    assert result["strategy"] == "industry-input"
    payload = client.responses.create.call_args.kwargs
    assert json.loads(payload["input"][1]["content"])["taxonomy_evidence"] == [row]
    labels = payload["text"]["format"]["schema"]["properties"]["shortlisted_emotions"]["items"][
        "properties"
    ]["emotion_label"]["enum"]
    assert "Concern" in labels and "Greed" not in labels
    client.vector_stores.search.assert_not_called()


def test_sentiment_copies_taxonomy_fields_but_writes_article_explanation(read_data, client_factory):
    taxonomy = read_data("taxonomies/sentiments_healthcare.json")
    row = taxonomy_records("sentiment", taxonomy)[0]
    sentiment = {k: v for k, v in row["Sentiments"][0].items() if k != "Examples"}
    sentiment["Explanation"] = "Article-specific explanation."
    data = {
        "shortlisted_sentiments": [
            {
                "industry": row["Industry"],
                "sub_category": row["Sub-category"],
                "reason": "Positive outlook.",
                "Sentiments": [sentiment],
            }
        ]
    }
    client = client_factory(data)
    result = run_experiment(
        client, "sentiment", "Positive payer outlook.", taxonomy, industries=industry_result(row)
    )
    assert result["data"] == data
    assert isinstance(
        result["data"]["shortlisted_sentiments"][0]["Sentiments"][0]["Typical Investor Action"], str
    )
    sentiment["Mood"] = "Invented mood"
    client.responses.create.return_value.output_text = json.dumps(data)
    with pytest.raises(ValueError, match="descriptors"):
        run_experiment(
            client,
            "sentiment",
            "Positive payer outlook.",
            taxonomy,
            industries=industry_result(row),
        )


@pytest.mark.parametrize("task", ["emotion", "sentiment"])
def test_affect_can_use_original_industry_store_path(task, read_data, client_factory):
    taxonomy = read_data(
        f"taxonomies/{'emotions' if task == 'emotion' else 'sentiments'}_healthcare.json"
    )
    records = taxonomy_records(task, taxonomy)
    data = (
        {"shortlisted_emotions": [], "emergent_emotion_candidate": None}
        if task == "emotion"
        else {"shortlisted_sentiments": []}
    )
    client = client_factory(data, records)
    result = run_experiment(client, task, "An article.", taxonomy, vector_store_id="vs_industry")
    assert result["strategy"] == "vector"
    assert client.vector_stores.search.call_args.kwargs["filters"]["value"] == "industry"


def test_unsupported_pairs_and_empty_event_input_do_not_make_calls(read_data):
    context = {
        "shortlisted_industries": [{"sector": "Unknown", "sub_category": "Missing"}],
        "emergent_industry_candidate": None,
    }
    result = run_experiment(
        None,
        "emotion",
        "An article.",
        read_data("taxonomies/emotions_healthcare.json"),
        industries=context,
    )
    assert result["unsupported_industries"] == [["Unknown", "Missing"]]
    assert result["response_id"] is None
    context["shortlisted_industries"] = []
    result = run_experiment(
        None, "event", "An article.", read_data("taxonomies/events.json"), industries=context
    )
    assert result["data"]["shortlisted_industries"] == []


def test_unconfigured_or_legacy_store_fails_clearly(read_data, client_factory):
    taxonomy = read_data("taxonomies/industries.json")
    client = client_factory({})
    with pytest.raises(ValueError, match="vector_store_id"):
        run_experiment(client, "industry", "An article.", taxonomy)
    with pytest.raises(ValueError, match="prepare-store"):
        run_experiment(client, "industry", "An article.", taxonomy, vector_store_id="vs_legacy")
    client.responses.create.assert_not_called()


@pytest.mark.parametrize("task", ["industry", "event", "emotion", "sentiment"])
def test_all_output_schemas_are_valid(task, read_data):
    from jsonschema import Draft202012Validator

    names = {
        "industry": "industries",
        "event": "events",
        "emotion": "emotions_healthcare",
        "sentiment": "sentiments_healthcare",
    }
    records = taxonomy_records(task, read_data(f"taxonomies/{names[task]}.json"))
    Draft202012Validator.check_schema(output_schema(task, records))
