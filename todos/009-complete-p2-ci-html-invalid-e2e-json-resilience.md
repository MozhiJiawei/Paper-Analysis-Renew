---
status: complete
priority: p2
issue_id: "009"
tags: [code-review, quality, resilience, artifacts, e2e]
dependencies: []
---

# Keep CI HTML generation resilient to corrupted e2e JSON

## Problem Statement

The CI HTML writer only treats a missing `result.json` as recoverable. If an e2e artifact exists but contains truncated or invalid JSON, `quality local-ci` raises `JSONDecodeError` while trying to build the review page, and the HTML artifact is not produced.

## Findings

- `paper_analysis/services/ci_html_writer.py:111` reads and parses `result.json` without handling malformed JSON.
- `paper_analysis/cli/quality.py:43-52` calls the HTML writer during both success and failure paths, so this exception aborts the final review artifact creation.
- The documented behavior in `docs/engineering/testing-and-quality.md` says HTML should still be generated as much as possible, including degraded states such as missing artifacts.

## Proposed Solutions

### Option 1: Treat malformed `result.json` as a degraded `missing` or `failed` section

**Approach:** Catch `JSONDecodeError` and return an `E2EReportSection` with a note explaining that the structured payload is unreadable, while still showing `summary.md` and `stdout.txt`.

**Pros:**
- Preserves the HTML review page
- Matches the documented degraded-mode behavior

**Cons:**
- Requires defining whether malformed JSON is labeled `missing` or `failed`

**Effort:** Small

**Risk:** Low

---

### Option 2: Validate report JSON before HTML generation and rewrite a safe fallback payload

**Approach:** Add a validation step that normalizes unreadable files into a minimal safe structure.

**Pros:**
- Centralizes artifact contract handling

**Cons:**
- More invasive than necessary for the immediate bug

**Effort:** Medium

**Risk:** Low to Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `paper_analysis/services/ci_html_writer.py`
- `tests/unit/test_ci_html_writer.py`
- `tests/integration/test_quality_html.py`

**Related components:**
- e2e artifact loading
- HTML review page fallback behavior
- `quality local-ci`

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `paper_analysis/services/ci_html_writer.py:98-121`
- `paper_analysis/cli/quality.py:43-52`
- `docs/engineering/testing-and-quality.md`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`

## Acceptance Criteria

- [ ] Malformed `artifacts/e2e/<source>/latest/result.json` does not crash `quality local-ci`
- [ ] `local-ci-latest.html` is still generated when one e2e JSON artifact is corrupted
- [ ] The affected e2e section clearly reports that the structured payload could not be parsed
- [ ] Regression tests cover invalid JSON and missing JSON separately

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Reviewed the e2e artifact loader and its error handling
- Traced the HTML generation call path from `quality local-ci`
- Identified an unhandled malformed-JSON failure mode

**Learnings:**
- The current implementation degrades cleanly only when the file is absent, not when it is present but unreadable
- This is important because partial artifact writes are realistic after interrupted runs

### 2026-03-20 - Fix implemented

**By:** Codex

**Actions:**
- Updated `paper_analysis/services/ci_html_writer.py` to catch `json.JSONDecodeError` when loading `result.json`
- Returned a degraded e2e section with `failed` status and an explicit note instead of aborting HTML generation
- Added unit and integration tests covering malformed JSON while still asserting `local-ci-latest.html` is generated
- Re-ran targeted and full quality checks

**Learnings:**
- “尽量生成 HTML” 需要把“文件缺失”和“文件损坏”都纳入同一套降级语义
