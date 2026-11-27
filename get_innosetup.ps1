# Inno Setup 6'yı sadece bu kullanıcı için sessizce kurar (yönetici izni gerekmez). build.bat çağırır.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$out = Join-Path $env:TEMP "innosetup_kurulum.exe"
Write-Host "Inno Setup indiriliyor..."
try {
  Invoke-WebRequest -UseBasicParsing "https://jrsoftware.org/download.php/is.exe" -OutFile $out
} catch {
  # jrsoftware.org unreachable: same official release from the vendor's GitHub
  Write-Host "jrsoftware.org erisilemedi, GitHub'dan indiriliyor..."
  Invoke-WebRequest -UseBasicParsing "https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe" -OutFile $out
}
$sig = Get-AuthenticodeSignature $out
if ($sig.Status -ne "Valid") { Remove-Item $out -Force; throw "Inno Setup imzasi gecersiz: $($sig.Status)" }
Start-Process -FilePath $out -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER" -Wait
Remove-Item $out -Force
Write-Host "Inno Setup hazir."
