<#
Works with the model loaded in a running Power BI Desktop through its local
Analysis Services instance.

  -Action info      list tables, row counts and partition states
  -Action refresh   full refresh of the model
  -Action query     run the DAX queries in -QueryFile (one query per block separated by a line "-- next")
                    and write the results as JSON to -OutFile

Usage: desktop_model.ps1 -Port <port> -TomPath <folder> -Action info|refresh|query [-QueryFile f] [-OutFile f]
#>
param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$TomPath,
    [Parameter(Mandatory = $true)][string]$Action,
    [string]$QueryFile,
    [string]$OutFile
)
$ErrorActionPreference = "Stop"
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Core.dll")
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Tabular.Json.dll")
Add-Type -Path (Join-Path $TomPath "Microsoft.AnalysisServices.Tabular.dll")
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("Data Source=localhost:$Port")
$db = $server.Databases[0]
$model = $db.Model

if ($Action -eq "info") {
    foreach ($t in $model.Tables) {
        $states = ($t.Partitions | ForEach-Object { "$($_.State)" + $(if ($_.ErrorMessage) { ": " + $_.ErrorMessage } else { "" }) }) -join "; "
        Write-Output ("{0,-26} measures={1,-3} partitions: {2}" -f $t.Name, $t.Measures.Count, $states)
    }
}
elseif ($Action -eq "refresh") {
    $model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $res = $model.SaveChanges()
    foreach ($m in $res.XmlaResults) { foreach ($msg in $m.Messages) { Write-Output "XMLA: $($msg.Description)" } }
    Write-Output "Refresh finished"
}
elseif ($Action -eq "query") {
    $conn = New-Object System.Data.OleDb.OleDbConnection
    $blocks = (Get-Content $QueryFile -Raw) -split "(?m)^-- next\s*$"
    $results = @()
    $cmdConn = $server.ConnectionString
    # Use XMLA execute through the TOM server (returns XML rows).
    foreach ($q in $blocks) {
        $q = $q.Trim()
        if (-not $q) { continue }
        try {
            $xml = $server.Execute("<Statement>" + [System.Security.SecurityElement]::Escape($q) + "</Statement>")
            $results += [pscustomobject]@{ query = $q; ok = $true; xml = $xml[0].Value }
        } catch {
            $results += [pscustomobject]@{ query = $q; ok = $false; error = $_.Exception.Message }
        }
    }
    $results | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $OutFile
    Write-Output "Wrote $($results.Count) results"
}
$server.Disconnect()
