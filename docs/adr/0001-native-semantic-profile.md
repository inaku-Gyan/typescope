# ADR 0001: Use one versioned native semantic profile

## Status

Accepted

## Context

TypeScope compares runtime Python type expressions while Python versions and static checkers differ in representation and edge-case behavior. A default that silently follows whichever checker or interpreter happens to be installed would make results unpredictable and would conflate a rule failure with an inability to evaluate an expression.

## Decision

The first reconstruction exposes one versioned native semantic profile. It follows the Python typing specification first, records checker conventions separately, and labels any TypeScope-specific behavior as an explicit Wayfinder semantic extension. The precedence is:

1. typing specification semantics;
2. documented checker conventions when an explicit checker profile is selected;
3. documented Wayfinder extensions;
4. `unknown`/`capability_error` when the expression cannot be decided.

Python 3.11–3.13 runtime representation differences are normalized inside the compatibility layer and do not create separate semantic profiles. The profile version changes only when the semantic rules or result contract changes.

The structured result records the profile, Python runtime metadata, rule source, and a stable rule path. The Boolean convenience API must not turn `unknown` or `capability_error` into `False`.

## Consequences

The native profile is the predictable implementation and test oracle. External checker integrations, if added later, must be explicit profiles whose engine and version remain visible in the result. New rules that diverge from typing specification semantics require a documented extension and a profile-version decision.
