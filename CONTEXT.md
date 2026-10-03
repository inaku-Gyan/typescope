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
