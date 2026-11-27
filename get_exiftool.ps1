# exiftool'un Windows sürümünü indirip bu klasöre koyar (build.bat çağırır).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
  $ver = (Invoke-WebRequest -UseBasicParsing "https://exiftool.org/ver.txt").Content.Trim()
  $zip = "exiftool-$ver`_64.zip"
  Write-Host "exiftool $ver indiriliyor..."
  Invoke-WebRequest -UseBasicParsing "https://exiftool.org/$zip" -OutFile $zip
} catch {
  # exiftool.org unreachable: official SourceForge mirror of the same release
  Write-Host "exiftool.org erisilemedi, SourceForge'dan indiriliyor..."
  $rss = (Invoke-WebRequest -UseBasicParsing "https://sourceforge.net/projects/exiftool/rss?path=/").Content
  $ver = ([regex]::Matches($rss, 'exiftool-([\d.]+)_64\.zip') | ForEach-Object { [version]$_.Groups[1].Value } | Sort-Object | Select-Object -Last 1).ToString()
  $zip = "exiftool-$ver`_64.zip"
  Write-Host "exiftool $ver indiriliyor..."
  Invoke-WebRequest -UseBasicParsing -UserAgent "Wget" "https://sourceforge.net/projects/exiftool/files/$zip/download" -OutFile $zip
}
Expand-Archive $zip -DestinationPath "_exiftool_tmp" -Force
$exe = Get-ChildItem "_exiftool_tmp" -Recurse -Filter "exiftool*.exe" | Select-Object -First 1
Copy-Item $exe.FullName "exiftool.exe" -Force
if (Test-Path "exiftool_files") { Remove-Item "exiftool_files" -Recurse -Force }
Copy-Item (Join-Path $exe.DirectoryName "exiftool_files") "exiftool_files" -Recurse
Remove-Item "_exiftool_tmp" -Recurse -Force
Remove-Item $zip -Force
Write-Host "exiftool hazir."
