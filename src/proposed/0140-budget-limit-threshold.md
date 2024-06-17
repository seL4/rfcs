<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2023 UNSW
-->

# MCS: Budget limit thresholds on endpoints for SC Donation

- Author: Mitchell Johnston
- Proposed: 2023-08-15

## Summary

This is a two stage RFC that proposes to add a new `budget threshold' to
endpoints, which would only allow scheduling context donation to occur if the
SC's available budget exceeds the threshold. This would provide a mechanism to
prevent budget-expiry from occurring in passive servers.

As a second optional stage, this threshold value could also restrict the budget
that a passive server is permitted to consume on a donated SC. We refer to this
as a `budget limit'. This would help bound priority inversion in a system as
well as reducing the trust that clients must place in passive servers they call.

## Motivation

### Thresholds

This change regarding thresholds is motivated by a desire to prevent budget
expiry from occurring inside passive servers, improving worst-case performance
and response time analysis. Additionally, it would shift timeout exceptions into
being a true error case, rather than an unavoidable, but routine occurrence on
many systems. This is likely to simplify system design.

Currently, there are almost no restrictions on the amount of budget required to
enter a passive server. This almost inevitably leads to budget expiry, resulting
in undesirable longer blocking times for other clients of the passive server.
This must also be accounted for in schedulability analysis of a system and is
particularly important for servers with clients of varying criticality.

The kernel currently supports a mechanism to manage budget expiry, timeout
handlers. These allow an error-handling thread to intervene and resolve the
budget expiry. However, as they address the issue after it occurs, these have
some limitations. Timeout handlers can provide extra budget, however, it is not
preferable to reward clients with additional budget just because they are
blocking the rest of the system. Alternatively, the server can be reverted to a
previous state, however this wastes any work the server performed and can be
expensive or impractical, depending on the nature of the passive server.

This RFC proposes a new mechanism, endpoint thresholds, which aim to prevent
budget expiry from occurring in passive servers, rather than reacting to it
after it occurs.

### Budget Limits

The second stage of budget limits is motivated by the current implicit
requirement that clients must completely trust passive servers that they call.
Under the current model, a server can consume as much budget as it desires on a
donated SC and is not forced to return it. A malfunctioning or malicious passive
server can therefore run indefinitely while also possessing a higher priority
than its clients, significantly impeding their ability to make progress.

The impact of this extends to any thread with a priority between that of the
passive server and its clients, even threads that are not themselves clients of
the passive server. Enforcing stronger bounds on passive server SC consumption
would reduce the level of trust threads in a system need to have in one another.

## Guide-level explanation

### Thresholds Guide

This change involves adding a new attribute to endpoint objects, known as a
threshold. By default, this threshold value would be set to zero and will have
no effect. Therefore, existing code will not need to be updated to accommodate
thresholds.

If the threshold is set to a non-zero value, sending invocations performed on
the endpoint will only be permitted if they donate a scheduling context with
available budget greater than or equal to the threshold. Available budget is the
amount of budget ready for use in the SC (the sum of refills with a release time
greater than the current time). By setting the threshold to the WCET of the
passive server associated with the endpoint, this guarantees that the server
will always receive an SC with sufficient budget to complete its execution,
preventing budget expiry from occurring. This will also ensure that timeout
exceptions will only occur as a result of a true error, such as a misconfigured
threshold value or a fault in the server code.

If a client has insufficient available budget in its SC, its refills will be
deferred and merged until its head refill has sufficient budget at some point in
the future. Once the thread resumes, the IPC invocation will transparently
continue. If a client's maximum budget is less than the threshold value, an
error will instead be returned to the client.

The time required to check an SC's available budget and to defer and merge are
both bounded by the maximum number of refills in an SC. When designing a system
using an endpoint with a threshold, this will be an additional factor to
consider regarding the optimal choice for the maximum number of SC refills.

The threshold value of an endpoint can be set via an object invocation,
performed indirectly through an invocation on the CNode, similar to the existing
Cancel Badged Sends invocation. However, we restrict the right to set the
endpoint threshold to only the original unbadged capability.

