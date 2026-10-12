# Vytvorí na ploche zástupcu „Quarto Studio“.
#   .\vytvor-zastupcu.ps1                      – pri spustení sa zobrazí výber priečinka
#   .\vytvor-zastupcu.ps1 -Folder "C:\cesta"   – vždy sa otvorí zadaný priečinok
#   .\vytvor-zastupcu.ps1 -Name "Diplomovka" -Folder "C:\...\diplomovka"
param(
    [string]$Folder = "",
    [string]$Name = "Quarto Studio"
)

$desktop = [Environment]::GetFolderPath("Desktop")   # funguje aj pri ploche v OneDrive
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path $desktop "$Name.lnk"))
$lnk.TargetPath = Join-Path $PSScriptRoot "qgui.bat"
$lnk.WorkingDirectory = $PSScriptRoot
if ($Folder) {
    $full = (Resolve-Path -LiteralPath $Folder -ErrorAction Stop).Path
    $lnk.Arguments = "`"$full`""
}
$lnk.WindowStyle = 7                                  # minimalizované okno servera
$lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,70"
$lnk.Description = "Úprava, náhľad a render Markdown/Quarto dokumentov"
$lnk.Save()
Write-Host "Zástupca vytvorený: $(Join-Path $desktop "$Name.lnk")"
