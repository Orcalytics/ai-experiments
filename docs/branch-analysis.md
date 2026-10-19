# Branch analysis and consolidation

This audit inspected every tracked file at the following original remote heads.
It is a source audit, not a live API evaluation; cached notebook outputs do not
establish reproducibility.

| Original branch | Commit | Relationship | Contents |
| --- | --- | --- | --- |
| `main` | `fd40cafc657c4e2ab75b10d15ba838d713c0f267` | Initial scaffold | `.gitignore` and a one-line README |
| `marwa` | `fd40cafc657c4e2ab75b10d15ba838d713c0f267` | Identical to original main | No additional experiment |
| `master` | `289ebe79b18b0125ede624a3be1abed5bb992b03` | Two commits, no common ancestor with original main | Three notebooks and two taxonomies |
| `yusra` | `672e50e119ae5f9b52d569eebdee7def28eccf3c` | One commit after original main | Two notebooks and two healthcare taxonomy files |

The consolidation imports and refactors these experiments onto main. It does not
merge the unrelated master history or move the master/yusra/marwa branch refs.
The original source is retrievable at the commit IDs above.

## master: industry and event experiments

### classify_industry.ipynb

This experiment loads the broad industry taxonomy, creates a vector store, uploads
files from `split_taxonomy/`, and calls `gpt-5-mini` using the Responses API's
`file_search` tool. The inline example is a broad market roundup with AI, telecom,
gold, and macroeconomic themes. Output is schema-constrained industry/subcategory
pairs labeled LOW, MEDIUM, or HIGH, with short reasons and an optional emergent
industry. The response parser tries to recover output text and parse JSON.

The local taxonomy variable is loaded but not used to validate output. The missing
`split_taxonomy/` folder prevents a clean setup. The model searches a hard-coded
store instead of the store just created. Repeated execution can create unused
stores. The prompt's request for determinism does not establish repeatability.

### classify_industries.ipynb

This alternative uses explicit retrieval. It searches a hard-coded industry store
with the full HCA Healthcare article, sorts matches by score, attempts to parse each
chunk as a single JSON object, and formats industry/subcategory names. `gpt-5.1`
then classifies the article using those candidates and a strict JSON schema.

This makes candidate retrieval inspectable, but silently skips non-JSON chunks and
discards descriptions before generation. Taxonomy context can disappear without
an error. Setup has the same missing-directory and store-ID problems as the other
industry notebook. There is no repeated-run comparison or labeled evaluation.

### event_classification.ipynb

The event experiment accepts an article and its already classified industries.
It uses `gpt-5-mini`, file search over an event taxonomy, and a structured output
schema to select at most one catalytic event per industry. It asks for an exact
article quote, event sentiment, significance, market-reaction likelihood,
confidence, and frequency. It includes six manually entered article/industry pairs:

1. TAG Heuer / New Balance product collaboration.
2. US market roundup, AI stocks, telecom, and gold.
3. Sun Holdings acquisition and restaurant expansion.
4. AeroCore's Brazil operations opening.
5. Lennar, American Eagle, and Toll Brothers ex-dividend discussion.
6. Toll Brothers stock analysis.

The final call references `article_text7` and `industry_object7`, which are undefined.
Pair 5 instead uses the unusually named `industry_object_5`. Another setup cell
unconditionally deletes a named remote vector store. Store creation, upload, and
query use different IDs. The prompt defines significance/confidence on 0–1, but
the schema allows significance through 10 and confidence through 100. The schema
does not enforce at most one event or frequency consistency. Event type is a free
string, and evidence quotes are not checked after generation. The six industry
inputs are demonstrations; they are not validated gold labels.

### Taxonomies

- `industrial_taxonomy.json`: 138 entries in 21 industries, each with Industry,
  Sub-category, and Description. It is a flat business-domain taxonomy.
- `eventss.json`: 11 event categories with descriptions and keyword examples,
  covering earnings, M&A, product launches, partnerships, legal/regulatory,
  workforce, leadership, operations, restructuring, funding, and ESG.

## yusra: emotion and sentiment experiments

### Copy_of_emotion_with_RAG.ipynb

This notebook searches the same industry store used by master, joins candidate
pairs to a healthcare emotion taxonomy, and asks `gpt-5-mini` for industry-specific
emotion labels, descriptive intensity/direction/confidence, relevance, and reasons.
It uses the HCA Healthcare article as an inline sample.

