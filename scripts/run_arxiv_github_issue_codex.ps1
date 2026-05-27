param(
    [switch]$PrintCommandOnly,
    [string]$CodexExe = "C:\Users\37274\AppData\Roaming\npm\codex.cmd"
)

$ErrorActionPreference = "Stop"

$RepoRoot = "D:\Git_Repo\Paper-Analysis-New"
$RepoFullName = "MozhiJiawei/Paper-Analysis-Renew"
$TimeZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("China Standard Time")
$NowShanghai = [System.TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $TimeZone)
$PaperDateLagDays = 4
$PaperDate = $NowShanghai.Date.AddDays(-$PaperDateLagDays)
$SubscriptionDate = $PaperDate.ToString("yyyy-MM/MM-dd")

$RunStamp = $NowShanghai.ToString("yyyyMMdd-HHmmss")
$LogRoot = Join-Path $RepoRoot "artifacts\automations\arxiv-github-issue-codex\$RunStamp"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Prompt = @(
    "Run the daily arXiv report workflow in repository D:\Git_Repo\Paper-Analysis-New, then publish the result to a GitHub Issue in repository $RepoFullName.",
    "",
    "Network access is explicitly allowed. Use the Gmail arXiv subscription email source, external web pages or APIs needed by the repository workflow, local GROBID if available, and GitHub. Do not force the arXiv API source. Do not call --deliver-subscription.",
    "",
    "The Windows scheduled script has computed the arXiv paper-content date in Asia/Shanghai as: $SubscriptionDate. Use this value as the CLI date argument.",
    "This is intentionally not the same as the email received date: arXiv subscription emails lag the paper Date fields. The current automation uses a $PaperDateLagDays-day lag from the Asia/Shanghai run date so that the requested paper date is present in the latest available subscription email.",
    "",
    "First run this stable repository CLI command:",
    "",
    "py -m paper_analysis.cli.main arxiv report --subscription-date $SubscriptionDate --fetch-all",
    "",
    "The CLI defaults to subscription-email when --subscription-date is provided. If this command exits non-zero, do not drift to --source-mode subscription-api. Inspect stdout/stderr and report the concrete Gmail, GROBID, embedding, or GitHub failure reason.",
    "",
    "After the command finishes, read the generated artifacts under artifacts/e2e/arxiv/latest, especially summary.md, result.json, result.csv, and stdout.txt.",
    "",
    "Create or update a GitHub Issue in $RepoFullName to carry this report. Use the GitHub issue creation capability available in the Codex session. If an open issue already exists for subscription date $SubscriptionDate, add a comment with the latest run result instead of creating a duplicate. Otherwise create a new issue.",
    "",
    "Issue title format: arXiv report $SubscriptionDate",
    "",
    "Issue body requirements:",
    "- Include subscription date, fetched paper count, recommended paper count, generation time, and local artifact paths.",
    "- Include the full Markdown summary from artifacts/e2e/arxiv/latest/summary.md, or a concise high-signal excerpt if GitHub body length would be too large.",
    "- Mention that email delivery is intentionally disabled and GitHub Issue is the delivery channel.",
    "- If report generation or GitHub issue creation fails, report the concrete failure reason and next step.",
    "",
    "Use the repository's existing stable CLI only. Do not create a new CLI namespace."
) -join [Environment]::NewLine

$PromptPath = Join-Path $LogRoot "prompt.txt"
$JsonLogPath = Join-Path $LogRoot "codex-events.jsonl"
$StderrLogPath = Join-Path $LogRoot "codex-stderr.txt"
$LastMessagePath = Join-Path $LogRoot "last-message.txt"
$ExitCodePath = Join-Path $LogRoot "exit-code.txt"

Set-Content -Path $PromptPath -Value $Prompt -Encoding UTF8

$Arguments = @(
    "--dangerously-bypass-approvals-and-sandbox",
    "--sandbox", "danger-full-access",
    "--search",
    "-c", "shell_environment_policy.inherit=all",
    "-C", $RepoRoot,
    "exec",
    "--json",
    "--output-last-message", $LastMessagePath,
    "-"
)

if ($PrintCommandOnly) {
    Write-Host "Codex executable: $CodexExe"
    Write-Host "Working directory: $RepoRoot"
    Write-Host "GitHub repository: $RepoFullName"
    Write-Host "Paper-content date: $SubscriptionDate"
    Write-Host "Paper date lag days: $PaperDateLagDays"
    Write-Host "Prompt path: $PromptPath"
    Write-Host "JSON log path: $JsonLogPath"
    Write-Host "Last message path: $LastMessagePath"
    Write-Host "Command:"
    Write-Host "`"$CodexExe`" $($Arguments -join ' ')"
    exit 0
}

Push-Location $RepoRoot
try {
    $Process = Start-Process `
        -FilePath $CodexExe `
        -ArgumentList $Arguments `
        -RedirectStandardInput $PromptPath `
        -RedirectStandardOutput $JsonLogPath `
        -RedirectStandardError $StderrLogPath `
        -NoNewWindow `
        -Wait `
        -PassThru
    $ExitCode = $Process.ExitCode

    if ($ExitCode -ne 0 -and (Test-Path $LastMessagePath)) {
        $LastMessage = Get-Content -Path $LastMessagePath -Raw -Encoding UTF8
        if ($LastMessage -match "github\.com/.+/issues/\d+" -or $LastMessage -match "Published the report to GitHub Issue") {
            $ExitCode = 0
        }
    }

    Set-Content -Path $ExitCodePath -Value $ExitCode -Encoding UTF8
    exit $ExitCode
}
finally {
    Pop-Location
}
