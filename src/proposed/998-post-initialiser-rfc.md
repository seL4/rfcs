# Post-initialiser RFC

- Author: Zoltan, Julia, Terry
- Proposed: 2026-07-08

## Summary

This RFC proposes a solution that adds a post-initialisation domain to allow capabilities shared among
user-defined initialiser components without breaking the existing Microkit assumptions on protection domains.

## Motivation

On x86, there are two primary requirements for ACPI/PCIe driver:

Unlike the ARM and RISC-V, x86 systems do not know the resource configurations at build time, and have to figure things out by interacting with the ACPI tables possibly located anywhere in memory. In previous internal meeting, we decided to have [an ACPI driver and a PCIe driver](https://github.com/au-ts/sddf/issues/622) to solve this problem, but the following use cases are not supported by the existing capDL initialiser/Microkit:

- The ACPI driver needs access to most if not all of the remaining untypeds (and internal information from the capDL initialiser about the watermarks about UTs if used), because:
    * It needs to be able to map in all the ACPI tables (the addresses are not fixed nor contiguous, so one needs to map-then-parse-then-map in a loop). , etc). 
    * It also likely needs to be able to create the (seL4 device) frames for PCIe config space and MMIO windows.

- The PCIe driver needs the ability to create IO ports, frames, and IRQ capabilities corresponding to a certain PCI device ID;
it also needs to be able to access the PCIe config space (to itself) and parts of the PCIe MMIO window (for other device drivers); these are frames that can be determined by the ACPI driver (from device UT)

The experimental implementation introduced a `cnode` tag in SDF to allow a custom CNode to be shared by PDs, but raised the [concerns from the verification experts](https://github.com/seL4/microkit/pull/539#issuecomment-4871178574). This feature brings more flexibility to the user CSpace management but breaks the Microkit's assumptions for the verification story. And it does not make sense to introduce a feature but disallow people to use it.

## Proposals

Given that both the ACPI driver and PCIe driver run only once before everything else, and they do not need most of features of protection domains in the current Microkit, it makes sense to be moved out from protection domains.

Zoltan proposed to add an explicit `post-initialiser` feature to run the one-shot code straight after the capDL initialiser. This keeps the Microkit state after `post-initialisation` still same as the assumptions, so does not screw up the verification story.

The solution could be:

### 1. Wrapper around the capDL initialiser

Use the capDL initialiser as a library and extend it with `post-initialisation` code.
(I @terryzbai personally don't think this is reasonable for the components that do not need the access to all the untypeds, e.g., the PCIe driver)

### 2. Post-initialiser component

New (non-protected) domains are executed after the capDL initialiser in the `phase` order, and the capabilities can be exchanged between the capDL initialisers.

The options of capability passing mechanisms:

1. Restricted CNode sharing between only `post-initialiser`

CNodes can only be mapped into `post-initialiser` so it won't affect the assumptions on protection domains. The `post-initialiser` can be executed like a pipeline with one-way capability passing, which meets all the known requirements. The Microkit SDF Syntax design looks like:
```
<system>
  <post_initialisation>
    <cnode name="post_capdl_untypeds" slot_count_bits="9" />
    <cnode name="pci_resources" slot_count_bits="8" />
  
    <post_initialiser name="acpi_driver" phase="1" />
      <cap_cnode name="post_capdl_untypeds" slot="2" />
      <cap_cnode name="pci_resources" slot="3" />
    </post_initialiser>
    
    <post_initialiser name="pci_driver" phase="2" />
      <cap_cnode name="pci_resources" slot="2" />
    </post_initialiser>
  </post_initialisation>

  <protection_domain name="ixgbe_driver" priority="100" />
    ...
  </protection_domain>

  ...
</system>
```

2. Capability passing via IPC
Each IPC can only pass at most 3 capabilities, so this means two `post-initialiser` components need to be active during the capability passing process.

## More potential use cases

Apart from the ACPI/PCIe driver, there might be some other use cases where the new feature can help:
- Clock/Pinmux driver: configure things to a static state at post-initialisation phase, but need to reconsider if we want dynamic clock/pinmux configurations at run time.
- HPET driver: the HPET driver itself might not be a `post-initialiser` but the configuration interface (e.g., device memory and IRQs) are extracted from the ACPI tables.
- Djawula?

## Unresolved questions

1. Microkit SDF syntax of post-initialiser component
2. Capabilities passing mechanism between `post-initialiser`.
3. New feature to the capDL loader for handing off all the remaining untypeds.

