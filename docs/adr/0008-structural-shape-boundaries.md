# ADR 0008: Separate structural shape extraction from nominal assignability

## Status

Accepted

## Context

Protocol and TypedDict assignability cannot be recovered from a class name, MRO, or
`issubclass()` result alone. Protocols require member lookup, callable signatures,
property mutability, and recursive structural evidence. TypedDicts describe a keyed
schema with requiredness, value types, read-only state, and openness. Runtime
introspection can also encounter postponed annotations, descriptors, `__getattr__`,
metaclass injection, and library-specific dataclass-like behavior.

`dataclasses.dataclass` is different: the decorator does not define a new structural
type category. Dataclass types remain nominally related. Their fields can be evidence
when a dataclass instance is checked against a Protocol or when a generated constructor
signature is inspected, but equal field lists do not make two dataclasses assignable.
`dataclass_transform` identifies a static convention but does not provide enough runtime
information to reconstruct every third-party provider.

## Decision

TypeScope introduces a structural shape boundary between normalization and semantic
evaluation:

```text
NormalizedType -> StructuralShape -> structural relation
```

A StructuralShape is immutable evidence with provenance and a completeness state. The
common shape vocabulary is shared, but its relations remain distinct:

- `MemberShape` describes object members, properties, methods, class variables,
  mutability, and callable signatures for Protocols and member-bearing sources.
- `KeyShape` describes TypedDict keys, value types, requiredness, read-only state, and
  supported openness or extra-item evidence.

An explicitly absent member or key is a definite semantic mismatch. An unresolved
annotation, dynamic member, unsafe descriptor, unsupported dataclass-like provider, or
incomplete shape is capability unknown and never silently becomes `not_assignable` or
`Any`.

The first reconstruction's native boundary is deliberately narrow:

1. The normalized model and shape boundary are normative architecture.
2. TypedDict-to-TypedDict is the first structural rule to implement when its public
   metadata is complete.
3. Protocol-to-Protocol and callback-Protocol comparisons may use complete member
   shapes, but concrete-class-to-Protocol, dynamic members, recursive unresolved
   structures, and third-party dataclass-like providers remain capability boundaries
   until their evidence can be proven safely.
4. Dataclass-to-dataclass comparison remains nominal. Standard-library dataclass fields
   may be exposed as source evidence for a Protocol or constructor signature; an
   unregistered `attrs`, Pydantic, or other `dataclass_transform` provider does not
   acquire structural semantics automatically.
5. `typing-inspection` may be wrapped as a replaceable normalization and feature-
   detection helper. `beartype` and `typeguard` are optional comparison or value-
   checking oracles only; neither defines the native profile.

The shape boundary uses public metadata and controlled annotation resolution. It does
not invoke user code or replace TypeScope's structured result contract.

## Consequences

- Structural relations have a common evidence model without conflating object members
  with mapping keys.
- The native profile can grow TypedDict, Protocol, and explicit provider support in
  stages while preserving a stable unknown result for incomplete runtime evidence.
- Dataclass-like ecosystems can be added through explicit providers rather than inferred
  from a marker or private fields.
- The first implementation must test complete, missing, and unknown shape evidence
  separately across Python 3.11, 3.12, and 3.13.
