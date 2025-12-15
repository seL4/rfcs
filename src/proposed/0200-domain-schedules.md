<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2025 Proofcraft Pty Ltd
-->

# Runtime Domain Schedules

- Author: Gerwin Klein, Rafal Kolanski, Indan Zupancic
- Proposed: 2025-09-10

## Summary

We propose to add the ability to set, maintain, and switch between domain
schedules at runtime, authorised by the existing `DomainCap`, retaining the
current information flow proof and behaviour when the `DomainCap` no longer
exists in the system or is not used.

## Motivation

Currently the domain schedule is provided as a `.h` file and compiled into the
kernel. This was an initial stop-gap implementation and is inconvenient for SDK
approaches such as the Microkit and overall inflexible and hard to use.

For instance, it is currently not possible to provide a verified kernel binary
and modify it with a new kernel schedule without invalidating the verification.

It is also currently not possible to run a system in multiple modes, such as
"wheels up" and "wheels down" in aviation.

The intended use for the proposed mechanism is that the initialiser sets up
domain schedules at boot time, for instance the two schedules in the example
above, or a single domain schedule as would now be provided as `.h` file. After
that, if the system is to remain static, the `DomainCap` can be deleted as it is
now, or it can be given to a high privilege mode control component that can
atomically switch between schedules.

Updating a running system to tweak an existing schedule or add a new mode at
runtime would also become possible.

## Guide-level explanation

At a conceptual level, we propose to mostly keep the current domain scheduler
implementation as it is: a compile-time sized array of entries consisting of
domain and duration. Instead of representing a single schedule as before, we
propose to use the array now for representing multiple schedules. The new
components are:

- entries with the value `(0, 0)` are end markers for a domain schedule
- there is a new kernel global that contains the start index for the current
  domain schedule

### Example

The following diagram shows an example.

```none
-----------------------------------------------------------------
| (d_0, t_0) | (d_1, t_1) | ... | (0, 0) | (d_x, t_x) | .. | .. |
-----------------------------------------------------------------
       0          ^                  n         n+1

ksDomainStart = 0
ksDomScheduleIdx = 1
```

The example has an overall array of length `config_DomScheduleLength`,
configured at compile time, a current domain start index of 0, and an currently
active domain schedule index of 1. The current entry will run domain `d_1` for a
duration of `t_1 > 0`, and the schedule will keep going until it hits index `n`
which has an entry with value `(0, 0)`. Instead of running the entry at index `n`,
it proceeds at `ksDomainStart`, i.e. index 0.

To populate the entires, a user thread with the `DomainCap` can invoke the
`setDomainEntry` method to set duration and domain for a specific index,
potentially with duration 0 to create an end marker.

To atomically switch to the second schedule in the example, a user thread with
the `DomainCap` can set `ksDomainStart` to `n+1`, which will start running
domain `d_x` for a duration `t_x`. The schedule will keep going until either
another entry with duration `0` occurs, or the index hits the end of the array.
In both cases, the index of the next entry will again be `ksDomainStart`.

### Conditions and Invariants

For both, setting the domain start and setting the value of an entry, the kernel
will prevent the user from creating a schedule where the entry at
`ksDomainStart` has duration 0. This would signify an empty domain schedule. It
would be possible to give this situation a useful meaning: not switching domains
until a new schedule is set. However, implementing it would be more invasive
than the currently proposed changes and the same effect can already be achieved
with a one-element schedule of long duration.

Apart from the value `(0, 0)`, the kernel will prevent the creation of entries
with duration 0. The duration is in timer ticks, and on MCS the duration at the
API level must be >= MIN_PERIOD.

The kernel initialises with an array where all entries are `(0, 0)`, apart from
the entry at index 0, which will run domain 0 for the maximum expressible time.

The kernel will preserve the following invariants:

- `ksDomainStart < config_DomScheduleLength`
- `ksDomScheduleIdx < config_DomScheduleLength`
- `schedule[ksDomainStart].duration ~= 0`
- for all `i` with `0 <= i config_DomScheduleLength`,
  if `schedule[i].duration = 0` then `schedule[i].domain = 0`


## Reference-level explanation

### Invocations

The current invocations of the `DomainCap` remain as they are.
There are two new invocations:

#### Set_Domain_Start

`static inline int seL4_Set_Domain_Start`

Set the start index of the current domain schedule. The schedule entry at this
index must not be the end marker `(0, 0)`. The domain at the schedule entry with
the specified index will start running immediately after the kernel call
completes.

