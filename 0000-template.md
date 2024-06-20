<!--
  SPDX-License-Identifier: MIT or CC-BY-SA-4.0
  Copyright 2024 seL4 Project a Series of LF Projects, LLC.
  Copyright Rust Language Community

  Based on the Rust RFC template at <https://github.com/rust-lang/rfcs>
-->

# seL4 RFC Template

<!--
  To use this template:

 - Fork this repository on GitHub
 - Choose a number nnn0 greater than any of the nnnx files in
       ls -l src/*/????-*.md

 - Make a branch <nnn0>-<short-rfc-name>
 - Copy this template into src/proposed/<nnn0>-<short-rfc-name>.md

 - Replace the title above with the title of your RFC
 - Choose CC-BY-SA-4.0 above for contributing the RFC (only the template should be MIT)
 - Add your name/company to Copyright, removing the other ones (they apply to the template)

 - Fill in author, at the end, before you submit, fill in proposal date
 - Fill in the rest of the sections. It is Ok to leave out sections that do not
   apply, but don't leave out sections lightly.

 - Make a pull request to <https://github.com/seL4/rfcs> to publish the RFC and
   start formal discussion.

 - If you are not sure yet how to fill in all sections or want to discuss informally
   before you start the process, you could post a link to your partially
   filled in template on your fork to https://sel4.discourse.group/c/rfc-discussion/
   or start a GitHub gist or other markdown drafting site with the template to
   work on it incrementally without doing all the setup steps first. Then go
   through the steps above when you are ready to submit the RFC.
-->

- Author: [fill in]
- Proposed: [YYYY-MM-DD fill in]

## Summary

One paragraph explanation of the change.

## Motivation

- Why are we doing this?
- What problem does it solve? What use cases does it support?
- What is the expected outcome?

## Guide-level explanation

Explain the change or feature as you would to another user of seL4.

This section should:

- clearly outline new named **concepts**
- provide some **examples** of how it will be used, and
- explain how **users** should think about it.

You should describe the change in a manner that is clear to both existing seL4
users and to new users of the ecosystem. For instance, if the change is to the
seL4 API, this section should include the prose of the corresponding new
paragraphs or sections int the seL4 manual.

Any changes that existing users need to make either as a result of the RFC or
such that the can use the feature should be clearly stated here.

## Reference-level explanation

Explain the change or feature as you would to the **developers and maintainers**
of the seL4 ecosystem. For instance, if it is a change to the seL4 API, this
section would contain the part that should go into API reference of the seL4
manual.

This section should provide sufficient technical detail to guide any related
implementation and ongoing maintenance. Where relevant, it should discuss
expected maintenace, performance, and verification impact.

This section should clearly describe how this change will interact with the
existing ecosystem, describe particular complex examples that may complicate the
implementation, and describe how the implementation should support the examples
in the previous section.

## Drawbacks

Outline any arguments that have been made against this proposal and discuss why
we may not want to accept it.  Also discuss any complications that may arise
from the proposed change that may require specific consideration.

## Rationale and alternatives

- Why is this design the best in the space of possible designs?
- What other designs have been considered and what is the rationale for not
  choosing them?
- What is the impact of not doing this?

## Prior art

Discuss prior art, both the good and the bad, in relation to this proposal.  A
few examples of what this can include are:

- For ecosystem proposals: Does this feature exist in similar systems and what
  experience have their community had?
- For community proposals: Is this done by some other community and what were
  their experiences with it?
- What lessons can we learn from what other communities have done here?
- Are there any published papers or great posts that discuss this? If you have
  some relevant papers to refer to, this can serve as a more detailed
  theoretical background.

This section is intended to encourage you as an author to think about the
lessons from other systems, provide readers of your RFC with a fuller picture.
If there is no prior art, that is fine -- your ideas are interesting to us
whether they are brand new or if it is an adaptation from other systems.

Note that while precedent set by other systems is some motivation, it does not
on its own motivate an RFC.

## Unresolved questions

- What needs to be resolved in further discussion before the RFC is approved?
- What needs to resolved during the implementation of this RFC?
- What related questions are beyond the scope of this RFC that should be
  addressed beyond its implementation?
