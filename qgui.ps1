# Spustenie Quarto Studio v PowerShelli:  .\qgui.ps1 [PRIEČINOK]
# Ak PowerShell blokuje skripty: powershell -ExecutionPolicy Bypass -File .\qgui.ps1 C:\cesta
$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m qgui @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m qgui @args
} else {
    Write-Error "Python sa nenašiel. Nainštaluj ho z https://www.python.org/downloads/ (zaškrtni 'Add python.exe to PATH')."
}
