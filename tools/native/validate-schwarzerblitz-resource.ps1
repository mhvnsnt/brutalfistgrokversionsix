param([Parameter(Mandatory=$true)][string]$CharacterDir)
$ErrorActionPreference="Stop"
$config=Join-Path $CharacterDir "Mesh1/config.txt"
$x=Get-ChildItem $CharacterDir -Recurse -Filter "*.x" | Select-Object -First 1
if(!(Test-Path $config)){throw "Missing Schwarzerblitz Mesh1/config.txt"}
if(!$x){throw "Missing DirectX .x skeletal mesh"}
$text=Get-Content $config -Raw
foreach($key in @("#MESH_FILENAME","#OUTFIT_NAME","#CHARACTER_NAME")){
  if($text -notmatch [regex]::Escape($key)){throw "Missing $key"}
}
if((Get-Item $x.FullName).Length -lt 1024){throw "Suspiciously small .x mesh"}
Write-Host "PASS native resource: $CharacterDir"
