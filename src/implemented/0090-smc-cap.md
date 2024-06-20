<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2021 Dornerworks
-->

# New Capability for seL4 SMC Forwarding

- Author: Robbie Van Vossen
- Proposed: 2021-11-06

## Summary

This RFC proposes to add a new, badged capability which certain threads can
invoke so seL4 can make SMC calls on ARM platforms in EL2 (virtualized mode) on
the thread’s behalf.

## Motivation

Currently, seL4 running in EL2 traps all SMC calls. Then, if setup, seL4 calls a
handler to deal with the call. Some SMC calls are emulated, such as PSCI for the
camkes-vm, but most are just ignored. However, there may be some SMC calls that
actually need to make it to the Supervisor, and this configuration does not
allow that to happen. This RFC proposes a solution to this problem by creating a
new, badged capability which can be given to specific threads to allows them to
forward configured SMC calls to seL4 so that the microkernel will make the
actual SMC call on the thread's behalf.

## Guide-level explanation

This change will allow you to forward to the microkernel, emulate, or block SMC
calls based on platform specific configuration. When an SMC call is made by a
VM, the microkernel intercepts the call, which it does for all SMC calls made at
EL1. It then calls `handle_smc()` for the corresponding VMM thread. That function
will decode the specific SMC call and decide whether to block it, emulate it, or
forward the call back into seL4. There are examples already for multiple
platforms on emulation and blocking. The zynqmp platform will have an example of
forwarding the SMC with the new API call, `seL4_ARM_SMC_Call()`.

### New concepts

#### `seL4_ARM_SMC_Call()`

`seL4_ARM_SMC_Call()` is the new ObjectInvocation API call and can be called in
two ways:

1. A VM attempts to make an SMC call which traps into the microkernel. The
   microkernel informs the VMM’s handler and the VMM decides that the SMC call
   really needs to be made. The VMM then calls `seL4_ARM_SMC_Call()` with the SMC
   capability and all the arguments that the VM provided.

2. Directly by constructing the SMC call from the thread with the SMC
   capability. This means that a trap isn’t needed.

Our expected use case has been using the first approach in the camkes-vm for VMM
handlers on the behalf of its VM. I am not sure if there is a use case for the
second approach, but it is certainly possible. In either case, the function
still requires the caller to set all 8 registers, even if the specific SMC call
uses less arguments.

#### `seL4_ARM_SMC`

`seL4_ARM_SMC` is the new capability. It needs to be given to any threads that
you expect to call `seL4_ARM_SMC_Call()`, otherwise it will be denied. We expect
that in most use cases, it will be given to each VMM thread.

The capability is badged and the badge represents the SMC Function Identifier.
Therefore, the specific SMC calls that each Thread can make is configurable and
checked by seL4.

### For users

We plan to implement this configuration as an example configuration of camkes-vm
for the zynqmp platform. Due to WCET implication of this approach, it will not
be the default for all platforms. It should only be enabled when actually needed
for a specific platform or application. Without this change, Linux is unable to
run as a guest on camkes-vm for the zynqmp platform.

Here is an example for how to enable SMC calls for some VMs in the
`devices.camkes` file implemented for a platform in `camkes-vm-apps`.

```camkes
vm0.allow_smc = true;
vm0.allowed_smc_functions = [
    0xC2000001, // PM_GET_API_VERSION
    0xC2000017  // PM_FPGA_GET_STATUS
];

vm1.allow_smc = true;
vm1.allowed_smc_functions = [
    0xC2000001, // PM_GET_API_VERSION
    0xC200000D, // PM_REQUEST_NODE
    0xC200000E  // PM_RELEASE_NODE
];

vm2.allow_smc = false;
vm2.allow_smc_functions = [];
```

As you can see in this example, you can configure each VM to allow or disallow
SMC calls. For each VM that has SMC calls enabled, you then specify which SMC
function calls they can make. These are integers that are defined per platform.
As you can see, VMs can share the same functions and they can have different
functions as well.

## Reference-level explanation

This implementation will meet the SMC Calling Convention specification from ARM
([ARM DEN 0028E v1.4]) for 32-bit SMC calls. 64-bit SMC calls are partially
supported, but full support could be added later.

[ARM DEN 0028E v1.4]: https://developer.arm.com/documentation/den0028/latest?_ga=2.116565828.390371079.1616755184-1989679030.1616755184


### seL4_ARM_SMC_Call()

```c
static int seL4_ARM_SMC_Call(seL4_ARM_SMC _service,
    seL4_ARM_SMCContext *smc_args,
    seL4_ARM_SMCContext *smc_response
)
```

```txt
Parameters
    [in]  _service      Capability to allow threads to interact with SMC calls.
    [in]  smc_args      The structure that has the provided arguments.

    [out] smc_response  The structure to capture the responses.

Returns
```

