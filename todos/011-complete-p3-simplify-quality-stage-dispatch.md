---
status: complete
priority: p3
issue_id: "011"
tags: [code-review, quality, simplicity, cli]
dependencies: []
---

# Simplify single-stage dispatch in `quality`

## Problem Statement

`handle_single_stage()` still linearly scans `QUALITY_STAGES` and retains an unknown-stage fallback branch, even though `register()` only exposes stage names from that same list. The current shape works, but it carries unreachable fallback code and unnecessary lookup logic.

## Findings

- `paper_analysis/cli/quality.py:58-64` iterates through `QUALITY_STAGES` to find a known stage.
- `paper_analysis/cli/quality.py:31-38` registers only those same stage names into argparse.
- Because argparse cannot hand `handle_single_stage()` an unknown stage from the CLI surface, the fallback failure message is effectively dead code.

## Proposed Solutions

### Option 1: Build a stage-name-to-command mapping once

**Approach:** Replace the search loop with a dict lookup keyed by stage name, and drop the unreachable fallback path.

**Pros:**
- Simpler control flow
- Makes the dispatch contract explicit

**Cons:**
- Slight refactor of the current list-based usage

**Effort:** Small

**Risk:** Low

---

### Option 2: Keep the current list but assert stage existence

**Approach:** Use a helper that resolves the stage once and raises if the code path becomes inconsistent.

**Pros:**
- Minimal structural change

**Cons:**
- Still keeps list scanning for a fixed-name dispatch case

**Effort:** Small

**Risk:** Low

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `paper_analysis/cli/quality.py`

**Related components:**
- CLI stage dispatch
- Quality command registration

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `paper_analysis/cli/quality.py:31-38`
- `paper_analysis/cli/quality.py:58-64`

## Acceptance Criteria

- [ ] Single-stage dispatch no longer scans `QUALITY_STAGES`
- [ ] Unreachable unknown-stage fallback is removed or converted into an internal invariant
- [ ] Existing single-stage commands still behave identically

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Compared CLI registration with runtime stage lookup
- Confirmed the unknown-stage fallback is not reachable through argparse

**Learnings:**
- This is a low-priority cleanup item rather than a correctness bug

### 2026-03-20 - Fix implemented

**By:** Codex

**Actions:**
- Replaced the linear single-stage lookup in `paper_analysis/cli/quality.py` with a runtime stage-name-to-command mapping helper
- Removed the unreachable unknown-stage fallback from `handle_single_stage()`
- Kept the command surface unchanged and verified the integration tests still pass

**Learnings:**
- 用运行时映射替代模块级缓存，可以同时保留简化后的分发路径和测试时对 `QUALITY_STAGES` 的可替换性
