param([switch]$SyncWiki)
$ErrorActionPreference = 'Stop'
$taskProject = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$taskPython = Join-Path $taskProject '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = (Get-Command python).Source }
$taskLock = Join-Path $taskProject 'code\runtime\weekly.lock'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $taskLock) | Out-Null
try { $taskHandle = [System.IO.File]::Open($taskLock, 'OpenOrCreate', 'ReadWrite', 'None') }
catch { throw '周报任务已经运行。' }
try {
    & $taskPython (Join-Path $taskProject 'code\cli.py') run
    if ($LASTEXITCODE -ne 0) { throw '周报生成失败，未执行同步。' }
    if ($SyncWiki) {
        $taskZone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
        $taskToday = [TimeZoneInfo]::ConvertTimeFromUtc([datetime]::UtcNow, $taskZone).Date
        $taskDays = (([int]$taskToday.DayOfWeek + 6) % 7) + 1
        $taskEnd = $taskToday.AddDays(-$taskDays)
        $taskThursday = $taskEnd.AddDays(-3)
        $taskWeek = [Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear($taskThursday, [Globalization.CalendarWeekRule]::FirstFourDayWeek, [DayOfWeek]::Monday)
        $taskName = '{0}第{1:00}周简报.md' -f $taskThursday.Year, $taskWeek
        & $taskPython (Join-Path $taskProject 'code\cli.py') sync-wiki --file (Join-Path $taskProject "report_add\week\$taskName")
        if ($LASTEXITCODE -ne 0) { throw '云文档同步失败。' }
    }
} finally { $taskHandle.Dispose() }