| Type        | Name       | Description                                     |
| ----------- | ---------- | ----------------------------------------------- |
| `seL4_DomainSet` | `_service` | Domain capability to authorise the call         |
| `seL4_Word`      | `index`    | The new start index. Must not point to `(0,0)` and must be smaller than `config_DomScheduleLength` |

The function returns `seL4_NoError` for success as usual. The following error
codes are returned otherwise:

| Error                  | Possible cause                                  |
| ---------------------- | ----------------------------------------------- |
| `seL4_InvalidCapability` | the provided capability is not the domain capability |
| `seL4_InvalidArgument`   | the entry at the provided index is an end marker     |
| `seL4_RangeError`        | the index is not less than `config_DomScheduleLength` |


#### Set_Domain_Entry

`static inline int seL4_Set_Domain_Entry`

Set and entry in the domain schedule at the specified index to the specified
domain and duration. If the duration is 0, the domain must also be 0 to indicate
and end marker. On MCS, the duration must be `>= MIN_BUDGET`. If the index is
the current schedule start index, the entry must not be an end marker `(0, 0)`.

The change to the schedule takes effect when the entry is next read by the
kernel. In particular, when the duration or domain of the currently running
schedule index are changed, the change will only take effect after the current
domain time slice has expired and the schedule reaches the current index again.

