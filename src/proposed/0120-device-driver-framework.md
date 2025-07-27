<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2022 UNSW
-->

# The seL4 Device Driver Framework

- Author: Lucy Parker
- Proposed: 2022-10-06

## Summary

The seL4 Device Driver Framework (sDDF) provides libraries, interfaces and
protocols for writing/porting device drivers to run as performant user level
programs on seL4. Specifically, the sDDF aims to:

- support a wide class of devices, including network, USB, graphics, storage,
  serial ports etc;

- achieve performance comparable to Linux in-kernel drivers, as measured by
  throughput, latency and CPU load, at least for latency-sensitive
  high-throughput devices (network cards and USB);

- be robust against defined threats;

- extend to a device virtualisation framework (sDVF) for sharing devices between
  virtual machines and native components on seL4;

- provide strong separation of concerns;

- enable the formal verification of its components.

## Motivation

The seL4 microkernel prescribes device drivers to run in user level. While this
provides strong fault containment, it can lead to performance degradation due to
the extra context switches required. Furthermore, writing/porting device drivers
to seL4 is tedious and error prone. The sDDF aims to ease this development by
defining a general device model that is performant, eliminates common causes of
driver bugs and aids formal verification. It is based on an asynchronous
transport mechanism that minimises overheads while keeping driver interfaces
simple.

The goals of the sDDF are to:

- simplify drivers by making them single-threaded and event-based

- further simplify drivers by having them serve no purpose other than
  abstracting device hardware

- exclusively use lock-free shared data structures

- avoid any data copying in the driver

- minimise trust in the driver by enabling configurations where I/O data is not
  mapped in the driver's address space


## Guide-level explanation

The sDDF will consist of:

- a general device model that enables formal reasoning and simplifies
  implementation of performant user level device drivers.

-  An asynchronous transport mechanism that provides a means of communication
   between a driver and other components in the system.

- User level libraries to ease development of I/O systems such as a network
  stack and file system.

- Sample device drivers.

The sDDF currently supports network interfaces on the [seL4 microkit] and
provides a sample Gigabit Ethernet driver as well a test configuration where the
driver's client consists of an IP stack (lwip) co-located with an echo server.
The configuration outperforms an equivalent Linux configuration on the same
hardware by a large margin.

[seL4 microkit]: https://github.com/seL4/microkit

## Reference-level explanation

For simplicity, the following explanation assumes a 2-component structure,
comprising a device driver running in one address space, and a server utilising
the driver's services in a separate address space. Multiple clients sharing a
device will require a multiplexer component that implements a sharing policy,
this leaves the driver focussed on hardware abstraction and largely policy-free.
Sample multiplexers will be provided in the near future.

The transport layer consists of a number of shared memory regions, data
structures and access protocols. The three memory regions are:

1. The control region shared between the driver and server
2. The metadata region, shared between the device and driver.
3. The data region, shared between the device and server.

The device takes instructions from its metadata region, and reads/writes data to
the data region. The data region can be considered as an array of I/O buffers.
The server and driver communicate and share the buffers via the control region.

The control region consists of single producer, single consumer, lockless
bounded queues implemented as ring buffers. There are two queues per direction.
The transmit free (TxF) queue keeps track of buffers that are ready to be
re-used for transmit. The transmit available (TxA) queue keeps track of buffers
with data available for transmit. Likewise, the receive free (RxF) queue and
receive free (RxA) queue store buffers to be re-used and with newly available
data.  The corresponding interfaces to dequeue and enqueue buffers are in
libsharedringbuffer. This library can be easily expanded to include interfaces
for request ring buffers to support storage device classes in the future.

The driver itself is event driven and acts in response to:

- Transmit requests from another component.
- Data available interrupts from the device.
- Transmit complete interrupts from the device.
- Receive buffers available signals from another component.

In this way, the driver can be a simple, single threaded component that reacts
to the above events. The driver thread runs at highest priority to ensure the
timely handling of interrupts as well as immediate response to server requests.
However, the driver could be active (with a scheduling context bound to it’s
TCB) or passive (with a scheduling context bound to its interrupt handling
notification object). The case for active vs passive drivers is yet to be fully
researched and likely depends on other component needs.

The active model uses seL4 notifications for all its interfaces.  The
notifications are used to signal updates to the shared memory regions. However,
in the passive model, the server must instead hold a badged capability to the
drivers endpoint in order to use IPC to signal updates to the control region.

The sDDF currently supports both driver models for a network device driver
running on the iMX8MM hardware, with a combined echo client and IP stack (lwIP)
operating as a server that communicate via the transport architecture as
outlined above.

## Drawbacks

While the zero-copy transport architecture enables high performance, it implies
that multiple clients would have to trust each other, which is unreasonable for
most use cases where a device is shared by multiple clients. Such cases require
a multiplexer that copies data as appropriate, or re-maps DMA buffers
frequently. The trade-offs here are not yet fully understood and are likely
dependent on the hardware platform and device class. More research is required
to fully understand these issues, this research is planned for the next calendar
year.

The sDDF is based on the newly developed seL4 Core Platform (seL4CP) and the MCS
version of seL4. At this stage, the seL4CP is still immature and only supports a
small number of hardware platforms. Furthermore, the sDDF is still missing many
components, including but not limited to:

- multiplexers;
- support for further device classes, particularly storage;
- support for other architectures/platforms;
- evaluation of more realistic use cases.

Finally, there are still many open research questions, including:

- What scenarios favour an active vs passive driver?

- What are appropriate budget/period configurations for a device driver
  servicing client/s with differing needs (eg.  client-initiated I/O vs
  device-initiated, asymmetric traffic)?

- How will the design perform when distributed over multiple cores? The
  relatively fine-grained modularity, combined with the lock-free, asynchronous
  transport, lends itself to using multiple cores without requiring extra effort
  or even code, but we have not yet evaluated that.


## Rationale and alternatives

The intention of the sDDF is that utilising the design will ease development of
user level device drivers on the seL4 Core Platform that achieve performance
competitive with in kernel drivers. Alternatives presented to date do not
achieve the level of performance we aim for, and generally result in more
complex drivers, although some ease the integration of legacy drivers.

## Prior art

The sDDF was originally implemented on the CAmkES framework. However, the
rigidity of that framework, and hidden overheads, made development difficult and
competitive performance infeasible, leading to re-targeting to the seL4CP. The
simplified, event driven model enforced by the Core Platform framework further
eases the development of device drivers on seL4.

## Unresolved questions

There is still outstanding research to be done in order to completely satisfy
the sDDF’s aims. These are outlined as drawbacks.

## Implementation

The initial proof of concept system can be found
[here](https://github.com/lucypa/sDDF). The current version of the sDDF is
hosted at <https://github.com/au-ts/sDDF>.

A more detailed design document can be found
[here](https://trustworthy.systems/projects/TS/drivers/).
