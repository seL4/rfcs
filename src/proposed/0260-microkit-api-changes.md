<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 seL4 Project a Series of LF Projects, LLC.
  Copyright Rust Language Community

  Based on the Rust RFC template at <https://github.com/rust-lang/rfcs>
-->

# Microkit API/Entrypoint Changes

- Author: Julia Vassiliki, UNSW
- Proposed: 2026-08-06

## Summary

We propose decoupling the 1:1 mapping the channel IDs used for
`void notified(channel) { }` and `microkit_notify(channel)`, replacing instead
with `microkit_ret_t notified(event mask)` and `seL4_Signal(cap)` functions,
to unify the deferred notify / IRQ ack functionality and at the same time
allow protection domains to have more than 64 clients.

## Motivation

These changes are motivated by these GitHub issues:

- [Deferred notify and IRQ ack may be overwritten](https://github.com/seL4/microkit/issues/510)
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

The second motivating example for this is the `microkit_deferred_notify()`
API. These functions allow users to tell the Microkit handler loop to utilise the
combined `seL4_NBSendRecv` syscall to combine two syscalls into one; in
contrast to the `microkit_notify()` function which immedately performs
`seL4_Signal`. There is also a `microkit_deferred_irq_ack()`. Until recently,
calling either of these functions twice would overwrite the same global
`microkit_deferred_send` variable storing an `seL4_MessageInfo_t` and
silently discard your previous deferred syscall invocations, now, they perform
the previous deferred call. This is considered a user error, but it's not very
obvious unless one knows internals of how the Microkit handler loop works.
Additionally, the `deferred` APIs can be called from the `fault()` or `protected()`
entrypoints, but they don't make sense here: these endpoints have replies already,
so it would be trying to combine two sends and a recv into a SendRecv call.

Something surprising is then that it's one `deferred_ack` call *per set of `notified()`*,
because one exit from `seL4_Recv` can call `notified()` multiple times; but you have
no way of knowing whether or not it is the "last" notified.

Something else which can matter: `notified(ch)` is called once for every bit set,
starting from the highest channel ID and going down. This means there is an
implicit order of handling notifications based on the channel ID.

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
        /* it doesn't really make sense to do deferred_notify here */        */
        do_stuff();
        microkit_notify(CH_PD_A);
        /* if we were to always do a deferred, if the ordering
           between notify(1) and notify(2) matters the deferred
           API has non-obvious behaviour */
        microkit_notify(CH_PD_B);
    } else if (ch == CH_PD_A || ch == CH_PD_B) {
        do_other_stuff();
        microkit_deferred_notify(CH_DRIVER);
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

There now remains the changes to the user-level `notified()` API. The key difference
here is that it now takes a one-hot encoded (aka bitset) word-sized argument,
where `bit n` being `1` means that we received a notification for that channel's recv_id[^2].
Another change is that we return a (yet-to-be-bikeshed-name)
`microkit_notified_ret_t` which would be a tagged enum of the "deferred" signal
APIs - but now it is integrated into the return value of notified(). This is stateless,
it is always fine to return a deferred signal, or not; upon return from `notified()`
the PD now always go immediately back to blocking for a new one.

[^2]: Note this is similar to what the [`rust-sel4` version of the Microkit code](
https://github.com/seL4/rust-sel4/blob/v5.0.0/crates/examples/microkit/banscii/pds/assistant/src/main.rs#L82-L108)
does (it should really have been the same API, but nevertheless).

We need to think of a new name for the 'deferred' APIs. It's really the 'combined syscall'
optimisation that we're taking advantage of, and I think there's a word for it, but I can't
figure out what it is. *FIXME: A name for this concept*.

```c
/* PD virtualiser */

#define CH_DRIVER (0)
#define CH_PDS (1)
#define NTFN_DRIVER (microkit_ntfn_cap(0))
#define NTFN_PD_A (microkit_ntfn_cap(1))
#define NTFN_PD_B (microkit_ntfn_cap(2))

microkit_notified_ret_t notified(seL4_Word channel_set) {
    /* Note how this explicitly shows handling priority
       and dealing with multiple notifications at once,
       whereas before that was implicitly. One can even
       do logic where the logic depends on whether or
       not we got notifications from PDs and Driver, or
       if we only got one, etc.
     */
    if (channel_set & BIT(CH_DRIVER)) {
        do_stuff();
        // microkit_notify(1);
        // microkit_notify(2);
        seL4_Signal(NTFN_PD_A);
        seL4_Signal(NTFN_PD_B);
    }

    /* Note the "if" here, not elif */
    if (channel_set & BIT(CH_PDS)) {
        do_other_stuff();
        /* on return from notified(), we will do this signal */
        return microkit_notified_ret_signal(NTFN_DRIVER);
        /* a driver could use this variant */
        return microkit_notified_ret_irq_ack(...);
    }

    /* don't do any deferred signals on return from here */
    return microkit_notified_ret_nothing();
}
```

It should be possible to back-compat implement `notified` be allowing people to
rename it to `notified_single` and such (so that you don't immediately have to
rewrite handler loops), but I'm not sure if this is actually worth it.

*FIXME:* This section needs more useful names for the concepts we are changing. I would
include them if I knew what to do.

#### The somewhat-optional change: removing microkit APIs

This is a rephrasing of [proto-rfc: the microkit API shouldn't exist (mostly)](https://github.com/seL4/microkit/issues/362).

Users should no longer call `microkit_notify(ch)` or `microkit_irq_ack(ch)`.
Instead, we exposing the seL4 capabilities via helper functions:

```c
seL4_CPtr microkit_ntfn_cap(microkit_ch send_id);
seL4_CPtr microkit_irq_cap(microkit_ch send_id);
seL4_CPtr microkit_ppcall_cap(microkit_ch send_id);
```

Then, you use the standard libsel4 `seL4_Signal`, `seL4_IRQHandler_ACK` and `seL4_Call` functions as necessary.

The user should understand that Microkit provides a method to initialise a static
system with a specific capability layout. Part of this abstraction is that it lays out the
CSpace of a PD in a particular way, and that PDs can only perform invocations on
objects they have capabilities to.

Previously, this was opaque — for normal channels users just know about "channel
IDs" as a *sort* of capability system. Except we have leaky abstractions with various
things such as TCB capabilities where you need to do
`seL4_TCB_WriteRegisters(BASE_TCB_CAP + child_id)`. That, or we wrap *every*
operation of the seL4 API in Microkit variants.

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



The API changes removes code from `libmicrokit`.

* The "badge-iter-loop" (see later code snippets) can be removed entirely.
  Zoltan Kocsis, whilst verifying libmicrokit, reported that Viper/Z3 struggled
  [greatly with the verification of "badge-iter-loop"](https://github.com/seL4/microkit/issues/526#issuecomment-4889854832)
  for some strange reason.

* Similarly, the `microkit_deferred_notify()` functions, previously
  implemented as:

  ```c
  static inline void microkit_deferred_notify(microkit_channel ch)
  {
      microkit_have_signal = seL4_True;
      microkit_signal_msg = seL4_MessageInfo_new(0, 0, 0, 0);
      microkit_signal_cap = (BASE_OUTPUT_NOTIFICATION_CAP + ch);
  }
  ```

  Can be removed, removing these global variables. These were apparently quite
  annoying for verification, too.



Regarding the removal of the "microkit" API, the code that currently does Signal + ch -> CPtr
conversion would be split into the appropriate parts, likely with `microkit_notify`
serving as backwards compatibility that can be removed in future.

```c
/* Note that the cap is located at fixed offset */
static inline void microkit_notify(microkit_channel ch) {
    /* elided: error handling for checking invalid ch */

    seL4_Signal(BASE_OUTPUT_NOTIFICATION_CAP + ch);
}
static inline void microkit_irq_ack(microkit_channel ch) {
    seL4_IRQHandler_Ack(BASE_IRQ_CAP + ch);
}
```

```c
seL4_CPtr microkit_ntfn_cap(microkit_ch send_id) {
    /* elided: error handling for checking invalid ch */
    /* FIXME: something to consider is whether this should
              maybe return an error (instead of panicking)
              for an invalid ch */

    return BASE_OUTPUT_NOTIFICATION_CAP + ch;
}

// User code
#define CONST_NTFN_CAP (microkit_ntfn_cap(0))
seL4_Signal(CONST_NTFN_CAP);
```

There are no changes to any global properties / component isolation, as the same caps
are provided to the PDs. It was still *possible* to perform other invocations on caps in
the Microkit PD, it nor their layout was not (supposed to be) exposed to users to do
general `libsel4` operations.

There will need to be updates to the Viper-export feature of the Microkit Tool.

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
        /* NOTE: Called "badge-iter-loop" for later reference */
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
        microkit_notified_ret resp = notified(badge & NTFN_MASK);
        switch (microkit_notified_get_type()) {
        case type_none:
            break;
        case type_signal:
            microkit_have_signal = true;
            microkit_signal_msg = seL4_MessageInfo_new(0, 0, 0, 0);
            microkit_signal_cap = /* signal from microkit_notified_ret */
            break;
        case type_irq_ack:
            /* ditto */
        }
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

* Obviously, this might break users of Microkit. It's possible that if
  we keep the same `<channel>` element, continue polyfilling
  `microkit_signal` and do some shenanigans to switch `notified()` to `notified_single()`
  (old behaviour) in user code. The deferred API might be hard to keep around, though.

* Having these extra namespaces and distinguishing between recv/send IDs
  adds additional complexity to the Microkit SDF description.
  However, for basic use cases, users can continue using `recvID == sendID`
  and ignore the distinction, so it's likely that the complexity
  has not substantially increased for basic users.

* The extra logic with checking bitmasks manually in `notified()` might
  be more complicated; previously you did not have to do bitmasks.
  We could resolve this with helper functions, like in the `rust-seL4`
  `ChannelSet` API, although C makes that somewhat more difficult.

* The change to replace `microkit_signal` with `seL4_Signal` and `microkit_ntfn_cap`
  functions might complicate verification of
  microkit PDs. According to Zoltan Kocsis, in his verification framework,
  PDs calling `libsel4` APIs directly on caps was disallowed, only the
  explicit invocations via the `microkit_XX` calls. This does not change
  what untrusted PDs can do as mentioned earlier, as the same caps
  still existed before (their addresses were not intentionally exposed
  but could be easily known).

## Rationale and alternatives

The rationale of these changes, according to motivation section, is threefold:

* Supporting more than 62 channels of a PD / 62 total PDs in a system.

* Fixing the `deferred_signal` API to be less of a footgun in various
  cases.

* Providing more flexibility / choice in handling multiple notifications
  at the same time, instead of an implicit priority order.

* Fixing a leaky abstraction with not exposing addresses of capabilities
  to users, forcing a duplication of `libsel4` in the `microkit__XX` APIs.



I believe that this lands in a sensible change to the API that makes sense
*together* / as a whole; the below alternatives I can think of only solve parts
of the design. However, some changes in this RFC could be dropped or
reworked; not all of them (i.e. the `notified` change or exposing cap
addresses to use `libsel4` APIs) are strictly necessary.

I would be willing to hear other alternatives, as most of these are (in my
opinion) quite bad alternatives; however I have not thought of other
ways to do this in the time I have spent thinking about these problems.


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



*Alternate 2:*

New kernel feature! 128-bit badges! Use multiple hardware registers :)

Technically possible, probably quite invasive, and compared to our
purely userspace solution, only helps a little bit.

Mentioning it because it is technically a valid solution.



----

*Alternative A*:

We could drop the `notified()` change. It would mean that the argument to it
does slightly change meaning (going from 'ch' to a 'recv_id'), but it wouldn't
break existing Microkit code. We could also define the semantics of priority order.

Note that this change is necessary for the `deferred_signal` API changes to work
well, as otherwise one has multiple return values at once.

(It would be easy to not break existing Microkit code *much*, via the `notified_single`
function called by a weak `notified()` function that keeps the existing behaviour.
This limits the compatibility break to be non-structural, just renaming a function.

----

*Alternative α*.

The "simple" alternative to the replacement of the `deferred_signal` API
would be to instead properly define a semantics for what happens when
you call it multiple times. We could say that it always overwrites, and define
this. It would also likely be necessary to add some call like `get_deferred`
which tells you whether or not there is an existing deferred signal or irq ack.

Why not:

* The `deferred_signal` and `deferred_irq_ack` calls could be called
  inside the `fault` or `protected` entrypoints; however, they make no
  sense inside these entrypoints, and so must




*Alternative β*:

Remove the `deferred_signal` API and instead make the `microkit_signal` API
implement an optimisation where it tries to combine the last (or first) signal with
the next `Recv` in the handler loop; and if there's something waiting already it
just does a `seL4_Signal` immediately (or replaces).

Note that `microkit_irq_ack` would also need this optimisation as one cannot
have a deferred IRQ and Signal at the same time, so they "interfere".

To me, this does not respect the principle-of-least-astonishment, and there are
cases where making `microkit_signal` implicitly deferred could affect the ordering
relative to other syscalls/shared-memory operations, which could definitely
break some user code in a subtle way (previously never used the deferred API).



## Prior art

* The `rust-seL4` version of `libmicrokit` (which provides the handler loop)
  provides a `fn notified(channels_set: ChannelSet)` function like is
  proposed in this design. Example: [rust-sel4/crates/examples/microkit/banscii/pds/assistant/src/](
  https://github.com/seL4/rust-sel4/blob/v5.0.0/crates/examples/microkit/banscii/pds/assistant/src/main.rs#L82-L108):

  ```rust
  fn notified(&mut self, channels: ChannelSet) -> Result<(), Self::Error> {
      if channels.contains(self.serial_driver) {
          // elided
      else {
          unreachable!();
      }
  }
  ```
- Similarly, `rust-seL4` uses a different mechanism for channels: it has

  ```rust
  const DEVICE: Channel = Channel::new(0);
  const CLIENT: Channel = Channel::new(1);

  // Which implements (with no reference to C implementation)
  fn cap<T: ChannelFacet>(&self) -> sel4::Cap<T> {
      if T::mask() & (1 << self.index) == 0 {
          panic!("{}: not valid for channel '{}'", T::METHOD_NAME, self.index);
      }
      sel4::Cap::from_bits((T::BASE_SLOT + self.index) as sel4::CPtrBits)
  }

  pub fn notification(&self) -> sel4::cap::Notification {
      self.cap::<sel4::cap_type::Notification>()
  }

  pub fn notify(&self) {
      self.notification().signal()
  }
  ```

  This relates more closer to the new `microkit_ntfn_cap(ch)` proposed API; and
  can call syscalls (which in rust-sel4 are invocations on typed caps).

- The Linux/POSIX APIs `select()`, `epoll()`, and the BSD `kevent()/kqueue()` all
  provide, upon returning from the syscall, information about all available events,
  with an ability to iterate through them arbitrarily (usually as an array and count);
  either way you have access to all events that just ocurred.

- [`libevent`](https://libevent.org/libevent-book/Ref3_eventloop.html#_running_the_loop)
  and [CAmkES](https://docs.sel4.systems/projects/camkes/) instead provide abstractions
  that automatically call your "helper" function code. However, `libevent` also
  provides priority levels to choose which function is called first, which we do
  not provide (only implicitly).

## Unresolved questions

* What do we call the new deferred API? "Notified-return-action" is the literal, if not
  particularly imaginative, description.

* Do we need a new name for channel, now that we have "channel" (any
  communication method), "sender id" (id for a sender of a channel), "recv id",
  and that we have multiple different ID namespaces.

* For the `fault()` entrypoint, we could replace the existing `bool` return and
  `seL4_MessageInfo_t *tag` argument with the same mechanism as `notified`:
  this would allow `fault()`, in the case one is not replying to a fault, to do a
  combining of the calls. It would also be more consistent.

  i.e. `tagged_enum microkit_fault_ret { reply, ntfy(cap), irq_ack(cap), none }`.
