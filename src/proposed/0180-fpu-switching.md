<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 Proofcraft Pty Ltd
-->

# FPU Context Switching

- Author: Gerwin Klein, Rafal Kolanski, Indan Zupancic
- Proposed: 2024-06-21

## Summary

We propose to let user level configure policy on when FPU context is switched
instead of relying on runtime faults to switch FPU context lazily. Policy is
configured via a flag in the TCB, authorised by the corresponding TCB
capability.

This improves performance, moves policy from kernel to user, enables verification
of FPU handling, and fixes an information leakage in current FPU context
switching.

## Motivation

Current FPU context switching in seL4 disables the FPU on kernel exit, waits for
a thread to fault when it accesses the FPU, transparently handles the fault,
saves/restores FPU context, and then returns to the thread.

The motivation for this scheme was that threads that never use the FPU do not pay
for FPU context switching cost. However, it has the following problems:

- this is a fixed context switching policy in the kernel;

- most of this complexity is invisible to the current formal verification, and
  therefore not covered by the proofs;

- when switching between domains, this scheme introduces information flow
  leakage, because the kernel performs actions on behalf of domain A while
  running in domain B: assuming A and B are the only domains, the first thread
  running in domain B can determine whether a thread in domain A used the FPU
  simply by using the FPU itself, since kernel FPU save/restore actions will
  only occur if another thread used the FPU.

- performance of this scheme is not optimal -- taking a fault every time the FPU
  is used adds unnecessary overhead, especially in systems where FPU usage is
  high.

The proposed scheme fixes these problems and maintains the original intent that
threads which do not use the FPU should not pay FPU context switching cost.

The assumption is that application threads are likely to be using the FPU, and
that low-level OS threads are unlikely to be using the FPU. One particular case
we are aiming to cover is an application thread calling the OS and the OS
returning to that thread. Ideally, this case should not need to save or restore
any FPU registers.

## Guide-level explanation

### Concepts

- The TCB will get a new flag `fpuDisabled` that determines whether the FPU is
  disabled or enabled when the kernel switches to the thread. If the FPU is
  disabled and the thread  uses the FPU, a fault is generated and delivered to
  the thread's fault handler like other faults. If the FPU is enabled, FPU
  context is saved and restored as needed. There is no more kernel-level
  transparent FPU fault handling.

- For backwards compatibility, the flag is initially false (the FPU is enabled)
  on platforms that have FPU enabled at kernel configuration time.

- The flag can be set/cleared via the new `seL4_TCB_Set_Flags` invocation of the
  corresponding TCB capability. This allows user level to configure fine-grained
  FPU context switching policy.

### High-level Performance Considerations

The following high-level properties will hold:

- When no thread is configured to use the FPU, no FPU context switching happens
  after initialisation.

- When all threads are configured to use the FPU, the scheme is equivalent to
  eager FPU switching, that is, FPU context is always saved and restored, no
  matter if the threads actually use the FPU or not.

- On domain exit, the current FPU context is always saved when it exists.

- Calls from FPU-threads to exclusively non-FPU threads do not trigger any FPU
  context save/restores.

  For example, consider three threads A, B, and C. A is configured to use the
  FPU, B and C are not. Switching from A to B will not need an FPU context save
  or restore, neither will switching from B to C or C to B. Switching from B to
  A only requires an FPU context save/restore if another thread has run in
  between that was configured to use the FPU.

<!-- TODO: add mermaid diagrams -->

## Reference-level explanation

Adding the flag to the TCB will not increase the TCB object size, and is
consistent with other TCB parameters authorised by the TCB cap.

The default is chosen so that a value of 0 (cleared memory after `retype`) means
that the FPU is enabled. That means user-level code that does not know about the
new FPU switching scheme will be able to use the FPU as before.

As it does now, the kernel will maintain a current FPU owner, which will be a
pointer to a TCB. The invariant on that pointer is that it points to the TCB of
the most recently running thread that was configured to use the FPU. It is the
TCB the current FPU state has to be saved to.

- When the kernel switches away from a thread, no FPU save/restore actions
  happen.

- When the kernel switches away from a domain, the current FPU context is always
  saved.

- When the kernel switches to a thread where the FPU is *disabled*, no FPU
  context actions happen.

- When the kernel switches to a thread where the FPU is *enabled*, the FPU
  context of the current owner is saved, and the FPU context of the new thread
  is restored. The current FPU owner is updated to the new thread.

<!-- TODO: add flow chart diagram -->

### API

#### TCB_Set_Flags

`static inline int seL4_TCB_Set_Flags`

Clear and set feature flags of the specified TCB -- in that order, i.e. when a
flag is both cleared and set, it will be set.

| Type        | Name       | Description                                     |
| ----------- | ---------- | ----------------------------------------------- |
| `seL4_TCB`  | `_service` | Capability to the TCB to set flags on           |
| `seL4_Word` | `clear`    | Bit 0: set to 1 to clear the `fpuDisabled` flag |
| `seL4_Word` | `set`      | Bit 0: set to 1 to set the `fpuDisabled` flag   |

