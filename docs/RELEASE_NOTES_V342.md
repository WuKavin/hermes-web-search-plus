# Web Search Plus v3.4.2 Release Notes

Web Search Plus v3.4.2 fixes a confusing Research output boundary: long source summaries are still presented as a bounded 500-character preview, but the formatter now states that the content is truncated and reports the exact original character count.

## Research source summaries

When a source summary exceeds the display preview limit, Hermes now emits a marker in this form:

```text
[TRUNCATED: showing first 500 of N characters]
```

Short summaries remain unchanged. The full structured `source_summaries` payload is preserved for callers that need the complete content; only the human-facing preview is bounded.

## Compatibility

No provider, routing, credential, or tool contract changes are included in this patch release.

## Verification

- 1,022 Python tests plus 6 schema subtests passed before release preparation.
- Ruff, compilation, and `git diff --check` passed.
- The long-summary regression test passed RED → GREEN before merge.
- The related MCP boundary preserved long `source_summaries` losslessly and required no code change.
