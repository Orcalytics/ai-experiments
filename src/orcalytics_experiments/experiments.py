"""Run the four experiment types through one validated Responses API boundary."""

import json
from importlib.resources import files

from jsonschema import Draft202012Validator

from .config import default_model
from .retrieval import retrieve_records
from .taxonomy import industry_input, record_pair, taxonomy_records

TASKS = ("industry", "event", "emotion", "sentiment")


def resource_text(folder, name):
    return files("orcalytics_experiments").joinpath("resources", folder, name).read_text("utf-8")


def output_schema(task, records):
    """Constrain labels to the actual supplied taxonomy, including healthcare emotions."""
    schema = json.loads(resource_text("schemas", f"{task}.json"))
    if task == "emotion":
        labels = sorted({emotion["Name"] for row in records for emotion in row["Emotions"]})
        schema["properties"]["shortlisted_emotions"]["items"]["properties"]["emotion_label"][
            "enum"
        ] = labels
    if task == "event":
        labels = [row["event_type"] for row in records]
        row = schema["properties"]["shortlisted_industries"]["items"]
        row["properties"]["events"]["items"]["properties"]["event_type"]["enum"] = labels
        emergent = schema["properties"]["emergent_industry_candidate"]["anyOf"][0]
        emergent["properties"]["event_type"]["enum"] = labels
    return schema


def parse_response(response, schema):
    if response.status != "completed":
        raise ValueError(f"Response {response.id} was {response.status}; no result accepted.")
    for item in response.output:
        for block in getattr(item, "content", []) or []:
            if getattr(block, "type", None) == "refusal":
                raise ValueError("The model refused this request; no classification was returned.")
    if not response.output_text:
        raise ValueError("The model returned no output text.")
    result = json.loads(response.output_text)
    Draft202012Validator(schema).validate(result)
    return result


def validate_grounding(task, result, records, article, industries=None):
    """Check taxonomy membership and event evidence beyond structural JSON validity."""
    if task == "event":
        expected = {(r["sector"], r["sub_category"]) for r in industries["shortlisted_industries"]}
        rows = result["shortlisted_industries"]
        actual = [(r["sector"], r["sub_category"]) for r in rows]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise ValueError("Event output must cover each supplied industry exactly once.")
        events = []
        for row in rows:
            if row["event_frequency"] != len(row["events"]):
                raise ValueError("event_frequency must equal the length of events (zero or one).")
            events.extend(row["events"])
        emergent = result["emergent_industry_candidate"]
        if emergent:
            supplied = industries["emergent_industry_candidate"]
            if not supplied or emergent["label"] != supplied["label"]:
                raise ValueError("The event stage cannot invent an emergent industry.")
            events.append(emergent)
        for event in events:
            if not event["evidence"].strip() or event["evidence"] not in article:
                raise ValueError("Event evidence must be a nonempty exact quote from the article.")
            if event["confidence"] < 0.4:
                raise ValueError(
                    "Events below the prompt's 0.4 confidence threshold must be omitted."
                )
        return
    lookup = {record_pair(row): row for row in records}
    key = {
        "industry": "shortlisted_industries",
        "emotion": "shortlisted_emotions",
        "sentiment": "shortlisted_sentiments",
    }[task]
    seen = set()
    for row in result[key]:
        pair = (row["sector"] if task == "industry" else row["industry"], row["sub_category"])
        if pair not in lookup:
            raise ValueError(
                f"Output industry/subcategory is outside the supplied evidence: {pair}"
            )
        identity = (*pair, row["emotion_label"]) if task == "emotion" else pair
        if identity in seen:
            raise ValueError(f"Duplicate classification: {identity}")
        seen.add(identity)
        if task == "emotion":
            definitions = {e["Name"]: e for e in lookup[pair]["Emotions"]}
            definition = definitions.get(row["emotion_label"])
            if definition is None or any(
                row[out] != definition[source]
                for out, source in [
                    ("intensity", "Intensity"),
                    ("direction", "Direction"),
                    ("confidence", "Confidence"),
                ]
            ):
                raise ValueError("Emotion descriptors must match the supplied taxonomy definition.")
        if task == "sentiment":
            definitions = {s["Type"]: s for s in lookup[pair]["Sentiments"]}
            selected = row["Sentiments"][0]
            definition = definitions.get(selected["Type"])
            if definition is None or any(
                selected[field] != definition[field]
                for field in selected
                if field not in ("Type", "Explanation")
            ):
                raise ValueError(
                    "Sentiment descriptors must match the supplied taxonomy definition."
                )


