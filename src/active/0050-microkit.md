<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 Ben Leslie
-->

# The seL4 Microkit

(Previous title: "seL4 Core Platform")

- Author: Ben Leslie
- Proposed: 2020-11-19
- Implementation repository: <https://github.com/seL4/microkit>

## Summary

The seL4 Core Platform is an operating system (OS) personality for the seL4
microkernel.

The purpose of seL4 Core Platform is to:

- provide a small and simple OS for a wide range of IoT, cyber physical and
  other embedded use cases;

- provide a reasonable degree of application portability appropriate for the
  targeted use cases;

- make seL4-based systems easy to develop and deploy within the target areas;

## Motivation

The seL4 microkernel provides a set of powerful and flexible mechanisms that can
be used for building almost arbitrary systems. While minimising constraints on
the nature of system designs and scope of deployments, this flexibility makes it
challenging to design the best system for a particular use case, requiring
extensive seL4 experience from developers.

The seL4 software ecosystem currently provides various options for developing
systems on seL4, however, such support is both overly broad (providing too many
options) and simultaneously too limited for many developers.

The seL4 Core Platform addresses this challenge by constraining the system
architecture and to one that provides enough features and power for this usage
class, enabling a much simpler set of developer-visible abstractions.

The goals of the platform are to:

- provide well-defined hardware interfaces to ease porting of the Platform;

- support a high degree of code reuse between deployments;

- provide well-defined internal interfaces to support diverse implementations of
  the same logical service to adapt to usage-specific trade-offs and ease
  compatibility between implementation of system services from different
  developers;

- leverage seL4's strong isolation properties to support a near-minimal trusted
  computing base (TCB);

- retain seL4's trademark performance for systems built with it;

- be, in principle, amenable to formal analysis of system safety and security
  properties (although such analysis is beyond the initial scope).

## Guide-level explanation

The seL4 Platform consists of:

- an seL4 Platform specification, which defines the key platform abstractions
  and platform API

- an seL4 Platform implementation, which provides implementations of the key
  abstractions and API

- definitions of key OS service interfaces and implementations of these

## Scope

The initial focus and scope of this RFC is on defining the key seL4 Platform
abstractions, which build on seL4 abstractions.

The seL4 Platform abstractions are:

- processor core (core)
- protection domain (PD)
- communication channel (CC)
- memory region
- notification
- protected procedure call (PPC)
- virtual machine (VM)

More details about these abstractions, and how they build on seL4 abstractions,
are available in
<https://github.com/BreakawayConsulting/platform-sel4-docs/blob/master/sel4-platform.md>

## Reference-level explanation

While this RFC initially targets the main platform abstractions, ultimately the
platform will provide an SDK (including interfaces, libraries, services, and
tools) for building seL4 Platform based systems.

The platform implementation (and SDK) could be based on, and incorporate,
existing technology such as CAmkES, capDL, seL4 runtime, seL4 driver framework,
etc. however this has not been decided yet.

The seL4 Platform will initially be limited to a small set of hardware
platforms. This is to ensure that effort is focussed on fully supporting the
platform on this hardware.  Ports to other hardware can be contributed by
others.

## Drawbacks

The RFC currently only presents the seL4 Platform concepts.  These have not yet
been implemented nor have they yet been used to build concrete systems.

While the intention of the seL4 Platform is to focus seL4 ecosystem and
developer effort on a single (well defined and supported) model, the danger is
that it adds yet another set of tools and platforms/frameworks to the mix making
it even less clear what developers should use.

## Rationale and alternatives

The intention is that experience from building seL4-based systems and developing
and using previous existing platforms/frameworks/libraries/tools will lead to a
more suitable and usable Platform definition that will supersede some of the
earlier platforms/frameworks/libraries/tools and that new (and existing)
developers will migrate to the seL4 Platform.

## Prior art

Prior (and similar) art includes:

- CAmkES
- Genode
- TRENTOS
- AADL and HAMR
- feL4
- various other (ad hoc) software

## Unresolved questions

This RFC addresses the first step towards defining the full seL4 Platform.

It does not provide a roadmap to the further steps.

## Disposition

The TSC has approved this RFC in today's (12 Sep 2023) meeting and also approved
a name change to the Microkit (or seL4 Microkit if context is needed).

The design concerns from previous meetings have been addressed and
implementation is expected to converge to that design. The repository will be
moved to the seL4 GitHub organisation.
