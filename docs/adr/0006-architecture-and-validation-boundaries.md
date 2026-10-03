# ADR-0006: Separate normalization, evaluation, explanation, and validation oracles

## Status

Accepted

## Context

The first reconstruction must replace the old module structure without losing a precise semantic
contract. Runtime carriers vary across Python versions, evaluation can recurse through aliases and
structural types, and a Boolean result cannot explain whether a relation was false or simply not
decidable. Tests also need to distinguish typing-standard behavior from checker conventions and
TypeScope-specific extensions.

## Decision

### Domain seams

The specification requires four dependency-ordered boundaries:

1. **Normalization** maps an input expression to a version-independent normalized form and
   representation provenance. It does not decide assignability.
2. **Semantic evaluation** compares normalized forms using a Semantic Profile and an explicit
   Evaluation Context. It does not inspect private runtime carrier classes or re-parse original
   expressions.
3. **Result and explanation** records status, profile identity, rule source, rule path, reason
   code, provenance, and nested evidence. It does not re-run semantic rules.
4. **Public API** selects the profile and projects structured results through the documented
   `on_unknown` policy.

The normalized form and evaluation context are stable internal domain interfaces, not a first
reconstruction public introspection API. A future public normalization API requires its own
versioned contract.

### Evaluation context and capabilities

Every evaluation receives an explicit, bounded context containing the profile, visited normalized
expression pairs, recursion or expansion budget, current rule path, and capability evidence.
Re-entering the same comparison pair uses the established recursive assumption. Exceeding a
budget returns capability unknown and never silently changes a definite rule result to false.

Parameter or API-shape errors are immediate argument errors. Unsupported carriers, unresolved
ForwardRefs, malformed expressions, dynamic resolution failures, and exhausted budgets are
structured unknown results with capability reason codes. A definite semantic contradiction is
`not_assignable`; `is_assignable(..., on_unknown="raise")` projects only structured unknown to
`AssignabilityCapabilityError`.

### Profile identity and caching

Each Semantic Profile has a comparable identity with at least a name and semantic version. A
checker profile additionally records checker name, version, and configuration. Runtime Python
version is evaluation metadata and does not automatically create a separate native profile.

Normalization and evaluation may use separate caches. Cache keys include every semantic input:
profile identity, relevant parsing environment, and any context setting that can affect the
result. Dynamic namespaces, budgets, and feature-detection capabilities are isolation boundaries;
an unsupported result from one environment is not a global semantic conclusion. Caching is an
optimization: disabling it cannot change status, reason code, or rule path.

### Results and evidence

The structured result exposes stable `status`, `profile`, `rule_source`, `rule_path`, and primary
`reason_code` fields. Reason codes use a versioned namespace such as
`normalization.forward_ref_unresolved`, `protocol.member_missing`, or
`callable.signature_unknown`; they do not use private carrier names, exception class names, or
full repr strings. Nested evidence may retain secondary reasons and provenance.

Rule paths use normalized semantic positions such as `union.member[0]`,
`generic.argument[1]`, `protocol.member["read"]`, and `callable.parameter[0]`. Union members,
Protocol members, and overload branches have deterministic normalized ordering. Equivalent
spellings may change provenance but cannot change native semantic paths or results.

### Validation oracles

Tests are separated into three oracle families:

- **standard** cases from the typing specification, accepted PEPs, and settled native rules;
- **checker** cases tied to an explicit checker, version, and configuration;
- **extension** cases for TypeScope's Unknown, capability boundaries, budgets, and explanation
  contract.

Native failures block integration. Checker comparisons document convention drift and never become
native execution backends. A semantic rule change updates its ADR, profile version, and fixtures
before implementation expectations change.

The test suite combines normalization and semantic matrix tests, result-contract assertions,
3.11/3.12/3.13 compatibility fixtures, and property tests for equivalent carriers, Union order,
repeated TypeVar binding, and cache independence. Every settled rule has positive and negative
cases; every capability boundary has an unknown case with a reason code. Tests do not depend on
private typing class names, repr output, or human-readable error text.

## Consequences

- The implementation can replace the old module graph while preserving domain seams.
- Unknown results are explainable and testable without turning capability gaps into false rules.
- Cache behavior, checker comparisons, and Python-version differences cannot silently alter the
  native semantic oracle.
- The internal normalized model can evolve until a separate public introspection contract is
  justified.

## Alternatives considered

- Expose the normalized node graph immediately: rejected because it would freeze implementation
  details before the semantic model is complete.
- Let the evaluator inspect original runtime carriers: rejected because version-specific typing
  classes would leak into native semantics.
- Use one checker as the test oracle: rejected because checker conventions and native typing
  semantics are intentionally separate.
- Treat cache keys and budgets as implementation details: rejected because they can change the
  observable unknown/diagnostic result when omitted from semantic isolation.
