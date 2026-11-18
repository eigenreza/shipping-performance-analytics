# Paginated report

`powerbi/paginated/SegmentPerformance.rdl` is a printable, page-exact report for Power BI Report Builder (free). A paginated report is laid out for paper or PDF, unlike the interactive report pages.

**Parameters.** Segment (vehicle carrier or ro-ro ship) and EU MRV reporting year.

**Content, on one A4 landscape page.**

- Header with the segment and year; a three-line guide (what it is, how to use it, what to notice).
- Five KPI tiles against the previous year: CO2, CO2 per nautical mile, average speed, share rated D or E (change in percentage points) and EU ETS cost.
- The CII rating mix for the year.
- The fifteen ships (pseudonyms) with the highest CO2 per nautical mile, with size class, speed, CO2 and rating.
- The EU ETS allowance price by month with the segment's allowances due spread evenly over the months and costed at each month's price.
- Notes and a footer with the author, the repository and the page number. No run date is printed.

**Data.** The data is embedded in the report as inline XML (Report Builder's XML data source with `XmlData` in the query), one dataset per section, filtered by the parameters. The report therefore opens and runs without any connection or credentials. `spa powerbi` regenerates it from the warehouse.

**Checks.** The RDL is validated against Microsoft's RDL 2016 schema in the tests. It was also rendered to PDF for several parameter combinations with an open-source port of the report viewer (`tools/rdl-render`) to catch expression and layout errors before opening it in Report Builder.

**Export to PDF.** Open the file in Report Builder, click Run, choose the parameters, then Export, PDF. The published PDF in the demo has its document metadata removed.
