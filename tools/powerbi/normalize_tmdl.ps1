<#
Loads a TMDL folder with Microsoft's Tabular Object Model (strict parse and
reference validation) and writes it back in canonical TMDL layout.

Usage: normalize_tmdl.ps1 -Source <staging folder> -Target <definition folder> -TomPath <folder with Microsoft.AnalysisServices.Tabular.dll>
#>
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$TomPath
)
$ErrorActionPreference = "Stop"
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Core.dll")
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Tabular.Json.dll")
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Tabular.dll")

try {
    $db = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($Source)
} catch {
    $e = $_.Exception
    while ($e.InnerException) { $e = $e.InnerException }
    Write-Output "TMDL ERROR: $($e.Message)"
    if ($e.PSObject.Properties.Name -contains "Document") { Write-Output "  document: $($e.Document) line: $($e.Line)" }
    exit 1
}
$m = $db.Model
$measures = 0; foreach ($t in $m.Tables) { $measures += $t.Measures.Count }
Write-Output ("Parsed: {0} tables, {1} measures, {2} relationships, {3} roles, compatibility {4}" -f $m.Tables.Count, $measures, $m.Relationships.Count, $m.Roles.Count, $db.CompatibilityLevel)
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
[Microsoft.AnalysisServices.Tabular.TmdlSerializer]::SerializeDatabaseToFolder($db, $Target)
Write-Output "Written: $Target"
