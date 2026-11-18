# Carbon rules: EU ETS and IMO CII

Both rule sets are kept as seed tables in `dbt/seeds/` with the source of every value, and tested in `tests/test_rules_and_parsers.py` and on synthetic fixtures in `tests/test_warehouse_fixtures.py`. The tables below are generated from the seeds.

## EU ETS for shipping

EU ETS: the EU emissions trading system, under which shipping companies must buy and surrender allowances for part of their CO2. Shipping entered the system in 2024 (Directive 2003/87/EC as amended by Directive (EU) 2023/959).

**Which emissions count (Article 3ga).** Emissions on voyages between EU/EEA ports and at berth in EU/EEA ports count in full; voyages that start or end outside count by half:

<!-- BEGIN:ets_scope -->
| Emissions | Share counted | Source |
|---|---|---|
| between_eea_ports | 1.00 | Directive 2003/87/EC Art. 3ga and Annex I |
| at_berth_in_eea_port | 1.00 | Directive 2003/87/EC Art. 3ga and Annex I |
| departing_eea_to_non_eea | 0.50 | Directive 2003/87/EC Art. 3ga and Annex I |
| arriving_eea_from_non_eea | 0.50 | Directive 2003/87/EC Art. 3ga and Annex I |
<!-- END:ets_scope -->

**Phase-in (Article 3gb).** Allowances are surrendered for a growing share of the verified emissions; methane and nitrous oxide are added from the 2026 emission year:

<!-- BEGIN:ets_phase_in -->
| Emission year | Share surrendered | Gases | Source |
|---|---|---|---|
| 2023 | 0.00 | CO2 | Directive 2003/87/EC Art. 3gb (shipping enters the EU ETS on 1 January 2024) |
| 2024 | 0.40 | CO2 | Directive 2003/87/EC Art. 3gb(a) |
| 2025 | 0.70 | CO2 | Directive 2003/87/EC Art. 3gb(b) |
| 2026 | 1.00 | CO2 CH4 N2O | Directive 2003/87/EC Art. 3gb(c) |
| 2027 | 1.00 | CO2 CH4 N2O | Directive 2003/87/EC Art. 3gb(c) |
<!-- END:ets_phase_in -->

**How the project applies it.** For every ship-year, CO2 in scope = CO2 between EEA ports + CO2 at berth + half of CO2 on voyages into and out of the EEA, all from the MRV report. Allowances due = CO2 in scope times the phase-in share of that year. EU ETS cost = allowances due times the average daily allowance price of the year (Ember). For the 2024 and 2025 reports MRV also publishes the emissions reported under the directive; they are kept as `co2_ets_reported_t` for comparison. The scenario measures use full surrender, the rule from 2026.

## IMO carbon intensity rating (CII)

CII: the IMO carbon intensity rating, A best to E worst. It compares a ship's attained CO2 per unit of capacity and distance with a required value that falls every year.

**Attained CII** (MEPC.352(78)): grams of CO2 divided by (capacity times distance). For ro-ro cargo ships and vehicle carriers the capacity is gross tonnage.

**Reference line** (MEPC.353(78)): CII_ref = a times capacity to the power of minus c. For vehicle carriers above 57,700 GT the capacity in the reference line is fixed at that value.

<!-- BEGIN:cii_reference -->
| Segment | Capacity | From | Below | Capacity cap | a | c | Source |
|---|---|---|---|---|---|---|---|
| Vehicle carrier | GT | 57700 |  | 57700 | 3627 | 0.590 | IMO MEPC.353(78) Table 1 |
| Vehicle carrier | GT | 30000 | 57700 |  | 3627 | 0.590 | IMO MEPC.353(78) Table 1 |
| Vehicle carrier | GT | 0 | 30000 |  | 330 | 0.329 | IMO MEPC.353(78) Table 1 |
| Ro-ro ship | GT | 0 |  |  | 1967 | 0.485 | IMO MEPC.353(78) Table 1 |
<!-- END:cii_reference -->

**Required CII** = (1 - Z) times CII_ref, with the reduction factor Z of the year (MEPC.338(76) for 2023 to 2026, MEPC.400(83) for 2027 to 2030):

<!-- BEGIN:cii_reduction -->
| Year | Reduction factor Z | Source |
|---|---|---|
| 2019 | 0.00 | IMO MEPC.338(76) (2019 reference year) |
| 2020 | 0.01 | IMO MEPC.338(76) |
| 2021 | 0.02 | IMO MEPC.338(76) |
| 2022 | 0.03 | IMO MEPC.338(76) |
| 2023 | 0.05 | IMO MEPC.338(76) |
| 2024 | 0.07 | IMO MEPC.338(76) |
| 2025 | 0.09 | IMO MEPC.338(76) |
| 2026 | 0.11 | IMO MEPC.338(76) |
| 2027 | 0.13625 | IMO MEPC.400(83) |
| 2028 | 0.1625 | IMO MEPC.400(83) |
| 2029 | 0.18875 | IMO MEPC.400(83) |
| 2030 | 0.215 | IMO MEPC.400(83) |
<!-- END:cii_reduction -->

**Rating** (MEPC.354(78)): the boundaries are exp(d1) to exp(d4) times the required CII. Below the first boundary the rating is A, then B, C, D, and E above the last.

<!-- BEGIN:cii_boundaries -->
| Segment | exp(d1) | exp(d2) | exp(d3) | exp(d4) | Source |
|---|---|---|---|---|---|
| Vehicle carrier | 0.86 | 0.94 | 1.06 | 1.16 | IMO MEPC.354(78) Table 1 (exp(d) values) |
| Ro-ro ship | 0.76 | 0.89 | 1.08 | 1.27 | IMO MEPC.354(78) Table 1 (exp(d) values) |
<!-- END:cii_boundaries -->

### An approximation, and why

The official CII uses the IMO Data Collection System, which covers all voyages; MRV covers only voyages to, from and between EU/EEA ports, plus time at berth. The rating here is therefore computed on the MRV scope. MRV also publishes no gross tonnage: it comes from Kystverket records where a ship called Norway and is otherwise estimated from AIS length and beam (see [data-model.md](data-model.md)). Ships with no AIS dimensions get no rating. Ratings for years before 2023, when the rules took effect, are shown for context only (`is_official_cii_year`).
