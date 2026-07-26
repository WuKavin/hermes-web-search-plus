# Web Search Plus 3.1 — Release Notes

WSP 3.1 delivers everything 3.0 deliberately deferred, plus the quality and
budget layers around it. The public surface is unchanged: the same two tools,
the same call style, and — with default configuration — functionally unchanged
behavior vs. 3.0.2 (see Compatibility for the two visible deltas). Every 3.1
feature is opt-in.

## Highlights

### Full Shadow Observer (deferred from 3.0 — now shipped)
With `routing.policy_mode: shadow`, a deterministic shadow policy
(`shadow-quality`, revision 3.1) evaluates every auto-routed search on the same
inputs as Classic Routing v2 — and never affects execution. Evaluations are
persisted (routing class, classic vs. shadow provider, agreement; never query
text) and aggregated in the read-only Console endpoint
`/api/v3/shadow-evaluation`. Classic remains authoritative;
`WSP_ROUTING_CLASSIC_ONLY=1` still disables everything shadow-related.
Canary/promotion gates remain future work by design.

### Budget Preflight
Opt-in via the `budget_preflight` config section: provider-call cap, daily
ledger quota, timeout budget, and context budget are checked before the first
provider call. Violations degrade deterministically (recorded as typed policy
actions in the routing receipt) or abort with a typed error and zero attempts.
`WSP_BUDGET_PREFLIGHT_OFF=1` force-disables.

### Diversity Score
Quality reports now include a deterministic diversity diagnosis: registrable-
domain coverage, canonical-URL duplication, near-duplicate content (shingle
similarity), and research-provider mix. Ten SEO variants of the same domain
score measurably worse than ten independent sources. Research-merge reranking
stays explicitly opt-in (`quality.diversity.rerank`).

### Extraction Cache Identity (contract)
The 3.0.2 cache fixes are now a versioned contract
(`docs/V3_EXTRACTION_CACHE_CONTRACT.md`): a typed, hashed cache identity over
every request component, per-field provenance on hits, fail-closed handling of
unknown identity versions and corrupt entries, and contract-tested write guards.
No wrong hits after endpoint, budget, or extraction-config changes.

### Self-hosted / No-paid-key Profile (deferred from 3.0 — now shipped)
`profile: self_hosted` restricts automatic routing to SearXNG and keyless
Keenable, with keyless extraction paths and offline prerequisite diagnostics in
`setup.py status`. Explicit keyed provider calls keep working and are flagged
as profile deviations.

### Semantic Span Extraction
`web_extract_plus(..., spans=true, spans_query=...)` returns query-conditioned
passages with a strictly mechanical offset contract: NFC-normalized text,
Unicode codepoint indices, half-open `[start,end)`, slicing invariant, and
`within_preview` flags valid against the retained full text
(`docs/V3_SPAN_CONTRACT.md`). The ranker is deterministic and stdlib-only, with
a documented seam for future semantic backends.

### Public Provider SDK (deferred from 3.0 — now shipped)
`wsp_sdk` + `providers.d` discovery: a new provider is one self-contained
module — no core-file edits. Includes `setup.py new-provider` scaffolding, a
conformance suite that also validates every built-in spec, typed startup
diagnostics for broken modules, and fail-closed duplicate handling. Discovered
providers stay explicit-only unless they opt into the auto-routing gate.
See `docs/PROVIDER_SDK.md`.

### Operator Console: provider health trends
New read-only endpoint `/api/v3/provider-health`: per-provider daily buckets
(samples, errors, error rate, result counts, median latency) from persisted
adaptive samples — no provider calls, no stored query text.

## Reliability

- Fixed a nondeterministic SQLite WAL checkpoint-on-close deadlock between
  concurrent short-lived state-store connections (research workers vs. shadow
  persistence vs. preflight ledger).

## Compatibility

- Default configuration: functionally unchanged vs. 3.0.2, with two visible
  deltas. (1) Quality reports (`quality_report=true`) always include the new
  `diversity` diagnostics block; result ordering is unchanged. (2) The
  extraction cache uses the new versioned identity, so the first request for
  each URL set after the upgrade is a cache miss (one-time repopulation;
  strictly fewer wrong hits afterwards). All other new receipt/response
  fields appear only when their feature is enabled.
- Operational state schema: v2 → v3 (additive; `shadow_evaluations_v3` table).
  The upgrade is automatic and in-place via idempotent DDL; no migration
  command is required when coming from 3.0.x. Coming from 2.x, run the
  existing dry-run-first `state-migrate` flow (see `docs/V3_MIGRATION.md`).
- Provider surface unchanged: 12 search / 8 extraction providers.

## Deprecated

- The legacy pre-v3 execution modules (`cache.py` search-response caching and
  the non-v3 projection paths) are deprecated; removal no earlier than 3.2.
  This is an advance notice only — nothing changes in 3.1.
