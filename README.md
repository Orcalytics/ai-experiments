# Orcalytics AI Experiments

Orcalytics explores how business news can be transformed into structured market
intelligence. The project combines a cloud data analysis workflow with LLM
experiments for industry classification, event extraction, emotion detection, and
industry-specific sentiment analysis.

The implementation includes reusable Python modules, a command-line interface,
five notebook walkthroughs, and explicit taxonomy and output schemas.

## Interactive dashboard

**[Explore the News Data Analysis dashboard →](https://datastudio.google.com/s/sDBUvI4UIhk)**

The dashboard explores the imported news dataset through article coverage and text
completeness, publisher activity, sentiment, concepts, relevance, duplicate content,
and source rankings.

The data workflow uses **NewsAPI.ai / Event Registry → Google Cloud Storage →
BigQuery → Looker Studio**. The dashboard presents exploratory analysis of the
acquired news data; the Python experiments in this repository develop the
article-level analytics layer.

See the [architecture diagram](docs/architecture.md) for the data flow and the
planned connection between the cloud dataset and the analytics experiments.

## Start here

| Goal | Entry point |
| --- | --- |
| Explore the news dataset interactively | [News Data Analysis dashboard](https://datastudio.google.com/s/sDBUvI4UIhk) |
| Understand the data pipeline and dashboard | [Architecture and data flow](docs/architecture.md), [dashboard review](docs/dashboard-review.md) |
| Run industry classification with explicit retrieval | [Notebook 01](notebooks/01_industry_vector.ipynb) |
| Compare model-directed file search | [Notebook 02](notebooks/02_industry_file_search.ipynb) |
| Extract industry-specific events | [Notebook 03](notebooks/03_event_classification.ipynb) |
| Explore emotions or sentiment | [Notebook 04](notebooks/04_emotion_classification.ipynb), [Notebook 05](notebooks/05_sentiment_classification.ipynb) |

## Repository structure

```text
ai-experiments/
├── README.md                         # Main setup and usage guide
├── pyproject.toml                    # Package, dependencies, CLI, development tools
├── .env.example                      # Local API/model/store configuration
├── data/
│   ├── taxonomies/                   # Industry, event, and healthcare affect definitions
│   ├── samples/                      # Two general articles and six event/input pairs
│   └── provenance.json               # Sample and taxonomy provenance
├── notebooks/                        # Five readable experiment walkthroughs
├── src/orcalytics_experiments/
│   ├── config.py                     # Environment and client setup
│   ├── taxonomy.py                   # Taxonomy normalization and industry input parsing
│   ├── retrieval.py                  # Explicit store setup and taxonomy retrieval
│   ├── experiments.py                # Shared execution and grounding checks
│   ├── cli.py                        # prepare-store and classify commands
│   └── resources/
│       ├── prompts/                  # One system prompt per task
│       └── schemas/                  # Versioned JSON output contracts
├── docs/                             # Architecture and dashboard documentation
├── tests/                            # Offline checks with fake API responses
└── .github/workflows/checks.yml       # Lint, offline tests, and package build
```

## Installation

Use Python 3.9 or later. Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,notebooks]'
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Set `OPENAI_MODEL` only if you want to override
the experiment defaults: `gpt-5.1` for explicit industry retrieval and
`gpt-5-mini` for the other experiments. The `--model` argument takes precedence.
Model access depends on your OpenAI project. Prompts request consistent choices,
but model outputs are not guaranteed to be identical across repeated calls.
The `gpt-5-mini` industry file-search and event experiments use high
reasoning effort. Other models use their API default reasoning setting.

### Prepare taxonomy stores once

Store creation is explicit, separate from classification, and incurs API/storage
usage. Run each command once, then reuse the returned store ID:

```bash
orcalytics prepare-store --task industry \
  --taxonomy data/taxonomies/industries.json \
  --output outputs/industry-store.json

orcalytics prepare-store --task event \
  --taxonomy data/taxonomies/events.json \
  --output outputs/event-store.json
```

Copy each manifest's `vector_store_id` into `INDUSTRY_VECTOR_STORE_ID` or
`EVENT_VECTOR_STORE_ID` in `.env`. Each taxonomy node is uploaded as a text file
with identifying metadata. Classification retrieves whole local taxonomy records
using that metadata, so it does not assume a search chunk is valid JSON.

Store IDs are specific to your OpenAI project. Keep the store and local taxonomy
in sync; prepare a new store when the taxonomy changes. Setup
does not delete resources. On failure it reports the partially created store ID
for inspection; rerunning setup creates another store.

## Running experiments

### Industry classification

```bash
orcalytics classify --task industry \
  --article data/samples/hca_healthcare.txt \
  --taxonomy data/taxonomies/industries.json \
  --output outputs/hca-industries.json
```

The default `vector` strategy searches the industry store, deduplicates matches,
then passes complete taxonomy definitions to the model. Add
`--strategy file-search` to run the alternative experiment in which the model
searches the store during its response. Both return `shortlisted_industries`
with `sector`, `sub_category`, `relevance`, and `reason`, plus an optional
`emergent_industry_candidate`.

### Event extraction

```bash
orcalytics classify --task event \
  --article data/samples/events/01_article.txt \
  --industries data/samples/events/01_industries.json \
  --taxonomy data/taxonomies/events.json \
  --output outputs/events.json
```

Supply the industry classifier's JSON for the **same article** using
`--industries`. Both plain industry JSON and the CLI's result envelope are accepted.
The event stage emits zero or one event per supplied industry, with an exact
article quote, sentiment, significance, confidence, and a market-reaction score.
Significance and confidence use **0–1**; market-reaction likelihood uses **0–100**.
These are uncalibrated model judgments, not validated forecasts.

### Emotion and sentiment

```bash
orcalytics classify --task emotion \
  --article data/samples/hca_healthcare.txt \
  --industries data/samples/hca_industries.json \
  --taxonomy data/taxonomies/emotions_healthcare.json \
  --output outputs/emotions.json

orcalytics classify --task sentiment \
  --article data/samples/hca_healthcare.txt \
  --industries data/samples/hca_industries.json \
  --taxonomy data/taxonomies/sentiments_healthcare.json \
  --output outputs/sentiment.json
```

The supplied healthcare taxonomies cover only **Health Insurance** and **Digital
Health**. The sample shortlist is generated from those taxonomy names for
the walkthrough; it is not a reviewed label set.
Unsupported industry pairs are listed in `unsupported_industries`; they are not
invented. Empty supported input produces an empty result without a model call.

Omit `--industries` to use the vector-retrieval approach: the industry
store supplies candidate pairs, which are joined to the local healthcare taxonomy.
This option requires `INDUSTRY_VECTOR_STORE_ID` and can miss relevant pairs outside
the retrieval result limit. Emotion/sentiment do not support `file-search` mode.

Emotion labels are read from the taxonomy. Their intensity/direction/confidence
fields retain the taxonomy's descriptive rubrics. Sentiment selects one definition
per pair and copies its descriptors, including the string-valued
`Typical Investor Action`; that field is a research taxonomy label. Neither taxonomy
provides an independently measured investor mood or investment recommendation.

### Notebooks

```bash
python -m ipykernel install --user --name orcalytics --display-name 'Python (Orcalytics)'
jupyter lab notebooks
```

Choose the **Python (Orcalytics)** kernel. Notebooks resolve paths relative to the
repository, read the same prompts/schemas as the CLI, and contain no stored outputs
or automatic store creation/deletion. Run the setup commands above before notebook
01, 02, or 03.

## Outputs and checks

Each classification returns an envelope containing `data`, task, model, strategy,
response ID, token usage, store ID, retrieval evidence, and unsupported pairs. Local
results belong under ignored `outputs/`. Refusals, incomplete responses, invalid
JSON, schema violations, unknown labels, and invalid event quotes are rejected.

```bash
python -m pytest
ruff check .
ruff format --check src tests
python -m build
```

Tests use fake API clients and do not upload articles or create cloud resources.
Passing these checks validates the code paths and data contracts; live model
quality, extraction accuracy, and cloud integration still need separate evaluation.
No labeled benchmark is included. The copied article samples have incomplete source
and collection provenance; see `data/provenance.json` before treating them as a dataset.

API implementation references: [OpenAI retrieval](https://developers.openai.com/api/docs/guides/retrieval),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