def run_experiment(
    client,
    task,
    article,
    taxonomy,
    *,
    vector_store_id=None,
    industries=None,
    model=None,
    strategy="vector",
    max_results=20,
):
    """Return classification JSON, usage, and provenance without writing any files.

    Industry/event tasks use a store. Emotion/sentiment accept either an explicit
    industry result or the industry store used by the original RAG notebooks.
    """
    if task not in TASKS:
        raise ValueError(f"Choose a task from {TASKS}.")
    if not article.strip():
        raise ValueError("The article is empty.")
    if strategy not in ("vector", "file-search"):
        raise ValueError("strategy must be vector or file-search.")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50.")
    if task in ("emotion", "sentiment") and strategy != "vector":
        raise ValueError("file-search is supported only for industry and event experiments.")
    if task == "industry" and industries is not None:
        raise ValueError("The industry experiment classifies the article directly.")
    context = industry_input(industries) if industries is not None else None
    if task == "event" and context is None:
        raise ValueError("The event experiment requires the industry classifier's JSON output.")
    records = taxonomy_records(task, taxonomy)
    evidence, unsupported = [], []
    empty_event = (
        task == "event"
        and not context["shortlisted_industries"]
        and not context["emergent_industry_candidate"]
    )
    if task in ("emotion", "sentiment") and context is not None:
        pairs = {(r["sector"], r["sub_category"]) for r in context["shortlisted_industries"]}
        supported = {record_pair(row) for row in records}
        unsupported = [list(pair) for pair in sorted(pairs - supported)]
        records = [row for row in records if record_pair(row) in pairs]
    elif not empty_event:
        if not vector_store_id:
            raise ValueError(
                "A vector_store_id is required; run prepare-store once and reuse its ID."
            )
        if strategy == "vector":
            lookup_task = "industry" if task in ("emotion", "sentiment") else task
            records, evidence = retrieve_records(
                client, vector_store_id, article, records, lookup_task, max_results
            )
    model = model or default_model(task, strategy)
    envelope = {
        "task": task,
        "model": model,
        "strategy": "industry-input" if task in ("emotion", "sentiment") and context else strategy,
        "vector_store_id": vector_store_id,
        "retrieval": evidence,
        "unsupported_industries": unsupported,
        "response_id": None,
        "usage": None,
    }
    # An explicitly empty shortlist is a valid downstream input, not a reason to invent data.
    if not records or empty_event:
        empty = {
            "industry": {"shortlisted_industries": [], "emergent_industry_candidate": None},
            "event": {"shortlisted_industries": [], "emergent_industry_candidate": None},
            "emotion": {"shortlisted_emotions": [], "emergent_emotion_candidate": None},
            "sentiment": {"shortlisted_sentiments": []},
        }
        return {**envelope, "data": empty[task]}
    schema = output_schema(task, records)
    user_input = {"article": article, "industries": context}
    if strategy == "vector":
        user_input["taxonomy_evidence"] = records
    request = {
        "model": model,
        "input": [
            {"role": "system", "content": resource_text("prompts", f"{task}.txt")},
            {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": f"{task}_classification",
                "schema": schema,
                "strict": True,
            }
        },
    }
    # Preserve the explicit reasoning setting used by the original file-search experiments.
    if model == "gpt-5-mini" and (
        task == "event" or (task == "industry" and strategy == "file-search")
    ):
        request["reasoning"] = {"effort": "high"}
    if strategy == "file-search":
        request.update(
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                    "max_num_results": max_results,
                }
            ],
            tool_choice="required",
            include=["file_search_call.results"],
        )
    response = client.responses.create(**request)
    result = parse_response(response, schema)
    validate_grounding(task, result, records, article, context)
    if strategy == "file-search":
        envelope["retrieval"] = [
            item.model_dump() for item in response.output if item.type == "file_search_call"
        ]
    return {
        **envelope,
        "data": result,
        "response_id": response.id,
        "usage": response.usage.model_dump() if response.usage else None,
    }
