<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2023 Hesham Almatary
-->

# Support CHERI/Morello in seL4

- Author: Hesham Almatary
- Proposed: 2023-11-13

## Summary

This RFC aims to discuss porting seL4 to Arm’s Morello (CHERI on
AArch64/Armv8.2a). The goal of this project is to provide complete fine-grained
spatial and referential (pointer) memory-safety for 1) new C-based seL4
applications, 2) existing C-based seL4 libraries (e.g., sel4_libs,
sel4_project_libs, util_libs, sel4test, sel4bench, muslc, sel4runtime, VMM,
etc). This should enhance the overall security of the current and new C-based
seL4 systems via (a) seL4’s security guarantees in the kernel and between
protection domains, and (b) CHERI’s spatial memory safety, intra protection
domain. The kernel will need to be changed to be CHERI-aware, and userlevel
libraries and applications will need to be adapted to implement, and comply
with CHERI C’s dialect.

## Motivation

seL4 is a secure software-only capability-based microkernel that has been
formally verified. It guarantees the kernel’s correctness and draws strict CIA
(confidentiality, integrity, and availability) boundaries between userlevel
protection domains. However, it does not provide memory safety guarantees within
a userlevel protection domain itself; a single address-space server (e.g.,
rumpkernel) running on top of seL4 could not easily be compartmentalised, a
vulnerability in a network stack could affect the whole server. Similarly,
seL4’s C user libraries (e.g., seL4_Libs) do not provide any security or
memory-safety guarantees. Most current C-based projects [6-8] rely on seL4 libs
which makes it a potential attack surface.

CHERI [5] is a capability-based hardware architecture that offers complete
spatial pointer/memory safety and (in-address-space) software
compartmentalisation. Using CHERI could significantly improve memory safety of
new and existing C/C++ servers, OSes, applications, and libraries running on
seL4, without either formally verifying them or re-writing the entire userspace
from scratch. Microsoft states that 70% of their software bugs are memory safety
issues [9]. Thus, CHERI could provide in-address-space (memory) security that
complements seL4’s inter-address space isolation guarantees. Further,
CHERI-based software compartmentalisation models [6] could further be researched
to defend against future unknown attacks within the same seL4 protection domain
(e.g., rumpkernels and servers). CHERI is an architecture-neutral protection
model, in that, like virtual memory, it can be integrated with multiple ISAs and
yet provide a consistent software-facing programming model. Morello [4, 12] is a
prototype implementation of CHERI for Arm’s AArch64. It is an ISA extension to
Armv8.2/AArch64. Further, the name Morello also usually refers to the SoC and a
prototype evaluation board that supports CHERI. Finally, porting seL4 and its
libraries to Morello will lay the groundwork for also supporting CHERI-RISC-V.

## Guide-level explanation

The first example is a user creating a C application from scratch on seL4. The
user will have to conform to CHERI C’s [11] style in order to build (using a
CHERI-aware toolchain) and run this application (on a CHERI platform like
Morello). CHERI memory safety will then be dynamically enforced on the
application..

The second example is porting existing C libraries, projects and applications to
CHERI C. Projects like rumpkernels, seL4 libraries and util_libs (currently over
200K LoC) will most likely be adapted to be memory-safe via CHERI C with minimum
efforts thanks to CHERI C’s source-code compatibility attribute. That is, there
is no need to rewrite the entire (already rich) userspace in memory-safe
languages/style.

Users who want to apply CHERI C’s memory safety to their libraries and
applications can do so by providing a compiler flag, and address all of the
memory-safety warnings and errors that the CHERI-aware compiler triggers.

## Reference-level explanation

The main goal of this project is to enable running CHERI C userspace. This will
require changes to the seL4 kernel and adaptations to the userspace. The first
approach for this RFC would be having a _**hybrid kernel and CHERI C
userspace**_ (see more details in the Appendix).

### Hybrid seL4 kernel