Changes to the threshold value are propagated weakly, meaning that clients only
interact with the threshold value at the moment where they invoke the endpoint.
If a threshold value is increased, clients already enqueued on the endpoint are
unaffected, even if they now possess insufficient budget. Similarly, threads
which have had their budget deferred will not be woken up early, even if the
threshold value is reduced. As the threshold is intended to reflect the WCET of
the passive server, changing it would be a rare operation. Therefore, we
consider this weak propagation behaviour acceptable.

Additionally, invocations which do not support scheduling context donation are
no longer permitted to invoke an endpoint with a non-zero threshold set. They
instead fail immediately as an invalid operation. This prevents a passive server
from performing a rendezvous with a client that did not donate an SC, which
would result in the server being unable to run, which causes similar issues to
budget expiry. Invoking a passive server without donating an SC is fundamentally
an invalid operation, so it is therefore desirable for the IPC to fail upon the
initial send, rather than causing an exception only after rendezvousing with the
server.

As an optional extension, the new defer and merge behaviour of SC's can also be
made available to threads as an explicit system call. We have provisionally
called this YieldUntilBudget, denoting it as a variant of Yield. This would
allow threads to specify a desired quantity of budget, after which the kernel
will merge and defer refills until the thread's head refill exceeds the desired
budget. We do emphasise that this additional system call is not required for the
functionality of thresholds. However, it will essentially be implemented
regardless as part of thresholds and exposing it to users is an easy change.

### Budget Limits Guide

The optional budget limit change extends the meaning of an endpoint threshold
value to also restrict budget consumption by a passive server on a donated SC.
An additional bit is added to endpoint objects to toggle budget limit behaviour.
By default, budget limits are disabled and only the aforementioned threshold
behaviour applies. If the threshold is non-zero and budget limits are enabled,
then both threshold and budget limit behaviour will be in effect. A budget limit
has a no effect if the threshold is zero, regardless of the value of the budget
limit bit.

If a passive server returns a donated SC having consumed less than the budget
limit (equal to the threshold value), then the budget limit has no effect.
However, if the server's consumption reaches the budget limit, the kernel will
forcibly return the SC to the caller, ensuring that the server’s consumption
does not exceed the limit. This will almost certainly leave the server in a
stuck state, so the server's timeout handler will be invoked to recover it.

When an SC is donated over an endpoint with budget limits enabled, that SC is
marked as possessing a budget limit. An SC with a budget limit can only be
further donated over endpoints that also have budget limits set.

During such a donation, the kernel must still determine whether the donated SC
has a sufficient budget (greater than the threshold). However, rather than
considering the total available budget in the SC, the kernel considers the
budget remaining until the existing budget limit would be reached. This allows
the kernel to guarantee that every server is able to use its full budget limit
allocation, while also being able to enforce the limit if any server exceeds its
allocated budget limit. The SC is only marked as no longer possessing a budget
limit once it is returned over the original budget limit endpoint.

## Reference-level explanation

### Thresholds Reference