Flags that are not available on the current platform or configuration will be
ignored. Currently only bit 0 (`fpuDisabled`) is available on platforms with
`CONFIG_HAVE_FPU`.

The function returns `seL4_NoError` for success as usual, and
`seL4_InvalidCapability` if the provided capability is not a TCB capability.

### Verification Impact

Verification impact should be moderate.

The following items will need to be added to the specifications and proofs on
all verification configurations that have FPU proof support (`ARM
imx8-fpu-ver`, `AARCH64`, `X64`).

- added `seL4_TCB_Set_Flags` system call decode and perform functions
- change to `TCB` object state, including default retype reasoning
- the owner of the FPU state will be tracked, which needs new invariants. For
  example:
  - when a current owner exists it always points to valid TCB
  - this TCB belongs to the current domain

The following main parts of the proof stack are affected by these:

- specifications: abstract spec, design spec, capDL spec
- functional correctness, all levels
- fast path for `ARM` and `AARCH64` (additional check for FPU)
- access control
- information flow
- capDL and system initialisation

While the changes are cross-cutting, we think the new invariants will remain
relatively isolated and will not require much interaction with existing ones.

### Potential Optimisations

- On Arm it is possible to interleave loading and storing of the FPU registers,
  which might be faster than first loading and then storing all registers. This
  interleaving is only possible if there is always an FPU context to save when
  there is one to restore. We propose to leave this up to the implementation
  phase.

- Newer x86 CPUs support the `XSAVES` instruction, which combines `XSAVEOPT` and
  `XSAVEC`. That means together with the high overhead of disabling the FPU,
  lazy switching may not make sense on newer x86 CPUs and the user may want to
  configure all threads as FPU threads.

- There are multiple options on how to represent the state where there is no
  current FPU owner. This happens at the start of the system where no FPU thread
  has run yet, and at the start of a domain when no FPU thread has yet run in
  that domain. This state could be represented by a NULL owner, or it could be
  represented by pointing to a dummy thread, e.g. the idle thread. The latter
  implies that the pointer always points to a valid thread and that the current
  FPU context can always be saved, even if there is no current owner. This would
  remove testing for NULL in the (very) frequent case where a current owner
  exists and would add a superfluous context save in the infrequent case where
  no owner exists. Doing this might complicate the information flow proofs where
  the FPU context of the idle thread would have to be modelled (and proved) as
  unobservable to the user. However, it may also reduce timing differences at
  domain switch (modulo caching), because each domain switch will always have a
  context to save.

## Drawbacks

- Compared to the current scheme, user level now needs to explicitly disable the
  FPU for a thread when no FPU context switching is required. This requires more
  system analysis than before. However, if user level is not consciously
  treating the FPU, it is likely that modern compilers on most architectures
  will at least use SIMD instructions that use FPU registers, which means that
  the default of "FPU enabled" should be the correct choice for such systems.

- For a workload where many threads do use the FPU, but use it only occasionally,
  the proposed scheme would perform
  many more FPU context switches than the current fault-based lazy scheme.

  In this case, it would still be possible to emulate the fault-based lazy
  scheme from user-level:

  - the rare-FPU thread is set to FPU disabled
  - when it does use the FPU, the user-level fault handler gets the
    corresponding fault
  - the fault handler enables the FPU on this thread and restarts it
  - the thread could either stay FPU enabled or be FPU-disabled again after its
    time slice or budget are up, depending on system policy.

  This does have more overhead than the current in-kernel transparent fault
  handling, but not massively more, and it allows full user-level control and
  trade-offs. For instance, this could also be used for starting all threads as
  FPU-disabled and enabling FPU for them on demand. That would yield low
  amortised overhead without needing system analysis.

## Rationale and alternatives

There are multiple alternatives to the semi-lazy context switching scheme
proposed here. The main classes are:

- fully eager -- FPU context is always saved and restored
- semi-lazy with early context saving -- FPU context is always saved when
  switching away from an FPU-enabled thread and always restored when switching to
  a FPU-enabled thread
- fault-based lazy -- the current scheme in seL4

This RFC has already argued that semi-lazy is preferable to the current scheme
for multiple reasons (policy, performance, verification). Compared to eager
switching, the proposal has the following advantages:

- Fully eager represents another fixed kernel policy vs configurable policy.
- Fully eager switching can be achieved in the proposed scheme by setting all
  threads to FPU enabled. The only overhead this is incurs is one branch test
  which checks the flag and always finds the FPU enabled.
- Fully eager switching does not perform well on all work loads, for example a
  common use case in the device driver framework is a chain of OS
  producers/consumers that do not use FPU, called by an application that
  potentially does use the FPU.
