<#
Runs DAX queries against the model loaded in a running Power BI Desktop.

Input:  JSON array of {"id": "...", "dax": "EVALUATE ..."}
Output: JSON array of {"id", "ok", "rows" (array of objects) or "error"}

Usage: run_dax.ps1 -Port <port> -InFile <queries.json> -OutFile <results.json>
#>
param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$InFile,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [string]$AdomdPath = "C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll"
)
$ErrorActionPreference = "Stop"
Add-Type -Path $AdomdPath
$queries = Get-Content $InFile -Raw -Encoding UTF8 | ConvertFrom-Json
$out = New-Object System.Collections.ArrayList
foreach ($q in $queries) {
    # Optional "roles": evaluate the query as a member of these RLS roles.
    $cs = "Data Source=localhost:$Port"
    if ($q.roles) { $cs += ";Roles=$($q.roles)" }
    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($cs)
    $conn.Open()
    try {
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = $q.dax
        $reader = $cmd.ExecuteReader()
        $rows = New-Object System.Collections.ArrayList
        while ($reader.Read()) {
            $row = [ordered]@{}
            for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                $v = $reader.GetValue($i)
                if ($v -is [System.DBNull]) { $v = $null }
                $row[$reader.GetName($i)] = $v
            }
            [void]$rows.Add([pscustomobject]$row)
        }
        $reader.Close()
        [void]$out.Add([pscustomobject]@{ id = $q.id; ok = $true; rows = $rows })
    } catch {
        [void]$out.Add([pscustomobject]@{ id = $q.id; ok = $false; error = $_.Exception.Message })
    }
    $conn.Close()
}
ConvertTo-Json -InputObject $out -Depth 6 | Set-Content -Encoding UTF8 $OutFile
Write-Output "Ran $($queries.Count) queries"
