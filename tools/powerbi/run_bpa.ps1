<#
Runs Tabular Editor 2's Best Practice Analyzer on the TMDL semantic model and
writes the findings to results/powerbi/bpa.json.

Usage: run_bpa.ps1 -TabularEditor <path to TabularEditor.exe> [-Model <definition folder>] [-Rules <rules json>]
#>
param(
    [Parameter(Mandatory = $true)][string]$TabularEditor,
    [string]$Model = "powerbi/ShippingPerformance.SemanticModel/definition",
    [string]$Rules = "powerbi/bpa/BPARules.json",
    [string]$Out = "results/powerbi/bpa.json"
)
$ErrorActionPreference = "Stop"
$tmp = New-TemporaryFile
$p = Start-Process -FilePath $TabularEditor -ArgumentList "`"$((Resolve-Path $Model).Path)`"", "-A", "`"$((Resolve-Path $Rules).Path)`"", "-V" `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tmp.FullName
$lines = Get-Content $tmp.FullName
Remove-Item $tmp.FullName
$findings = @()
foreach ($l in $lines) {
    if ($l -match 'type=(warning|error);\](.+) violates rule "(.+)"') {
        $findings += [pscustomobject]@{ severity = $Matches[1]; object = $Matches[2].Trim(); rule = $Matches[3] }
    }
}
$rulesCount = (Get-Content $Rules -Raw | ConvertFrom-Json).Count
$summary = [pscustomobject]@{
    rules_checked = $rulesCount
    findings = $findings.Count
    errors = ($findings | Where-Object severity -eq "error").Count
    by_rule = $findings | Group-Object rule | Sort-Object Count -Descending | ForEach-Object { [pscustomobject]@{ rule = $_.Name; count = $_.Count } }
    items = $findings
}
$outDirectory = Split-Path $Out
if ($outDirectory) {
    New-Item -ItemType Directory -Force $outDirectory | Out-Null
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $Out
Write-Output "BPA: $($findings.Count) findings ($($summary.errors) errors) against $rulesCount rules"
$summary.by_rule | Format-Table -AutoSize | Out-String -Width 200
exit 0
