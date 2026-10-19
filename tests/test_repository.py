import ast
from pathlib import Path

import nbformat
import pytest

from orcalytics_experiments.config import default_model
from orcalytics_experiments.taxonomy import industry_input, load_json, taxonomy_records

ROOT = Path(__file__).resolve().parents[1]


def test_taxonomy_coverage_and_legacy_sample_pairs():
    rows = taxonomy_records("industry", load_json(ROOT / "data/taxonomies/industries.json"))
    assert len(rows) == 138
    assert len({r["Industry"] for r in rows}) == 21
    events = load_json(ROOT / "data/taxonomies/events.json")
    assert len(taxonomy_records("event", events)) == 11
    for index in range(1, 7):
        assert (ROOT / f"data/samples/events/{index:02d}_article.txt").read_text().strip()
        inputs = industry_input(
            load_json(ROOT / f"data/samples/events/{index:02d}_industries.json")
        )
        assert inputs["shortlisted_industries"]


def test_notebooks_have_valid_paths_syntax_and_no_saved_outputs():
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))
    assert len(notebooks) == 5
    for path in notebooks:
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            assert cell.outputs == [] and cell.execution_count is None
            tree = ast.parse(cell.source)
            assert "/content/" not in cell.source and "vs_" not in cell.source
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value.startswith("data/")
                ):
                    assert (ROOT / node.value).is_file(), node.value


def test_original_model_defaults_and_explicit_environment_override(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert default_model("industry") == "gpt-5.1"
    assert default_model("industry", "file-search") == "gpt-5-mini"
    assert default_model("sentiment") == "gpt-5-mini"
    monkeypatch.setenv("OPENAI_MODEL", "selected-model")
    assert default_model("industry") == "selected-model"


@pytest.mark.parametrize(
    "bad_input", [[], {}, {"shortlisted_industries": {}}, {"shortlisted_industries": ["bad"]}]
)
def test_industry_input_rejects_invalid_shapes(bad_input):
    with pytest.raises(ValueError):
        industry_input(bad_input)


def test_industry_input_accepts_envelopes_and_deduplicates():
    row = {"sector": "Industry", "sub_category": "Subcategory"}
    result = industry_input({"data": {"shortlisted_industries": [row, row]}})
    assert result == {"shortlisted_industries": [row], "emergent_industry_candidate": None}
