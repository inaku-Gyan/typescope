# Structural assignability implementation status

This note records the current implementation of the structural typing work under the
native profile. It covers T4 and T5 from the parent [native assignability issue](https://github.com/inaku-Gyan/typescope/issues/20);
the parent issue remains open for the later typing forms and integration work.

## T4: TypedDict KeyShape (#23)

T4 is complete on the current `main` branch. TypedDict declarations normalize into an
immutable `KeyShape` that retains representation provenance and shape completeness. The
evaluator compares requiredness, value types, mutable versus read-only keys, and complete
open, closed, or extra-item metadata. A known absent required key is a definite
`not_assignable` result. Unresolved annotations, missing metadata, and unsupported openness
remain capability `unknown`. Ordinary `dict[K, V]` keeps its generic identity and does not
become a TypedDict schema.

The tests cover equivalent and incompatible schemas, required and optional keys, mutable
value variance, read-only evidence, incomplete metadata, standard-library/backport forms,
and the ordinary-dict boundary. The detailed semantic boundary is in
[ADR 0008](adr/0008-structural-shape-boundaries.md) and [ADR 0009](adr/0009-scope-of-remaining-typing-forms.md).

## T5: Protocol MemberShape and dataclass boundary (#24)

T5 is complete on the current `main` branch. Protocol declarations and inherited members
normalize into an immutable `MemberShape` with provenance and completeness. Protocol
comparisons check required attributes, properties, methods, mutability, callable parameter
coverage, and inherited conflicts. A concrete class is used as a source only when static
member evidence is complete and safe; known missing members are `not_assignable`, while
unresolved annotations, dynamic members, unsafe descriptors, and unregistered providers
produce capability `unknown`.

Dataclasses remain nominal when compared with other dataclasses. Their declared fields may
serve as controlled source evidence for a Protocol. Recursive Protocol members use the
bounded evaluation context, and nominal Protocol inheritance remains a separate rule from
structural member comparison.

The tests cover inherited and equivalent Protocol shapes, properties, methods and callable
boundaries, missing and incomplete evidence, recursion, concrete classes, dataclass source
evidence, dataclass nominal behavior, and provider boundaries. The semantic target is
[ADR 0005](adr/0005-protocol-and-callable-structural-assignability.md).

## Verification

The repository check passes on the current environment:

```text
92 passed; coverage 84.04%; Ruff format/check passed; Pyrefly passed;
wheel and source distribution verification passed.
```

The check uses `just check`, with `UV_CACHE_DIR` redirected when the default uv cache is
read-only in a sandboxed environment.
