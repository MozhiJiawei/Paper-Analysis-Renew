param(
    [switch]$PrintCommandOnly,
    [string]$CodexExe = "C:\Users\37274\AppData\Roaming\npm\codex.cmd"
)

$ErrorActionPreference = "Stop"

$RepoRoot = "D:\Git_Repo\Paper-Analysis-New"
$RepoFullName = "MozhiJiawei/Paper-Analysis-Renew"
$TimeZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("China Standard Time")
$NowShanghai = [System.TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $TimeZone)
$Yesterday = $NowShanghai.Date.AddDays(-1)
$SubscriptionDate = $Yesterday.ToString("yyyy-MM/MM-dd")

$RunStamp = $NowShanghai.ToString("yyyyMMdd-HHmmss")
$LogRoot = Join-Path $RepoRoot "artifacts\automations\arxiv-github-issue-codex\$RunStamp"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Prompt = @(
    "Run the daily arXiv report workflow in repository D:\Git_Repo\Paper-Analysis-New, then publish the result to a GitHub Issue in repository $RepoFullName.",
    "",
    "Network access is explicitly allowed. You may access the official arXiv API, external web pages or APIs, and GitHub. Do not use email or SMTP. Do not call --deliver-subscription.",
    "",
    "The Windows scheduled script has already computed yesterday in Asia/Shanghai as: $SubscriptionDate. Use this value as the CLI date argument.",
    "",
    "First run this stable repository CLI command:",
    "",
    "py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date $SubscriptionDate --fetch-all",
    "",
    "If this CLI command exits non-zero because arXiv returns HTTP 429, do not repeatedly retry and do not use email. Instead, check whether artifacts/e2e/arxiv/latest contains a usable fresh report. If usable artifacts exist, publish them to the GitHub Issue and explicitly note the HTTP 429 rate-limit condition in the issue.",
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
    Write-Host "Subscription date: $SubscriptionDate"
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
