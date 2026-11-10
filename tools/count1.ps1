<#
count1.ps1 - count lines of code in DroneFlightUltimate, per folder and file type.

    powershell -ExecutionPolicy Bypass -File tools/count1.ps1
    powershell -ExecutionPolicy Bypass -File tools/count1.ps1 -Path . -Detail

Counts non-empty lines of .py .json .toml .md .ps1 files, skipping .venv, caches,
logs and calibration pictures. -Detail also lists every file.
#>
param(
    [string]$Path = (Join-Path $PSScriptRoot ".."),
    [switch]$Detail
)

$extensions = @(".py", ".json", ".toml", ".md", ".ps1")
$skip = '\\(\.venv|venv|\.git|__pycache__|\.pytest_cache|\.ruff_cache|logs|images|build|.*\.egg-info)(\\|$)'

$root = (Resolve-Path $Path).Path
$files = Get-ChildItem -Path $root -Recurse -File |
    Where-Object { $extensions -contains $_.Extension -and ($_.FullName.Substring($root.Length) -notmatch $skip) }

$rows = foreach ($f in $files) {
    $relative = $f.FullName.Substring($root.Length).TrimStart('\', '/')
    $top = ($relative -split '[\\/]')[0]
    if ($top -eq $f.Name) { $top = "(root)" }
    [pscustomobject]@{
        Folder = $top
        Type   = $f.Extension
        File   = $relative
        Lines  = @(Get-Content -LiteralPath $f.FullName | Where-Object { $_.Trim() -ne "" }).Count
    }
}

if ($Detail) {
    $rows | Sort-Object Folder, File | Format-Table File, Lines -AutoSize
}

"`nPer folder:"
$rows | Group-Object Folder | ForEach-Object {
    [pscustomobject]@{ Folder = $_.Name; Files = $_.Count; Lines = ($_.Group | Measure-Object Lines -Sum).Sum }
} | Sort-Object Lines -Descending | Format-Table -AutoSize

"Per type:"
$rows | Group-Object Type | ForEach-Object {
    [pscustomobject]@{ Type = $_.Name; Files = $_.Count; Lines = ($_.Group | Measure-Object Lines -Sum).Sum }
} | Sort-Object Lines -Descending | Format-Table -AutoSize

$total = ($rows | Measure-Object Lines -Sum).Sum
"Total: $($rows.Count) files, $total non-empty lines"
