# ADR 0009: Bound the first profile for remaining typing forms

## Status

Accepted

## Context

The first reconstruction needs a predictable boundary for typing forms that are not
ordinary classes, unions, or fixed-arity generics. Their runtime carriers differ across
Python 3.11, 3.12, and 3.13, and equivalent forms may be supplied by
`typing_extensions`. Some forms describe assignable values, while others carry declaration
or type-narrowing metadata that only has meaning in a callable or structural context.

## Decision

### Aliases, references, and metadata

`TypeAliasType` and legacy aliases are transparently expanded for native semantics while
alias chains remain provenance. Alias cycles and expansion-budget exhaustion are capability
unknown. A `ForwardRef` or string annotation is resolved only with an explicit evaluation
context; unresolved references are capability unknown. `Annotated[T, ...]` uses `T` for
native assignability and retains metadata as provenance.

### Literal

`Literal` is a native semantic form. Literal identity includes the exact value and its
exact value type, so `Literal[0]` and `Literal[False]` are distinct. A matching literal
is assignable to itself and a compatible ordinary type; an ordinary type is not assignable
to a specific literal without evidence. Values that cannot be compared safely produce
capability unknown.

### TypedDict

TypedDict-to-TypedDict is the first native structural rule using `KeyShape`. Requiredness,
value type, mutability/read-only state, and supported openness evidence participate in the
relation. Standard-library and known `typing_extensions` forms share semantic identity.
`ReadOnly` participates when the runtime exposes complete public metadata; missing
mutability metadata remains capability unknown. `closed` and `extra_items` participate when
their public metadata is complete, while unsupported or partial openness evidence remains a
capability boundary.
Ordinary `dict[K, V]` is not assignable to a TypedDict merely because its key and value
parameters are compatible.

### Variadic forms

`TypeVarTuple` and `Unpack` retain identity and expansion structure. Fully concrete
expansions use tuple rules, and direct identity is reflexive. Variadic length inference,
splitting, or rebinding that cannot be proven from the evaluation context is capability
unknown.

### Type predicates

`TypeGuard[T]` and `TypeIs[T]` are normalized as type-predicate markers, not ordinary
containers. In supported callable-return contexts they are assignable to `bool`; matching
markers can be compared. `TypeIs` target relations are invariant. Other marker relations or
standalone contexts without a defined callable meaning are capability unknown.

### Other forms

`NewType` is a nominal subtype wrapper: the wrapper is assignable to its underlying type,
but the underlying type is not assignable back without evidence. `Final` and `ClassVar`
remain declaration or structural-view qualifiers and are retained as provenance outside
those contexts. `ParamSpec` and `Concatenate` follow the existing Callable identity and
binding rules. `LiteralString` and future unsupported forms are capability unknown in the
native profile rather than silently widened to `str` or `Any`.

### Version and backport policy

Known equivalent standard-library and `typing_extensions` forms share semantic identity;
carrier module and Python version remain provenance and capability metadata. Normalization
uses feature detection and the public APIs available on Python 3.11, 3.12, and 3.13. A
missing runtime feature without a supported backport produces capability unknown and does
not create a new semantic profile.

## Consequences

- The first profile has explicit native rules for Literal, TypedDict schema comparison,
  TypeAlias expansion, NewType, and concrete variadic forms.
- Type-predicate markers and declaration qualifiers cannot be misused as ordinary runtime
  types.
- Backports do not fork the semantic oracle, while unavailable capabilities remain visible.
- Future support for `LiteralString`, richer variadic solving, closed TypedDicts, or new
  typing forms requires a profile or acceptance-standard decision rather than an implicit
  fallback.
