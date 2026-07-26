# WSP 3.1 Semantic Span Contract

`span_contract_version: 1`

Semantic spans are an opt-in extraction result field. Set `spans: true` on
`web_extract_plus`; `spans_query` may provide the ranking query. When an
originating query is carried by an internal extract invocation, it is used as
the default. Without either query, ranking uses deterministic lexical-density
and position heuristics.

## Offset contract

Every offset is a Python-style Unicode codepoint index into the complete
retained cleaned text after Unicode NFC normalization. Offsets are not UTF-8
byte offsets and are not UTF-16 code-unit offsets. They also do not address the
raw, pre-NFC provider string.

Ranges are half-open: `[start, end)`. For the NFC string `full_text`, every span
obeys:

```python
0 <= span["start"] < span["end"] <= len(full_text)
span["text"] == full_text[span["start"]:span["end"]]
```

Returned spans are non-overlapping and sorted by `start`. Selection is
deterministic: candidate score ties are resolved by descending score and then
ascending start offset; final output is source ordered. No clock, randomness,
network service, or model is involved.

## Result shape

When spans are enabled, every extraction result has:

```json
{
  "span_contract_version": 1,
  "spans": [
    {
      "start": 120,
      "end": 181,
      "text": "The exact selected text from the retained NFC document.",
      "score": 4.25,
      "within_preview": true
    }
  ]
}
```

`within_preview` is true only when the complete half-open span is present in
the inline bounded-context `content`/projected `text` preview. Truncate-and-store
does not change span offsets: offsets always address the full retained cleaned
text, including spans beyond the inline preview. The retained text is the same
NFC text stored for page-on-demand access.

With `spans: false` (the default), neither `spans` nor
`span_contract_version` is added, preserving the existing response shape.

## Heading-aware section retention

When a query term occurs in an ATX Markdown heading (`#` through `######`),
selection explicitly retains that heading's section even if its body has no
query terms. The section starts at the matching heading and ends immediately
before the next heading at the same or a shallower level; deeper subheadings
belong to the section. The returned range still uses the normal NFC offsets and
half-open slicing invariant.

This behavior is deliberately bounded: one call considers at most two explicit
heading sections (and never more than `max_spans`), and each retained section
is capped at `min(max_span_chars, 1200)` Unicode codepoints. These deterministic
caps prevent a relevant heading from flooding context on a very large page.
Documents without a query-matching Markdown heading retain the ordinary passage
selection behavior.

The bounded heading interaction was independently implemented for WSP, inspired
by [Hound/Master-Fetch v11.2.0](https://github.com/dondai1234/master-fetch), an
independent MIT project by [Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234).
This is respectful upstream collaboration and attribution, not a code transfer:
WSP does not import, fork, or copy Hound/Master-Fetch implementation code.

## Ranker seam

`span_extraction_v3.select_spans` accepts an optional `ranker` callable. It is
called as `ranker(candidate_text, normalized_query)` for every mechanically
segmented candidate and any bounded heading-section candidate, and must return
a finite numeric score. Omitting it uses the standard-library lexical ranker
(query term and adjacent-token shingle overlap, lexical density, and a mild
positional prior). This seam can host a future embedding-backed ranker without
changing offset construction or result selection invariants.

Operator receipts and Operator Console payloads never include span text. The
current receipt projection omits semantic spans entirely; future receipt
versions may expose counts only.