These are the anticipated changes in the kernel in order to support running
CHERI C applications.

**build systems:** Will need to add a new CONFIG option or flag that depends on
AArch64 (and RISC-V in the future). This will be in the kernel and userspace.

**bootcode:** This will enable various hardware bits in the Morello’s config
registers for CHERI. In libsel4, all the shared structures that contain pointers
and are used by userspace will need to be annotated as capabilities.

**Exceptions:** All the save/restore assembly code will need to be changed to
use CHERI instructions and capability registers (prefixed with c), instead of
AArch64’s GPRs (prefixed with x). This is specific to all registers that could
hold either an integer or a capability. Unlike FPUs, Morello implements a
unified register set; i.e., it extends the existing GPRs to be able to hold
capabilities and effectively doubles its size. There are no separate CHERI GPRs
like with FPUs. We also expect to make the fault-handler CHERI aware to send the
user a new CHERI violation code similar to VM faults.

**vspace:** Morello introduces new permission bits in each page table entry
(PTE) to save/restore capabilities. A page that doesn’t have these bits set will
not have valid capabilities and attempts to save/restore capabilities to such
pages will either fault or be invalidated. The AArch64’s PTE representation (in
structures.bf) will need to add these bits as well as the vspace.c code that
creates PTEs. These new bits will need to be exposed to the user (e.g., in
`seL4_ARM_VMAttributes`) while mapping pages so that the user can manage what
(shared) pages could load/store capabilities.

### CHERI C userspace

This will adapt all the pointers in userspace to be CHERI capabilities;
effectively having complete spatial memory safety. We are targeting all the
libraries that sel4test and sel4bench depend on. This includes libsel4,
sel4_libs, sel4_project_libs, util_libs, sel4test, sel4bench, muslc, and
sel4runtime. No plans to support CAmkES, Microkit, device driver framework, or
VMMs at the moment, but might do if time allows.

## Drawbacks

The main drawback this proposal might have is its potential effects on formal
verification due to the changes required in the kernel. Ideally, we would want
to upstream all of this work and make others reuse it, collaborate, and build on
it, rather than forking. We propose having CHERI support as a build option
(similar to FPU and SMP), when attempting to merge it. This should open the
opportunity to formally verify these changes in the future if there’s interest.

On the user-level side, we anticipate that changes in the existing user
libraries will be relatively disruptive because of the fact that the libraries
didn’t go through any kind of assurance (e.g., formal verification, addressing
compiler warnings, static analysis tools for memory safety, etc).

## Rationale and alternatives

CHERI C offers complete fine-grained spatial memory safety to existing C-based
projects, without having to rewrite everything from scratch (e.g., in
memory-safe languages) or formally verify them. Further, CHERI has different
models to allow scalable software compartmentalisation such as libraries or
co-processes.

### Source-code Compatibility

The main similar effort is rewriting the seL4 userspace in Rust. This takes
significant effort to (re)-write, test, learn (for new users), maintain, and
test. Using CHERI C, we are using the same rapid, already rich, user C libraries
that are dependencies and being used for most other existing C-based projects
such as sel4test, sel4bench, VMM, CaMKes, Rump kernels, etc.

The other alternative is to formally verify a new cleanly-written C userspace
framework. But this could take time, and might not be as scalable when it comes
to incremental advancement, adding features, and increasing the number of lines
of codes. Furthermore, CHERI’s compartmentalisation is dynamic, and assumes
future unknown vulnerabilities exist and behave accordingly. This makes it
different compared to static analysis tools.

Without having CHERI C in seL4, existing seL4 libraries will stay vulnerable and
memory unsafe. This puts all of the projects relying on them under a significant
attack surface.

## Prior art

Other OSes have been ported to Morello and CHERI including FreeBSD, Linux,
FreeRTOS and RTEMS. This has significantly improved the overall security of such
systems to be memory-safe, without having to rewrite them. Our experiences
suggest that for cleanly-written code, these’s no or minimum efforts required to
adapt to CHERI C. In contrast, there could be lots of memory-safe
vulnerabilities for code that hasn’t gone under some form of analysis with
regards to memory safety. For more detailed documentation about CHERI and
Morello, see [1-5, 10-12].

