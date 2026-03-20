---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, documentation, quality, cli]
dependencies: []
---

# Narrow the schema-validation claim in the solution note

## Problem Statement

The new solution note describes `paper_analysis/shared/sample_loader.py` as if schema errors are broadly translated into `CliInputError`. The implementation only guarantees top-level shape checks (`list` for papers, `dict` for preferences) plus constructor-time `TypeError` handling. That is narrower than the current wording and can mislead future changes or reviews.

## Findings

- `paper_analysis/shared/sample_loader.py` checks that paper input is a list and each item is a dict, then constructs `Paper(**item)`.
- `load_preferences()` checks that preferences input is a dict, then constructs `PreferenceProfile(**raw)`.
- The code converts some malformed input cases into `CliInputError`, but it does not perform generic nested or field-level schema validation beyond constructor compatibility.
- The solution note currently says “结构错误会转成 `CliInputError`”, which reads broader than what the code actually enforces.

## Proposed Solutions

### Option 1: Tighten the wording to match the current implementation

**Approach:** Rephrase the note so it explicitly describes top-level type checks and constructor-field validation only.

**Pros:**
- Fastest fix
- Keeps the note accurate

**Cons:**
- Does not improve runtime validation

**Effort:** Small

**Risk:** Low

---

### Option 2: Expand the implementation to match the current wording

**Approach:** Add explicit schema validation for paper/preference fields and nested structures, then keep the stronger documentation claim.

**Pros:**
- Stronger user-facing guarantees
- Better failure consistency

**Cons:**
- More code and tests
- Broader behavioral change than this doc update implies

**Effort:** Medium

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
- `paper_analysis/shared/sample_loader.py`

**Related components:**
- CLI input validation
- Shared JSON loading
- Documentation accuracy

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md:63`
- `paper_analysis/shared/sample_loader.py:10`
- `paper_analysis/shared/sample_loader.py:26`

## Acceptance Criteria

- [ ] The solution note no longer implies broader schema guarantees than the code enforces
- [ ] If stronger validation is desired, the implementation and tests are updated first
- [ ] CLI input-validation documentation matches actual failure semantics

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Compared the new solution note with `sample_loader.py`
- Verified the code only guarantees top-level shape checks plus constructor-time validation
- Captured the mismatch as a documentation accuracy issue

**Learnings:**
- Solution notes need to distinguish “top-level shape validation” from full schema validation
- Overstated docs are costly because later work starts depending on guarantees the code never made
