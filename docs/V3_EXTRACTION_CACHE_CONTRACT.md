# WSP v3 — Contract Amendment 004: Extraction Cache Identity

This amendment is normative for v3 extraction-cache behavior.

Amends [`V3_SOURCE_EVIDENCE_CONTRACT.md`](V3_SOURCE_EVIDENCE_CONTRACT.md) and [`V3_BOUNDED_CONTEXT_CONTRACT.md`](V3_BOUNDED_CONTEXT_CONTRACT.md). Those contracts remain unchanged except where this amendment is more specific. On conflict, this amendment wins.

## Scope

This amendment makes successful extraction-cache entries request-exact, lossless and versioned. It adds no provider, public tool parameter, migration, retention target or response field. Public extraction behavior is unchanged except that requests which previously could have reused non-identical evidence now miss safely.

## Identity

Every cacheable extraction request has one typed `ExtractionCacheIdentityV3` object. Its canonical JSON uses NFC strings, lexicographically sorted object keys, compact separators and the request URL sequence in request order. The cache key is `extract_` followed by the full SHA-256 hex digest of that canonical JSON. `request_id`, cache TTL/mode and operator receipt settings are excluded.

| Component | Required canonical value | Vary guarantee |
| --- | --- | --- |
| `identity_version` | Explicit integer, currently `6` | Any unknown or older version is a miss. |
| Requested URLs | Complete original URL sequence, before fan-out capping | URL additions, removals, substitutions and ordering changes miss. |
| Attempt budget | Requested budget plus effective request/provider attempt ceilings | A different execution budget misses. |
| Effective context limits | Applied `max_urls` and `max_context_chars` | Bound changes that affect execution or output miss. |
| Extraction controls | `output_format`, `include_images`, `include_raw_html`, `render_js` | Each control varies independently. |
| Provider selection | Requested provider, fallback permission, and the config-derived candidate basis | Identity is deliberately health-independent: transient cooldowns or the provider that happened to serve never vary the key; the serving provider stays recorded in the cached evidence. |
| Provider endpoint configuration | Effective, non-secret extractor settings for every candidate | Endpoint, timeout, Parallel extraction limit/model and keyless mode changes miss; this includes `serper.scrape_url`. Discovered Provider-SDK extraction providers contribute their spec's config section restricted to non-secret scalar settings (credential-shaped keys are excluded); unknown, unregistered providers still fail closed. |
| URL policy | Effective private/internal URL permission | A policy transition cannot serve a previous entry. |
| Semantic spans | Effective span options (`spans`, `spans_query`, span limits) | Span-enabled and span-free requests never share an entry; a different span query misses. |
| Full-text storage policy | Opaque storage-root fingerprint, TTL and owned-byte limit | Retained-content namespace or retention changes miss. |

Credentials are never identity material. Storage-root paths are represented only by a SHA-256 fingerprint in the stored identity envelope.

## Lossless cache value

The cache stores normalized source observations, projected result evidence, exact provenance/segments, policy actions, bounded-context metadata, retained full-text references, warnings, dedup clusters and cache-origin routing evidence. It does not store a verbatim `ResponseV3`; a hit has a new request/execution identity and no fabricated current provider attempts.

Extraction legacy projection hints retain only safe fields needed for byte-stable reconstruction: the `raw_content` alias and per-result provider attribution. A hit reconstructs those fields from the cached evidence. Retained full-text references are revalidated at hit time against the current owned store; unavailable content is reported as unavailable and never substituted.

## Write guards

An extraction result is not written when a lossless canonical reconstruction cannot be guaranteed. This includes:

- any partial-error result;
- requested image or raw-HTML payloads;
- provider-specific top-level or result fields outside the safe extraction projection;
- failed responses; and
- cache-bypass requests.

These rules only bypass reading/writing for the affected request shape; they do not change provider execution or legacy response projection.

Per-execution provider metadata at the top level of the legacy payload —
upstream `request_id`, `cost_dollars` accounting, and upstream `statuses` —
describes one live execution only. It never disqualifies a write, is never
stored in the cache material, and is never reproduced on a hit: a cache hit
carries WSP cache-origin evidence instead of the origin execution's upstream
metadata.

## Miss and corruption semantics

- A key or identity mismatch is an ordinary cache miss.
- An entry with an older or unknown `identity_version` is an ordinary miss and is never interpreted through the current canonical form.
- A malformed owned-path candidate, invalid owned envelope, mismatched entry ID, or malformed current-version identity is corrupt. It is atomically moved under `v3/response/quarantine/<capability>/` when possible, never served, and never reported as a provider-health failure.
- Valid foreign JSON is not quarantined, counted or deleted by cache lookup, stats or clear operations.

No eager migration occurs. Historical entries remain untouched unless they are corrupt; a successful current-version write naturally creates a fresh entry.

## Versioning policy

`identity_version` is independent of response `cache_schema_version` and the v3 wire contract version. It MUST be incremented whenever the canonical identity object, canonical serialization or any included component changes. Implementations MUST fail closed on a version they do not recognize. Version `4` began this typed form after the unversioned 3.0.2 extraction-cache key material; version `5` added the `semantic_spans` component (span options participate in identity); version `6` replaces the transient provider plan with the config-derived candidate basis, so provider health changes never vary identity.
