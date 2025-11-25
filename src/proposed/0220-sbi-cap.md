<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2025 UNSW
  Copyright 2025 Proofcraft
-->

# RISC-V SBI capability

- Author: Gerwin Klein & Ivan Velickovic
- Proposed: 2025-10-23

## Summary

This RFC proposes to add a new, badged capability (similar to the SMC capability)
that allows threads to ask seL4 to make a RISC-V Supervisor Binary Interface (SBI)
call on its behalf.

## Motivation

On RISC-V, there is machine mode, supervisor mode, and user mode. Some hardware
functionality is only available from machine mode and is only accessible through
SBI.

There exists user-level applications that need to make use of certain M-mode
only hardware, such as the PMU for doing performance monitoring. One example
of this is the Foundation's [sel4bench project](https://docs.sel4.systems/projects/sel4bench/).
Without this RFC, recently released and future RISC-V platforms will not work
with sel4bench.

## Guide-level explanation

The [SBI](https://github.com/riscv-non-isa/riscv-sbi-doc/tree/master) can be
invoked via the `ecall` instruction from supervisor mode, in this case seL4.

For each SBI call (excluding the legacy interace which we ignore in this RFC),
there are two values associated.
* The Extension ID (EID)
* The Function ID (FID)

In addition to the EID and FID, there may be up to 5 user-provided arguments.
Returned are two values, the error indicator and value.

We introduce an 'SBI' capability with an invocation that allows user-space
to make such SBI calls.

The capability may be badged to restrict the possible SBI call to a single
EID, or an FID within a specific EID.

The invocation `seL4_RISCV_SBI_Call()` takes the SBI capability and
the SBI arguments in 8 message registers and returns the SBI error and value
in 2 message registers.

The badging occurs in two steps.

The first mint/mutate operation on the SBI cap restricts the cap to only be
used for SBI calls with a badged EID.

Capabilities with a badged EID can be minted/mutated again to restrict
which FID is used for the SBI call.

Capabilities without a badged FID can use all FIDs for the badged EID.

We limit the value of the EID to 28-bits and the value of the FID to
64-bit (on 64-bit systems) and 30-bits on 32-bit systems.

The EID limitation is based on the listed EIDs in the SBI specification.
There is no clear limitation for FIDs, so we allow as much as seL4 can
store within a capability. The FID limitation will not restrict any
interfaces that have been specified in the SBI specification, however
in theory there could be vendor-specific or firmware-specific FIDs that
exceed this limit.

## Reference-level explanation

The implementation is based on the ratified RISC-V SBI v2.0 specification.
The implementation is supported on both 32-bit and 64-bit RISC-V platforms.

### `seL4_RISCV_SBI_Call()`

```c
seL4_Error seL4_RISCV_SBI_Call(seL4_RISCV_SBI _service,
    seL4_RISCV_SBIContext *sbi_args,
    seL4_RISCV_SBIRet *sbi_ret
)
```

```
Parameters
    [in]  _service      Capability to allow threads to make SBI calls.
    [in]  sbi_args      The structure that has the provided arguments.

    [out] sbi_ret  The structure to capture the return values.

Returns
```

Register a6 is for the SBI function ID (FID).
Register a7 is for the SBI extension ID (EID).
Registers a0-a5 are for the SBI call's arguments.
Takes a0-a7 as arguments to an SBI call which are defined as a seL4_RISCV_SBIContext
struct. The kernel makes the SBI call and then returns the registers a0 and a1
in a new seL4_RISCV_SBIRet as the result.

### `seL4_RISCV_SBIContext`

```c
typedef struct seL4_RISCV_SBIContext_ {
    seL4_Word a0;
    seL4_Word a1;
    seL4_Word a2;
    seL4_Word a3;
    seL4_Word a4;
    seL4_Word a5;
    seL4_Word a6;
    seL4_Word a7;
} seL4_RISCV_SBIContext;
```

### `seL4_RISCV_SBIRet`

```c
typedef struct seL4_RISCV_SBIRet_ {
    seL4_Word error;
    seL4_Word value;
} seL4_RISCV_SBIRet;
```

## Drawbacks

The drawbacks are similar to the [SMC RFC](https://sel4.github.io/rfcs/implemented/0090-smc-cap.html#drawbacks)
in that the seL4 WCET is no longer guaranteed and the verification can not make any claims about the effect
of an SBI call.

## Rationale/alternatives and prior art

While the main motiviation is for hardware access such as the PMU, the SBI is so
widely used that it is not possible for all SBI calls to realistically be abstracted
at the supervisor level.

This approach is so far working well for ARM platforms with SMC.

## Unresolved questions

- What happens if a future SBI specification introduces more standard EIDs that
  exceed 28-bits?
- What happens if (on a 32-bit platform) a user needs to use a FID that uses more
  than 30-bits?
