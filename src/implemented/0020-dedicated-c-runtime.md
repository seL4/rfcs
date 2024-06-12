<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2019 Data61, Curtis Millar
-->

# A dedicated C runtime for seL4

- Author: Curtis Millar
- Proposed: 2019-01-04

## Summary

Many languages provide a runtime in order to provide the initial abstractions to
run code within an operating system process. Many borrow heavily from the
runtime provided by the C library.

A new runtime will be provided to abstract the interface provided to seL4
processes. It will be the most minimal set of abstractions needed to allow a
process to run and access all of the language features that must be supported by
the runtime directly. All abstractions commonly available in a standard library
(such as allocators and thread-creation) will then be left as to be supported
via external libraries.

## Motivation

Most seL4 projects currently rely on a fork of the musl libc library and runtime
to provide process initialisation and libc support. Due to the modifications
made to this port, it is difficult to benefit from any upstream maintenance.

An official internally supported runtime would decouple these projects from musl
libc and allow the use of alternative C standard libraries (such as newlib and
external pthread libraries) without need for modification.

The runtime would also have little to no external dependencies or conflicts
allowing it to be used as the basis for other language runtimes and to support
library-OS projects on seL4.

## Guide-level explanation

The runtime would support two types of process being created; those starting in
the style of the seL4 initial process, and those starting using the static
System-V ELF loaded method.

The runtime would require the sysroot within which code is compiled to ensure
that its runtime objects are compiled and linked with all binaries built, that
its library is linked into all binaries, and that its link script is used with
all libraries being built.

Code built with the library would run from an initial `main` function as would
normally be the case in an C program and the full range of features such as
thread-local variables and dynamic constructors and destructors would be
available.

Additionally, a few mechanisms that reflect particular abstractions available to
seL4 would be made available to processes and threads running within the
runtime. These would exist to support abstractions that would be common in
systems built on seL4 that rely on communication between user level programs.
These would include mechanisms for informing processes of their capability state
and location of their IPC buffer.

## Reference-level explanation

The runtime is primarily responsible for constructing the environment in which
code expects to run. This means that it should have a functioning stack and that
all library systems should be fully initialised, and the initial thread's
thread-local storage should be correctly initialised.

As such, the first thing the runtime needs to do for a seL4 initial process is
create the stack and construct the initial System-V stack data (command line
arguments, environment variables, and auxiliary vector).

For all processes, the runtime must then configure the TLS region for the
initial thread using information found in the auxiliary vector. It should also
record this information to allow it to later construct and modify TLS regions
for newly created threads.

The runtime must then initialise all global runtime state, such as state that
records the initial capability layout of the process.

After that, all constructors for the binary, including all library constructors
must be run.

Finally, the stack information for the command line arguments and the
environment variables must be passed to the main function as it expects to
receive them.

The runtime must also provide routines for handling process exit. These should
ensure that that all dynamic destructors are run before the process exits.

## Drawbacks

This will become a maintenance burden and, as it will be relied upon for
production systems, would require a similar level of support as the kernel.

Making this runtime will probably lead to particular patterns being enforced
across all processes running on seL4. Design decisions made in the development
of this runtime must be thoroughly considered as they will form the basis of
effectively all processes running on seL4.

## Rationale and alternatives

Existing runtimes from well supported libc implementations could be used,
however they are all tightly coupled to the operating systems for which they are
purpose-built and supporting them requires emulating many of the abstractions
provided natively by those operating systems. For example, to support
thread-safety in muslc, the Linux futex API must be emulated to support musl's
locking mechanisms.

Providing an entire C library and runtime to fully support the entire C language
requirements is another alternative, however there is no sufficient reason to
maintain a C library when an external C library, such as newlib, can be easily
supported with minimal abstractions over existing seL4 concepts.

## Prior art

Many of the seL4 rapid development libraries utilise a common set of patterns,
some of which are sufficiently common that should be standardised at this level.

The musl libc runtime is a primary reference for this implementation.

## Unresolved questions

What are the natural abstractions that should be available to all processes
running under seL4?

What patterns should this encourage or standardise?

## Future possibilities

This runtime will allow for further, more high-level abstractions such as
re-usable allocators and POSIX-style threading libraries to be provided.

## Disposition

After much internal discussion this been approved. Development will happen in
the [seL4/sel4runtime] repository. This will depend on the outcomes of the RFC
[Cross-platform thread-local storage support][RFC-3] and so will not be usable
until that is approved and implemented.

[seL4/sel4runtime]: https://github.com/seL4/sel4runtime
[RFC-3]: https://github.com/seL4/rfcs/blob/main/src/implemented/0030-cross-platform-tls-support.md
