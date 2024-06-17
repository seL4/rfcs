<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 Kry10
-->

# seL4 multikernel IPI API

- Author: Kent McLeod
- Proposed: 2024-02-13

- Implementation PR: [seL4/seL4#1222]
- Verification PR: [seL4/l4v#733]

## Summary

Proposal to add an seL4 capability to generate interprocessor interrupts (IPIs).

## Motivation

There's a proposed approach for enabling multicore seL4 while still using
verified single-core configurations -- a partitioned multikernel.

As part of this approach, we need a way to both send and receive asynchronous
signals between different cores in a system. Receiving IPIs from other cores is
currently supported by existing IRQ handling mechanisms. We need to add a new
mechanism for sending asynchronous signals to another core by generating IPIs.

It's desirable for this mechanism to have minimal verification effort to add to
the baseline verified kernel implementations.

It could also be desirable for this mechanism to be able to scale from a couple
of cores up to very large multicore systems with tens or even hundreds of cores.

## Guide-level explanation

There are already hardware IPI mechanisms present on all supported platforms
that the SMP kernel uses for sending and receiving signals between multiple
cores. We can use the same mechanisms but give user level more direct access via
additional APIs for generating and receiving IPIs directly. This would allow
each single-core kernel instance to be able to send interrupts to other kernels
and receive interrupts from other kernels while having zero shared kernel state
between cores. Each kernel can think of the other kernels as just devices that
they can send and receive interrupts between each other, and delegate any shared
memory access to user level.

Breaking this new API up into two parts:

- we need a way to send interrupts to a remote core from user space,

- and we need a way to receive interrupts from a remote core and deliver them to
  user space.

Sending interrupts involves creating a new capability type, an IPI cap, that can
be created from an IRQ control cap.

- The IRQControl invocation to create the new IPI cap encodes any
  hardware-specific configuration that will be used whenever the IPI cap is
  invoked.

- The IPI Cap is invoked in the same way as a notification send cap. The sender
  cannot be blocked and the kernel is expected to deliver at-most-one event to
  the target receiver.

- The target receiver is going to be running in user space on a remote core.

- For the first implementation we'll only support unicast signalling, but
  broadcast and multicast functionality can be added later via extensions to the
  IRQControl invocation that creates the IPI cap.

It is already possible to register send-notification-caps that are invoked when
an interrupt is received so receiving IPIs doesn't require adding any new caps
and only requires limited `IRQControlCap` invocation changes on some platforms.

- The architecture specific IRQControl invocation for creating IRQ handler caps
  will need to allow creating IRQ caps for receiving IPIs.

- Then these will work with notification objects the same as all other IRQ
  handler caps.

- On Arm it's already possible to request IRQ caps to the IPI interrupt IDs so
  no changes are required.

- On RISC-V the IRQControl invocation will need to be extended to allow the SWI
  interrupt to be delivered to user level.

- On x86 it should already be possible to receive IRQs for a specified vector
  and so changes to the IRQControl invocation shouldn't be required.

## Reference-level explanation

A quick note on terminology, since each architecture uses a different name for
inter-processor interrupts:

- x86 = IPI (Inter-processor interrupts)

- Arm = SGI (Software generated interrupts)

- RISC-V = SI/SWI (Software interrupts)

So while this RFC will use IPI to refer to all three, I expect that the new
invocations we add for creating the caps will use the arch specific names as
IRQs are currently all handled by arch specific invocations.

Sending IPIs is dependent on the platform's interrupt controller.

- on Arm cores that use the Generic Interrupt Controller, there are 16 different
  interrupt IDs that can be used to receive IPIs on. A core can thus send up to
  16 different signals to each target. Once more signals are required, the
  interrupt IDs must be reused and a user-space shared memory protocol is needed
  to distinguish between messages.

- on RISC-V cores there is only one interrupt ID for an IPI. A core can send
  IPIs to multiple cores at once using the SBI API.

- on x86 cores IPIs can have an arbitrary vector ID between 0 and 255 (excluding
  reserved vectors). Sending an IPI can be to any target and with any vector.

At a minimum this is sufficient to build a user level component that implements
more sophisticated software signal multiplexing over a single hardware
interrupt. This approach creates no shared kernel state and avoids concurrency.

## Drawbacks

Some scalability limitations include:

- Using different interrupt lines to distinguish cores requires there's at least
  as many IRQ lines available for IPIs as there are cores in the system. This is
  not typically the case. When there's more cores than IRQ lines, distinguishing
  cores apart requires an additional shared memory protocol that must be
  implemented at user level.

## Rationale and alternatives

Platform specific extensions:

On Arm, the GICv2 and GICv3 have 16 lines reserved for SGI. This allows 16
different channels to be supported on each core. This may be helpful for systems
that want to support direct software signalling without having to implement a
user level component assuming their requirements are simple enough.

Future steps may involve seeking to use a method that involves direct memory
access between cores allowing shared memory to be used for more information to
be associated with each interrupt. However this leads to increased complexity
around designing and implementing protocols that can guarantee at-least-once
delivery of all signals with reasonable scalability overhead.

## Prior art

– `seL4_DebugSendIPI(seL4_Uint8 target, unsigned irq)` has existed for several
  years as a debug function for generating SGIs on ARM platforms. The current
  proposal takes this functionality and adds capability management for it. (As
  well as adding support for interrupting multiple targets as supported by GICv2
  and GICv3).

## Unresolved questions

The current proposed implementation is here, but it’s awaiting a minor update to
the revoke paths as part of some ongoing verification work:
<https://github.com/seL4/seL4/commit/7fda970d382c034c4e9b6d49b10bfbe33d4f815f>

## Disposition

The TSC approved the RFC with the following conditions:

- The RFC should be updated to remove the API for broadcast and multicast for
  now. Until we have figured out a good general model for multicast, we want to
  keep the API small so that conservative extensions are possible. The rationale
  is that for the current use case of a low number (2-16) of cores, it is cheap
  to simulate multicast and broadcast in user space via a loop over caps to each
  of the core, whereas it will be hard to change the API later if we commit to a
  specific multicast model too early. This means, the `SGISignalCap` (on Arm)
  should authorise sending to a single core (and store a single SGI number).

- The API for Arm should be updated to include higher affinity bits for GICv3 to
  support sending to more cores. For platforms that do not support these bits
  (e.g. GICv2), the corresponding `IRQControl` invocation should fail if those
  bits are attempted to be set.

- The TSC confirmed that we want the API for invoking `SGISignalCaps` to be like
  notifications, that is, the invocation should not take any parameters beside
  the `SGISignal` cap itself. The current (not yet updated) pull request for this
  RFC is [seL4/seL4#1222].

[seL4/seL4#1222]: https://github.com/seL4/seL4/pull/1222
[seL4/l4v#733]: https://github.com/seL4/l4v/pull/733