Section [Initialisation](#initialisation) contains a scenario where setting the
entry at the currently running index may be useful, but generally one should
avoid updating the currently running schedule. Instead create new schedules
beyond current end marker and then set the schedule start once the system is
ready to switch.

| Type        | Name       | Description                                     |
| ----------- | ---------- | ----------------------------------------------- |
| `seL4_DomainSet` | `_service` | Domain capability to authorise the call         |
| `seL4_Word`      | `index`    | The index of the entry to set. Must be smaller than `config_DomScheduleLength`. |
| `seL4_Uint8`     | `domain`   | The domain of the schedule entry. Must be smaller than `CONFIG_NUM_DOMAINS`. Must be 0 if the duration is 0. |
| `seL4_Word`      | `duration` | The duration for the entry. On MCS, must be 0 or `>= MIN_BUDGET`. |

The function returns `seL4_NoError` for success as usual. The following error
codes are returned otherwise:

| Error                  | Possible cause                                  |
| ---------------------- | ----------------------------------------------- |
| `seL4_InvalidCapability` | the provided capability is not the domain capability |
| `seL4_InvalidArgument`   | the index is the current domain start index and the duration is 0, or the duration is 0, but the domain is not 0. |
| `seL4_RangeError`        | the index is not less than `config_DomScheduleLength`, or the domain is not less than `CONFIG_NUM_DOMAINS`, or on MCS the duration is less than `MIN_BUDGET` |

### Configuration Options

The new config option `config_DomScheduleLength` determines the static size of
the overall domain schedule array and thereby the longest domain schedule that
is possible to configure at runtime. The default value for
`config_DomScheduleLength` is 256.

### Initialisation

At system startup, the array contains 2 active entries: entry 0 with domain 0
and a long duration, and entry 1 with `(0, 0)`. With the following scheme it is
possible to use the full length of the array even though these two entries are
already in use.

At kernel boot time, given a user-provided schedule [(d_0, t_0), (d_1, t_1),
...] that satisfies the requirements [described
above](#conditions-and-invariants), the root task could achieve the provided
schedule as follows:

1. First, set up the of rest system as before, including starting all threads
2. Set all `(d_i, t_i)` according to the schedule where `i > 1`.
3. Then, overwrite the two active schedule entries 0 and 1 with
   `(d_0, t_0)` and `(d_1, t_1)`.
4. Set the schedule start to the desired start value, e.g. index 0
5. Suspend/stop the initialiser

With this the first run of domain 0 after the initialiser will not get its full
time slice, because step 5 will already run in the user-provided schedule, but
after that, the user-provided schedule will be in force.

This works if the initialiser can finish its work within the duration of entry
0. Since the duration is set to the maximum expressible time, this should in
practice never be an issue. Even if the time is not sufficient, the procedure
will still work unless the domain time of the initialiser happens to expire
during the execution of step 3. If that is a possibility, the initialiser could
include a suitable delay before step 3 to make this impossible.

The reason the scheme works is that the kernel will not act on new values in the
schedule before the current domain slice has expired whereas setting the start
index in step 4 comes into effect immediately.

### capDL initialiser

The capDL initialiser will change to also initialise the domain schedule if one
is provided.

The schedule is provided in a separate new section of the capDL input
specification, specifying the schedule as a comma-separated list of pairs
(domain, duration). If no end marker is provided at the end of the list,
an implicit end marker is assumed.

## Drawbacks

The main drawback is that this is a breaking change for users. Setting and
initialising a domain schedule now works differently, and build scripts may
need to be updated to no longer generate/add the former `.h` file that contained
the schedule.

In theory a tool could be provided that converts current `.h` file schedules
into the capDL sections, but since `.h` files can contain anything we are not
proposing such a tool as part of this RFC.

Tests for the domain scheduler in sel4test will need to be changed to create the
test schedules at initialisation time instead of expecting them to be compiled
in.

Tools and applications that do not use the domain scheduler should be
unaffected.

## Rationale and alternatives

The proposed design was chosen for its conceptual simplicity, flexibility,
implementation simplicity, and low proof impact. There are no changes in how
domains are treated currently in the implementation at runtime or in the proofs
for information flow. The current information flow proofs should be fully
preserved in systems that no longer have the domain capability, which is already
assumed in the current proofs.

The two extreme choices in the design space would be to leave the static
schedule as is and to remove domain scheduler completely. This RFC has already
motivated why the former is not a good option. Removing the domain scheduler
from the kernel completely and delegating partition scheduling to user level
would invalidate the information flow theorems for seL4 without any even
conceptual formal remedy for the statement of these theorems. Isolation would
no longer be a property of seL4.

Other points in the design space that have been considered are the following.

### Batched setting of the domain schedule

The current proposal requires multiple kernel calls to set a new schedule -- one
for each entry in the new domain schedule. An alternative would be to batch
multiple such calls and collect an entire schedule or larger parts of a schedule
in the IPC buffer. Since setting new schedules, as opposed to switching between
existing schedules, is unlikely to be a performance critical operation. That
means, added complexity of a batched API with variable length arguments brings
no tangible benefit for system performance or even user convenience.

### Restricting to two schedules

Instead of using one array with end markers, the domain schedule could be
represented as two (or more) separate arrays: one active, running schedule, and
one (or more) inactive schedule that can be edited. The representation proposed
in this RFC achieves the same overall API with more flexibility and less
storage.

### Allowing zero-length schedules

The API proposed in this RFC forbids schedules of length zero -- these are
schedules where the start directly points to an end marker. An alternative would
be to allow such schedules and to treat all entries with duration 0 as end
markers. A zero-length schedule with an end marker for a domain `d` would then
mean that the kernel will stay in domain `d` indefinitely until a new schedule
is set, practically disabling domain scheduling at runtime. The RFC did not
choose this option, because a one-element schedule with very long domain time
(e.g. years) already achieves the same result in practice and has a simpler,
more efficient implementation. Allowing zero-length schedules would require
additional state to be checked any time the kernel reduces the consumed domain
time.

### Point of activation of setting domain/duration

In the proposed API domain schedule *switches* take effect immediately, but
setting domain and duration of an entry in the currently running schedule takes
effect only the next time the schedule wraps around to the current index.

This behaviour has the simpler implementation and is also simpler conceptually.
Making domain/duration changes take effect immediately would mean that the
system call might have to switch immediately to a new domain when either the new
domain does not match the current domain or the new duration is shorter than the
already expired domain time. Either would mean that the kernel has already
violated the new domain schedule and is attempting to catch up and rectify the
violation. If the semantics instead is that the effect takes place at the next
time the index is visited, the kernel never needs to violate the schedule.

The behaviour difference is largely theoretical -- the recommended use of the
API is to never edit the current schedule, but instead edit a new schedule and
switch to the new schedule atomically.

## Prior art

Most separation kernels provide some form of configurable static scheduling.

The motivation for the original domain scheduler design in seL4 was an explicit
customer/user request for a static separation kernel configuration of seL4 with
static scheduling in a security and information flow context. This also
motivated the current form of the information flow theorem. For the application
at the time, the current API was sufficient, but for a more general use case it
is too restrictive and has too much build system impact, because it needs
recompilation for schedule changes.

Another application area with similar requirements is aviation, in particular
the ARINC 653 standard, which would be better supported by this RFC than the
current implementation.

This RFC is not attempting to provide a full implementation of any particular
standard, it merely aims to make the existing API more usable and improve the
overall developer experience on seL4.


## Unresolved questions

The API is expressed in terms of timer ticks in expectation of an additional
upcoming RFC to change the rest of the API to timer ticks as well. Depending on
the outcome of that discussion, the API could also be in terms of `time_t`
instead if required for consistency.