The actual taxonomy contains eight labels: Optimism, Concern, Surprise, Criticism,
Relief, Neutral, Encouragement, and Curiosity. The schema instead permits a different
six-label set (Fear, Greed, Optimism, Uncertainty, Relief, Anger). The prompt mixes
emotion labels with Positive/Negative/Neutral sentiment, alternates between one
emotion and all emotions, and permits inference while forbidding new labels.
Its emergent schema requires `rationale` but defines `Description`; strict mode is
disabled. Retrieval passes only emotion names, omitting the descriptors the model
is instructed to copy. Parsing assumes each retrieved chunk is complete JSON.
Paths assume Google Colab's `/content`, and setup/query use different store IDs.

### sentiments_with_RAG.ipynb

The sentiment notebook retrieves industry candidates, enriches them with local
Positive/Neutral/Negative definitions, and calls `gpt-5-mini`. Each definition has
mood, intensity, trend, magnitude, time horizon, confidence, investor-action text,
and examples. It prints usage as well as the result.

The expected filename differs from the checked-in `- Copy.json` file. Paths assume
Colab, stores are hard-coded, and missing taxonomy entries can produce a dictionary
fallback where a list is expected. The prompt contains copied emotion output keys
that conflict with the sentiment schema. It asks for a reason the schema forbids,
and an action array where the data/schema use strings. It forces at least two
industries even though only one industry exists in the taxonomy (two subcategories).
As with emotion, the article and taxonomy are narrow HCA examples, not general
market coverage. Taxonomy example situations must not be treated as article facts.

### Healthcare taxonomy files

Both files contain one industry, Healthcare & Biotech, and two subcategories,
Health Insurance and Digital Health. `rebuild emotion taxanomy article 1.txt`
contains JSON despite the text extension. Both are preserved as JSON with clearer
names. Their definitions are article-specific hand-authored research material.

## Old-to-new mapping

| Source | Main entry point or data |
| --- | --- |
| master/classify_industries.ipynb | notebooks/01_industry_vector.ipynb |
| master/classify_industry.ipynb | notebooks/02_industry_file_search.ipynb |
| master/event_classification.ipynb | notebooks/03_event_classification.ipynb; data/samples/events/ |
| master/industrial_taxonomy.json | data/taxonomies/industries.json |
| master/eventss.json | data/taxonomies/events.json |
| yusra/Copy_of_emotion_with_RAG.ipynb | notebooks/04_emotion_classification.ipynb |
| yusra/sentiments_with_RAG.ipynb | notebooks/05_sentiment_classification.ipynb |
| yusra/rebuild emotion taxanomy article 1.txt | data/taxonomies/emotions_healthcare.json |
| yusra/article1 emotion taxanomy - Copy.json | data/taxonomies/sentiments_healthcare.json |

## Shared implementation and intentional corrections

- `config.py` centralizes environment loading, model selection, and client creation.
- `taxonomy.py` normalizes the four formats and accepts both bare industry results
  and the CLI envelope for downstream stages.
- `retrieval.py` creates stores only on explicit request, attaches node metadata,
  and joins search hits to full local definitions. No chunk JSON parsing is needed.
- `experiments.py` shares Responses calls, strict schema validation, incomplete/
  refusal handling, label checks, deduplication, event quotes, and frequency checks.
- Prompts and schemas are separate text/JSON files included in the installed package.
  All notebooks call the package rather than maintaining separate implementations.
- The two original industry retrieval approaches remain available. Event also
  supports explicit retrieval and the original file-search approach.
- Event scores now agree with the original prompt's 0–1 ranges; maximum one event
  and frequency 0/1 are enforced. The example starts with a real sample pair.
- Emotion names derive from the loaded taxonomy, with all descriptors available to
  the model. Multiple distinct supported emotions are permitted. The emergent
  emotion field is retained as null; unsupported labels are not invented.
- Sentiment uses its own output keys, one selected definition per pair, an
  article-specific reason, and string-valued action text matching the taxonomy.
  There is no minimum-industry requirement.
- Emotion/sentiment can consume industry-stage results directly, or retain the
  original vector candidate retrieval path. Unsupported pairs are explicit.
- Notebook outputs/execution counts are cleared. Article fixtures, all six event
  pairs, and taxonomy values are preserved outside notebooks.

This is a functional refactor with documented contract corrections, not a
byte-for-byte reproduction of prior model outputs. Offline tests exercise data
handling and API boundaries. They do not establish extraction accuracy, score
calibration, or generalization beyond the small sample inputs.
