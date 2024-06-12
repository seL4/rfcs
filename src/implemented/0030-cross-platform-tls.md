<!--
  SPDX-License-Identifier: MIT or CC-BY-SA-4.0
  Copyright 2024 seL4 Project a Series of LF Projects, LLC.
  Copyright Rust Language Community

  Based on the Rust RFC template at <https://github.com/rust-lang/rfcs>
-->

# Cross-platform thread-local storage support

- Author: Curtis Millar
- Proposed: 2019-01-04

## Summary

Currently, the kernel does not support thread-local storage (TLS) on all
platforms it otherwise does support. In particular, there is no such support for
TLS on RISC-V.

This proposal seeks to ensure that the kernel and supporting libraries support
static TLS on all platforms. Due to hardware and ABI restrictions however, this
also requires changing the user-level API for determining the location of IPC
buffers.

This change would see that all platforms can use TLS, but that it would be
entirely the responsibility of user-level to determine and track the location of
IPC buffers for each thread and for newly created processes. In addition, a
configuration-dependent `seL4_SetTLSBase` system call would be added, allowing a
thread to change the value of its own TLS register without a capability to its
own TCB.

To assist with the creation of threads using TLS, the [seL4 runtime] will
provide simple primitives for initialising and modifying the TLS of threads from
within a running process as well as initialising the TLS of System-V style
processes.

## Motivation

seL4 already supports TLS on some platforms in the same manner as the Linux ABI.
On aarch32 (ARMv7 and newer) and aarch64, TLS is supported via a EL0 readable
control coprocessor process ID register. On x86, the TLS region can be
dereferenced from a general purpose segment register.

Many projects on seL4 utilise TLS to store state associated with particular
threads. This feature is used particularly heavily in library-OS projects.

The kernel supports the IPC buffer as a kind of thread-local storage area on all
platforms. With the kernel supporting generic TLS on all platforms, this would
no longer be necessary as threads would simply be able to record the address of
their IPC buffers in their TLS region.

To allow for implementations of green-threading and to allow a process to
initialise its own TLS without a capability, threads would be able to modify
their own TLS address using seL4_SetTLSBase across all platforms where they
would not otherwise be able to modify the designated TLS register directly. This
ensures that across all platforms, the TLS Base register is viewed as being
completely mutable by the executing thread, just like all of the general purpose
registers.

On platforms where the TLS Base register can be set in unprivileged mode
(aarch64, aarch32 with the `c13` control register, riscv, and x86_64 with
`FSGSBASE set`), threads should set their TLS address without the use of the
invocation.

## Guide-level explanation

### Thread-local storage

Any code running on seL4 can use thread-local variables within its code. These
variables will be initialised to the same value for each new thread (unless
modified by the thread creator).

For gcc-compatible C code, this is as simple as marking a global or static
variable with the `__thread` attribute or the C11 standard `_Thread_local`
attribute.

When constructing a thread, it is the responsibility of the code constructing
the thread to ensure that the layout of the TLS region follows the appropriate
layout for the given platform (the seL4 runtime will provide the tools necessary
for this on supported platforms).

It is also the responsibility of the runtime of the process being started to
correctly initialise the TLS of the initial thread of a process (the seL4
runtime will perform this task for System-V style processes on all supported
platforms).

### Determining the location of the IPC buffer

A thread can determine the address of its IPC buffer via the `__sel4_ipc_buffer`
thread-local variable provided by libsel4. This must be initialised when the
thread is created to refer to the location of the thread's IPC buffer.

libsel4 will also continue to provide the seL4_GetIPCBuffer function that
returns the address of the current thread's IPC buffer, however this will now
simply read the value from the thread-local variable.

## Reference-level explanation

### Implementation of TLS

The kernel will support TLS in a manner allowing for the use of System-V style
TLS using the same TLS ABI as Linux. In particular it will use the following
registers on the following platforms to store the thread identifier (the address
of the TLS region).

- `fs` on x86_64

- `gs` on ia32

- `tp` (`x4`) on RISC-V

- `tpidrurw` where it is available on AArch32 and the GLOBALS_FRAME otherwise.
  This requires building for the arm ELF EABI (code generated for
  `arm-none-eabi` assumes no operating system and an emulated TLS rather than an
  ELF style TLS) and building with the `--mtp=soft` option to use the thread ID
  lookup function from the [seL4 runtime] rather than the Linux default of using
  `tpuiduro`.

- The `tpidr_el0` register on aarch64

The seL4 runtime will provide full support for TLS for each platform but will
only support the *local static* TLS model on supported platforms. Statically
linked code will be able to use TLS whilst dynamically linked code will not. It
will use TLS variant appropriate for each platform (variant I for Arm and RISC-V
and variant II for x86).

