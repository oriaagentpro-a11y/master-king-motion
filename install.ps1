# Installation COMPLÈTE et automatique de master-king-motion sous Windows. Aucune question posée.
# Lancer :  powershell -ExecutionPolicy Bypass -File install.ps1
# Installe : Node.js LTS, Python 3.12, FFmpeg, Git (via winget si absents), modules Node, Chromium, modules Python,
# modèle de transcription, Blender 4.2 LTS portable dans blender\app\, puis diagnostic avec rendu de test.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
function Step($t) { Write-Host "`n== $t ==" }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

Step "Outils système"
$tools = @(
  @{ cmd = "node";   id = "OpenJS.NodeJS.LTS" },
  @{ cmd = "ffmpeg"; id = "Gyan.FFmpeg" },
  @{ cmd = "git";    id = "Git.Git" }
)
foreach ($t in $tools) {
  $ok = Get-Command $t.cmd -ErrorAction SilentlyContinue
  if (-not $ok) {
    Write-Host "installation de $($t.id)"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      winget install --id $t.id -e --silent --accept-package-agreements --accept-source-agreements
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
      $choco = @{ "node" = "nodejs-lts"; "ffmpeg" = "ffmpeg"; "git" = "git" }[$t.cmd]
      choco install -y --no-progress $choco
    } else { Write-Host "winget est absent : installez 'App Installer' depuis le Microsoft Store, puis relancez."; exit 1 }
    Refresh-Path
  }
}

Step "Python 3.9 à 3.13 (les modules de calcul n'existent pas encore pour les versions plus récentes)"
function Find-Py {
  $ErrorActionPreference = "Continue"   # py -3.x absent écrit sur stderr : ne pas en faire une erreur fatale
  $rec = "$Here\.python"
  $cands = @()
  if (Test-Path $rec) { $cands += (Get-Content $rec -Raw).Trim() }
  foreach ($v in "3.12", "3.11", "3.13", "3.10") {
    if (Get-Command py -ErrorAction SilentlyContinue) { $p = (& py "-$v" -c "import sys; print(sys.executable)" 2>$null); if ($LASTEXITCODE -eq 0 -and $p) { $cands += $p.Trim() } }
    $cands += "$env:LOCALAPPDATA\Programs\Python\Python$($v.Replace('.',''))\python.exe"
  }
  $g = Get-Command python -ErrorAction SilentlyContinue; if ($g) { $cands += $g.Source }
  foreach ($c in $cands) {
    if ($c -and (Test-Path $c)) {
      & $c -c "import sys; sys.exit(not ((3, 9) <= sys.version_info[:2] <= (3, 13)))" 2>$null
      if ($LASTEXITCODE -eq 0) { return $c }
    }
  }
  return $null
}
$Py = Find-Py
if (-not $Py) {
  Write-Host "installation de Python 3.12"
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
  } elseif (Get-Command choco -ErrorAction SilentlyContinue) { choco install -y --no-progress python312 }
  else { Write-Host "winget est absent : installez 'App Installer' depuis le Microsoft Store, puis relancez."; exit 1 }
  Refresh-Path; $Py = Find-Py
  if (-not $Py) { Write-Host "Python 3.9-3.13 introuvable après installation"; exit 1 }
}
Set-Content -Path "$Here\.python" -Value $Py -NoNewline   # chaque script se relance avec ce Python (scripts\_mkpy.py)
Write-Host "Python : $Py"

Step "Moteur de rendu (Node : GSAP, Three.js, Playwright)"
Push-Location "$Here\engine"; npm install --no-audit --no-fund
Step "Chromium (rendu et mesures)"
npx --yes playwright install chromium; Pop-Location

Step "Outils d'analyse (Python)"
& $Py -m pip install -q -r "$Here\requirements.txt"

Step "Modèle de transcription de la voix"
& $Py -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ.get('MK_WHISPER','small'), device='cpu', compute_type='int8'); print('modèle prêt')"

Step "Polices libres courantes (≈ 30 familles : Inter, Poppins, Montserrat…)"
$Fonts = Join-Path $HOME ".cache\reverse-motion\google-fonts"
$Fams = "inter poppins montserrat roboto opensans lato oswald raleway playfairdisplay dmsans spacegrotesk manrope plusjakartasans sora bebasneue anton archivo worksans rubik nunito urbanist outfit syne unbounded lexend barlow figtree onest instrumentsans dmserifdisplay".Split(" ") | ForEach-Object { "ofl/$_" }
try {
  if (-not (Test-Path "$Fonts\.git")) { git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google/fonts.git $Fonts }
  Push-Location $Fonts; git sparse-checkout set @Fams; Pop-Location
} catch { Write-Host "(polices non téléchargées : elles le seront au prochain lancement)" }

Step "Blender 4.2 LTS (3D photoréaliste, Cycles)"
$App = "$Here\blender\app"
if (-not (Test-Path "$App\blender.exe")) {
  $V = "4.2.3"; $Url = "https://download.blender.org/release/Blender4.2/blender-$V-windows-x64.zip"
  $Tmp = Join-Path $env:TEMP "mkm-blender"; New-Item -ItemType Directory -Force $Tmp | Out-Null
  Write-Host "téléchargement de Blender $V (≈ 400 Mo) : $Url"
  Invoke-WebRequest -Uri $Url -OutFile "$Tmp\b.zip"
  Expand-Archive -Force "$Tmp\b.zip" $Tmp
  New-Item -ItemType Directory -Force $App | Out-Null
  Copy-Item -Recurse -Force "$Tmp\blender-$V-windows-x64\*" $App
  Remove-Item -Recurse -Force $Tmp
}
& "$App\blender.exe" --version | Select-Object -First 1

Step "Diagnostic"
& $Py "$Here\scripts\doctor.py"
if ($LASTEXITCODE -eq 0) { (Get-Date).ToUniversalTime().ToString("s") | Out-File "$Here\.installed" }
