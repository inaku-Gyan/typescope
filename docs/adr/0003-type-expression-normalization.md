# ADR-0003: Normalize type expressions before semantic evaluation

## Status

Accepted

## Context

Python exposes equivalent typing expressions through different runtime carriers. For example,
`typing.Union[int, str]` and `int | str` have different `type(...)` results, and static
type-checkers may display them differently. The same issue appears with `typing.List[int]`
and `list[int]`, standard-library forms and `typing_extensions` backports, and PEP 695 type
aliases. Branching on private carrier classes would make native assignability depend on a
specific Python implementation rather than on typing semantics.

Diagnostics and future checker profiles still need to explain the spelling and carrier that
the caller supplied. Erasing that information would make equivalent expressions indistinguishable
to users and would prevent checker-specific presentation later.

## Decision

TypeScope places a normalization boundary before semantic evaluation. The boundary creates an
explicit normalized type form with a semantic kind and semantic fields. Native assignability
uses that form's semantic identity, not the expression's `type(...)`, repr, module, or private
runtime class. Public `typing.get_origin`, `typing.get_args`, special markers, documented
attributes, and feature detection are the supported observation mechanisms.

The native profile treats equivalent standard spellings and known `typing_extensions` backports
as one semantic form. Union members are flattened and deduplicated with order ignored. The
original spelling, carrier, Python version, alias chain, and other diagnostic details remain in
representation provenance; checker display differences are not native semantic distinctions.

Type aliases are transparently expanded for native semantics while their alias provenance is
retained. Cycles and expansion-budget exhaustion produce unknown normalization with a stable
reason code. `Annotated` metadata is retained as provenance but does not affect native
assignability in the first profile.

An unresolved forward reference, unsupported or checker-specific carrier, malformed expression,
alias cycle, or normalization budget failure produces an unknown/capability result. It is never
silently converted to `Any` or to `not_assignable`.

## Consequences

- Python-version differences are isolated in normalization and do not leak into semantic rules.
- Diagnostics can report the caller's original spelling without changing native answers.
- The evaluator can remain independent of CPython's private `typing` implementation classes.
- Normalization needs bounded recursion and stable reason codes for unsupported forms.
- Future checker profiles can consume provenance or add an explicit carrier adapter without
  changing native semantic identity.

## Alternatives considered

- Compare `type(...)` and private alias classes directly: rejected because equivalent forms vary
  across Python versions and implementations.
- Preserve every runtime carrier as a distinct semantic type: rejected because it contradicts
  the typing specification's equivalence for standard spellings.
- Treat unresolved forms as `Any`: rejected because it hides capability failures and changes the
  meaning of explicit `Any`.
