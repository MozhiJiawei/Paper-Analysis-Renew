---
status: complete
priority: p3
issue_id: "010"
tags: [code-review, quality, simplicity, templates]
dependencies: []
---

# Centralize status-label mapping for the CI HTML report

## Problem Statement

Status-label mapping is split between Python and the Jinja2 template. That duplicates contract logic, increases drift risk, and weakens the intended separation where Python prepares view data and the template focuses on presentation.

## Findings

- `paper_analysis/services/ci_html_writer.py:18-23` defines `STATUS_LABELS`.
- `paper_analysis/services/ci_html_writer.py:90-97` already precomputes `status_label` for stage results.
- `paper_analysis/templates/ci_report.html.j2:158` embeds a second hard-coded status map for e2e sections instead of consuming a precomputed field.

## Proposed Solutions

### Option 1: Precompute `status_label` for e2e sections in Python

**Approach:** Extend the serialized e2e section payload with `status_label`, then remove the inline template map.

**Pros:**
- Keeps business/state mapping in Python
- Simplifies the template

**Cons:**
- Minor service-layer touch

**Effort:** Small

**Risk:** Low

---

### Option 2: Move all status-label logic into the template

**Approach:** Remove Python-side labels and make the template fully responsible for presentation labels.

**Pros:**
- One place for rendered wording

**Cons:**
- Pushes data-contract logic into the view
- Conflicts with the current design direction

**Effort:** Small

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `paper_analysis/services/ci_html_writer.py`
- `paper_analysis/templates/ci_report.html.j2`

**Related components:**
- CI HTML rendering contract
- Status presentation

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `paper_analysis/services/ci_html_writer.py:18-23`
- `paper_analysis/services/ci_html_writer.py:69`
- `paper_analysis/templates/ci_report.html.j2:158`

## Acceptance Criteria

- [ ] Status labels are defined in one place only
- [ ] The template consumes prepared display fields instead of duplicating state mapping
- [ ] Tests still cover passed, failed, skipped, and missing states

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Compared Python-side serialized stage payloads with template-side e2e rendering
- Found duplicated status wording logic across layers

**Learnings:**
- This is not user-visible breakage today, but it is a likely drift point as statuses evolve

### 2026-03-20 - Fix implemented

**By:** Codex

**Actions:**
- Added `status_label` to the serialized e2e section payload in `paper_analysis/services/ci_html_writer.py`
- Removed the inline e2e status-label mapping from `paper_analysis/templates/ci_report.html.j2`
- Kept template rendering focused on display-only fields prepared by Python

**Learnings:**
- Once the service layer owns the view contract, template logic stays noticeably easier to read and evolve
