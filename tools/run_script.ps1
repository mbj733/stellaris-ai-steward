param(
    [Parameter(Mandatory=$true)][string]$Script
)
# ===== 配置区：改成你本机的路径 =====
$GhidraHome     = "D:\ghidra"                     # Ghidra 安装目录
$GhidraProject  = "D:\ghidra\projects"            # Ghidra 项目目录（先建好 Stellaris 项目并导入 stellaris.exe）
$JavaHome       = ""                              # JDK 路径（留空则用 Ghidra 自带要求的环境变量）
# ===================================

chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($JavaHome -ne "") { $env:JAVA_HOME = $JavaHome }
$env:GHIDRA_INSTALL_DIR = $GhidraHome
$src  = Join-Path $PSScriptRoot "ghidra_scripts"
$dst  = Join-Path $GhidraHome "ghidra_scripts"
if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst | Out-Null }
Copy-Item (Join-Path $src $Script) (Join-Path $dst $Script) -Force
$log = Join-Path $PSScriptRoot ("_ghidra_" + $Script + ".log")
& "$GhidraHome\support\analyzeHeadless.bat" $GhidraProject Stellaris -process stellaris.exe -noanalysis -scriptPath $dst -postScript $Script *> $log
"exit=$LASTEXITCODE  log=$log"
Get-Content $log -Tail 60
