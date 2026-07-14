# Post-initialiser RFC

- Author: Zoltan, Julia, Terry
- Proposed: 2026-07-08

## Summary

This RFC proposes a solution that adds a post-initialisation domain to allow 
capabilities shared among user-defined initialiser components without breaking 
the existing Microkit assumptions on protection domains.

## Motivation

On x86, there are two primary requirements for ACPI/PCIe driver:

Unlike the ARM and RISC-V, x86 systems do not know the resource configurations 
at build time, and have to figure things out by interacting with the ACPI tables
possibly located anywhere in memory. In previous internal meeting, 
we decided to have 
[an ACPI driver and a PCIe driver](https://github.com/au-ts/sddf/issues/622) to 
solve this problem, but the following use cases are not supported by the existing 
capDL initialiser/Microkit:

- The ACPI driver needs access to most if not all of the remaining untypeds (and 
internal information from the capDL initialiser about the watermarks about UTs if 
used), because:
    * It needs to be able to map in all the ACPI tables (the addresses are not 
    fixed nor contiguous, so one needs to map-then-parse-then-map in a loop)., etc). 
    * It also likely needs to be able to create the (seL4 device) frames for PCIe 
    config space and MMIO windows.

- The PCIe driver needs the ability to create IO ports, frames, and IRQ 
capabilities corresponding to a certain PCI device ID; it also needs to be able 
to access the PCIe config space (to itself) and parts of the PCIe MMIO window 
(for other device drivers); these are frames that can be determined by the ACPI 
driver (from device UT)

An experimental implementation introduced a `cnode` tag in SDF to allow a custom 
CNode to be shared by PDs, but raised the 
[concerns from the verification folks](https://github.com/seL4/microkit/pull/539#issuecomment-4871178574). 
The shared CNodes bring more flexibility to the user CSpace management but breaks
the Microkit's assumptions for the verification story. And it does not make sense 
to introduce a feature but disallow people to use it.

## Guide-level explanation

Given that both the ACPI driver and PCIe driver run only once before everything 
else, and they do not need most of features of protection domains in the current 
Microkit, it makes sense to be moved out from protection domains.

Zoltan proposed to add an explicit `post-initialiser` feature to run the 
one-shot code straight after the capDL initialiser. This can make sure, after
the post-initialisation phase, the capabilities owned by protection domains are 
still static (i.e., the staticity assumptions in Microkit proofs), so does not 
screw up the verification story.

The `post-initialisers` are executed in the `phase` order, and can pass
capabilities via the shared CNodes, which are restricted inside the 
`post-initialisation` block. Take the ACPI/PCIe work as an example, the Microkit
SDF Syntax design would look like:

```
<system>
  <post_initialisation>
    <cnode name="post_capdl_untypeds" slot_count_bits="9" />
    <cnode name="pcie_resources" slot_count_bits="8" />
  
    <post_initialiser name="acpi_driver" phase="1" />
      <cap_cnode name="post_capdl_untypeds" slot="2" />
      <cap_cnode name="pcie_resources" slot="3" />
    </post_initialiser>
    
    <post_initialiser name="pcie_driver" phase="2" />
      <cap_cnode name="pcie_resources" slot="2" />
    </post_initialiser>
  </post_initialisation>

  <protection_domain name="ixgbe_driver" priority="100" />
    ...
  </protection_domain>

  ...
</system>
```

In the above example, the ACPI drvier runs as the first post-initialiser and 
receives all the leftover untypeds from the capDL initialiser via the shared
CNode `post_capdl_untypeds`, (which associates with another feature to capDL, 
but is not included in this discussion). After mapping and parsing the ACPI
tables, it handoffs all the required capabilities to the PCIe driver via shared
CNode `pcie_resources` for centralised resource allocation and configurations.
Therefore, at the start point of PDs running, the memory, I/O Ports, and IRQs
of PCIe device drivers have been ready.

This feature is useful when ther are some components running at only the init 
phase and some other PDs waiting for them to start. Even if a component has no 
requirements on shared CNodes, moving it into the `post-initialisation` block 
also helps remove the startup signaling the waitings, as they are good to
go once get scheduled.

## Reference-level explanation

The introduced `post-initialiser` feature does not affect any existing features
supported by Microkit, and the users do not need to make changes to their
existing systems.

The Microkit implementation for this RFC includes:
- `post-initialisation` block: provides a scope that the users can define 
`post-initialisers` inside and map the resources to the `post-initialisers`.
- `cnode` tag: allows the users to define custom CNodes inside the 
`post-initialisation` block and map them into `post-initialisers`.
- `post-initialiser` component: defines a non-PD component that runs after the 
capDL initialiser in `phase` order, and has a subset of features of PD, including
(1) cap_sharing: access to capabilities of other PDs or `post-initialisers`; 
and (2) memory mapping: access to MemoryRegions. The programming model of
a `post-initialiser` is slightly different from that of a PD, so it should have
the only program entry `main()` rather than `init()` and `notified()`.

The Microkit maintainers might need to duplicate work when shared features of PD
and `post-initialiser` are changed or added, as a `post-initialiser` should
have different CSpace as well.

## Drawbacks

This RFC restricts the shared CNodes inside the `post-initialisation` block, but
they might be wanted for PDs in the future, e.g., in template PDs.

## Rationale and alternatives

### Alternative 1: ACPI tables relocation in a preloader

Peter's thought: have a preloader runs in a pre-seL4 phase to relocate all the
ACPI tables at specific addresses and then the capDL initialiser can just map 
the ACPI tables and pass only device memory untypeds rather than all the untypeds.

Would it be better to just put the whole ACPI parser into the seL4 boot process?

### Alternative 2: Pass capabilities via IPC

Instead of passing capabilities via the shared CNode, one thread can pass at 
most 3 capabilities in an IPC, but need a more complicated mechanism if there 
are more than 3 capabilities to pass.

## Unresolved questions

1. Microkit SDF syntax of post-initialiser component?
2. Capabilities passing mechanism between `post-initialiser`?
3. Should post-initialiser run in a strict order?
4. Does this design actually not break the Microkit verification story?

