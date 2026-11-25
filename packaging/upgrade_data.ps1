# Runs elevated before replacing the application. Never imports or rewrites SQLite rows.
param(
    [Parameter(Mandatory=$true)][ValidateSet('snapshot', 'restore', 'clear', 'detect')][string]$Mode,
    [string]$BackupRoot,
    [string]$ResultFile,
    [string]$InstallDir,
    # Used only by isolated Windows regression tests; production discovers real profiles.
    [string]$TestRoot
)
$ErrorActionPreference = 'Stop'
$DataName = '微机教室考试系统'

function Get-DataHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '') }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}

function Get-DataDirectories {
    if ($TestRoot) {
        return @((Join-Path $TestRoot "user/$DataName"), (Join-Path $TestRoot "other/$DataName"), (Join-Path $TestRoot "common/$DataName"))
    }
    $paths = @(
        (Join-Path ([Environment]::GetFolderPath('ApplicationData')) $DataName),
        (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) $DataName)
    )
    # Registry enumeration also covers profiles relocated outside C:\Users.
    Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' | ForEach-Object {
        $profile = (Get-ItemProperty $_.PSPath).ProfileImagePath
        if ($profile) {
            $paths += Join-Path ([Environment]::ExpandEnvironmentVariables($profile)) "AppData/Roaming/$DataName"
        }
    }
    # Older uninstallers enumerate these folders even if their profiles are not registered.
    $users = Join-Path $env:SystemDrive 'Users'
    if (Test-Path -LiteralPath $users) {
        Get-ChildItem -LiteralPath $users -Directory -Force | Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } | ForEach-Object {
            $paths += Join-Path $_.FullName "AppData/Roaming/$DataName"
        }
    }
    return @($paths | Sort-Object -Unique)
}

function Assert-NoLinks([string]$Path) {
    if ((Get-Item -LiteralPath $Path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Data directory is a link; upgrade stopped: $Path"
    }
    foreach ($item in Get-ChildItem -LiteralPath $Path -Recurse -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Linked data cannot be safely copied or cleared: $($item.FullName)"
        }
    }
}

function Stop-Application {
    if ($TestRoot) { return }
    $processes = @(Get-Process -Name ExamSystem -ErrorAction SilentlyContinue)
    foreach ($process in $processes) {
        & "$env:SystemRoot/System32/taskkill.exe" /F /T /PID $process.Id | Out-Null
    }
    if (Get-Process -Name ExamSystem -ErrorAction SilentlyContinue) {
        throw 'Could not stop ExamSystem; no data was changed.'
    }
}

try {
    $directories = @(Get-DataDirectories | Where-Object { Test-Path -LiteralPath $_ -PathType Container })
    if ($Mode -eq 'detect') {
        if ($ResultFile) { [IO.File]::WriteAllText($ResultFile, [string]$directories.Count) }
        exit 0
    }
    Stop-Application
    if ($Mode -eq 'snapshot') {
        if (-not $BackupRoot -or (Test-Path -LiteralPath $BackupRoot)) { throw 'A new backup directory is required.' }
        New-Item -ItemType Directory -Path $BackupRoot | Out-Null
        if (-not $TestRoot) {
            # Account/password hashes must not become readable to other local users.
            & "$env:SystemRoot/System32/icacls.exe" $BackupRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not restrict backup permissions.' }
        }
        $manifest = @()
        foreach ($source in $directories) {
            Assert-NoLinks $source
            if ($InstallDir -and ($source.TrimEnd('\') -eq $InstallDir.TrimEnd('\') -or $source.StartsWith($InstallDir.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase))) {
                throw "Data inside the installation directory requires manual migration: $source"
            }
            $slot = [string]$manifest.Count
            $destination = Join-Path $BackupRoot $slot
            New-Item -ItemType Directory -Path $destination | Out-Null
            $files = @()
            foreach ($file in Get-ChildItem -LiteralPath $source -Recurse -File -Force) {
                $relative = $file.FullName.Substring($source.TrimEnd('\', '/').Length + 1)
                $target = Join-Path $destination $relative
                New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $target -Force
                $hash = (Get-DataHash $file.FullName)
                if ((Get-DataHash $target) -ne $hash) { throw "Backup verification failed: $relative" }
                $files += @{ path = $relative; sha256 = $hash }
            }
            $manifest += @{ source = $source; slot = $slot; files = @($files) }
        }
        # Write only after all copies have succeeded. Includes SQLite WAL/journal files.
        @{ version = 1; directories = @($manifest) } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $BackupRoot 'manifest.json') -Encoding UTF8
    } elseif ($Mode -eq 'restore') {
        $manifest = Get-Content -LiteralPath (Join-Path $BackupRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        # Verify the entire snapshot before restoring any file.
        foreach ($entry in $manifest.directories) {
            foreach ($file in $entry.files) {
                $source = Join-Path (Join-Path $BackupRoot $entry.slot) $file.path
                if ((Get-DataHash $source) -ne $file.sha256) { throw "Damaged backup: $source" }
            }
        }
        foreach ($entry in $manifest.directories) {
            New-Item -ItemType Directory -Path $entry.source -Force | Out-Null
            Assert-NoLinks $entry.source
            foreach ($file in $entry.files) {
                $target = Join-Path $entry.source $file.path
                # New uninstallers preserve data in place: do not touch identical files.
                if ((Test-Path -LiteralPath $target -PathType Leaf) -and (Get-DataHash $target) -eq $file.sha256) { continue }
                New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
                Copy-Item -LiteralPath (Join-Path (Join-Path $BackupRoot $entry.slot) $file.path) -Destination $target -Force
                if ((Get-DataHash $target) -ne $file.sha256) { throw "Restore verification failed: $target" }
            }
        }
    } elseif ($Mode -eq 'clear') {
        # Validate every directory first, before deleting any of them.
        foreach ($directory in $directories) { Assert-NoLinks $directory }
        foreach ($directory in $directories) {
            Remove-Item -LiteralPath $directory -Recurse -Force
            if (Test-Path -LiteralPath $directory) { throw "Could not clear data: $directory" }
        }
    }
    exit 0
} catch {
    $message = $_.Exception.Message
    if ($ResultFile) { [IO.File]::WriteAllText($ResultFile, $message) }
    Write-Error $message -ErrorAction Continue
    exit 1
}
