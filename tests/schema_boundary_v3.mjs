// Amendment 002 JSON-schema boundary check (Ajv).
// Exit 0 only when the generated response schema enforces the amendment shape
// and all six golden fixtures validate. Expected RED until the schema
// generator implements Amendment 002 (generator itself is out of scope here).
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const Ajv = require("ajv/dist/2020");

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const schema = JSON.parse(
  readFileSync(join(root, "schemas/v3/response.schema.json"), "utf-8"),
);
const ajv = new Ajv({ strict: false, allErrors: true });
ajv.addFormat("uri", {
  type: "string",
  validate(value) {
    try {
      const parsed = new URL(value);
      return Boolean(parsed.protocol && parsed.hostname);
    } catch {
      return false;
    }
  },
});
ajv.addFormat("date-time", {
  type: "string",
  validate(value) {
    return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
      && !Number.isNaN(Date.parse(value));
  },
});
const validate = ajv.compile(schema);

const failures = [];

const FIXTURES = [
  "01_search_success", "02_extract_success", "03_cache_hit",
  "04_fallback", "05_degraded", "06_total_failure",
];

// 1. All six golden fixtures must validate.
for (const name of FIXTURES) {
  const doc = JSON.parse(
    readFileSync(join(root, `tests/fixtures/v3/${name}.json`), "utf-8"),
  );
  if (!validate(doc)) {
    failures.push(`${name}: ${ajv.errorsText(validate.errors)}`);
  }
}

// 2. Schema must REQUIRE the amendment fields: stripping them must invalidate.
const base = JSON.parse(
  readFileSync(join(root, "tests/fixtures/v3/01_search_success.json"), "utf-8"),
);
for (const required of ["execution_id", "observations", "policy_actions", "source_diversity"]) {
  const mutated = JSON.parse(JSON.stringify(base));
  delete mutated[required];
  if (validate(mutated)) {
    failures.push(`schema does not require ${required}`);
  }
}

// 3. Schema must REJECT the removed legacy field and diversity scalars.
const withLegacy = JSON.parse(JSON.stringify(base));
withLegacy.source_independence_estimate = { score: 0.7 };
if (validate(withLegacy)) {
  failures.push("schema still accepts source_independence_estimate");
}
const withScalar = JSON.parse(JSON.stringify(base));
withScalar.source_diversity.scalar = 0.8;
if (validate(withScalar)) {
  failures.push("schema accepts a source_diversity scalar (additionalProperties)");
}

// 4. Partial engine object must be invalid; complete one valid.
const partialEngine = JSON.parse(JSON.stringify(base));
partialEngine.engine = { name: "wsp", version: "3.0" };
if (validate(partialEngine)) {
  failures.push("schema accepts a partial engine object");
}
const fullEngine = JSON.parse(JSON.stringify(base));
fullEngine.engine = { name: "wsp", version: "3.0", build_commit: "deadbeef" };
if (!validate(fullEngine)) {
  failures.push(`schema rejects a complete engine object: ${ajv.errorsText(validate.errors)}`);
}

// 5. Format constraints are executable, not ignored annotations.
const invalidUri = JSON.parse(JSON.stringify(base));
invalidUri.results[0].url.observed = "not a uri";
if (validate(invalidUri)) {
  failures.push("schema accepts an invalid observed URI");
}
const invalidDateTime = JSON.parse(JSON.stringify(base));
invalidDateTime.started_at = "yesterday-ish";
if (validate(invalidDateTime)) {
  failures.push("schema accepts an invalid date-time");
}

// 6. Semantic spans are optional, versioned, and strict when present.
const withSpans = JSON.parse(JSON.stringify(base));
withSpans.results[0].span_contract_version = 1;
withSpans.results[0].spans = [{
  start: 0,
  end: 4,
  text: "test",
  score: 1.25,
  within_preview: true,
}];
if (!validate(withSpans)) {
  failures.push(`schema rejects semantic spans: ${ajv.errorsText(validate.errors)}`);
}
const malformedSpan = JSON.parse(JSON.stringify(withSpans));
delete malformedSpan.results[0].spans[0].within_preview;
if (validate(malformedSpan)) {
  failures.push("schema accepts a semantic span without within_preview");
}
const unversionedSpans = JSON.parse(JSON.stringify(withSpans));
delete unversionedSpans.results[0].span_contract_version;
if (validate(unversionedSpans)) {
  failures.push("schema accepts unversioned semantic spans");
}

if (failures.length) {
  console.error("SCHEMA BOUNDARY FAILURES:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("schema boundary: all checks passed");
