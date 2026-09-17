# Part 3 — Internals: A Note to the Reader

The three chapters that follow are not written for this manual. They are RADIANT's living
architecture specifications, bound here exactly as they exist in the repository:

| Chapter | Source document | What it specifies |
|---------|-----------------|-------------------|
| Signal-Chain Internals | `docs/architecture/RADIANT_Signal_Chain_Architecture.md` | The `Stage` protocol, `ChainState` and its `with_*` constructors, reference frames, regime dispatch, the runner |
| Parameter System Internals | `docs/architecture/RADIANT_Parameter_System.md` | `ParameterDef`, `ParameterSet`, resolution order, consistency groups, tolerances, provenance |
| Testing & Validation Framework | `docs/architecture/RADIANT_Testing_Validation.md` | The Level 0/1/2 test hierarchy, the reference cases, golden-result protocol, provenance tracking |

**Why bound as-is rather than rewritten.** These three documents are under the project's
doc-and-code lock-step rule: any change to a stage protocol, a `ChainState` field, the
parameter schema surface, or the test contract must update its specification in the same
pull request that changes the code. That makes them the freshest description of the
internals that exists. Distilling them into manual prose would create a second copy with
no such guarantee — a copy that would start drifting the day it was written. Binding them
directly means this volume inherits their accuracy for free.

The only editorial change is mechanical: the build strips each document's
Date / Status / Depends-on / Scope metadata block, which is repository bookkeeping rather
than manual content. The files on disk are never modified by the build.

**What that means for you as a reader.** These chapters address a contributor working in
the source tree, so their voice is more prescriptive than the rest of this volume and
their cross-references cite repository paths — `src/radiant/core/chain.py`,
`docs/adr/ADR-0006-geometry-stage.md`, `tests/integration/` — rather than chapters of this
manual. A path of that form refers to the RADIANT repository. Where a chapter names a rule
by number ("Rule 9", "C6"), it means the numbered constraints in `CLAUDE.md` and
`docs/architecture/RADIANT_Master_Architecture.md`; the ones that matter to a user of the
framework are summarized in the System Overview chapter of this volume.

**When to read them.** Part 1 and Part 2 of this volume are sufficient for driving
RADIANT — writing scripts, writing configs, reading results, interpreting errors. Read
Part 3 when you intend to change the framework: add a stage, add a parameter, add a
physics term, or write a test that the project will accept. The final chapter,
"Extending RADIANT", is the practical walkthrough those three specifications support.
