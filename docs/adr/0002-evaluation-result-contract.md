# ADR 0002: Separate structured evaluation from Boolean convenience

## Status

Accepted

## Context

Runtime type expressions can be definitely assignable, definitely not assignable, or impossible to decide because context or a supported capability is missing. A Boolean-only API is convenient, but silently mapping the third state to `False` would erase the difference between a rule result and an evaluation failure.

## Decision

Expose two public operations:

- `evaluate_assignability(source, destination, *, profile=native)` returns an `AssignabilityResult` with a stable status (`assignable`, `not_assignable`, or `unknown`) and machine-readable profile, rule-source, rule-path, and reason-code fields.
- `is_assignable(source, destination, *, profile=native, on_unknown="raise")` projects the result to a Boolean.

`on_unknown` accepts exactly `"raise"`, `"return_none"`, `"return_true"`, and `"return_false"`. The default raises `AssignabilityCapabilityError`. The return policies are explicit caller choices: `return_none` preserves the third state, while `return_true` and `return_false` are convenience fallbacks that intentionally discard it. The structured API always preserves `unknown`.

The Boolean API accepts only resolved type expressions in the first reconstruction. Invalid policy values are argument errors. Human-readable messages may evolve; status, profile, rule source, rule path, and reason codes are the compatibility surface.

## Consequences

Callers can choose strict behavior or an explicit fallback without changing the native semantic profile. Tests can assert rule provenance and stable reason codes without coupling to prose. Type overloads should expose `bool` for raising/Boolean policies and `bool | None` for `return_none`.