There has been some prior work on seL4 and Morello by Arm [13] and MCA [14].
However, this mainly supports hybrid-mode userspace; it doesn’t provide
(complete) memory-safety, unlike our goal from this RFC. That said, we share the
same end-goal having as much as possible of the seL4 userspace ported to CHERI
C. MCA and TrustedTS are also exploring VM ideas, unlike the main goal of this
project; the existing seL4 userspace. We think that our work is complementary
and we hope we can collaborate and combine all efforts into one under this RFC.

## Unresolved questions

The main question is whether our kernel changes will be accepted upstream
without formal verification. This includes both hybrid and CHERI C kernel
changes. There are more implementation details and questions regarding the CHERI
C kernel as we have different approaches to that.

## Future possibilities

- Extend CHERI support to the RISC-V port.

- Support CHERI’s temporal memory safety.

- Run the entire virtualisation stack in CHERI C, including the VMM and VMs
  (e.g., CheriBSD, CheriLinux). This gives complete (spatial) memory safety for
  the entire software stack from the hypervisor, to the guest applications.

- Explore existing CHERI compartmentalisation ideas such as co-processes or
  library-based compartmentalisation [3] to provide intra-protection-domain
  isolation (e.g., in rumpkernels or library OSes running in a single seL4
  protection domain).

- Port more C-based projects to CHERI C (e.g., Microkit, rumpkernels, CAmkES,
  etc).

- Explore research ideas performing userlevel IPC using CHERI.

## Appendix

We propose supporting Morello in seL4 across 4 milestones:

1. Baseline Armv8.2-a seL4 Morello

   - To benchmark against.
   - To ensure it works with Armv8.2, interrupt controllers, and device drivers

2. Hybrid seL4 kernel + CHERI C userspace

   - Potentially less disruptive to the kernel and formal verification

3. CHERI C seL4 + CHERI C userspace

   - To benchmark disruptiveness/performance and compare CHERI C vs seL4’s C

4. Pass tests, evaluate security and performance, documentation

Each milestone is further explained with more details and tasks in the following
sections.

### Implementation Goals

- Minimise code duplication between AArch64 code and Morello (by sharing as much code as possible).

- No plans to do formal verification on this work, but aim to upstream the parts
  that don’t affect formal verification much in the kernel.

- Detect and fix CHERI security violations (e.g., out-of-bounds accesses), if
  any, in the seL4’s userspace C libraries, and hence enhance their overall
  quality and security by following CHERI C style.

- Reuse the existing C userspace code without having to re-write it.

- For a specific variation, aim to do very minimal changes to the kernel just to
  enable running CHERI C code in userspace, and not to disrupt formal
  verification much.

### Evaluation Goals

- Performance: How is performance affected by using different variants of CHERI
  (hybrid vs CHERI C) on both the kernel and userspace.

- Security: How could CHERI improve security at userlevel (e.g., how many
  security violations found there).

- Disruptiveness: How much code needs to change to adopt CHERI C at both kernel
  and user-level for different CHERI models (hybrid vs purecap).

### Baseline seL4 Morello

This will support new platforms for Morello like QEMU and the Morello board. It
will only run in AArch64 mode (i.e., no CHERI) as with other AArch64 platforms.
The affected subsystems include the seL4 kernel and user libraries. The proposed
tasks for this are:

1. Enable building seL4 projects with LLVM/LLD. seL4 has support for building
   with LLVM/Clang but not with the lld linker.

2. Make sure core device drivers work (e.g., UART, timer, GICv2/GICv3).

3. Add a new QEMU-Morello platform to the seL4 kernel and user libraries.

4. Support and run sel4test on Morello.

5. Support and run sel4bench on Morello.