- If the one-branch-test overhead for fully eager switching in the proposed
  scheme is important for a specific workload, it would be possible to provide
  an optimisation: have an always-eager compile-time config flag that statically
  sets the `fpuDisabled` flag to `false`, which eliminates the branch. This
  would disallow disabling the FPU in `seL4_TCB_Set_Flags`. We do not anticipate
  this to be needed currently, but it is an option for the future if this turns
  out to be a common case.

The proposed scheme is slightly more complex than the semi-lazy scheme with
early context save, and early saving would not need any special treatment on
domain switch, but the targeted use case of OS threads without FPU called by an
application thread with FPU would still need one FPU context save and restore,
whereas the proposed scheme does not require any.


## Prior art

There has been initial [discussion] and a [draft pull request] for a proposal to
introduce an FPU object to seL4, which served as inspiration for this RFC. The
FPU object proposal similarly makes context switching configurable by binding or
not binding an FPU object to a TCB, and implements a similar switching strategy.

Adding a new object to the API has much higher implementation+verification
impact as well as higher API breaking impact for user-level systems. The issue
of memory-backing for the FPU is orthogonal to the issue of when to context
switch the FPU. The approach proposed here focuses on context switching only,
which keeps verification manageable. The performance numbers we measured for the
proposal in this RFC are similar to the numbers obtained in the FPU object proposal.

If TCB size and memory pressure do turn out to be an issue in practice, the FPU
object can still be added on top of this RFC in the future.

[discussion]: https://sel4.discourse.group/t/pre-rfc-fpu-as-an-object/475
[draft pull request]: https://github.com/seL4/seL4/pull/821

## Performance Numbers

The following numbers compare the fault-based lazy switching (current seL4
implementation) with fully eager switching (FPU always on). The tables will
be updated when more results are available, including an implementation of
the proposed semi-lazy switching without faulting.

These measurements should give an indication of the trade-off space: lazy
fault-based switching where no thread is using the FPU should be the same as the
base line, because the FPU is always off. Eager switching is the highest context
switching load. The space in between has trade-off between these and cost for
enabling/disabling the FPU, potentially more complex logic, and taking faults.

Expectations for final performance: Task with FPU enabled will behave close to
eager switching and tasks with FPU disabled will behave like the current lazy
switching, which always disables the FPU at task switch.

All tests done on non-SMP, non-MCS and release builds of seL4 and `sel4bench`.
Keep in mind that all cycles are not in CPU cycles, but in platform specific
fixed clock cycles, hence the numbers should not be compared between boards.

### AArch64

The AArch64 `tqma` system:

| Cortex-A35 | Call | ReplyRecv |
|------------|-----:|----------:|
| Old Lazy   |  311 |       328 |
| Eager      |  429 |       493 |

Basic save + restore overhead seems to be about 120 cycles (after aligning
`fpuState`). The unexpected extra slowdown for `ReplyRecv` may be because of
secondary effects, like less optimal memory accesses. Performance is mostly
limited by store and load throughput.

On ARM enabling and disabling the FPU is cheap.

<!-- TODO: Measure trap overhead (1k cycles?). -->

### x86

The `skylake` system:

| Skylake    | Call | ReplyRecv | Consumer to producer |
|------------|-----:|----------:|---------------------:|
| Old Lazy   |  157 |       163 |                 2455 |
| Eager      |  556 |       527 |                 1203 |
| Sync no FP |      |           |                  945 |

The other sync tests had similar results. The compiler is much more eager to
use SIMD instructions on x86 compared to AArch64, causing FPU traps during the
sync tests. The Last column shows the FPU trap overhead.

When compiling the sync test with `-mgeneral-regs-only`, the lazy FPU sync
results are much better, see "Sync no FP" row. However, the result is only ~250
cycles faster instead of the expected 350-400, compared to eager switching.

| Comet Lake | Call | ReplyRecv | Consumer to producer |
|------------|-----:|----------:|---------------------:|
| Old Lazy   |  124 |       126 |                 1839 |
| Eager      |  427 |       405 |                  926 |
| Sync no FP |      |           |                  675 |

Other measurements have been made, and all-in-all the x86 performance
measurements do not seem very reliable. For instance, adding extra FPU
disable+enable calls added 300 cycles, which should be similar to the cost of
`XSAVE`+`XRSTOR`, yet we don't see that in the actual results.

Other examples are measuring 2k trap overhead cycles, while the difference
between "Sync no FP" is around 1.5k on Skylake, and getting much worse results
when compiling the IPC test with general regs only too, while from the results
it is clear that no trapping happens, so there should be no FP instructions used
during the measured window.

A cycle counter overhead of 200 seems to complicate things too. For x86 it may
be better to use PMU counters instead of `rdtsc`.

### Benchmark Conclusions

Although micro-benchmark results are much worse for eager switching, on a macro
level the results are dramatically better if the FPU is used at all. The proposed
semi-lazy switching with FPU flag should get the best of both approaches.

## Unresolved questions

1. While the internal representation needs to be `fpuDisabled` to get the right
   default, it may be nicer for the API to present the inverted flag
   `fpuEnabled` instead.
