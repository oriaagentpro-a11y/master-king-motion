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
  @{ cmd = "python"; id = "Python.Python.3.12" },
  @{ cmd = "ffmpeg"; id = "Gyan.FFmpeg" },
  @{ cmd = "git";    id = "Git.Git" }
)
foreach ($t in $tools) {
  $ok = Get-Command $t.cmd -ErrorAction SilentlyContinue
  if ($t.cmd -eq "python" -and $ok) { & python -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>$null; $ok = ($LASTEXITCODE -eq 0) }
  if (-not $ok) {
    Write-Host "installation de $($t.id)"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      winget install --id $t.id -e --silent --accept-package-agreements --accept-source-agreements
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
      $choco = @{ "node" = "nodejs-lts"; "python" = "python312"; "ffmpeg" = "ffmpeg"; "git" = "git" }[$t.cmd]
      choco install -y --no-progress $choco
    } else { Write-Host "winget est absent : installez 'App Installer' depuis le Microsoft Store, puis relancez."; exit 1 }
    Refresh-Path
  }
}

Step "Moteur de rendu (Node : GSAP, Three.js, Playwright)"
Push-Location "$Here\engine"; npm install --no-audit --no-fund
Step "Chromium (rendu et mesures)"
npx --yes playwright install chromium; Pop-Location

Step "Outils d'analyse (Python)"
python -m pip install -q -r "$Here\requirements.txt"

Step "Modèle de transcription de la voix"
python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ.get('MK_WHISPER','small'), device='cpu', compute_type='int8'); print('modèle prêt')"

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
python "$Here\scripts\doctor.py"
if ($LASTEXITCODE -eq 0) { (Get-Date).ToUniversalTime().ToString("s") | Out-File "$Here\.installed" }
