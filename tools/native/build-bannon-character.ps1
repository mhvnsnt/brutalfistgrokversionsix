param(
    [Parameter(Mandatory=$false)][string]$CharacterId = "bannon",
    [string]$SourceGlb = "",
    [string]$OutRoot = "native/media/characters"
)

# Bannon canonical GLB → Schwarzerblitz DirectX .x character resource.
# Windows path (this file) and Linux path (build-bannon-character.sh) share
# the Python conversion boundary so the canonical GLB is never mutated.
# Assimp is optional; glb_to_directx_x.py emits the Irrlicht xof 0303txt
# templates FK_Character::loadMeshsAndEffects already loads via getMesh.

$ErrorActionPreference = "Stop"
$root = Resolve-Path "."
$bannon = Join-Path $root "BannonSource"
if (!(Test-Path $bannon)) { $bannon = Join-Path $root "vendor/Bannon" }

if ([string]::IsNullOrWhiteSpace($SourceGlb)) {
    $SourceGlb = Join-Path $root "native/source/BANNON.glb"
}
if (!(Test-Path $SourceGlb)) { throw "GLB not found: $SourceGlb  (REAL_GLB_ONLY — no procedural fallback)" }

$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python is required for the Bannon → .x conversion" }

Write-Host "0/7  Named-part Mixamo rig (open-source, rigid weights, no UniRig smear)"
& $py.Source "tools/native/rig_named_parts.py" --glb $SourceGlb --out "native/source/BANNON_mixamo_rigged.glb" --preview "native/qa/bannon-named-part-preview.png"
if ($LASTEXITCODE -ne 0) { throw "rig_named_parts failed" }
$SourceGlb = Join-Path $root "native/source/BANNON_mixamo_rigged.glb"


Write-Host "1/7  Convert $SourceGlb → DirectX .x"
& $py.Source "tools/native/glb_to_directx_x.py" --glb $SourceGlb --out $OutRoot --public "public/native"
if ($LASTEXITCODE -ne 0) { throw "glb_to_directx_x failed" }

Write-Host "2/7  Extract real GLB locomotion clips"
& $py.Source "tools/native/extract_preview_anims.py"
if ($LASTEXITCODE -ne 0) { throw "extract_preview_anims failed" }

Write-Host "3/7  Fetch real Git-LFS mocap FBX (no procedural fill-in)"
& $py.Source "tools/native/fetch_mocap_lfs.py"
if ($LASTEXITCODE -ne 0) { throw "fetch_mocap_lfs failed" }

Write-Host "4/7  Batch-export real FBX mocap through the animation bridge"
& $py.Source "tools/native/batch_export_mocap.py"
if ($LASTEXITCODE -ne 0) { throw "batch_export_mocap failed" }

Write-Host "5/7  Bind clips into engine animation names"
& $py.Source "tools/native/bind_engine_anims.py"
if ($LASTEXITCODE -ne 0) { throw "bind_engine_anims failed" }

Write-Host "6/7  Install chara_bannon into the Schwarzerblitz media tree"
& $py.Source "tools/native/install_into_engine.py"
if ($LASTEXITCODE -ne 0) { throw "install_into_engine failed" }

Write-Host "7/7  Rehearse smgr->getMesh on the installed .x"
& $py.Source "tools/native/engine_load_rehearsal.py"
if ($LASTEXITCODE -ne 0) { throw "engine_load_rehearsal failed" }

$mesh = Join-Path $root (Join-Path $OutRoot "chara_$CharacterId/Mesh1/BF_$CharacterId.x")
Write-Host "Built native resource for $CharacterId : $mesh"
Write-Host "Installed into schwarzerblitz_engine/bin/media/characters/chara_$CharacterId"
Write-Host "The Win32 executable loads this file via FK_Character::loadMeshsAndEffects → getMesh."
