<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2026 Proofcraft Pty Ltd
-->

# Remove support for the IA-32 architecture

- Author: Gerwin Klein
- Proposed: 2026-11-04

## Summary

This is an RFC for removing support for the Intel 32-bit architecture from seL4
and the related seL4 Foundation repositories, including the removal of seL4
features that only exist for supporting IA-32, such as `SYSENTER` kernel calls.

## Motivation

As far as the Foundation knows, the IA-32 support for seL4 is unused externally,
and corresponding calls on the developer mailing list and at the seL4 summit
have not yielded any external users.

Removing IA-32 support will reduce maintenance burden and eliminate a source of
defects, because the IA-32 and x64 versions of seL4 can have subtly different
requirements.

A welcome side effect will be that after the removal, all architectures seL4
runs on will have formal verification support.

## Guide-level explanation

The main user-visible changes will be that the IA-32 configuration options in
seL4 CMake are removed, as well as the config choice `KernelFSGSBase=gdt`.

Special cases for the number of fast message registers can be removed: IA-32 is
the only architecture that only has 2, all other architectures have 4.

This proposal includes removing the configuration option
`KernelSyscall=sysenter`, that is, making seL4 kernel calls via `SYSENTER`. This
option is currently also available on x64, but it is supported there only
because it was required for IA-32. The more modern `SYSCALL` is the default for
x64 on seL4 and does not exist on IA-32 hardware.

32-bit VT-x guests on x64 seL4 are *not* in scope for removal. They will still
be supported.

## Reference-level explanation

The following source trees in seL4 will be removed

- `src/arch/x86/32`
- `include/arch/x86/arch/32`
- `include/plat/pc99/plat/32`
- `libsel4/sel4_arch_include/ia32`

together with the corresponding changes in build system, linker, fastpath, trap
code, manual, API reference etc.

Corresponding code and tests from the following other repositories will be
removed:

- `ci-actions` and docker setup
- `seL4_tools`
- `sel4test` and `sel4bench`
- `seL4_libs`, `global-components`, `sel4runtime`
- `capdl`
- `camkes`, `camkes-tool`, `camkes-vm-examples`
- `docs`, `sel4-tutorials`, `website`

Most CAmkES IA-32 simulation tests can easily be retargeted to x64.

The CAmkES GDB server, which is IA-32 only and currently untested, will become
unusable and will be removed, together with `virtio_blk_sample` and IA-32-only
features in `libsel4debug`.

The `arch ia32` in capDL will be removed. This means old capDL specifications
for IA-32 will no longer parse.

Since IA-32 is not covered by any proofs, no proof impact is anticipated.

## Drawbacks

There may be a loss of test coverage for some CAmkES examples, for instance
`aeroplage`, `keyboard`, `pit`, and `vgatest`.

## Rationale and alternatives

The main alternative is to keep support, which would be an unnecessary drag on
resources.

With more effort, some of the CAmkES and user-level library tests and examples
could be kept, but that effort does not appear to be justified at this stage.
They are preserved in version control and can be resurrected if there is demand.
