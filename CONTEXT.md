# TypeScope Runtime Typing

This context defines the vocabulary for a runtime library that compares Python type expressions and records whether a source expression is assignable to a destination expression.

## Assignability

**Assignability**:
Whether every value described by a source type expression may be used where a destination type expression is expected, under the library's documented semantic profile.
_Avoid_: compatibility, equality, castability

**Source type**:
The type expression being placed into another context.
_Avoid_: actual type, input type

**Destination type**:
The type expression whose accepted values define the target context.
_Avoid_: expected type, output type

**Type expression**:
A runtime object representing a Python type-system concept, including classes and forms from `typing` or related syntax.
_Avoid_: annotation string, runtime value

**Representation carrier**:
The concrete runtime object and `type(...)` result used to carry a type expression, such as a `types.UnionType` or a `typing` alias; it is not the expression's semantic identity.
_Avoid_: semantic type, canonical type

**Normalized type form**:
The version-independent semantic representation used by TypeScope to compare a type expression after inspecting public origin, arguments, special markers, and provenance. It has an explicit semantic kind such as class, special type, union, generic, type variable, callable, or protocol; a Python runtime carrier class is never its identity.
_Avoid_: runtime class, normalized `type`

**Representation provenance**:
Metadata retained from the original spelling or carrier, such as `typing.Union` versus PEP 604 syntax, so diagnostics can explain equivalent forms without using them as distinct native semantics.
_Avoid_: checker result

**Semantic identity**:
The normalized kind and semantic fields that determine native assignability. Equivalent standard and backported spellings share semantic identity even when their runtime carriers, `type(...)` results, or checker displays differ.
_Avoid_: representation identity, display name

**Normalization**:
The boundary operation that maps a type expression into a normalized type form and representation provenance using public introspection and feature detection.
_Avoid_: casting, runtime value inspection

**Alias provenance**:
The retained chain of type-alias declarations and source carriers encountered while normalizing an alias. Alias provenance explains diagnostics while the alias target supplies native semantic identity.
_Avoid_: alias identity as assignability

**Explicit Any**:
The `typing.Any` type expression written explicitly by the caller. It has the native bidirectional assignability rules for `Any` and is never inferred from a missing argument or a normalization failure.
_Avoid_: implicit any, unknown type

**Implicit Unknown**:
A normalized type node created by a semantic profile when a supported generic expression omits type arguments, such as `list` interpreted as `list[Unknown]`. It is a type-system node, not an evaluation failure.
_Avoid_: explicit Any, capability unknown

**Implicit unknown mode**:
The profile rule for the assignability of an implicit Unknown node. `unknown_as_any` gives it the bidirectional behavior of `Any`; `unknown_as_opaque` makes it non-assignable to and from every type, including another implicit Unknown.
_Avoid_: `on_unknown`, error mode

**Capability unknown**:
The normalization result when a type expression cannot be resolved safely, such as an unresolved forward reference, unsupported carrier, alias cycle, or exhausted expansion budget. It carries a stable reason code, is distinct from an implicit Unknown node, and does not become `Any` or `not_assignable` implicitly.
_Avoid_: fallback type, implicit any

## Semantic sources

**Standard semantics**:
Behavior defined by Python's typing specifications and language-level typing documentation.
_Avoid_: canonical behavior

**Checker convention**:
Behavior commonly implemented by static type checkers, recorded separately when it is not directly required by the typing specification.
_Avoid_: de facto standard

**Wayfinder semantic extension**:
A behavior defined by this library when standard semantics and checker conventions do not settle the runtime question; each extension must be explicitly documented.
_Avoid_: special case

**Semantic profile**:
The named, versioned set of rules used for one assignability evaluation, including standard behavior, checker conventions, and any library extensions.
_Avoid_: config, mode

**Native profile**:
TypeScope's single normative profile for the first reconstruction, based on typing specification semantics and explicitly documented Wayfinder extensions.
_Avoid_: default checker, built-in mode

**Checker profile**:
A future explicit compatibility profile that records the conventions of one external checker and never silently replaces the native profile.
_Avoid_: checker truth

**Rule source**:
The provenance label for a rule in an evaluation: `standard`, `checker`, or `extension`.
_Avoid_: rule type

**Capability error**:
An explicit indication that the requested type expressions or semantic profile cannot be evaluated by the selected runtime implementation.
_Avoid_: false, unsupported type

**Unknown result**:
An evaluation state used when the implementation lacks enough information to decide assignability; it is distinct from a rule result of `not_assignable`.
_Avoid_: negative result

## Result contract

**Assignability result**:
The structured outcome of one evaluation, carrying a definite assignable/not-assignable status or unknown together with profile, rule provenance, and reason metadata.
_Avoid_: checker diagnostic

**Evaluation API**:
The structured operation that returns an `AssignabilityResult` with status, profile, rule provenance, and reason metadata.
_Avoid_: checker call

**Boolean convenience API**:
The `is_assignable` operation that projects a structured evaluation to a Boolean according to an explicit unknown policy.
_Avoid_: truth probe

**Unknown policy**:
The `on_unknown` choice controlling how the Boolean convenience API handles an indeterminate evaluation: `raise`, `return_none`, `return_true`, or `return_false`.
_Avoid_: error mode
