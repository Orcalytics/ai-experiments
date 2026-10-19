"""Normalize the branch-specific taxonomy formats while preserving their values."""

import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def taxonomy_records(task, taxonomy):
    """Return one evidence record per industry/subcategory or event category."""
    if task == "industry":
        records = [dict(row) for row in taxonomy]
        for row in records:
            for key in ("Industry", "Sub-category", "Description"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError(f"Industry taxonomy record requires a nonempty {key}.")
    elif task == "event":
        records = [
            {"event_type": name, **details} for name, details in taxonomy["categories"].items()
        ]
        if any(not isinstance(row.get("description"), str) for row in records):
            raise ValueError("Every event category requires a description.")
    elif task in ("emotion", "sentiment"):
        records = []
        field = "Emotions" if task == "emotion" else "Sentiments"
        for industry in taxonomy:
            for sub in industry["Sub-categories"]:
                if not sub.get(field):
                    raise ValueError(f"Missing {field} definitions for {sub['Name']}.")
                records.append(
                    {
                        "Industry": industry["Industry"],
                        "Sub-category": sub["Name"],
                        "Description": sub.get("Description", ""),
                        field: sub[field],
                    }
                )
    else:
        raise ValueError(f"Unknown task: {task}")
    if not records:
        raise ValueError("The taxonomy is empty.")
    identities = [row["event_type"] if task == "event" else record_pair(row) for row in records]
    if len(set(identities)) != len(identities):
        raise ValueError("The taxonomy contains duplicate entries.")
    return records


def record_pair(row):
    return row["Industry"], row["Sub-category"]


def industry_input(value):
    """Accept classifier JSON or the CLI result envelope; deduplicate exact pairs."""
    if not isinstance(value, dict):
        raise ValueError("Industry input must be a JSON object.")
    obj = value.get("data", value)
    if not isinstance(obj, dict) or "shortlisted_industries" not in obj:
        raise ValueError("Industry input must contain shortlisted_industries.")
    if not isinstance(obj["shortlisted_industries"], list):
        raise ValueError("shortlisted_industries must be an array.")
    rows, seen = [], set()
    for row in obj["shortlisted_industries"]:
        if not isinstance(row, dict):
            raise ValueError("Each shortlisted industry must be an object.")
        pair = row.get("sector"), row.get("sub_category")
        if any(not isinstance(v, str) or not v.strip() for v in pair):
            raise ValueError("Each shortlisted industry needs sector and sub_category strings.")
        if pair not in seen:
            rows.append(dict(row))
            seen.add(pair)
    emergent = obj.get("emergent_industry_candidate")
    if emergent is not None and (
        not isinstance(emergent, dict)
        or any(not isinstance(emergent.get(k), str) for k in ("label", "rationale"))
    ):
        raise ValueError("An emergent industry needs label and rationale strings.")
    return {"shortlisted_industries": rows, "emergent_industry_candidate": emergent}
