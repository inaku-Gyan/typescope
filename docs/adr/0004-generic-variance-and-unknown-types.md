# ADR-0004: Define generic variance and separate implicit Unknown from capability unknown

## Status

Accepted

## Context

Generic assignability depends on the variance declared by each type parameter, on mappings
through generic inheritance, and on the meaning of omitted type arguments. A runtime library
also needs to distinguish a checker-style unknown type from an expression that the normalization
engine failed to understand. Treating both cases as `Any`, or treating both as an evaluation
failure, would erase information that callers need to choose a policy.

## Decision

TypeScope compares nested generic arguments recursively according to the origin's declared
variance:

- covariant parameters compare source to destination;
- contravariant parameters compare destination to source;
- invariant parameters require assignability in both directions.

Known generic origins use their documented variance. A generic origin may be projected through
its generic inheritance relations when the parameter substitution can be recovered. If the
origin relation or substitution is unavailable, evaluation returns capability unknown. A known
generic declaration whose parameters have no covariance or contravariance declaration is
invariant; missing runtime metadata for an otherwise unsupported carrier is not silently treated
as invariant.

Unsubscripted known generics are normalized according to a profile-level implicit unknown mode.
The native profile uses `unknown_as_opaque`; an explicit checker profile may use
`unknown_as_any`. In the former mode an implicit Unknown node is not assignable to or from any
type, including another implicit Unknown. In the latter it has the bidirectional behavior of
`Any`. Explicit `typing.Any` is unaffected by this choice.

The first checker-compatible profile is exposed as
`typescope-checker/unknown-as-any/1`; it changes only implicit Unknown handling and labels the
resulting rule as checker provenance. It does not claim compatibility with a particular external
checker.

`TypeVar` identity is preserved within a normalized expression. Repeated occurrences of the
same variable share one binding. A destination variable may bind to a source that satisfies its
bound or one of its constraints. A source variable is assignable to a destination only when all
of its permitted instantiations satisfy the destination; otherwise the result is unknown.
Independent free variables are not unified implicitly. A `bound` is an upper bound, constraints
form a finite admissible set, and a TypeVar default is used only when no explicit binding
evidence exists. Constraint-solving choices that are not determined by these rules remain
unknown rather than adopting a checker-specific algorithm.

Normalization has a separate failure path. A supported expression with an omitted argument
produces a `Known` normalized form containing an implicit Unknown node. An unresolved forward
reference, unsupported carrier, malformed expression, alias cycle, or expansion-budget failure
produces `CapabilityUnknown(reason_code)`. Capability unknown is never a type node and always
flows to the structured evaluation status `unknown`.

## Consequences

- `list[int]` and `list` can be compared without confusing omitted information with parser or
  introspection failure.
- Generic inheritance and nested arguments have an explicit recursive rule.
- Native behavior is conservative where runtime metadata or TypeVar solving is unavailable.
- Profiles can reproduce a checker convention for implicit unknown without changing explicit
  `Any` or capability-error behavior.
- Tests must cover both implicit Unknown modes and the distinct capability-unknown path.

## Alternatives considered

- Treat every omitted argument as explicit `Any`: rejected because it hides the distinction made
  by modern checkers between explicit `Any` and inferred unknown.
- Treat every unknown as `not_assignable`: rejected because normalization failures are capability
  results, not type-rule results.
- Default all missing variance metadata to invariant: rejected for carriers whose semantics are
  genuinely unavailable; only known invariant declarations receive that default.
