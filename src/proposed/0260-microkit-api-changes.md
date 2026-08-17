<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 seL4 Project a Series of LF Projects, LLC.
  Copyright Rust Language Community

  Based on the Rust RFC template at <https://github.com/rust-lang/rfcs>
-->

# Microkit: lifting the 62-channel limit

- Author: Julia Vassiliki, UNSW
- Proposed: 2026-08-06

## Summary

We propose decoupling the 1:1 mapping the channel IDs given to components,
allowing for channels mapped to separate notification cap (senders) to be
combined into the same notification badge (receivers), thereby allowing for
more than 62 senders to map to only 62 IDs limited by the size of an `seL4_Word`.

We also decouple the PPCall channel IDs from notifications, as they have none
of the same limitations (being endpoints, they can use binary, not one-hot
encodings).


## Motivation

These changes are motivated by these GitHub issues:

- [Improvements to the 64 PD/channel limit](https://github.com/seL4/microkit/issues/526)

Microkit has one major problem: a protection domain (PD) can only
receive notifications on 62 distinct channels, as well as 62 protected-
procedure calls (ppcalls, i.e. endpoints) and 62 fault handlers. This
enforces a similar limit on the total number of PDs, as the Microkit
Monitor acts as a default fault handler for all PDs, and can only then
handle up to 64 distinct fault sources.

Ostensibly, this comes from the limitations on the size (`seL4_Word`)
of a badged notification or endpoint, we can only transfer 64-bits of
information about the source; notifications from multiple sources
`||` -together their badges and so bit *n* being set means we received
a notification from channel *n* (a one-hot encoding).

However, this is not quite true. The current allocation of bits allocates
the 2 upper bits to identifying the origin (notification, fault, or ppcall)
and the lower 62 bits to identifying the sender, using 1 bit for each sender.
Whilst for notifications this is true, you need 1 bit per unique sender[^1]
because each time `seL4_Recv` returns to user-level multiple notifications
may need to be handled, for both faults and ppcalls (which are `Recv` on
*endpoints*), only **one** message is handled at a time. Endpoints form a queue,
and so the badge can instead be a binary number, giving us unique
identification for up to $2^{62}$ senders.

[^1]: Note: *unique* sender, and **not* 1 per sender-receiver *pair*. We'll get to this in a bit.

In addition, whilst we can only distinguish between 62 different sources
via the badge, it is not always necessary for the badge to be the one to
distinguish these clients; it can be done in shared memory. For instance,
our [sDDF network virtualisers](https://github.com/au-ts/sddf/blob/0.6.0/network/components/virt_tx.c#L115-L119)
look at the shared memory queues of all clients and ignore the channel
identifer. We could instead (for example), use the information in the badge
to indicate the priority in a priority-based grouping scheme, or not at all.

## Guide-level explanation

### Previous (current) API

Briefly, below is the **previous** Microkit C-level API and System Description
File (SDF, XML) syntax, with irrelevant parts removed.

```xml
<system>
    <!-- Declared Protection Domains, etc... -->

    <!-- Channel declaration -->
    <channel>
        <!-- Note how in PD "virt" we specify a channel ID of '1'
             So we notified(ch) is called with notified(1),
             and in the code we respond to this with
             microkit_notify(1).
         -->
        <end pd="virtualiser" id="1" />
        <!-- And in this one, with channel '0', it uses 0 -->
        <end pd="a" id="0" />
    </channel>

    <channel>
        <!-- Even though our user code does the exact
             same thing for ch 1 or ch 2, using ch 1 here
             we complain about duplicate channels defined
             in the system description -->
        <end pd="virtualiser" id="2" />
        <end pd="b" id="0" />
    </channel>

    <channel>
        <!-- We do however, want to do different things if we
             are notified by the driver instead of a client -->
        <end pd="virtualiser" id="0" />
        <end pd="driver" id="0" />
    </channel>
</system>
```

```c
/* PD "virtualiser" - user code */

#define CH_DRIVER (0)
#define CH_PD_A (1)
#define CH_PD_B (2)

void notified(microkit_channel ch) {
    if (ch == CH_DRIVER) {
        do_stuff();
        microkit_notify(CH_PD_A);
        microkit_notify(CH_PD_B);
    } else if (ch == CH_PD_A || ch == CH_PD_B) {
        do_other_stuff();
        microkit_notify(CH_DRIVER);
    }
}
```

### Proposed (new) API

*FIXME: Names are not final, nor is the syntax of the SDF file - it could be
changed to structurally represent the new changes, but it would be more effort
to migrate. I propose several alternatives later.*

The major conceptual change is that we no longer have a singular, PD-unique
concept of a channel 'ID' for notifications. Instead, there are (possibly)-distinct
'send' IDs and 'recv' IDs, as well as a unique namespace for ppcall IDs and fault
IDs.

```xml
<!-- We replace <channel> elements with a new
     <notification_channel> element to indicate
     that these apply only to notifications (and IRQs)
     In theory, this is unnecessary, but we'd need to
     add something like ppcall_id="x". Maybe better? -->
<notification_channel>
    <!-- virtualiser would call microkit_notify(1)
         to talk to PD "a".

         - recv_id must lie in the range [0, 62],
           constrained by the badge size.
         - send_id can lie in the range [0, 63],
           constrained only by the size of the CNode
           allocated for storing capabilities. in theory,
           we could have a dynamic/unbounded maximum.
    -->
    <end pd="virtualiser" recv_id="1" send_id="1" />
    <!-- id='0' implies both send_id="0" and recv_id="0",
         for backwards compatibility/simplicity -->
    <end pd="a" id="0" />
</notification_channel>

<notification_channel>
    <!-- microkit_notify(2) for PD "b".
         Note how we have a duplicate recv_id="1" declaration
         for the virtualiser PD; this is allowed.
         However, send_id="1" would not be allowed as it
         would be a duplicate. -->
    <end pd="virtualiser" recv_id="1" send_id="2" />
    <end pd="b" id="0" />
</notification_channel>

<notification_channel>
    <!-- This would be the syntax for defining a 1-way channel
         from b to a; because "a" has no send_id there is no
         way for it to name the capability to signal "b" -->
    <end pd="a" recv_id="1" />
    <end pd="b" send_id="0" />
</notification_channel>

<!-- This sort of declaration would remain mostly unchanged.
     Except maybe for <channel> -> <notification_channel> -->
<notification_channel>
    <end pd="virtualiser" id="0" />
    <end pd="driver" id="0" />
</notification_channel>

<protection_domain name="driver">
    <!-- Something to be aware of is that IRQs signal
         a notification from kernel-land, so they also
         take up part of the notification namespace.
         Hence this ID will conflict with recv_id and
         send_id of the <notification_channel>.
         In theory, we could also support send_id
         recv_id specifiers here, but they would both
         always be mandatory (though they don't *have*
         to be the same - notably we could use a different
         ID namespace for microkit_irq_ack(1) -->
      -->
    <irq irq="112" id="1"/>
</protection_domain>

<ppcall_channel>
    <!-- Unlike for notifications, we have a practically
         infinite ID namespace for PPCs, so anything from
         [0, 2^62) on the server is allowed.
         Because the `protected()` call always *immediately*
         replies to a client (via the reply cap), the sender
         names an ID (to send), which is constrained by the
         size of the CNode, which currently has 64 slots
         allocated (i.e. [0, 63]).

         Notice these ones are not called <end> but are instead
         <client> and <server>; especially as only ppcs to higher
         priority are allowed.
      -->
    <server pd="a" id="2" />
    <client pd="b" id="2" />
</ppcall_channel>

<!-- Note: we can maintain backwards compatibility by still
     supporting the previous <channel> syntax, as it is just
     less a less restrictive form of the new syntax.
 -->

<!-- The final case to support is fault() IDs.
     It is similar to PPCs, where the receiver has
     essentially infinite ID namespace. And the sender is...
     a PD fault handler, so there are absolutely no limitations
     on the IDs used here.

     This can be the ID of VMs or child PDs (which are a shared
     ID namespace).

     This remains identical to previous.
  -->
<protection_domain name="vmm">
   <virtual_machine>
     <vcpu id="0"/>
   </virtual_machine>

   <!-- this wouldn't normally be part of the VMM but
        for example's sake -->
   <protection_domain name="child" id="1" />
</protection_domain>
```

```c
#define RECV_CH_DRIVER (0)
#define RECV_CH_PDS (1)

#define SEND_CH_DRIVER (0)
#define SEND_CH_PD_A (1)
#define SEND_CH_PD_B (2)

void notified(microkit_recv_channel recv_ch) {
    if (recv_ch == RECV_CH_DRIVER) {
        do_stuff();
        microkit_notify(SEND_CH_PD_A);
        microkit_notify(SEND_CH_PD_B);
    } else if (recv_ch == RECV_CH_PDS) {
        do_other_stuff();
        microkit_notify(SEND_CH_DRIVER);
    }
}
```

## Reference-level explanation

We can utilise some of our knowledge to optimise the number of IDs. In the
handler loop, we perform `seL4_Recv` (technically also `ReplyRecv` or `NBSendRecv`,
but focusing on the second-phase of the syscall). We receive on `INPUT_CAP`,
which is either a notification, or an endpoint with a bound notification. seL4
will return setting the notification *badge* bits, (exclusive)-or the endpoint badge
bits for a *single* message (ppcall or fault). Both will not happen at the same time.

Previously, uppermost bits 63:62 were either `10` (notification), `00` (ppcall), or `01` (fault),
giving us 62 bits for notification badges and 62 bits for endpoints/ppcalls.

We can give a 63rd bit by checking notification bits first. Since endpoint receives
dequeue one message at a time, we can utilise a binary encoding for ppcalls/faults.

Allocation within the Microkit tool remains largely the same, except for the addition
of a few more namespaces for checking collisions.

#### Code Snippets

This is the **old** handler loop:

```c
for (;;) {
    seL4_Word badge;
    seL4_MessageInfo_t tag;

    if (have_reply) {
        deferred_flush();
        tag = seL4_ReplyRecv(INPUT_CAP, reply_tag, &badge, REPLY_CAP);
    } else if (microkit_have_signal) {
        tag = seL4_NBSendRecv(microkit_signal_cap, microkit_signal_msg, INPUT_CAP, &badge, REPLY_CAP);
        microkit_have_signal = seL4_False;
    } else {
        tag = seL4_Recv(INPUT_CAP, &badge, REPLY_CAP);
    }

    uint64_t is_endpoint = badge >> BADGE_ENDPOINT_BIT;
    uint64_t is_fault = (badge >> BADGE_FAULT_BIT) & 1;

    have_reply = false;

    if (is_fault) {
        seL4_Bool reply_to_fault = fault(badge & PD_MASK, tag, &reply_tag);
        if (reply_to_fault) {
            have_reply = true;
        }
    } else if (is_endpoint) {
        have_reply = true;
        reply_tag = protected(badge & CHANNEL_MASK, tag);
    } else {
        unsigned int idx = 0;
        do  {
            if (badge & 1) {
                notified(idx);
            }
            badge >>= 1;
            idx++;
        } while (badge != 0);
    }
}
```

This would be the **new** one:

```c
for (;;) {
    seL4_Word badge;
    seL4_MessageInfo_t tag;

    if (have_reply) {
        tag = seL4_ReplyRecv(INPUT_CAP, reply_tag, &badge, REPLY_CAP);
    } else if (microkit_have_signal) {
        tag = seL4_NBSendRecv(microkit_signal_cap, microkit_signal_msg, INPUT_CAP, &badge, REPLY_CAP);
        microkit_have_signal = seL4_False;
    } else {
        tag = seL4_Recv(INPUT_CAP, &badge, REPLY_CAP);
    }

    uint64_t is_notification = badge & BADGE_NTFN_BIT;
    // only valid if !is_notification
    uint64_t is_fault = badge & BADGE_FAULT_BIT;

    have_reply = false;

    if (is_notification) {
        unsigned int idx = 0;
        do  {
            if (badge & 1) {
                notified(idx);
            }
            badge >>= 1;
            idx++;
        } while (badge != 0);
    else if (is_fault) {
        seL4_Bool reply_to_fault = fault(badge & PD_MASK, tag, &reply_tag);
        if (reply_to_fault) {
            have_reply = true;
        }
    } else {
        have_reply = true;
        reply_tag = protected(badge & CHANNEL_MASK, tag);
    }
}
```



## Drawbacks

* Having these extra namespaces and distinguishing between recv/send IDs
  adds additional complexity to the Microkit SDF description.
  However, for basic use cases, users can continue using `recvID == sendID`
  and ignore the distinction, so it's likely that the complexity
  has not substantially increased for basic users.


## Rationale and alternatives

The rationale of these changes, according to motivation section, is threefold:

* Supporting more than 62 channels of a PD / 62 total PDs in a system.

*Alternative 1:*

This is a clearly-bad solution to the 62 channels problem. Something
that users can do *right now* is have an intermediary PD, forming "levels"
in a hierarchy; so one has something like:



```
Server A
  |        \           ..           \
 Mux 1    Mux 2        60 times    Mux 62
/ | \     / | \                 /        |             ....    \
 ....     ...              Client 62-1    Client 62-2        Client 62-62


```

And then the mux servers can use shared memory to communicate additional information
to Server A about which client notified. (or not, if that's not necessary, like
for sDDF).

However, the major downside of this is that it causes an *extra* context switch, for
basically no purpose at all.

What this does do is give you $O(\log(n))$ checking growth; in the badge-combining
scheme presented, one has to check $O(n/k)$ memory locations where $n$ is the
number of clients and $k$ the number of distinct bits.

*Alternate 2:*

New kernel feature! 128-bit badges! Use multiple hardware registers :)

Technically possible, probably quite invasive, and compared to our
purely userspace solution, only helps a little bit.

The main issue with this is the space in the caps, as currently we only have
64 bits for the `badge` inside caps. Increasing this would need to do changes
to the capability sizes (affecting sizes of CNodes and things) or some other
way to get more information here.

Mentioning it because it is technically a valid solution.


## Prior art

- Uncertain? This is a very Microkit/seL4 specific problem; CAmkES (I don't think)
  dealt with that at all.

## Unresolved questions

* Do we need a new name for channel, now that we have "channel" (any
  communication method), "sender id" (id for a sender of a channel), "recv id",
  and that we have multiple different ID namespaces.

  - We need to do a lot of thinking of how this appears in the SDF. From a brief
    internal talk, it's not clear what the "best" way of talking about or
    describing this is.
