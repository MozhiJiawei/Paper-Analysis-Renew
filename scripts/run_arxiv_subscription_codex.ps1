param(
    [switch]$PrintCommandOnly,
    [string]$CodexExe = "C:\Users\37274\AppData\Roaming\npm\codex.cmd"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IssueScript = Join-Path $ScriptDir "run_arxiv_github_issue_codex.ps1"

if ($PrintCommandOnly) {
    & $IssueScript -PrintCommandOnly -CodexExe $CodexExe
}
else {
    & $IssueScript -CodexExe $CodexExe
}
exit $LASTEXITCODE
