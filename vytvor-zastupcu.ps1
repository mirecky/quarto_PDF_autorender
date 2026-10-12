# Vytvorí na ploche zástupcu „Quarto Studio“.
#   .\vytvor-zastupcu.ps1                      – pri spustení sa zobrazí výber priečinka
#   .\vytvor-zastupcu.ps1 -Folder "C:\cesta"   – vždy sa otvorí zadaný priečinok
#   .\vytvor-zastupcu.ps1 -Name "Diplomovka" -Folder "C:\...\diplomovka"
#   .\vytvor-zastupcu.ps1 -Icon "C:\...\moja-ikona.ico"   – vlastná ikona (.ico)
#   .\vytvor-zastupcu.ps1 -Console             – spúšťať s konzolovým oknom (diagnostika)
param(
    [string]$Folder = "",
    [string]$Name = "Quarto Studio",
    [string]$Icon = "",
    [switch]$Console
)

$ErrorActionPreference = "Stop"

# Spúšťač Pythonu bez konzoly: pyw.exe (Python Launcher) alebo pythonw.exe.
# Aliasy z Microsoft Store (WindowsApps) sa vynechávajú – zo zástupcu často nefungujú.
function Find-Exe([string[]]$names) {
    foreach ($n in $names) {
        foreach ($c in @(Get-Command $n -All -ErrorAction SilentlyContinue)) {
            if ($c.Source -and $c.Source -notmatch "\\WindowsApps\\") { return $c.Source }
        }
    }
    return $null
}

$folderArg = ""
if ($Folder) {
    $full = (Resolve-Path -LiteralPath $Folder).Path
    $folderArg = " `"$full`""
}

if ($Console) {
    $target = Join-Path $PSScriptRoot "qgui.bat"
    $arguments = $folderArg.Trim()
} else {
    $pyw = Find-Exe @("pyw")
    if ($pyw) {
        $target = $pyw; $arguments = "-3 -m qgui$folderArg"
    } else {
        $pythonw = Find-Exe @("pythonw")
        if (-not $pythonw) {
            $python = Find-Exe @("python", "py")
            if ($python) {
                $cand = Join-Path (Split-Path $python) "pythonw.exe"
                if (Test-Path $cand) { $pythonw = $cand }
            }
        }
        if ($pythonw) {
            $target = $pythonw; $arguments = "-m qgui$folderArg"
        } else {
            Write-Warning "pyw.exe ani pythonw.exe sa nenašli – zástupca použije qgui.bat s konzolou."
            $target = Join-Path $PSScriptRoot "qgui.bat"; $arguments = $folderArg.Trim()
        }
    }
}

$desktop = [Environment]::GetFolderPath("Desktop")   # funguje aj pri ploche v OneDrive
$path = Join-Path $desktop "$Name.lnk"
# Existujúci zástupca (napr. z Chromu/Edge) by si ponechal staré parametre – vytvoriť ho nanovo.
if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($path)
$lnk.TargetPath = $target
$lnk.Arguments = $arguments
$lnk.WorkingDirectory = $PSScriptRoot                 # odtiaľ sa načíta balík qgui
$lnk.WindowStyle = 1
if (-not $Icon) { $Icon = Join-Path $PSScriptRoot "assets\quarto.ico" }
if (Test-Path -LiteralPath $Icon) {
    $lnk.IconLocation = (Resolve-Path -LiteralPath $Icon).Path + ",0"
} else {
    Write-Warning "Ikona sa nenašla ($Icon), použije sa systémová."
    $lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,70"
}
$lnk.Description = "Úprava, náhľad a render Markdown/Quarto dokumentov"
$lnk.Save()

Write-Host "Zástupca vytvorený: $path"
Write-Host "  Cieľ:       $target"
Write-Host "  Argumenty:  $arguments"
Write-Host "  Spustiť v:  $PSScriptRoot"
Write-Host "Log aplikácie: $HOME\.qgui\qgui.log"