### struct seL4_ARM_SMCContext

```c
typedef struct seL4_ARM_SMCContext_ {
    /* register arguments */
    seL4_Word x0, x1, x2, x3, x4, x5, x6, x7;
} seL4_ARM_SMCContext;
```

## Drawbacks

There are a couple of drawbacks to allowing SMC calls to actually go through.
Both relate to allowing a supervisor to do anything in the system past
initialization time.

One drawback is that the worst case execution time (WCET) is no longer
guaranteed for the system. Each SMC call can take an arbitrarily long amount of
time. This means a thread can essentially lock up all of the cores for an
unspecified amount of time. The core the SMC call is made on is obviously
blocked because the supervisor will not return to seL4 until it completes its
function. The other cores will become locked as soon as seL4 runs and tries to
grab the Big Kernel Lock (BKL).  One potential fix for the multicore issue is to
release the BKL before making the SMC call. However, that is out of the scope of
this RFC as it has a lot of implications. The current approach will be to have
this config option off by default and add documentation about how enabling it
affects WCET.

Another drawback is the effect this has on assurance. Since the Supervisor is a
higher privilege level than seL4, it can make changes to the system of which
seL4 is unaware. This would likely add on to the assumptions made if the proof
ever included this configuration setting. The proofs would have to assume that
the SMC calls that are made will not invalidate the proof. This is on the User
to look at what each allowed SMC call does and check that it won’t interfere
with the proof.

## Rationale and alternatives

This design is the best because it gives users flexibility by allowing them to
make some SMC calls while still being able to emulate other SMC calls. It is the
preferred method, because the microkernel shouldn't need to be updated with each
new platform, VMM configuration, and secure application implementation. It can
all be configured in user space.

### Alternative approaches

SMC filtering could be done in the microkernel so that developers are less
likely to configure the system incorrectly. However, there are some cases where
the filtering is dependent on specific threads and the application level (Secure
world communication) instead of just platform dependent. On the first point,
instead of creating a cap for making the SMC call, you could have a cap for each
numbered SMC call so that you could configure what SMC call each thread can make
using the root thread. However, that is quite a bit of work as that will differ
for each ARM platform and adds another step when porting the microkernel to new
ARM platforms. That could also solve the second point, but then users would
likely need to modify the microkernel to support their specific secure world
application, which is something that should really be avoided.

Another part of the implementation that could be done differently is using the
VCPU capability with an access right instead of creating a new type of
capability. The kinds of access rights are already determined as read, write,
grant, and grantreply. A write access right would probably make the most sense,
but it still seems obtuse that a write access on a VCPU capability would allow
the invoker to make an SMC call. Besides that, there are two other issues I see
with this approach:

1. I can foresee a use-case where you have a health monitor component that isn’t
   associated with a VCPU but needs to be able to forward an SMC call to
   actually interact with EL3 or secure applications.

2. If the VCPU capability ever needs read/write access rights that make more
   sense with the type of object it is, for example, limiting which threads can
   actually read or write that VCPUs registers.

For those reasons we believe a new capability makes the most sense.

### Impact of not implementing this

Not implementing this will limit the ARM platforms we can use for the camkes-vm
and/or the guests that can run on those platforms. It will also limit support
for applications that run in secure side of the trustzone that need to
communicate with the nonsecure side (Where sel4, VMMs, and the VMs run).

## Prior art

Xen has a similar implementation for the Zynqmp where arbitration is done to
allow/disallow/emulate SMC calls from guest VMs. The arbitration is quite
specific and is automatically generated based on resource allocation for each
VM. Xen does not have VMM pieces that run in Userspace. Basically all of the
management runs in EL2. Therefore, all of the arbitration is done in Xen itself.
This approach does not make sense for seL4 for the reasons stated above in the
[Rationale](#rationale-and-alternatives) section.

However, this does show a need for this feature in hypervisors on ARMv8
platforms.

If necessary, we could reference the Xen arbitration code to help improve the
default arbitration for the zynqmp in our implementation.

## Unresolved questions

1. How do we address the WCET issue? (Doesn’t need to be solved by this RFC
   because we are documenting the effects)


## Disposition

The TSC has approved the API design in this RFC for implementation as presented
in the current state, but notes that the following two issues should be
clarified in the RFC and corresponding documentation:

- the option 2 for a thread to make SMC calls is to invoke the SMC cap directly,
  and not to switch off trapping on SMC calls for specific threads

- the actual SMC performed by seL4 happens while the kernel holds the kernel
  lock. That means kernel entry will be blocked on other cores until the SMC has
  terminated.

The second point is basically the WCET discussion, but the TSC felt it important
to clearly spell out the consequences.
