---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, security, documentation, quality, artifacts]
dependencies: []
---

# Add a redaction and retention note for quality-stage artifacts

## Problem Statement

The quality pipeline captures combined stdout and stderr from every stage and writes the raw output to `artifacts/quality/*-latest.txt`. The new solution note describes this as a stability improvement, but it does not mention any redaction, retention limit, or secret-handling policy.

## Findings

- `paper_analysis/cli/quality.py` captures `stdout` and `stderr`, concatenates them, and writes the result directly to a file.
- The solution note treats the artifact as safe and deterministic, but does not call out that test output can contain environment details, file paths, tokens, or other sensitive strings.
- On shared machines or in CI artifact storage, this can persist data that should not be retained or published.

## Proposed Solutions

### Option 1: Add explicit redaction before artifact write

**Approach:** Scrub obvious secrets and environment-derived values from captured output before writing the artifact.

**Pros:**
- Reduces leakage risk
- Keeps artifacts more broadly shareable

**Cons:**
- May hide useful debugging context
- Needs careful pattern selection

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Make the artifact local-only and short-lived

**Approach:** Keep the current capture behavior, but document that the artifact is ephemeral and should not be uploaded or committed.

**Pros:**
- Minimal code change
- Preserves full debug output

**Cons:**
- Still exposes raw sensitive content on disk
- Depends on operator discipline

**Effort:** Small

**Risk:** Medium

---

### Option 3: Separate safe summary from full raw logs

**Approach:** Write a sanitized summary to the standard artifact path and keep raw logs behind an opt-in debug path.

**Pros:**
- Balances safety and debuggability
- Safer default for CI and local runs

**Cons:**
- More implementation work

**Effort:** Medium

**Risk:** Low to Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `paper_analysis/cli/quality.py`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`

**Related components:**
- Quality pipeline artifacts
- CI output retention
- Secret exposure in logs

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `paper_analysis/cli/quality.py:64-75`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md:23-24`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md:78-85`

## Acceptance Criteria

- [ ] The solution note warns that raw stage output may contain sensitive data
- [ ] The artifact retention policy is documented clearly
- [ ] If redaction is implemented, tests verify secrets are not written to disk
- [ ] The quality pipeline behavior is described accurately for local and CI use

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Reviewed `quality.py` artifact-writing behavior
- Compared it with the new solution note
- Identified that raw subprocess output is persisted without a redaction policy

**Learnings:**
- The current implementation is convenient for debugging, but the docs should not imply that the artifact is inherently safe
- This is the higher-risk issue because it can persist sensitive runtime output
