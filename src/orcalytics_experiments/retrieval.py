"""Explicit store setup and retrieval with stable taxonomy metadata."""

import json

from .taxonomy import record_pair, taxonomy_records


def prepare_store(client, task, taxonomy, name=None):
    """Create a new store explicitly; each node becomes a searchable UTF-8 text file.

    The returned ID must be reused for classification. This function never deletes
    stores or files. If an upload fails, the error identifies the store to inspect.
    """
    if task not in ("industry", "event"):
        raise ValueError("Only industry and event taxonomies need vector stores.")
    records = taxonomy_records(task, taxonomy)
    store = client.vector_stores.create(name=name or f"Orcalytics {task} taxonomy")
    manifest = {"vector_store_id": store.id, "task": task, "files": []}
    for index, row in enumerate(records, 1):
        attributes = {"taxonomy": task}
        if task == "industry":
            attributes.update(industry=row["Industry"], sub_category=row["Sub-category"])
        else:
            attributes["event_type"] = row["event_type"]
        payload = json.dumps(row, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            uploaded = client.files.create(
                file=(f"{task}_{index:03d}.txt", payload, "text/plain"), purpose="assistants"
            )
            attached = client.vector_stores.files.create_and_poll(
                vector_store_id=store.id, file_id=uploaded.id, attributes=attributes
            )
            if attached.status != "completed":
                raise RuntimeError(f"File {uploaded.id} indexing status: {attached.status}")
            manifest["files"].append({"file_id": uploaded.id, "attributes": attributes})
        except Exception as exc:
            raise RuntimeError(
                f"Indexing failed in store {store.id} after {len(manifest['files'])} files. "
                "Inspect the store before retrying; it was not deleted."
            ) from exc
    return manifest


def retrieve_records(client, vector_store_id, article, records, task, max_results=20):
    """Map ranked search hits to complete local records instead of parsing JSON chunks."""
    lookup = {row["event_type"] if task == "event" else record_pair(row): row for row in records}
    hits = client.vector_stores.search(
        vector_store_id=vector_store_id,
        query=article,
        max_num_results=max_results,
        filters={"type": "eq", "key": "taxonomy", "value": task},
    )
    selected, evidence, seen = [], [], set()
    for hit in sorted(hits.data, key=lambda item: item.score, reverse=True):
        attrs = hit.attributes or {}
        key = (
            attrs.get("event_type")
            if task == "event"
            else (attrs.get("industry"), attrs.get("sub_category"))
        )
        if key not in lookup or key in seen:
            continue
        seen.add(key)
        selected.append(lookup[key])
        evidence.append(
            {
                "file_id": hit.file_id,
                "score": hit.score,
                "attributes": attrs,
                "text": "\n".join(part.text for part in hit.content if part.type == "text"),
            }
        )
    if not selected:
        raise ValueError(
            "No search hits matched this taxonomy. Use a store created with prepare-store "
            "for the same taxonomy; old notebook stores lack the required metadata."
        )
    return selected, evidence