For more information, see [Elf Handling For Thread-Local
Storage](https://www.uclibc.org/docs/tls.pdf).

### Managing the IPC buffer address

The seL4 runtime will expect the IPC buffer address of the initial thread to be
passed via an AUX vector as part of the System-V ELF process loading.

The runtime will also provide a mechanism to allow for modifying thread-local
variables, such as `__sel4_ipc_buffer`, of other threads.

### Kernel change

Only a holder of a TCB capability is able to modify the IPC buffer address and
page for that TCB and only the kernel is able to read either for that TCB. There
will be no way to determine the IPC buffer address either as the running thread
or as the holder of the TCB capability.

The kernel will consider the register used for the TLS base and all thread
identifier registers that can be written to from user mode to be general-purpose
registers and saves and restores them with all other registers upon trap and
context switch.

- **aarch32 (with GLOBALS_FRAME)**

  - **Before:** The kernel writes the IPC buffer address and `TLS_BASE` to a
      global frame mapped into all virtual address spaces as read-only (the
      `GLOBALS_FRAME`). Both require an invocation to change.

  - **After:** The kernel writes the `tpidr_el0`/`tpidrurw` and
      `tpidrro_el0`/`tpidruro` to the `GLOBALS_FRAME`. The values in the globals
      frame are saved and restored with all other general-purpose registers. The
      thread can update its own TLS register (`tpidr_el0`/`tpidrurw`) using
      `seL4_SetTLSBase`.

- **aarch64 and aarch32 (with `TPIDRURW` & `TPIDRURO`)**

  - **Before**: The kernel uses `tpidr_el0`/`tpidruro` for the TLS register and
      `tpidrro_el0`/`tpidrurw` for the IPC buffer. It writes both from virtual
      registers and requires an invocation to change either.

  - **After**: A thread uses `tpidr_el0`/`tpidrurw` for TLS which can be written
      to from user mode. The kernel saves and restores `tpidr_el0`/`tpidrurw`
      with all other general-purpose registers.

- **x86_64**

  - **Before**: The kernel uses `fs` as the TLS register and `gs` for the IPC
      buffer. It writes to both from virtual registers in the TCB and requires
      an invocation on the TCB to change either.

  - **After**: A thread uses `fs` as the TLS register. *The kernel always
      enables `FSGSBASE` to allow user mode to write directly to `fs` and `gs`*.
      The kernel saves and restores fs and gs with all other general-purpose
      registers.

- **ia32**

  - **Before**: The kernel uses `gs` as the TLS register and `fs` for the IPC
      buffer. It writes to both from virtual registers in the TCB and requires
      an invocation on the TCB to change either.

  - **After**: The kernel uses `gs` as the TLS register. The kernel saves and
      restores `gs` with all other general-purpose registers. The thread can
      update its own TLS register using `seL4_SetTLSBase`.

- **riscv**

  - **Before**: The kernel uses `tp` for the IPC buffer. The kernel writes to
      the `tp` virtual register in the TCB and requires an invocation to change
      it.

  - **After**: A thread uses `tp` as the TLS register which can be written to
      from user mode. The kernel saves and restores `tp` with all other
      general-purpose registers.

In all cases, the holder of the TCB capability can read and modify the any
newly-defined general purpose registers (virtual or otherwise) using
`seL4_TCB_ReadRegisters`, `seL4_TCB_WriteRegisters`, and
`seL4_TCB_CopyRegisters`.

## Drawbacks

This change requires more work by user code for threads to be able to determine
the location of the IPC buffer. The addition of a provided runtime will take
care of most of this additional work.

This requires anyone compiling code for seL4 to use a linux-compatible ABI or
with compilers that support the given TLS ABI. Any code using the seL4 runtime
or libsel4 will need to be compiled with such compilers.

Code used to create new processes will need to be modified to pass the IPC
buffer address via the auxiliary vectors.

## Rationale

In order to make the best use of existing standards and tooling that supports
them, we have decided to borrow from the implementation used across many
Unix-like platforms such as Linux.

We could achieve the user level support for this by modifying our fork of the
musl libc runtime to co-operate with whichever standard we chose. However, due
to ongoing growing pains as well as not wanting to tightly couple seL4 to a
particular fork of musl, providing support as part of the seL4 runtime is more
appropriate.

## Prior art

All major operating systems implement TLS in a similar manner. Many UNIX
operating systems (such as Linux) use this exact model.

Many Linux libc alternatives (such as glibc and musl) provide similar support
for Linux's TLS implementation. The musl implementation is the primary reference
for this implementation.

## Unresolved questions

How will code written in other languages operate with the new requirements for
managing the IPC buffer address? How will they be able to leverage TLS?

## Future possibilities

Given that the current support is only intended to allow for static binaries
with no dynamic linking, this could be extended in the future to also cater to
dynamically linked binaries that have been loaded via some linker as well as
libraries that perform internal dynamic library loading.

## Disposition

After long discussion internally as well as external interest this has been
approved and implementation is underway and will occur in the seL4 repository.
Implementation will occur in conjunction with that of the [seL4 runtime] will
provide the runtime and interface necessary to utilise the features.

[seL4 runtime]: ./0020-dedicated-c-runtime.md
