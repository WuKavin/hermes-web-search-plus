# Web Search Plus 3.3 — Release Notes

Web Search Plus 3.3 improves the evidence returned by Search and Extract and
reduces unnecessary waiting in multi-provider Research. The two Hermes tool
names, provider defaults, and existing legacy result fields remain compatible.

## Heading-aware semantic spans

When an extraction query matches an ATX Markdown heading, semantic spans can now
retain the useful body below that heading, including deeper subheadings, until
the next heading at the same or a shallower level. Selection remains bounded and
deterministic: at most two heading sections and at most 1,200 Unicode codepoints
per section.

This avoids the old failure mode where a keyword-bearing heading survived but
the instructions or explanation directly beneath it did not.

## Provenance-safe result enrichment

Canonical-URL clusters may now expose a structured `snippet_aggregate` assembled
from several provider observations. Every retained fragment names its
`observation_id` and source field, and the v3 validator reconstructs the merged
text from that provenance instead of trusting an opaque summary.

Two additive result hints help agents choose what to fetch next:

- `source_type` — a provider-neutral heuristic classification with method,
  version, and confidence;
- `fetch_priority` — an explainable priority tier with closed reason codes.

These are routing hints, not factual or quality guarantees. Existing `title`,
`url`, and `snippet` fields remain available.

## Faster, truthful Research

Research Mode now harvests providers in completion order and can stop waiting
once a conservative quality quorum has enough results, contributing providers,
and unique domains. Public result order remains deterministic.

Providers that were still running when the quorum was reached remain visible as
`preempted_after_quorum`. Explicit Research-provider lists now bypass the
automatic-routing allowlist, matching explicit single-provider semantics while
still honoring disabled, unconfigured, and cooldown safety gates.

## Compatibility

- No Hermes tool is renamed or removed.
- Existing legacy result fields remain stable; enrichment fields are additive.
- Quality-quorum Research is configurable under `quality.research_quorum`.
- Existing provider configuration and automatic-routing defaults remain valid.
- Hound remains a separately installed, explicit-only sidecar unless an operator
  deliberately enables `auto_allow`.

## Hound / Master-Fetch attribution

The heading-aware interaction and completion-order Research ideas are inspired
by [Hound/Master-Fetch v11.2.0](https://github.com/dondai1234/master-fetch/releases/tag/v11.2.0),
an independent MIT-licensed project created and maintained by
[Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234).

Web Search Plus independently implements these ideas for its own provider,
provenance, budget, cache, and receipt contracts. It does not bundle, fork, copy,
or claim ownership of Hound/Master-Fetch code. The optional Hound provider still
connects to a separately installed loopback MCP sidecar.

## Upgrade

```bash
hermes plugins update web-search-plus
```

Reload Hermes after updating so the registered plugin tools use the new code.
