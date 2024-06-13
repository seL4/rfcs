<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2021 Proofcraft Pty Ltd
-->

# Removing CNode_Mutate

- Author: Gerwin Klein
- Proposed: 2021-08-22

## Summary

This RFC proposes to remove the API `seL4_CNode_Mutate()`.

## Motivation

`CNode_Mutate` does not do what the manual describes (a combination of move and
and setting badge). The only action `CNode_Mutate` can currently take that
`CNode_Move` cannot take is setting the guard of a `CNode`, which can also be
done via `CNode_Mint` (where `CNode_Mint` would be copying the cap – if you
wanted the same effect, you could afterwards delete the cap it was copied from).

## Guide-level explanation

`seL4_CNode_Mutate()` is mostly unused and has no use cases that cannot already be
achieved with other API calls. The current description of `seL4_CNode_Mutate()` in
the manual is incorrect.

## Drawbacks

I suspect there are no real drawbacks. It is theoretically possible that there
is an application out there that makes extensive used of re-setting guards on
CNodes while not copying the CNode caps, but that sounds unrealistic.

> Edit: the discussion has revealed one severe drawback, which is that using
> `CNode_Mint` as outlined above makes the corresponding cap non-revocable in the
> current API. This means removing the syscall removes the ability to create
> revocable CNode caps that have a guard set. This is likely too strong a
> limitation to go forward.

## Rationale and alternatives

Different options would be to extend `CNode_Mutate` to allow changing badges,
and possibly even to allow changing cap rights. If we wanted to, we could even
allow an in-place update. As the discussion in [SELFOUR-136] indicates, mutating
an existing cap is not a good fit for the cap model in general and makes
reasoning about caps harder.

The minimal action would be to do nothing and only update the manual to reflect
that `CNode_Mutate` has almost no useful purpose.

[SELFOUR-136]: https://sel4.atlassian.net/browse/SELFOUR-136


## Disposition

As recommended in the discussion below the TSC has voted to reject this RFC and
implement the documentation updated instead.
