// Renders an RDL whose datasets carry inline XML data (<XmlData>) to PDF with
// the open-source ReportViewer port. Used to test the paginated report.
// Usage: RdlRender <report.rdl> <out.pdf> [Name=Value ...]
using System.Data;
using System.Xml.Linq;
using Microsoft.Reporting.NETCore;

var rdlPath = args[0];
var outPath = args[1];
var doc = XDocument.Load(rdlPath);
XNamespace ns = doc.Root!.Name.Namespace;

var report = new LocalReport();
using (var stream = File.OpenRead(rdlPath)) { report.LoadReportDefinition(stream); }

foreach (var ds in doc.Descendants(ns + "DataSet"))
{
    var name = ds.Attribute("Name")!.Value;
    var query = XDocument.Parse(ds.Element(ns + "Query")!.Element(ns + "CommandText")!.Value);
    var fields = ds.Element(ns + "Fields")!.Elements(ns + "Field").Select(f => f.Element(ns + "DataField")!.Value).ToList();
    var table = new DataTable(name);
    foreach (var f in fields) table.Columns.Add(f, typeof(string));
    foreach (var row in query.Descendants("Row"))
    {
        var r = table.NewRow();
        foreach (var f in fields) r[f] = (object)row.Element(f)?.Value ?? DBNull.Value;
        table.Rows.Add(r);
    }
    report.DataSources.Add(new ReportDataSource(name, table));
}

var parameters = args.Skip(2).Select(a => a.Split('=', 2)).Select(p => new ReportParameter(p[0], p[1])).ToList();
if (parameters.Count > 0) report.SetParameters(parameters);
var pdf = report.Render("PDF");
File.WriteAllBytes(outPath, pdf);
Console.WriteLine($"Rendered {pdf.Length / 1024} KB to {outPath}");