This will allow us to build on and benchmark CHERI support against.

### Hybrid seL4 kernel + CHERI C userspace

CHERI capabilities are pointers with bounds, permissions, tag bit, and other
metadata. In Morello, this means any type or register that may hold a pointer is
doubled in size (i.e., 128-bit for AArch64). The existing AArch64 GPRs and some
system registers are thus extended to hold these extra data to effectively
represent a CHERI capability. Thus, CHERI differentiates between pointers
(represented as capabilities) and integers (normal 64-bit types).

In hybrid mode, unlike CHERI C (AKA purecap) mode, pointers are not
automatically converted (during compilation and runtime) to CHERI capabilities.
Only manually annotated pointers are represented as capabilities. This could
work for seL4 as it is already memory safe and does not need all pointers to be
capabilities. Instead, the kernel has to be changed to only be able to save and
restore capability registers (similar to FPU registers) in order to support
running userlevel code in CHERI C.

The significant part of this milestone would be on the existing userlevel C
code. We are aiming to adapt the existing seL4 libraries to CHERI C, where every
pointer would be a capability. This would get us complete fine-grained spatial
memory safety at the pointer level. The main changes will address mixing the use
of pointers and integers and differentiate them. For example, variables that are
known to be pointers will be held in `[u]intptr_t` or type *, and not int/long.
This includes casting and pointer arithmetic as well.

We anticipate adding a new `KernelSel4Arch=morello` similar to arm_hyp.

### CHERI C seL4 + CHERI C userspace

The only difference between this milestone and the previous one is adapting the
seL4 kernel to CHERI C style. We understand that, from the security point of
view, this isn’t going to add any benefit. However, this is just an exploration
milestone to understand:

- How disruptive/similar CHERI C is compared to seL4 C style.

- What the performance overhead is of having a CHERI C kernel.

- Could we accelerate some of the seL4’s operations (e.g., memcpy) by using
  CHERI C?

- Could we save seL4 capabilities (or encode the base and bounds/sizes) using
  CHERI capabilities?

- Would having a CHERI C kernel make some of the memory-safety-touching proofs
  run less frequently?

- Is it easier to port the seL4 kernel to CHERI C compared to hybrid?

### Pass tests, evaluate security and performance, documentation

This milestone will aim at passing all of the sel4test suite for the previous
configurations as well as reporting sel4bench results for each and comparing
them. We also want our work to be reusable by others, so we will write
documentations for what has been done, and how new users could build
CHERI-enabled applications and C-based userspace frameworks.

## References

[1] CHERI Reference Manual v9 - <https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-987.pdf>

[2] CHERI Exercises - <https://ctsrd-cheri.github.io/cheri-exercises/exercises/index.html>

[3] Almatary, Hesham, et al. "CompartOS: CHERI Compartmentalization for Embedded Systems." arXiv preprint arXiv:2206.02852 (2022)

[4] Morello Program - <https://www.arm.com/architecture/cpu/morello>

[5] CHERI webpage - <https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/>

[6] <https://github.com/seL4/seL4_libs>

[7] <https://github.com/seL4>

[8] <https://github.com/seL4Proj>

[9] <https://www.zdnet.com/article/microsoft-70-percent-of-all-security-bugs-are-memory-safety-issues/>

[10] Almatary, H. (2022). CHERI compartmentalisation for embedded systems (Doctoral dissertation, University of Cambridge).

[11] CHERI C/C++ Programming Guide - <https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-947.pdf>

[12] Morello Documentation - <https://www.dsbd.tech/technical-resources/documentation/>

[11] Experience of running hybrid CHERI userspace on seL4 - <https://sid-agrawal.ca/sel4,/cheri,/morello,/aarch64,/cheribsd/2023/01/01/seL4-CHERI.html>

[13] seL4 on Arm Morello - Martin Atkins, Mission Critical Applications Limited - <https://www.youtube.com/watch?v=YeBqmRWQWrI>
