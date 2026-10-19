# News Data Analysis dashboard review

Reviewed on 19 October 2026 (Australia/Melbourne) using the supplied
[dashboard link](https://datastudio.google.com/s/sDBUvI4UIhk). It resolves to report
`29e13822-2b1d-49ba-90e7-50e841ba6700`, titled **News Data Analysis**.
The owner confirmed the collection source as NewsAPI.ai / Event Registry and
described the flow through Cloud Storage, BigQuery, and Looker Studio.

## Pages inspected

| Report page | Visible purpose or chart headings |
| --- | --- |
| Articles analysis | Average article volume by day/hour/weekday, average body length and words, full-body versus partial coverage |
| Sources Analysis | Count of articles per source; articles each source publishes per day |
| Sentiment Analysis | Overall sentiment, sentiment over time/week, news coverage sentiment |
| Concept Analysis | Most frequent topics and concept frequency over time |
| Concept analysis | Top concepts by publisher and sentiment of frequent topics |
| Relevence Analysis | Source volume versus relevance |
| Duplicates Analysis | Source-level total/unique article counts, duplicate counts and ratios |
| Top Sources Analysis | Table of Source, Volume, Avg Relevance, Avg Sentiment, Engagement, and Quality Score; a Source control shows one saved selection |

The two concept pages differ in content but have nearly identical names. Renaming
them to "Topic trends" and "Topics by publisher" would make navigation clearer.
"Relevence" is the original report spelling.

## Directly readable values

These are the displayed values under the report's existing default state, not
independently recomputed dataset statistics. The underlying date range, aggregation
formulas, and source table configuration were not inspected.

| Displayed metric | Value | Interpretation limit |
| --- | --- | --- |
| Avg Articles / day | 15,427 | Day denominator, active filters, and source coverage not verified |
| Avg body length | 3,045 | Unit and truncation treatment not shown on the card |
| Avg Number of words | 482.4 | Word-count method and missing-body handling not verified |
| Overall Sentiment | 0.12 | Scale, weighting, and provider-versus-custom provenance not verified |

The duplicate table is readable. Examples shown include The Daily Nexus (4 total,
3 unique, 1 duplicate, ratio 0.25), FITSNews (5/4/1, ratio 0.2), Morgan Stanley
(7/6/1, ratio 0.14), and MLB.com (204/203/1, displayed ratio 0).
The table pagination reads **1–100 / 2792**, indicating 2,792 table rows in that view.
This should not be treated as a verified total of distinct publishers without
checking the table's dimensions and filters.

A nearby authored annotation refers to "1000 publishers", says 11 showed duplicates,
and says no top publishers republish duplicate content. The table's 2,792 rows do
not match that annotation's denominator. The annotation may describe an earlier
sample or different filter; its current accuracy was not verified. The visible
MLB.com row also demonstrates that rounding can display a nonzero duplicate ratio
as zero. Keep the duplicate count and display ratios with enough precision.

Another authored annotation states that high-volume publishers do not always have
the highest relevance. This is a useful question to investigate, but the chart's
actual distribution was not readable in this session, so that conclusion was not
independently confirmed.

The top-source table is also readable. Yahoo! Finance is shown with Volume 1,
Avg Relevance 1, Avg Sentiment 0.21, Engagement 0.09, and Quality Score 0.65. World
Bank follows with 0.1, 1, 0.17, 0.49, and 0.63 respectively. These are displayed
metrics, not an independent endorsement of those rankings. Fractional Volume
values suggest a derived or normalized metric, but its formula is unverified.
The Source control displays one saved selection; its scope/effect on different
charts was not established, so these values should not be generalized beyond
the visible report state. The definition and weighting of Quality Score were
not inspected; do not equate it with independently measured publisher credibility.

## Visibility and verification limits

Report navigation, headings, scorecards, annotations, and the duplicate/top-source tables were
accessible. Several embedded chart frames remained blank in the browser. No chart
distributions, full-body percentage, date-window totals, or
trend slopes are inferred from those blank charts. Report refresh labels appeared,
including some noting that not all page items had updated; these labels do not
establish the timestamp of the newest imported news article.

This review did not inspect connector settings, BigQuery SQL, source schema, raw
files, importer code, or IAM. The architecture describes the cloud flow as reported
by the owner, rather than claiming deployment verification.

## Implications for Orcalytics analytics

1. Establish full-body eligibility before sending articles to classifiers. The
   experiments analyze complete text; mean length alone does not establish coverage.
2. Keep provider sentiment and concepts alongside model-derived industry outputs.
   A whole-article sentiment card cannot validate industry-specific sentiment.
3. Define duplicate handling for trend volume. Publisher-level duplicate flags may
   not establish independent reporting across different publishers; inspect actual
   provider duplicate links and their meaning before weighting narratives.
4. Record publication time, import time, and analysis time independently. Source
   coverage and daily denominators need explicit timezones and missing-day policy.
5. Add run coverage, failure rate, unsupported taxonomy coverage, and model/taxonomy
   versions when enriched outputs reach BigQuery. These are proposed dashboard
   measures, not existing report features.
6. Reconcile static annotations with dynamic table filters and show duplicate
   ratios as percentages with sufficient precision.
7. Document the Volume normalization and Quality Score formula, components,
   weights, and selected-source scope before using those rankings to weight news
   signals. Positive article sentiment is not itself a measure of source accuracy.

NewsAPI.ai documents `relevance` as relevance relative to the collection query.
Check whether the report uses that field before treating Avg Relevance as a
general measure of publisher quality. Orcalytics' industry relevance labels measure
a different relationship: an industry's prominence within an article.

NewsAPI.ai's [official data-search overview](https://newsapi.ai/blog/exploring-the-sandbox/)
describes article text, concepts, sentiment, relevance, and duplicate metadata.
That is consistent with the report topics, but the actual imported fields still
need to be checked against the BigQuery schema.
