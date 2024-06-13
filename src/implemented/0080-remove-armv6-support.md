<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2021 Matthew Brecknell
-->

# Remove support for ARMv6 (KZM/i.MX31)

- Author: Matthew Brecknell
- Proposed: 2021-09-15

## Summary

This RFC proposes to remove seL4 support for KMC's KZM evaluation board, which
used the freescale (now NXP) i.MX31 processor with an ARM1136 core. Since this
is the only ARMv6 platform supported by seL4, this proposal would also remove
support for ARMv6.

## Motivation

The KZM board has been unavailable for purchase for some years. The i.MX31
processor exited NXP's product longevity program in 2015. We previously asked
the seL4 community [[1],[2],[3]] if there are current users of the KZM platform. From
the responses, we believe there is already consensus that there is little value
in continuing support for KZM.

With no known users, we are motivated to eliminate the overhead of maintaining
support for KZM. Unlike all other platforms supported by seL4, KZM lacks
sufficient registers for thread-local identifiers such as TLS_BASE and the IPC
buffer address. For KZM alone, seL4 implements a workaround by mapping a special
frame into each thread (the globals frame) to store these identifiers.

As an example of the cost of maintaining support for KZM, the globals frame
currently makes it difficult to uniformly describe the address space available
to user-space programs.

Additionally, the KZM board the seL4 Foundation has used for testing KZM support
is no longer reliable, so we are currently only able to test using QEMU
simulation. Although KZM was the original seL4 verification target, KZM support
has not been verified since early 2016.

Since we believe there is already consensus around the removal of KZM support,
this RFC can be considered a formal last call for objections.

[1]: https://sel4.discourse.group/t/should-we-continue-to-support-armv6-and-kzm-imx31/46
[2]: https://lists.sel4.systems/hyperkitty/list/devel@sel4.systems/thread/EQ27WYPJIN3KKRGB4VNXUZKJYL65IZ6J/
[3]: https://github.com/seL4/seL4/issues/578


## Guide-level explanation

We propose to remove from seL4:

- seL4 kernel build targets for the KZM board, i.MX31 processor, and ARMv6
  architecture;

- any platform-specific code that is only required for those build targets,
  including platform-specific definitions, drivers and device-tree
  specifications.

Prior to removing support from seL4, we will remove code from other repositories
that depend on seL4 support for KZM and ARMv6, including tests, benchmarks, and
tools such as CAmkES.

We propose to update documentation on the [docs.sel4.systems] website to show
that the KZM board is no longer supported, and to show the last seL4 release
version that included support.

The impact of this change is that any current users of seL4 on the KZM board
would not be able to use new releases of seL4 on the KZM board. They would most
likely need to freeze the version of seL4 they use, and would therefore not be
able to expect the usual level of support from the seL4 community.

Since we are not aware of any users, we do not expect significant impact.

[docs.sel4.systems]: https://docs.sel4.systems

## Reference-level explanation

We have drafted a pull request to remove seL4 support for KZM, i.MX31 and ARMv6:

- <https://github.com/seL4/seL4/pull/580>

A number of related pull requests remove references from related repositories. Some of these are already merged, since the changes they make do not require an RFC process:

- <https://github.com/seL4/seL4_libs/pull/46>
- <https://github.com/seL4/sel4test/pull/51>
- <https://github.com/seL4/sel4runtime/pull/13>
- <https://github.com/seL4/sel4bench/pull/7>
- <https://github.com/seL4/camkes-tool/pull/92>
- <https://github.com/seL4/seL4_projects_libs/pull/22>

## Drawbacks

Since the KZM board is the only ARMv6-based platform supported by seL4, this
proposal implies the removal of ARMv6, even though later ARMv6 boards might
would not require the same workaround as the KZM board. Removing ARMv6 will make
it slightly harder to add a new ARMv6-based platform in the future. But it would
not be prohibitively difficult, since the main difference between ARMv6 and
ARMv7 support in seL4 is the workaround required for KZM.

In any case, we believe that new ARM-based applications of seL4 will most likely
use ARMv7 or later, so the benefits of removing KZM support currently outweigh
the drawbacks.

## Rationale and alternatives

We've already addressed the rationale for removing KZM support.

One might ask why it's necessary to remove all references to ARMv6 when we
remove support for KZM, since retaining ARMv6 references might make it easier to
support other ARMv6 boards in the future. However, we do not think it makes
sense to retain references to ARMv6 without a specific ARMv6 board to exercise
them, and without a clear demand for ARMv6 support. Again, the cost of
maintaining those references outweighs any clear benefit.

## Prior art

The Linux kernel removed support for the KZM board and i.MX31 processor in 2015.

## Unresolved questions

We are not aware of any unresolved questions, but welcome discussion on this
RFC.
