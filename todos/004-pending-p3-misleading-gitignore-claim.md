---
status: pending
priority: p3
issue_id: "004"
tags: [code-review, documentation, trust, hygiene]
dependencies: []
---

# Correct the .gitignore hygiene claim in the solution note

## Problem Statement

The new solution note states that this change adds repository hygiene rules for `__pycache__/`, `*.py[cod]`, and `artifacts/`. That wording is misleading because the repository already ignores these paths, so the document reads like a completed hygiene change when it is only a narrative note.

## Findings

- `.gitignore` already contains `__pycache__/`, `*.py[cod]`, and `artifacts/`.
- The solution note presents them as newly added ignore rules and implies a repo-state change that is not present in this diff.
- This can confuse future reviewers into thinking the hygiene fix landed in code when only the documentation was added.

## Proposed Solutions

### Option 1: Rephrase the note to describe verification, not addition

**Approach:** Change the wording from "new .gitignore rules" to "existing ignore rules were verified" or similar.

**Pros:**
- Accurate
- No code changes required

**Cons:**
- Does not add any new behavior

**Effort:** Small

**Risk:** Low

---

### Option 2: Link the note to the actual hygiene change, if one exists

**Approach:** If a separate commit or branch added the ignore entries, reference that change explicitly.

**Pros:**
- Preserves historical traceability
- Prevents future confusion

**Cons:**
- Requires finding the real source of truth

**Effort:** Small

**Risk:** Low

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
- `.gitignore`

**Related components:**
- Documentation trustworthiness
- Repo hygiene claims

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- Current review target: `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`

## Acceptance Criteria

- [ ] The note no longer claims the ignore rules were newly added unless a code change is linked
- [ ] Any repository-hygiene statement matches the actual `.gitignore` state
- [ ] The wording is clear enough that future readers can tell this is a documentation record, not a code diff

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Compared the solution note against the current `.gitignore`
- Confirmed the ignore patterns were already present before this doc was added

**Learnings:**
- Documentation can drift into implying code changes that never happened
- This is low severity, but it is exactly the kind of trust leak that makes later reviews harder
