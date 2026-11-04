<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2024 seL4 Project a Series of LF Projects, LLC.
  Copyright Rust Language Community

  Based on the Rust RFC template at <https://github.com/rust-lang/rfcs>
-->

# Microkit Entrypoint & Deferred API Changes

- Author: Julia Vassiliki, UNSW
- Proposed: 2026-08-14

## Summary

We propose changing the `void notified(channel) { }` entrypoint (called once
per-channel from the notification badge) into `notified(channel_set) { }` (called
once with the notification badge).

We also propose removing the `microkit_deferred_signal` APIs, and utilising the
return value `microkit_notified_ret_t` of the new `notified(channel_set)`
entrypoint to implemenet syscall-combining.

## Motivation

This is motivated in part by the GitHub issue [Deferred notify and IRQ ack may
be overwritten](https://github.com/seL4/microkit/issues/510).

The `microkit_deferred_notify()` API allow users to tell the Microkit handler
loop to utilise the combined `seL4_NBSendRecv` syscall to combine two syscalls
into one; in contrast to the `microkit_notify()` function which immedately performs
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
no way of knowing whether or not it is the "last" notified. This is both
confusing as a user (to use it correctly) but also makes verification harder.

The second part is that there is an implicit ordering of the notification handling;
currently it handles the lowest channel ID first, and goes down. The fact that
you may have multiple pending notifications is also not exposed to you, as the
user. This motivates the `notified(ch) -> notified(channel_set)` change by itself,
which then allows the new deferred API.

## Guide-level explanation

### Previous (current) API

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

The `notified()` API takes an `seL4_Word` sized argument "channel_set" that
is a one-hot encoding of the channels; i.e. the literal badge (with one bit
masked off) used for the notification. It then also returns a tagged enum
called `microkit_notified_ret_t` (*FIXME*: bikeshed a name) which indicates
an operation to do "deferred" at the time of `ReplyRecv`/`NBSendRecv`.

This is stateless, it is always fine to return a deferred signal, or not;
upon return from `notified()` the PD now always go immediately back to blocking for a new one.


```c
/* PD: virtualiser */

#define CH_DRIVER (0)
#define CH_PD_A (1)
#define CH_PD_B (2)

microkit_notified_ret_t notified(seL4_Word channel_set) {
    /* Note how this explicitly shows handling priority and dealing with
       multiple notifications at once, whereas before that was implicit
       based on channel ID. One can even do logic where the logic depends
       on whether or not we got notifications from PDs and Driver, or
       if we only got one, etc.
     */
    if (channel_set & BIT(CH_DRIVER)) {
        do_stuff();
        microkit_notify(CH_PD_A);
        microkit_notify(CH_PD_B);
    }

    /* Note the "if" here, not elif */
    if (channel_set & (BIT(CH_PD_A) | BIT(CH_PD_B))) {
        do_other_stuff();
        /* on return from notified(), we will do this signal */
        return microkit_notified_ret_signal(CH_DRIVER);
        /* a driver could use this variant */
        return microkit_notified_ret_irq_ack(...);
    }

    /* don't do any deferred signals on return from here */
    return microkit_notified_ret_nothing();
}
```

## Reference-level explanation

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
  annoying for verification, too; not just for `libmicrokit` but also requiring
  a loop invariant in *user code* talking about `libmicrokit` behaviour
  (according to Zoltan A. Kocsis).


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

* Obviously, this might break users of Microkit.
  We could do some shenanigans with weak symbols to keep both a `notified()` and
  maybe a `notified_single()` variation to make the fix a simple rename, or
  something more complex (two variations of `libmicrokit`?) if we really want
  to keep backwards compatibility.
  We can also retain the deferred APIs and make them just aliases of the
  standard `microkit_signal` API.

* The extra logic with checking bitmasks manually in `notified()` might
  be more complicated; previously you did not have to do bitmasks.
  We could resolve this with helper functions, like in the `rust-seL4`
  `ChannelSet` API, although C makes that somewhat more difficult.

## Rationale and alternatives

The rationale of these changes, according to motivation section, is threefold:

* Fixing the `deferred_signal` API to be less of a footgun in various
  cases.

* Providing more flexibility / choice in handling multiple notifications
  at the same time, instead of an implicit priority order.


*Alternative 1*.

The "simple" alternative to the replacement of the `deferred_signal` API
would be to instead properly define a semantics for what happens when
you call it multiple times. We could say that it always overwrites, and define
this. It would also likely be necessary to add some call like `get_deferred`
which tells you whether or not there is an existing deferred signal or irq ack.

Why not:

* The `deferred_signal` and `deferred_irq_ack` calls could be called
  inside the `fault` or `protected` entrypoints; however, they make no
  sense inside these entrypoints, and so currently end up making an extra
  syscall anyway.

* Verification of Microkit PDs, as it significantly complicates verification.
  Zoltan can comment more, but it requires talking about the Microkit handler
  loop as part of the user PD.


*Alternative 2*:

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

  It does not implement the return-value behaviour, though.

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

* For the `fault()` entrypoint, we could replace the existing `bool` return and
  `seL4_MessageInfo_t *tag` argument with the same mechanism as `notified`:
  this would allow `fault()`, in the case one is not replying to a fault, to do a
  combining of the calls. It would also be more consistent.

  i.e. `tagged_enum microkit_fault_ret { reply, ntfy(cap), irq_ack(cap), none }`.

* Calling it `badge` instead of `channel_set`?
