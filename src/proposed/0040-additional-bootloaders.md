<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2020 Dornerworks
-->

# Ability to build additional bootloaders inside the seL4 build system

- Author: Alex Pavey
- Proposed: 2020-09-16

## Summary

Currently, the seL4 build system only provides the ability to build the BBL.
Depending on the targeted system or application, it is not always desired to
build the BBL. The addition the UseBootEnv CMake config option expands on the
current capability of building boot artifacts by providing the user the ability
to specify the desired boot chain as a string of options (Ex: `-DUseBootEnv="hss
u-boot"`). When specified, the system will build the desired boot options along
with a build of the rest of the project.

A current proof of concept implementation can be found under the
polarfire-support branch of our fork of seL4_tools here:
<https://github.com/dornerworks/seL4_tools/tree/polarfire-support>.


## Motivation

Other build systems provide the option to build all the boot artifacts required
to get a system up and running. Having this option will allow for added
convenience and make it easier to get a system up and running.

Currently, it only supports building of the BBL (current way it was being built
was moved to this option), U-Boot, and the Hart Software services for the
Polarfire SoC. The design, however, is meant to be extendable for other
bootloaders and platforms in the future by adding additional command sequences
under an if statement for the desired bootloader.

If supported bootloaders are specified by the user in this config option, the
specified bootloaders will be built with a build of the rest of the system and
their images as well as any necessary artifacts (i.e. `uEnv.txt`) will be placed
in the `<build-dir>/images` directory with the seL4 images.

## Guide-level explanation

The UseBootEnv config option can be configured just like any of the other CMake
config options in the system. This variable is a string that when specified
should contain your desired boot stages. For the polarfire SoC this would look
like -DUseBootEnv="hss u-boot" if you were to specify it as an option during the
execution of the init-build.sh script. This option, however, can also be
specified as part of a settings.cmake file. By specifying the options in the
polarfire example, the build system will add additional commands to build the
hss and u-boot images and any supporting artifacts to a project build. The
output images and artifacts are then placed in the `<build-dir>/images`
directory where they can then be deployed to your system through whatever boot
mechanism you are using (for example an SD card).

If your specific bootloader doesn't currently have any supported commands, they
can be added to the `ConfigureBootEnv` CMake function in the
`tools/seL4/cmake-tool/helpers/bootenv.cmake` file. To do so add an if statement
with the bootloader name as you would specify it in the `UseBootEnv` string and
add the following under the statements scope. The build commands and any
additional config options such as a path variable to the bootloader's source
under the tools directory. And add the path to the expected output image to the
CMake boot_files list so it gets linked into the build.

## Reference-level explanation

This change adds additional functionality to the current seL4 build system and
does not change any of the features of seL4 itself. Expansions of this concept
should be isolated under an if statement and therefore should not affect other
users unless they want to use one of the specified bootloaders. As it currently
stands, an attempt was made to keep the U-Boot build fairly platform agnostic
(but RISC-V specific), however, it is mostly geared toward the Polarfire SoC.
Therefore, some additions will probably be necessary to utilize with other
systems. This option is minimally plugged into the `rootserver.cmake` process
and therefore the only real maintenance that I can see being required at the
moment would be due to a change in the `rootserver.cmake` process, the handling
of cmake configuration options, polarfire specific changes to the boot process,
or changes in how these bootloaders are built.

## Drawbacks

The current implementation is very specific to booting a polarfire board from an
SD card and is tied to specific versions of the bootloader repos. Additional
work will be needed to handle broader use cases.

## Rationale and alternatives

The current design allows for simple expansion through the use of isolated if
statements as "handlers" for a specific bootloader and minimal affect on current
build methods due to the fact that it does not have to be utilized.

## Prior art

Many other build systems provide the ability to build in the necessary
bootloaders as part of their build process.