This RFC proposes to add a `ticks_t` value to endpoint objects as the
`threshold'. It is also viable to associate the threshold with endpoint
capabilities, this is discussed in the rationale and alternative section below.
For every sending IPC invocation, fastpath or slowpath, the kernel checks the
threshold value of the relevant object. If it is set to zero, this represents
threshold behaviour being disabled and the IPC continues, with no further
behaviour changes.

However, if the threshold value is non-zero, then the kernel calculates the
available budget of the thread (released refills in the SC) and compares against
the budget required to pass the threshold. The intention is for the 'threshold'
value to represent the required runtime of a passive server. Therefore, the
budget to pass the threshold is the 'threshold' value plus twice the kernel
WCET, to account for the call and reply system calls. Additionally, the kernel
must account for time consumed by the client, but not yet charged to its SC. If
the available budget is sufficient, again, the IPC continues without further
behaviour changes.

However, if the available budget is insufficient, alternate action needs to be
taken. At this point, the fastpath and slowpath diverges. If the available
budget check on the fastpath fails, the kernel switches over to the slowpath to
reduce complexity on the fastpath.

Returning to the slowpath behaviour, after determining that the thread has
insufficient available budget, the thread's maximum budget is compared to the
threshold. If the maximum budget is insufficient, an error is returned to the
client. Otherwise, the client's usage is first charged to it, and then its SC's
refills are merged and deferred until the head refill is sufficient to pass the
threshold. This will mostly likely be at some point in the future, so the client
will be inserted into the release queue and the system call will be restarted
once the refill is released.

### Budget Limits Reference

Supporting budget limits requires multiple changes in addition to those required
for thresholds. Each endpoint object requires an additional bit to represent the
budget limit toggle, however this does not require an increase in the object
size. SC's also require additional fields to track whether they currently
possess a budget limit, along with a budget consumption field. Finally, reply
objects have an additional limit field added to track the budget limit currently
in effect.

When a thread and SC (without a budget limit in effect) calls over an endpoint
with a budget limit set, the donated SC is marked as possessing a budget limit
and its budget consumption is reset to zero. The reply object's limit field is
then set to the threshold value. When setting the timer interrupt, the kernel
additionally compares the active SC's consumed budget field against the limit in
the reply object. This allows the kernel to preempt the thread if it exceeds the
budget limit.

When a thread, where the SC has a budget limit in effect, calls over an
endpoint, the kernel only permits the operation if the endpoint has a budget
limit set.The remaining budget limit is then compared to the endpoint's
threshold value and the operation is only permitted if the remaining budget
exceeds the threshold value. The SC’s consumed budget field is not reset, but
the reply object’s limit field is set to the SC’s consumed budget plus the
endpoint threshold value. This allows the kernel to track and enforce the new
budget limit, while not affecting the information required to enforce the
original budget limit.

If a thread with a budget limit enabled exceeds its budget limit, the kernel
preempts it and returns the SC one layer down to the caller. In a multi-level
call chain, other budget limits further down the chain remain in effect.

This functionality requires additional overhead on the fastpath, in particular
reprogramming the timer interrupt.

### Performance summary

In this section we present a summary of performance results, checking the
increased overhead that would result from implementing these proposed changes.
Three broad cases were tested:

- Baseline: The baseline MCS kernel, without any changes.

- Threshold disabled: A kernel with our proposed changes, but tested over an
  endpoint that does not enforce threshold or budget limit behaviour.

- Threshold/Budget limit enabled: A kernel with the proposed changes, over an
  endpoint that enforces threshold/budget limit behaviour.

#### Thresholds only

First, we compare successful IPC cost of thresholds only (no budget limits)
against the baseline kernel using the standard seL4bench IPC tests.

These tests were performed with an SC with a single refill.

|                     | **Fastpath** | **Fastpath overhead** | **Slowpath** | **Slowpath overhead** |
| ------------------- | ------------ | --------------------- | ------------ | --------------------- |
| Baseline            | 269 (3)      | N/A                   | 945 (12)     | N/A                   |
| Thresholds disabled | 276 (4)      | 3%                    | 959 (10)     | 1%                    |
| Thresholds enabled  | 304 (2)      | 13%                   | 976 (12)     | 3%                    |

*IPC Call overhead from endpoint thresholds. Results are cycles, presented as:
mean (standard deviation)*

Thresholds introduce a new case to IPC, whereby instead of succeeding
immediately, the thread's budget is deferred. We measured the cost of deferring
budget for SC's with various numbers of refills.

| **Operation**   | **Extra Refills** | **Fastpath** | **Slowpath** |
| --------------- | ----------------: | -----------: | -----------: |
| IPC call        |               N/A |      272 (2) |     962 (15) |
| IPC block       |               N/A |     852 (11) |     796 (17) |
| Threshold defer |                 0 |    1150 (24) |    1015 (17) |
| Threshold defer |                10 |    1391 (18) |    1300 (26) |
| Threshold defer |                20 |    1665 (25) |    1545 (19) |
| Threshold defer |                30 |    1942 (30) |    1819 (20) |
| Threshold defer |                40 |    2174 (18) |    2079 (23) |
| Threshold defer |                50 |    2446 (24) |    2331 (29) |

*IPC Call defer costs. Results are cycles, presented as: mean (standard
deviation)*

#### With Budget Limits

In this section, we consider the costs on a system that supports both thresholds
and budget limits. We compare the increase in overhead for both IPC Call and
ReplyRecv.

First, overheads for IPC Call:

|                      | **Fastpath** | **FP overhead** | **Slowpath** | **SP overhead** |
| -------------------- | -----------: | --------------: | -----------: | --------------: |
| Baseline             |      269 (3) |             N/A |     945 (12) |             N/A |
| Thresholds disabled  |      291 (2) |              8% |    1068 (14) |             13% |
| Budget limit enabled |      327 (0) |             22% |    1108 (18) |             17% |
|                      |              |                 |              |                 |

*IPC Call overhead from budget limit thresholds. Results are cycles, presented
as: mean (standard deviation)*

Next, the overheads for ReplyRecv:

|                      | Fastpath | FP overhead |  Slowpath | SP overhead |
| :------------------- | -------: | ----------: | --------: | ----------: |
| Baseline             |  290 (0) |         N/A |  972 (16) |         N/A |
| Thresholds disabled  |  298 (3) |          3% | 1131 (20) |         16% |
| Budget limit enabled |  352 (5) |         21% | 1208 (17) |         24% |

*IPC ReplyRecv overhead from budget limit thresholds. Results are cycles,
presented as: mean (standard deviation)*

### Other implementation details

An example implementation and draft pull request, for clarity of changes, is
available here:

- <https://github.com/Yermin9/seL4/tree/threshold_rfc>
- <https://github.com/Yermin9/seL4/pull/6>

The core of this change is additional code on the IPC path that checks if a
calling client has sufficient budget compared to the threshold and if not,
deferring and merging until its head refill has sufficient budget. The size of
endpoint objects has been increased by 1 bit to make room to store the threshold
value, which is a `ticks_t` value. On a 64-bit system, this increases the size
from 16 bytes to 32 bytes.

The calculation of available budget requires summing over all of an SC's
released refills. This is not a major issue, but does introduce a new kernel
time dependence on the refill size of an SC. The same is true with deferring and
merging refills. There already exists a performance trade-off regarding max
refill sizes, this is simply an additional factor for system designers to
consider.

## Drawbacks

The primary drawback is that this change will increase the IPC path cost,
imposing an additional cost on all IPC calls. This is true even for endpoints
with thresholds set to zero, as the kernel still needs to check whether it
should impose the threshold behaviour restrictions. However, while non-zero,
this checking cost is small. Where thresholds are enforced, there will be a
modest performance impact. However, as outlined above, budget limits will impose
a more significant performance cost.

## Rationale and alternatives

A key benefit is that this change will support better schedulability analysis
and reduced server complexity. The threshold change trades slightly slower
average-case performance for much improved worst-case performance. However, this
more predictable behaviour is of particular benefit for schedulability analysis.
In particular, this predictability is highly important for real-time systems
that the MCS kernel is targeted at. Further, this change also moves timeout
faults into a true error case, rather than an unavoidable consequence of passive
servers.

The current model supports changes to the threshold value, however, changes are
propagated very weakly. As described above, budgets are only compared to the
threshold value at the point where a thread invokes an endpoint. Threads already
enqueued on the endpoint or waiting for sufficient budget are only affected by a
change to the threshold value when they invoke the endpoint again.

We had considered stronger threshold propagation models, whereby all threads
enqueued on the endpoint or waiting for sufficient budget were affected by
changes to the threshold value immediately. Upon a change to the threshold
value, threads would be enqueued or dequeued from the endpoint to reflect the
change. However, this behaviour involved significant additional kernel
complexity, in particular requiring two additional release queues. Briefly, this
is because deferring and merging budget would not be possible, as a thread's
available budget must be preserved in case the threshold value is decreased.
This required significant additional infrastructure to track the threads and
their budgets, while also waiting for additional refill releases. Given that
changing an endpoint threshold is expected to be a rare operation, we do not
consider this compromise of kernel minimality worth the benefit. Therefore, we
implemented the weak propagation behaviour described above.

Alternative associations for the threshold value were considered, namely the
passive server's TCB and endpoint capabilities, rather than objects.

- Association with the server's TCB would add significant kernel complexity with
  little benefit.  Threshold values would need to be checked at the point of IPC
  rendezvous, rather than at the point of entering the endpoint. This could
  require endpoints to have two queues, one containing servers that ready to
  receive and another with clients that are ready to send, but unable to
  rendezvous because of insufficient budget.

- Association with endpoint capabilities would allow different client's entry
  points to have different thresholds. There is potentially a use for different
  threshold value representing different operations into a passive server, with
  correspondingly different WCET's. However, this would require increasing the
  size of endpoint capabilities. Due to the nature of the capability system,
  this would also require increasing the size of all capabilities. This is not
  an insurmountable issue and may be the best design.

### Budget limit call stack restriction

For budget limits, we introduced the restriction that threads with a budget
limit in effect could only donate their SC over an endpoint with a budget limit.
Originally, we did consider a model that did not restrict how users could
construct call stacks, however there were significant downsides. We now
illustrate this with an example.

Consider a client (C) that calls a server (S) over a budget limit endpoint.
Then, over endpoints without budget limits set, S donates its SC to s_1, s_1 to s_2
and so on to s_n. We outline two system behaviour assumptions that we believe are
reasonable:

- The original budget limit guarantee made from S to C should still be enforced
  regardless of which thread the SC is bound to at the time. If this is not
  enforced then the usefulness of the budget limit to guarantee scheduling
  properties is greatly diminished.

- Further, any thread that is skipped over by the returning SC needs to have its
  timeout handler invoked, to restore them to a sane state. This is required for
  the system to remain usable. Otherwise, some mechanism must exist to notify
  some user-level error-handling thread of which server threads are stuck and
  allow it to recover them. This is essentially the same concept as a
  timeout/error handler regardless.

Therefore, if the budget limit is exceeded by s_n, the reply stack needs to be
traversed until the original client is found, triggering timeout handlers at
each level as well. The result is that kernel execution time would be O(n)
dependent on the size of the call stack created, which we consider unreasonable.

Further, S is making a guarantee to C that only a certain amount of budget will
be consumed on the donated SC, that being the semantic meaning of the budget
limit. It would be a poor design for S to then donate that SC to another server
(s_1) with no timing guarantees, as if s_1 consumes too much budget, S will also
be skipped over when the SC is returned to C. This means that S cannot guarantee
it will meet its own scheduling obligations. Therefore, we consider it a
reasonable design restriction to only allow S to donate its SC to servers that
also provide a budget limit guarantee.

If S needs to donate its SC to a server (s_1) that cannot provide a budget limit
guarantee, we believe it is most sensible for S to not offer a budget limit
either, as S does not know how much budget will be required. Alternatively, we
believe adding a budget limit to s_1 would also be a sensible design pattern.

## Prior art

See also this [honours thesis], where this proposed change was discussed in more
detail.

[honours thesis]: https://trustworthy.systems/publications/theses_public/22/Johnston%3Abe.abstract

## Unresolved questions

What is the best API for the new Yield system call?

- The cleanest API would probably be to change `seL4_Yield()` to accept a single
  parameter. If the parameter is zero, the existing Yield behaviour occurs,
  otherwise, a non-zero value triggers the new defer and merge behaviour.
  Unfortunately, this would be a breaking API change. However, the change
  required would be fairly simple, replacing every `seL4_Yield()` with
  `seL4_Yield(0)`.

- Same as above, but make the true system call `seL4_YieldUntilBudget(time_t
  val)`. This would allow `seL4_Yield()` to be made a macro for
  `seL4_YieldUntilBudget(0)`. This seems to be a messier API, but maintains
  backward API compatibility. It would however, break existing binary
  compatibility.

- Two true system calls, the existing `seL4_Yield()` and the new
  `seL4_YieldUntilBudget`. This seems to be less preferable from an API
  perspective (and potentially performance, though this has_n't been tested), but
  also maintains backward compatibility.

We restrict sending invocations on an endpoint with a threshold set to only those that permit SC donation. There are some possible extensions of this:

- It is potentially reasonable to also restrict receiving invocations to only
  those that allow SC donation? For a passive server, receiving in a manner that
  does not permit SC donation is an invalid configuration.  This change would
  cause an explicit error upon invocation, rather than the server getting stuck
  after IPC rendezvous. This is potentially desirable.
