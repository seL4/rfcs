<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2020 Ben Leslie
-->

# The seL4 Core

- Author: Ben Leslie
- Proposed: 2020-11-19

## Summary

The seL4 Core is the essential set of seL4 components that are needed to build
**any** seL4-based system. These include systems built on the seL4 Core
Platform, but also other classes of systems, such as dynamic systems and minimal
systems based on directly supporting run-times for languages like Rust or
Erlang.

## Motivation

There are several complications and restrictions of the current state of the
seL4 software ecosystem that complicate using seL4 to develop systems.

In particular:

- the requirement to use the CMake-based build system
- the requirement to use the muslc C library
- the assumption that one of the provided higher-level frameworks (e.g. CAmkES,
  the dynamic prototyping libraries, etc.) will be used. These impose some
  policy on the resulting systems.  Trying to untangle the core of seL4 from
  this is complicated.
- the number of (kernel) configuration options (and understanding which
  combinations are supported and how well they are supported)
- the varying quality of support for different hardware platforms, i.e. not all
  supported hardware platforms are equally well supported (e.g. not all kernel
  configs supported, not all tests pass, kernel is not verified, etc.)

The goal is to identify a core set of components that the developer of any
seL4-based system will use.

Such a core should not impose policy that restricts the design space enabled by
se4. This policy freedom applies to both run-time and build-time.

Furthermore, this core must be of high quality.

High quality means:

1. It must be clearly documented which boards and configurations are supported.
2. It must be clearly documented which configurations use a verified kernel
3. If there is a verified kernel for a platform, the Core must use it.
4. All the supported boards must support all configurations.
5. The release must include a way to test the functionality and performance of
   the components.
6. All the individual tests and benchmarks must be clearly documented as to their purpose.
7. All the tests must pass.
8. All the benchmarks must run and provide reasonable results; any marketing
   material as to kernel performance must be based these benchmarks for a
   release version only.
9. The release must include evidence of tests and benchmarks (so a human
   readable report with clear traceability must be included as part of the
   release).
10. The release must include a cryptographic hash of the contents that is
    clearly published on the website.
11. The build must be reproducible; a user must be able to take the source
    release and generate a bit-for-bit accurate copy of the release.
12. Any configuration options must be documented, including explaining why/when
    a user would want to set it (ideally fewer options the better).
13. All APIs must be accurately documented.
14. Source code of the core must be high-quality and an exemplar for users.
15. Any JIRA tickets associated with the configurations / boards have been
    resolved. Or, if not, are very clearly spelled out in the release notes.

## Guide-level explanation

The seL4 Core consists of:

- an SDK
- tests (sel4test)
- benchmarks (sel4bench)
- documentation

The SDK consists of

- kernel binary
- sel4corelib: a minimal C library with no dependencies
- simple starter root task code
- minimal linker file
- image building script
- SHA hashes of source used to build the kernel

The SDK does not contain:

- a Makefile (or other build system files)
- kernel source
- build tools (including compiler, etc.)

There should be a simple directory layout per board/configuration. A user, in
their build system, would point to and use the appropriate SDK directory.

More details can be found in:
<https://github.com/BreakawayConsulting/platform-sel4-docs/blob/master/sel4-core.md>

## Reference-level explanation

The SDK could be delivered as a single tar file.

This means that:

- users never have to deal with repo (unless they want to)
- users don't have to deal with cmake (unless they want to)
- users can start and build up easily.

As an example, a developer wishing to start development with the SDK would:

- Download the binary SDK
- Open a text editor with "rootserver.c"
- Type in the classical hello world.
- Compile with `gcc -I$SDK/include -L$SDK/lib -lsel4 rootserver.c -o rootserver`
- Create an image `$SDK/bin/build_image_script rootserver -o bootable_image`
- Run the image on their board

Ultimately the code to generate seL4 Core should just all go in a single
repository, removing the need for a tool like `repo` to manage multiple
repositories (not that systems built on to of the Core (e.g. CAmkES) may still
span multiple repositories and use repo (or other approach to managing multiple
repositories).

## Drawbacks

The core platform would limit the set of supported platforms.  A limited set of
platforms will never please everyone - there will be potential users who are not
well served by the seL4 Core and would/could be alienated by this.

There is the risk that developers start with the seL4 Core and do not move
beyond it. Re-inventing higher-level platforms and frameworks, rather than using
existing ones.

## Rationale and alternatives

This seL4 Core aims to solve two problems with the seL4 software ecosystem:

- to much policy/framework required when using seL4
- low quality support for some most hardware platforms

Alternatives are

- to provide only the kernel source
- require developers to use higher level platforms and frameworks (like CAmkES)

## Prior art

- the existing seL4 codebase
- various projects (e.g. Genode) using only the seL4 kernel and no the other
  related code

## Unresolved questions

- which hardware platforms should be targetted?
- how many hardware platforms should be supported?
