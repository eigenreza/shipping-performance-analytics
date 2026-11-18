# AI analyst and insight checker

Two uses of language models, both measured and both shown with their failures.

## AI analyst

An agent answers business questions in plain English by calling tools (`src/spa/ai/analyst.py`):

| Tool | What it does |
|---|---|
| `list_metrics()` | Lists the metric catalog: the same definitions as the Power BI measures, written in SQL (`src/spa/ai/catalog.py`) |
| `get_metric(metric, filters, year_from, year_to)` | Computes one metric with filters on segment, size class, flag region, design generation, ship, port or month |
| `query_sql(sql)` | Runs one read-only SELECT on the public star schema |

**Safety of `query_sql`.** The query must parse (with sqlglot) as a single SELECT, may read only the `marts` and `reference` schemas, may not call file, network or system functions, and runs on a read-only DuckDB connection with a 200-row and 5-second limit (`src/spa/ai/sqlguard.py`). The private layers that hold ship identifiers are out of reach. Every answer keeps the SQL that ran, including the SQL behind each catalog metric.

## Evaluation (frozen before any model was scored)

40 business questions with gold answers computed directly by SQL (`src/spa/ai/questions.py`): 10 for development and 30 for the test. A number is correct within 0.5% (or 0.0005 for values below 1; shares may be given as fractions or percentages); a name, year or letter must match. A missing answer counts as wrong.

Models: two local models through Ollama (Qwen 2.5 7B and Llama 3.2 3B, on a laptop GPU with 4 GB of memory) and Gemini 3.5 Flash Lite on the free tier. Temperature 0. Every model call is cached by model, prompt version and full request (`results/ai/calls/`), so `spa ai eval` reruns offline.

<!-- BEGIN:ai -->
| Model | Test accuracy (95% interval) | Dev accuracy | Median seconds per question | Insight findings fully supported |
|---|---|---|---|---|
| Gemini 3.5 Flash Lite (free tier) | 97% (83% to 99%), 29/30 | 100% | 4.3 | 100% |
| Qwen 2.5 7B (local, Ollama) | 13% (5% to 30%), 4/30 | 10% | 54.5 | 67% |
| Llama 3.2 3B (local, Ollama) | 3% (1% to 17%), 1/30 | 10% | 22.7 | 53% |
<!-- END:ai -->

## Insight writer and checker

The writer gets the data behind one report page and writes three findings (`src/spa/ai/insights.py`). The checker extracts every number from each finding (with units such as %, million and thousand, skipping year labels) and searches for it among the values the data supports: the values themselves and their differences, ratios and percentage changes within a column, at the precision the finding uses (half a unit of the last digit shown, plus 0.05%). A finding is "supported" when every number is found and "unsupported" when at least one is not. The demo's "Ask the data" page highlights each number green or red.

## What the AI is good and bad at here

- **Good:** choosing the right catalog metric and filters; writing correct joins on a documented star schema; quoting a number it has just read.
- **Bad:** small local models skip filters (for example the segment), confuse a share with a percentage, answer without calling a tool, keep calling tools until the step limit without answering, or copy a value from the instructions. Insight writers sometimes state a number close to, but not equal to, the data value; the checker catches these.
- **What makes it usable:** tools with fixed definitions instead of free SQL where possible, the SQL shown with every answer, automatic checks on every number, and an evaluation frozen before scoring.
