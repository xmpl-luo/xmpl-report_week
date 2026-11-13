param([string]$TaskName = 'XMPL-Game-Weekly-Report', [switch]$SyncWiki)
$ErrorActionPreference = 'Stop'
$taskScript = Join-Path $PSScriptRoot 'run_weekly.ps1'
$taskZone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
if ([TimeZoneInfo]::Local.Id -ne $taskZone.Id) { throw '计划任务按系统本地时间运行。请先将系统时区设为北京时间，再注册。' }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw '同名任务已存在，请先检查现有任务。' }
$taskArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $taskScript + '"'
if ($SyncWiki) { $taskArguments += ' -SyncWiki' }
$taskAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArguments
$taskTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '10:15'
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Description '每周一北京时间10:15生成上一周游戏产品周报；不发送机器人消息'

