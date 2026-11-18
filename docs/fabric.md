# Microsoft Fabric: Fabric-ready

The project runs on a laptop at no cost and is built **Fabric-ready**: it was not deployed to a Fabric workspace. Each piece maps to a Fabric item, and the gold layer could be loaded into a lakehouse unchanged.

| In this project | Fabric counterpart | How it carries over |
|---|---|---|
| Raw Parquet files (`data/raw`) | Lakehouse, Files area | Upload the folder as is |
| Bronze, silver and gold Delta tables (`data/exports/delta`, written with the open-source `deltalake` package) | Lakehouse Tables in medallion layers | Delta tables are Fabric's native table format; copy the folders into the Tables area or use shortcuts |
| Python ingest modules and `spa refresh` | Notebooks and a Data Pipeline | The ingest modules run unchanged in a Fabric notebook; the pipeline calls them in the order of `spa refresh` |
| dbt models on DuckDB | Fabric Warehouse with the dbt-fabric adapter, or Spark SQL notebooks | The SQL is standard apart from a few DuckDB functions (`regexp_extract`, `arg_max`, `date_diff`) with direct T-SQL or Spark equivalents |
| TMDL semantic model in Import mode | Semantic model in Direct Lake mode on the gold Delta tables | The star schema, integer keys, measures, calculation group, field parameter and roles carry over; only the partitions change from Power Query to Direct Lake entity partitions |
| PBIR report and RDL paginated report | Report and paginated report items in the workspace | PBIP folders sync to a workspace through Fabric Git integration |
| GitHub Actions CI | Fabric deployment pipelines plus the same CI | Unchanged |

**Why the model is Direct Lake compatible.** No calculated columns, no Power Query transformations beyond column selection and types, integer relationship keys and a separate date table are all requirements or recommendations for Direct Lake. The calculated tables that remain (what-if and field parameters, the speed relation choice) are supported next to Direct Lake tables.

**Medallion layers.** `spa export` writes bronze (staging models), silver (intermediate models) and gold (marts and reference tables) as Delta tables. Bronze and silver contain ship identifiers and stay local; gold is pseudonymous.
