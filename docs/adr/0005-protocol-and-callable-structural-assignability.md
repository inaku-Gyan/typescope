# ADR-0005: Define Protocol and Callable structural assignability

## Status

Accepted

## Context

Python typing defines structural relationships for Protocols and contravariant parameter /
covariant return relationships for Callable types. Runtime objects expose only partial evidence:
`@runtime_checkable` can support a limited attribute check but does not describe member types,
and signatures may be incomplete for dynamic descriptors or advanced callback forms. TypeScope
must preserve the distinction between an explicit incompatibility and a capability it cannot
establish.

## Decision

### Protocols

The destination Protocol is represented by a structural view containing all members declared by
the Protocol and its Protocol inheritance chain. Python MRO resolves same-name declarations;
unresolved inherited conflicts produce capability unknown. A concrete source is assignable to the
view when every required member exists and its type is assignable under the native rules. A
Protocol source is assignable to another Protocol by the same member relation. A Protocol source
is not assignable to a concrete destination unless nominal inheritance establishes that relation.

Structural comparison is independent of `@runtime_checkable`. That decorator is retained as
provenance for possible future value-oriented APIs, but it neither enables nor disables static
assignability. A runtime `isinstance` or `callable` result is never a substitute for the
normalized type relation.

Member comparison follows these rules:

- methods use Callable signature assignability;
- a writable attribute is invariant;
- a writable source attribute may satisfy a read-only destination property;
- a read-only source property cannot satisfy a writable destination attribute;
- an explicitly missing member is not assignable;
- missing annotations, unresolved member types, unsupported descriptors, dynamic members, and
  unresolved inherited conflicts produce capability unknown.

The first profile supports ordinary instance attributes, methods, and read-only properties.
`ClassVar`, complex descriptors, dynamic `__getattr__`, and `Final` metadata that cannot be
reduced to member mutability are retained as provenance or return capability unknown; they are
not guessed into a compatible member.

Protocol comparisons are recursive but bounded. Re-entering the same normalized source /
destination member pair is treated as the current recursive assumption. A definite incompatible
member returns not_assignable; an unresolved type, exhausted budget, or unsafe recursive case
returns capability unknown.

### Callable signatures

Callable assignability is based on call shapes rather than runtime callable identity. Source
parameters are contravariant and source returns are covariant. Positional-only parameters are
matched by position; keyword-only parameters by name; positional-or-keyword parameters must
support both forms. A source may accept additional optional parameters, but it may not require
parameters the destination call contract does not require. Parameter names matter for keyword
calls, while a parameter list with no names supports only conservative positional comparison.
Defaults determine requiredness but their values are not compared. `*args` and `**kwargs` are
considered when deciding whether all destination call shapes are accepted.

Functions, methods, and callable classes use an available static signature; a callable class uses
its `__call__` signature. TypeScope does not invoke user code. A callback Protocol first compares
its additional members and then its `__call__` member.

`Callable[..., R]` is a gradual callable parameter form. Its return type is still compared
normally, but it is not rewritten as a concrete `Any` signature. When one side has a concrete
parameter list and the other has an unknown parameter set, the relation is capability unknown
unless a profile rule proves it without guessing. ParamSpec and Concatenate require the same
identity and a recoverable binding; otherwise they produce capability unknown.

Overloads are compared by call-shape coverage, not list position. Every destination call shape
must be accepted by at least one source branch with a compatible return type. Ambiguous or
incomplete coverage is capability unknown; a definite uncovered destination shape is
not_assignable. Branch ordering does not define native semantics.

## Consequences

- Protocol structural semantics remain separate from the limited behavior of
  `@runtime_checkable`.
- The evaluator can distinguish a missing member from insufficient runtime introspection.
- Callable comparison has a single rule path that also applies to Protocol methods and
  `__call__` members.
- Advanced descriptors, unresolved callback forms, and ambiguous overloads remain explicit
  capability boundaries instead of silently becoming `Any` or false.
- Recursive structural comparisons require bounded state and stable capability reason codes.

## First-reconstruction boundary

ADR-0008 narrows the implementation commitment for the first reconstruction. The
member rules in this ADR remain the semantic target, but concrete-class-to-Protocol
comparisons require a complete `MemberShape` from an explicit, safe provider. Dynamic
members, unresolved annotations, unsafe descriptors, and unregistered dataclass-like
providers return capability unknown. Protocol-to-Protocol and callback-Protocol
comparisons may proceed when their member shapes are complete; dataclass-to-dataclass
assignability remains nominal.

## Alternatives considered

- Use `isinstance` with `@runtime_checkable` as the Protocol answer: rejected because it cannot
  check member types or callable variance.
- Compare Protocol members by names only: rejected because typed attributes, mutability, and
  method signatures are part of structural assignability.
- Treat `Callable[..., R]` as `Callable[[Any], R]`: rejected because gradual unknown parameters
  are not an explicit `Any` argument list.
- Compare overloads by position: rejected because overload order is not the call-shape relation.
