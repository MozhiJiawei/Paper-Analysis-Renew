---
status: complete
priority: p1
issue_id: "008"
tags: [code-review, security, quality, html, artifacts]
dependencies: []
---

# Enable HTML escaping for the CI report template

## Problem Statement

The new CI review page renders untrusted report content into a browser-facing HTML file, but the Jinja2 environment does not actually enable autoescaping for the `.html.j2` template. A paper title, reason, or stage output containing HTML can therefore execute as script when someone opens `artifacts/quality/local-ci-latest.html`.

## Findings

- `paper_analysis/services/ci_html_writer.py:84` uses `select_autoescape(("html", "xml"))`.
- The active template file is `paper_analysis/templates/ci_report.html.j2`, and Jinja2 does not treat that filename as autoescaped under the current configuration.
- The template renders multiple untrusted fields directly into the page, including stage summaries, stage output, `summary.md`, `stdout.txt`, paper titles, and recommendation reasons.
- I verified locally that `select_autoescape(("html", "xml"))("ci_report.html.j2")` returns `False`.

## Proposed Solutions

### Option 1: Explicitly enable autoescape for the report environment

**Approach:** Configure the Jinja2 `Environment` with `autoescape=True`, or provide a callable that explicitly returns `True` for `.html.j2`.

**Pros:**
- Fixes the vulnerability at the rendering boundary
- Keeps the existing template structure

**Cons:**
- Requires reviewing any intentionally raw HTML paths

**Effort:** Small

**Risk:** Low

---

### Option 2: Rename the template to a suffix Jinja autoescapes by default

**Approach:** Rename `ci_report.html.j2` to `ci_report.html` and keep the current autoescape selection.

**Pros:**
- Aligns with Jinja defaults
- Reduces configuration surprise

**Cons:**
- Slightly less explicit as a source template file
- Requires updating template loading and package data if needed

**Effort:** Small

**Risk:** Low

---

### Option 3: Manually escape each untrusted field in the template

**Approach:** Add explicit escaping filters to every interpolated field.

**Pros:**
- Fine-grained control

**Cons:**
- Easy to miss future fields
- More brittle than fixing the environment

**Effort:** Medium

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `paper_analysis/services/ci_html_writer.py`
- `paper_analysis/templates/ci_report.html.j2`
- `tests/unit/test_ci_html_writer.py`

**Related components:**
- `quality local-ci`
- HTML review artifact generation
- Browser-based manual review flow

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- `paper_analysis/services/ci_html_writer.py:84`
- `paper_analysis/templates/ci_report.html.j2:120`
- `paper_analysis/templates/ci_report.html.j2:143`
- `paper_analysis/templates/ci_report.html.j2:178`

## Acceptance Criteria

- [ ] The CI report template is rendered with HTML escaping enabled
- [ ] Stage output and paper metadata render as text, not executable markup
- [ ] A regression test proves a `<script>`-like payload is escaped in `local-ci-latest.html`
- [ ] `quality local-ci` still produces a readable HTML report after the change

## Work Log

### 2026-03-20 - Review finding captured

**By:** Codex

**Actions:**
- Reviewed the Jinja2 environment and template filename
- Verified the current autoescape matcher returns `False` for `ci_report.html.j2`
- Identified browser-executable rendering paths in the HTML report

**Learnings:**
- `.html.j2` does not inherit autoescape from a plain `("html", "xml")` selector
- This blocks merge because the report is explicitly meant to be opened by humans in a browser

### 2026-03-20 - Fix implemented

**By:** Codex

**Actions:**
- Changed `paper_analysis/services/ci_html_writer.py` to render the Jinja2 environment with `autoescape=True`
- Kept the `.html.j2` template name while ensuring all interpolated report data is escaped by default
- Added unit coverage that verifies `<script>` and raw HTML payloads are escaped in the generated report
- Re-ran unit, integration, e2e, and `quality local-ci`

**Learnings:**
- For browser-facing artifacts, relying on filename heuristics is weaker than enabling explicit escaping at the environment boundary
