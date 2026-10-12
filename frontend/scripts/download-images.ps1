# Download the photo originals listed in scripts/image-sources.json into the
# git-ignored .image-src/ folder (D23). Skips files already present, waits
# between requests, and stops at the first "too many requests" answer, so it
# never hammers Wikimedia Commons. Run it again later to continue.
#
# Wikimedia's User-Agent policy asks for contact details; pass yours:
#   powershell -File scripts/download-images.ps1 -Contact "you@example.com"
# Then optimise: npm run images:optimise

param(
  [Parameter(Mandatory = $true)][string]$Contact,
  [int]$DelaySeconds = 10
)

$ProgressPreference = 'SilentlyContinue'   # Windows PowerShell 5.1 downloads crawl with the progress bar on
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root '.image-src'
New-Item -ItemType Directory -Force $dest | Out-Null
$sources = Get-Content (Join-Path $root 'scripts\image-sources.json') -Raw | ConvertFrom-Json
$userAgent = "VRMS-image-download/1.0 ($Contact)"

foreach ($s in $sources) {
  $out = Join-Path $dest ($s.id + '.jpg')
  if (Test-Path $out) { continue }
  Start-Sleep -Seconds $DelaySeconds
  try {
    Invoke-WebRequest -Uri $s.download -OutFile $out -UserAgent $userAgent -UseBasicParsing -TimeoutSec 90
    Write-Output "downloaded $($s.id)"
  } catch {
    if (Test-Path $out) { Remove-Item $out }
    if ($_.Exception.Message -match '429') {
      Write-Output "Stopped: the server asked to slow down (429) at $($s.id). Run again later."
      break
    }
    Write-Output "failed $($s.id): $($_.Exception.Message)"
  }
}
$missing = @($sources | Where-Object { -not (Test-Path (Join-Path $dest ($_.id + '.jpg'))) })
Write-Output "present: $($sources.Count - $missing.Count) of $($sources.Count)"
