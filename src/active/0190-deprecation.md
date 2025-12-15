<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2025, UNSW
-->

# Remove support for boards that are out of production

- Author: Peter Chubb
- Proposed: [2025-03-18]

## Summary

Deprecate boards using old no-longer-available-for-purchase system-on-chips

## Motivation

A number of the boards that are currently supported are no longer
available for purchase, and the System-On-Chip they use has been
marked 'End-Of-Life' by the manufacturer.  These are not going to be
used for new designs.

Our continuous integration process takes a long time to run; the more
systems that are supported and tested, the longer it takes.  It is
better to test only the systems that are actually likely to be used,
rather than obsolete systems that noone uses.

In addition, some of the boards we have for the continuous integration
testing have died, and cannot be replaced.  Some have not been tested
for several years now.

By removing some old boards from the list of supported boards:

- the time to perform CI will reduce
- we can over time remove board-specific code from the kernel
- we can create room in the CI system for newer boards.


## Guide-level explanation

I propose removing the following boards from the list of fully
supported boards, and marking them as 'deprecated' on the docs website:

| Board          |   SoC       | Notes |
|----------------|-------------|-------|
| Arndale        | Exynos 5250 | Introduced 2012, last available in 2018 |
| Odroid X       | Exynos 4412 | introduced 2012, last available 2018|
| Hikey960       | Kirin 620   | Introduced 2017, last available 2020|
| Inforce IFC6410| Snapdragon  | Introduced 2013; no userspace support at present|

This would mean in the short term, changing their status to
'unsupported' on the docs wenbsite, and removing them from the CI
system.  For some of them they haven't been tested in quite a while
_anyway_, because of the lack of available working hardware.

In longer term, another RFC in six month's time can propose removing
the code that supports them from the seL4 kernel source.

In addition I propose a regular trigger for considering board
deprecation.  I suggest that once a year, all boards using SoCs no
longer available for purchase be considered for deprecation.  Polling
via the `devel` mailing list, followed by a public RFC, will ensure
that anyone continuing to support and provide seL4-based firmware
updates for such a SoC can object and keep the SoC supported until
they too have marked their product end-of-life.

Any board marked 'deprecated' should have added a time for the
deprecation period to end, and the code that supports it removed from
the kernel.


## Drawbacks

If anyone is still using any of these boards, or supporting a product
that uses the SoC with firmware updates based on seL4, then removing
the board is obviously a bad idea.  However the RFC process should
ensure that such uses can be identified and the board's life extended
if necessary.

Removing code from the kernel (even though board-support code is
generally unverified) is work that would not need to be done without
this proposal.

## Rationale and alternatives

Sooner or later, all things come to an end.  Maintaining systems that
noone wants to use is wasted effort.

## Prior art

RedHAT divides hardware into 'Enabled and fully maintained',
'Deprecated', 'Unmaintained', 'Disabled', and 'Removed' (see
https://access.redhat.com/solutions/6663421 )

Using a deprecated driver results in a message on the console;
'disabled' drivers don't work; 'removed' are not compiled into the
kernel.
Typically a driver remains in 'Deprecated' state for one release
before becoming 'unmaintained' and then 'Disabled' or 'Removed'


## Unresolved questions

- Is anyone maintaining seL4-based firmware in a production environment
  that uses any of these SoCs?

  - No reply has been received during the comment period and after posting to
    the developer mailing list, so the assumption is that they are not in active
    use.

## Disposition

The TSC has voted to approve this RFC, keeping support for the BeagleBoard which
was originally mentioned in the table. Since no concerns have been raised during
the comment period, support for the boards will be removed.

As proposed, we are aiming to check annually for boards that should be dropped,
and are keeping the RFC process and comment period in place as before.
