<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2022 Kry10
-->

# AArch64: remove seL4_ARM_PageDirectory and seL4_ARM_PageUpperDirectory

- Author: Kent McLeod
- Proposed: 2022-03-11

## Summary

This RFC proposes to remove two AArch64 VSpace object types,
`seL4_ARM_PageDirectory` and `seL4_ARM_PageUpperDirectory`. The functionality
previously provided by these types will be provided by the existing
`seL4_ARM_PageTable` object type.  This allows for a simpler API and enables a
smaller kernel implementation that will be easier to verify.

## Motivation

This change is motivated by an ongoing verification project to verify the
AArch64 design and implementation. Unified PageTable object types was attempted
during the RISCV64 verification project and it successfully reduced verification
complexity. By applying the same design strategy to Aarch64, the verification
can become easier.

The change is also motivated by an reducing complexity of the kernel user API
where there are less object and capability types and less different
invocation-object pairs while maintaining the same functionality. The ability to
use PageTable objects for any level of the page-table hierarchy can also make
virtual address space resource management easier as objects are more
interchangeable.


## Guide-level explanation

This change only affects the AArch64 architecture, but affects every
configuration.

This change requires removing the `seL4_ARM_PageDirectory` and
`seL4_ARM_PageUpperDirectory` object types. This means that it will no longer be
possible to create these objects from Untyped capabilities. To make up for this,
`seL4_ARM_PageTable` objects will be able to be mapped into an `seL4_ARM_VSpace`
object or other `seL4_ARM_PageTable` objects.

This change will require modifications to existing user code. Every usage of an
`seL4_ARM_PageDirectory` or `seL4_ARM_PageUpperDirectory` will need to be
updated to instead use a `seL4_PageTable`. This update should be reasonably
direct as all three object types have the same kind of invocations, are the same
size, and contain the same number of table entries as each other.

## Reference-level explanation

The entire sections of the `seL4_ARM_PageDirectory` and
`seL4_ARM_PageUpperDirectory` interfaces have been removed from the libsel4 API
XML interface definitions. The kernel will no longer recognize them as objects.

It's possible to redefine all of the deleted constants and symbols in the
libsel4 implementation using CPP macro definitions in a `deprecated.h` header
file. This can allow migration with minimal manual updating. Manual updates may
still be required in places where the programming language used expects each
object type to have a different number such as in a C `switch` statement.

In addition to a patch to the kernel, there is a patch to `seL4_libs` showing
the minimal set of changes required to migrate the seL4test and seL4bench
applications to the new API.

Internally, the kernel will use a single `pte_t` datatype to represent all page
table entries in the VSpace implementation. This allows for considerably less
code duplication for mapping and unmapping operations as well as for object
creation and revocation. This new implementation follows the design taken with
the RISC-V architecture.

## Drawbacks

The main drawback for this change is that is API breaking -- existing user space
programs will require their sources and binaries to be updated to use the newer
kernel version. However, this will only affect configurations that previously
have not been verified which should already be expecting API breakages as part
of a verification process.

## Rationale and alternatives

As AArch64 will be the third 64-bit architecture to go through a verification
process we are able to make decisions that are informed by the experiences of
the x86_64 and RISCV64 projects. In particular, the reduction in effort that
this type unification allows was directly seen when comparing the x86_64
project, which used a separate object type for each level of the page table
hierarchy, to the RISCV64 project which uses a single type.

One change that has been made compared to the RISC-V design is using a different
type for the `seL4_ARM_VSpace` object. This object serves as the root page table
of the address space. The AArch64 virtual memory architecture allows the top
level page table to be sized differently depending on the size of the address
space. This object also supports additional invocations that can't be applied to
intermediate page table objects and it is also likely to gain more invocations
in the future.

## Prior art

Having a single page table object type is based on the design of the AArch64
virtual memory system architecture which sets out to reuse page table descriptor
formats at all levels of the virtual address space.

## Unresolved questions

There are existing pull-requests that show-case the proposed changes.

- <https://github.com/seL4/seL4/pull/801>
- <https://github.com/seL4/seL4_libs/pull/59>

As always, verification progress can lead to design or implementation changes as
bugs are found or verification blockers are encountered.

## Disposition

The TSC has voted to approve this RFC for implementation without changes.
