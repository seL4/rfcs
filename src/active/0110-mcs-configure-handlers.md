<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2022 Proofcraft Pty Ltd
-->

# MCS: set fault and timeout handler parameters while configuring TCBs

- Author: Corey Lewis
- Proposed: 2022-07-22

## Summary

This RFC proposes to modify TCB configuration functions so that it is possible
to directly set the badge and rights of the fault and timeout handler Endpoint
Caps. This would make it consistent with how the CSpace and VSpace of threads
are set.

## Motivation

This change is motivated by wanting to simplify the process of configuring fault
and timeout handlers when using a system with the MCS extensions enabled.
Without this change, setting the badge or rights of a fault handler requires
first minting a new copy of the Endpoint Cap with the desired parameters, and
then installing it in the TCB. In many systems this additional copy of the cap
ends up being unnecessary.

A longer term motivation is that we would like to port how fault handlers are
configured on MCS to mainline seL4. This would resolve [SELFOUR-29],  improve
consistency, and provide increased functionality to systems that do not use MCS.
However, this next step would be very difficult without this change, due to
technicalities in the existing verification approach of the CapDL Loader.

[SELFOUR-29]: https://sel4.atlassian.net/browse/SELFOUR-29

## Guide-level explanation

On systems with the MCS extensions enabled, caps to a TCB's fault and timeout
handler endpoints are installed directly in the TCB. This change adds two new
parameters to the relevant API calls used to install these caps
(`TCBSetSchedParams`, `TCBSetTimeoutEndpoint`, `TCBSetSpace`). These parameters
can be used to set the badge and rights of the fault and timeout handler
endpoints being installed. In cases where the badge and rights do not need to be
set, the existing approach is still supported by setting both parameters to 0.

See [seL4/capdl#47](https://github.com/seL4/capdl/pull/47) for an example of
this new functionality being used. The CapDL Loader previously minted a new
endpoint cap for the fault handler with the required badge and rights. With this
change it no longer needs to mint the extra cap and instead seL4 sets the fields
while installing the endpoint caps in the TCB.

[seL4/sel4test#78](https://github.com/seL4/sel4test/pull/78) is an example of
updating existing code without using the new functionality. As the seL4 tests
generally do not need to set the badge and rights, they are able to be updated
for this change by just using `seL4_NilData` and `seL4_NoRights` as the
parameters.

## Reference-level explanation

The API calls `TCBSetSchedParams`, `TCBSetTimeoutEndpoint` and `TCBSetSpace`
have each had two new parameters added, and their corresponding decode functions
expect two additional syscall arguments. These arguments are used in the same
pattern as used when setting the CSpace and VSpace of a TCB. When the parameters
are non-zero then the provided cap is modified with updateCapData and
maskCapRights, and then it is confirmed that it is safe to copy the capability
by calling deriveCap. Following this, the decode functions then confirm that the
modified cap is a valid cap through validFaultHandler.
[seL4/seL4#889](https://github.com/seL4/seL4/pull/889) is the current proposal
for what these changes would look like.

In addition to the patch to the kernel, there are also patches for seL4_libs,
sel4test, and capdl which show the required changes to migrate these projects to
the new API. The patch to sel4test is an example of a minimal migration which
does not use the new functionality, while the patch for capdl is a migration
that does make use of it.

## Drawbacks

On some platforms, the extra parameters that this change adds might exceed the
hardware limit on the number of message registers, which would cause the syscall
to go into the IPC buffer. In the worst case, if this does become an issue then
it could possibly be avoided by modifying the API so that each syscall performs
fewer operations and hence does not require as many arguments.

This implementation also means that seL4 will silently downgrade some incorrect
capabilities to `NullCaps` if a user attempts to set them as a TCBs fault or
timeout handler instead of returning an error. This behaviour currently occurs
when setting the CSpace and VSpace and is generally safe, although could cause
confusion if it hides a user error. If this behaviour is not desired then we
could separately check for this happening and explicitly return the error.

## Rationale and alternatives

This design provides increased consistency within seL4, as it makes setting the
fault and timeout handlers of TCBs exactly the same as setting their CSpace and
VSpace.

An alternative design with a minor difference that was considered was combining
the badge and right parameters into one word, in the same fashion as the
`seL4_CNode_CapData` structure. While this would lead to a slightly simpler API
due to only needing one parameter, on 64-bit platforms it would limit the badge
to 60 bits instead of the full 64. Since existing users often make use of all
available bits for the badges, this alternative was not chosen.

## Unresolved questions

There are existing pull-requests that demonstrate the proposed changes.

- <https://github.com/seL4/seL4/pull/889>
- <https://github.com/seL4/seL4_libs/pull/65>
- <https://github.com/seL4/sel4test/pull/78>
- <https://github.com/seL4/capdl/pull/47>

There is also some initial work on updating the seL4 proofs for this proposal at
[seL4/l4v#505](https://github.com/seL4/l4v/pull/505). While initial verification
efforts suggest that no further implementation changes are required to maintain
verifiability, this work is not yet completed and progress might lead to issues
being discovered.

## Disposition

The TSC has approved this RFC in terms of API design as is, leaving the decision
on a potential compatibility wrapper in libsel4 or not to the PR discussion in
the implementation stage.
