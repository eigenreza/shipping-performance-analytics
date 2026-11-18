# Data notice

Every source is open data. Raw downloads stay in the local, ignored `data/raw` folder; only derived, pseudonymous tables are published.

| Source | Publisher | Used for | Licence and terms | Attribution |
|---|---|---|---|---|
| EU MRV public emission reports (THETIS-MRV), reporting years 2018 to 2025 | European Maritime Safety Agency (EMSA) | Yearly fuel, CO2, distance, time at sea and transport work per ship | Reproduction is authorised provided the source is acknowledged (EMSA legal notice) | Source: EU MRV data published by the European Maritime Safety Agency |
| AIS positions, port call records ("time in port") and the location register, via Kystdatahuset | Norwegian Coastal Administration (Kystverket) | Ship tracks and port calls on the Norwegian coast, 5 August to 30 September 2026 | Norwegian licence for open government data (NLOD); open access excludes small fishing and leisure craft | Contains data under the Norwegian licence for Open Government data (NLOD) distributed by Kystverket |
| Historical Weather API (ERA5 reanalysis) and Marine Weather API | Open-Meteo | Hourly 10 m wind and significant wave height along voyage legs | CC BY 4.0; free non-commercial use | Weather data by [Open-Meteo.com](https://open-meteo.com). Generated using Copernicus Climate Change Service information (ERA5). Wave data from the marine models listed by Open-Meteo (Copernicus Marine Service and ECMWF) |
| EU ETS allowance price, front December contract | Ember (price data from Montel) | Daily carbon price, 2018-01-01 to 2026-09-30 | CC BY 4.0 | Carbon price data: Ember |
| Land polygons, 1:10m | Natural Earth | Coastline on the demo map | Public domain | Made with Natural Earth |
| IMO CII guidelines (MEPC.352(78), MEPC.353(78), MEPC.354(78), MEPC.338(76), MEPC.400(83)) | International Maritime Organization | Reference lines, reduction factors and rating boundaries | Official public texts | Cited in docs/carbon-rules.md |
| Directive 2003/87/EC as amended by Directive (EU) 2023/959 | European Union (EUR-Lex) | EU ETS phase-in and scope rules for shipping | Official public text | Cited in docs/carbon-rules.md |

## Services used, all free

| Service | Basis |
|---|---|
| EMSA THETIS-MRV public download | Public, no account |
| Kystdatahuset web services (Kystverket) | Open endpoints, no account |
| Open-Meteo APIs | Free tier, no key, below the published per-minute, hourly and daily limits |
| Ember data | Public chart data |
| Gemini API | Free tier only, used for the AI evaluation; every call is cached |
| Ollama | Local models on the developer's computer |
| GitHub and GitHub Actions | Free for public repositories |
| Azure App Service | Free (F1) plan |

## Privacy

Public outputs never show ship names, IMO numbers, MMSI numbers, call signs or company names. Each ship gets a stable pseudonym (for example "Carrier 017") derived from a salted hash; the salt is kept locally and never published. Ships are described only by segment, size class, design generation and flag region. A test scans every published file, including the Parquet tables, for real identifiers and names.
