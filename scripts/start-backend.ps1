param(
    [Alias("Host")]
    [string]$BackendHost = "127.0.0.1",

    [int]$Port = 8000,

    [switch]$NoReload,

    [switch]$Help
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$uncPrefix = "\\wsl.localhost\"

if (-not $repoRoot.StartsWith($uncPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "This script must live under \\wsl.localhost\<Distro>\... so it can delegate to WSL. From a normal Windows path, run scripts/start-backend.sh inside WSL instead."
    exit 1
}

$relativePath = $repoRoot.Substring($uncPrefix.Length)
$parts = $relativePath -split "\\", 2

if ($parts.Count -lt 2 -or [string]::IsNullOrWhiteSpace($parts[0]) -or [string]::IsNullOrWhiteSpace($parts[1])) {
    Write-Error "Could not parse WSL UNC repo path: $repoRoot"
    exit 1
}

$distro = $parts[0]
$linuxRepoRoot = "/" + ($parts[1] -replace "\\", "/")

if ($Help) {
    & wsl.exe -d $distro --cd $linuxRepoRoot -- ./scripts/start-backend.sh --help
    exit $LASTEXITCODE
}

$scriptArgs = @("--host", $BackendHost, "--port", "$Port")
if ($NoReload) {
    $scriptArgs += "--no-reload"
}

& wsl.exe -d $distro --cd $linuxRepoRoot -- ./scripts/start-backend.sh @scriptArgs
exit $LASTEXITCODE
