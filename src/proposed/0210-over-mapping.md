<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2025, UNSW
-->

# Unify behaviour of the Page Map invocation

- Author: Krishnan Winter
- Proposed: 2025-10-21

## Summary

Enforce the same over-map behaviour of the page map invocation across all architectures.

## Motivation

- Currently the handling of over-mapping between architectures differs. On RISCV,
it is not permitted, whereas on aarch32, aarch64 and x86 it is.
- This difference isn't due to any specific hardware requirement. It is a policy
choice in the kernel that should be consistent.
- This RFC proposes to enforce the same behaviour across all architectures,
that is, prevent over-mapping on all architectures.

## Guide-level explanation

Over-mapping refers to when a user overwrites an existing mapping with a
new one. That means, if the user has already mapped frame A to address x,
they would be able to map frame B to address x (supposing that the rest of the
error checking doesn't fail).

Currently, on aarch32, aarch64 and x86 we allow the user to over-map a page.

However, on RISC-V, this is not the behaviour. If you wanted to do the above,
you would get a `seL4_DeleteFirst` error.


## Reference-level explanation

This change is a breaking change to the `seL4_XXX_Page_Map` invocation on the
following architectures:
- aarch32
- aarch64
- x86

Note that there is a difference between "re-mapping" and "over-mapping".

Re-mapping is when the user attempts to map a frame that they have previously
mapped into their address space at the same address, potentially for a permissions
change.

Over-mapping is the case where the kernel has been provided an unmapped frame,
and the user is attempting to map to an address that already has a differnt frame
backing it.

Additions have been made to the `decodeXxxxFrameInvocation` functions for the
above architectures to introduce a check to prevent overmapping, and if detected
then we return a `seL4_DeleteFirst` error.


## Drawbacks

This is a breaking change for existing users that may rely on overmapping.
Additionally, this restricts the flexibility of the API.

Another major drawback that has been brought up is the verification effort that
will be required for this change as it breaks existing proofs.

## Rationale and alternatives

There are two other alternatives to the proposed changes:

- Make RISCV follow the other architectures, allowing over-mapping.
- Make no code changes, and update the manual to explictily mention over-mapping.
This would mean that there are no verification changes that need to be done.

The behaviour of `map` should be well documented, and to avoid confusion for
users, the behvaiour should be the same across architectures if there's no
hardware reason for the difference. This is a change that should be done
sooner rather than later, as although this change may affect some users now, it may
potentially affect many more users if we defer til later.

## Prior art

Linux allows users to choose if over-mapping is allowed through the use of the
`MAP_FIXED` and `MAP_FIXED_NOREPLACE` flags in `mmap`. Whichever approach we
decide is not necessarily incorrect, but should be uniform across architectures.


## Unresolved questions

- Is the verification of these changes something that can be funded?
