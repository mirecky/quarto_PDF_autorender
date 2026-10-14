# Zaregistruje Quarto Studio ako aplikáciu na otváranie súborov .md a .qmd
# (iba pre aktuálneho používateľa, bez práv správcu).
#
#   powershell -ExecutionPolicy Bypass -File .\nastav-predvolenu-aplikaciu.ps1
#   powershell -ExecutionPolicy Bypass -File .\nastav-predvolenu-aplikaciu.ps1 -Remove
#
# .qmd sa nastaví ako predvolené priamo. Pri .md si Windows predvolenú aplikáciu
# chráni – po spustení skriptu ju potvrď raz ručne: pravé tlačidlo na .md →
# Otvoriť pomocou → Vybrať inú aplikáciu → Quarto Studio → Vždy.
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$progId  = "QuartoStudio.Document"
$classes = "HKCU:\Software\Classes"
$exts    = @(".md", ".qmd", ".markdown", ".rmd")

function Notify-Shell {
    $sig = '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, uint f, IntPtr a, IntPtr b);'
    $t = Add-Type -MemberDefinition $sig -Name Shell -Namespace QuartoStudio -PassThru -ErrorAction SilentlyContinue
    if ($t) { $t::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero) }  # SHCNE_ASSOCCHANGED
}

if ($Remove) {
    Remove-Item -Path "$classes\$progId" -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($e in $exts) {
        Remove-ItemProperty -Path "$classes\$e\OpenWithProgids" -Name $progId -ErrorAction SilentlyContinue
        $k = Get-Item -Path "$classes\$e" -ErrorAction SilentlyContinue
        if ($k -and $k.GetValue("") -eq $progId) { Set-ItemProperty -Path "$classes\$e" -Name "(default)" -Value "" }
    }
    Notify-Shell
    Write-Host "Registrácia Quarto Studio bola odstránená."
    return
}

# Spúšťač bez konzoly: pyw.exe (Python Launcher) alebo pythonw.exe (bez aliasov z WindowsApps).
$launcher = $null
foreach ($n in @("pyw", "pythonw")) {
    foreach ($c in @(Get-Command $n -All -ErrorAction SilentlyContinue)) {
        if ($c.Source -and $c.Source -notmatch "\\WindowsApps\\") { $launcher = $c.Source; break }
    }
    if ($launcher) { break }
}
if (-not $launcher) { throw "Nenašiel sa pyw.exe ani pythonw.exe. Nainštaluj Python z python.org." }

$script = Join-Path $PSScriptRoot "qgui_start.pyw"
$icon   = Join-Path $PSScriptRoot "assets\quarto.ico"
if (-not (Test-Path $script)) { throw "Chýba $script – spusti najprv git pull." }
$command = "`"$launcher`" `"$script`" `"%1`""

# ProgID
New-Item -Path "$classes\$progId" -Force | Out-Null
Set-ItemProperty -Path "$classes\$progId" -Name "(default)" -Value "Dokument Markdown/Quarto"
New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "$classes\$progId\DefaultIcon" -Name "(default)" -Value "$icon,0"
New-Item -Path "$classes\$progId\Application" -Force | Out-Null
Set-ItemProperty -Path "$classes\$progId\Application" -Name "ApplicationName" -Value "Quarto Studio"
Set-ItemProperty -Path "$classes\$progId\Application" -Name "ApplicationIcon" -Value "$icon,0"
New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$classes\$progId\shell\open" -Name "FriendlyAppName" -Value "Quarto Studio"
Set-ItemProperty -Path "$classes\$progId\shell\open\command" -Name "(default)" -Value $command

foreach ($e in $exts) {
    New-Item -Path "$classes\$e\OpenWithProgids" -Force | Out-Null
    New-ItemProperty -Path "$classes\$e\OpenWithProgids" -Name $progId -Value "" -PropertyType String -Force | Out-Null
    # Ako predvolené nastaviť iba tam, kde nič iné predvolené nie je (typicky .qmd).
    $current = (Get-Item -Path "$classes\$e").GetValue("")
    if (-not $current) { Set-ItemProperty -Path "$classes\$e" -Name "(default)" -Value $progId }
}
Notify-Shell

Write-Host "Quarto Studio je zaregistrované pre: $($exts -join ', ')"
Write-Host "  Príkaz: $command"
Write-Host ""
Write-Host "Ak sa .md stále otvára v inej aplikácii: pravé tlačidlo na súbor .md →"
Write-Host "Otvoriť pomocou → Vybrať inú aplikáciu → Quarto Studio → Vždy."
