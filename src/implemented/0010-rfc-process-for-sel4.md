<!--
  SPDX-License-Identifier: CC-BY-SA-4.0
  Copyright 2018 Data61, Curtis Millar
-->

# An RFC process for the seL4 ecosystem

- Author: Curtis Millar
- Proposed: 2018-12-13

## Summary

> [!NOTE]
> This is the RFC process as it was first proposed in 2018. The process has
> changed in details over time, for instance it now runs on GitHub instead of
> Jira.
>
> The current seL4 RFC process is described in the [seL4 RFC repository].

[seL4 RFC repository]: https://github.com/seL4/rfcs/blob/main/README.md

In order to deal with major changes to the seL4 ecosystem, a process of Requests
For Comments (RFCs) will be introduced. These will take the form of issues on a
dedicated Jira project which are open to the public to view changes as they are
planned and to provide feedback and input on the direction of those changes.

## Motivation

We have in the past made many large changes to the ecosystem with little or no
warning that such changes were being planned only to notify the community of
such changes as they were deployed. This has been a limitation of the processes
we have in place for making such changes.

As the seL4 community grows and the platform is more widely used we need to
ensure that such changes occur in a manner that provides the best outcomes for
all affected parties and that gives advanced warning of such changes that
affected projects have ample time to plan and prepare.

The RFC process ensures that the community is aware of fundamental changes to
the ecosystem and provides opportunity for discussion and contribution ahead of
major changes. The process also provides an avenue for the community to
co-ordinate large changes to the ecosystem with all of the same benefits in a
manner we have had difficulty supporting in the past.

## Guide-level explanation

The RFC process is one that any member of the community can initiate allowing
not only the core seL4 team but also all users of seL4 to co-ordinate major
changes to the ecosystem.

The RFC process begins with a discussion on one of the existing points of
communication, namely the IRC channel and the mailing list. This is to ensure
that when an RFC is proposed its purpose and design are clear multiple
alternatives have been considered and the impact on the ecosystem is understood.

Once the discussion has lead to support for the change, both from the community
and the seL4 development team, someone will create an RFC issue on the dedicated
Jira project. The person who does takes responsibility for maintaining the
proposal through the approval process. This includes monitoring discussion on
the issue and updating the issue description to reflect changes that need to be
made to the proposal.

Where RFCs cannot gather enough discussion for a consensus to be formed but the
issue is still considered worthy of further consideration it will be postponed
and may be reconsidered at a later date when a member of the community
volunteers to take responsibility for it.

Once there is consensus on the change from a majority of the community and the
seL4 development team the RFC may be approved or rejected. Whomever approves the
RFC is then responsible for maintaining the RFC through its implementation.

In cases where an RFC is approved but the resources cannot be found to see it
through to complete implementation or resources are diverted from the
implementation of an RFC it will be deferred. Continuing work on deferred RFCs
will take priority over approving new RFCs when resources later become
available.

## Reference-level explanation

RFCs will be submitted via a public Jira project which will enforce the RFC
workflow and chain of responsibility. Each RFC will be maintained in the
description field of an 'RFC' issue within that project. All discussion of the
RFC post-proposal will occur on the issue itself.

The Jira workflow will ensure that the RFC is assigned to its creator upon its
proposal and then assigned to the user by whom it is later approved.

The approver is then responsible for updating the description as changes are
made in the process of implementation and linking related issues from other
projects to track the implementation of the proposal.

## Drawbacks

Jira is limited in many ways, users cannot comment on particular sections of the
description and the comment section does not allow for any level of threading.

There is also no way to review further changes to the RFC as one could with
other document forms, instead a certain set of users are able to change it at
will without review. This can be accounted for, to some degree, by limiting the
ability to modify the issue to the assignee and the project administrators.

## Rationale and alternatives

This process heavily borrows from the Rust RFC process. That process documents
RFCs in a dedicated git repository with the initial process requiring a pull
request, changes recorded in commits, and post-approval changes requiring
further pull-requests. The whole process, moves from their forums in the
pre-proposal stage, to the RFC repository in the approval stage, to a separate
tracking issue in a different repository in the implementation stage.

We felt that the process used by the Rust team would split the information
across too many locations making it harder for all to be maintained and for
users of the platform to find the information that they were looking for.

The chosen design trades features of a more robust approval process for greater
centralisation of the process to a single service. We believe that it is more
important to keep the information spread over fewer sources and that we are not
likely to see the level of involvement that would require a more structured
process in the near future.

We feel the particular features of Jira, such as the ability to enforce a
particular workflow and permissions in software, allow us to account for some of
the benefits we lose by not using both a Git repository and an issue tracker. We
also have experience in administrating and using Jira to track issues which
positions us to better utilise these features.

## Prior art

This sort of process has been used by many other communities to manage and
co-ordinate large scale changes to widely used systems.

A few notable sources of inspiration are:

- Rust's [RFC](https://github.com/rust-lang/rfcs/blob/master/text/0002-rfc-process.md) process,
- Python's [PEP](https://www.python.org/dev/peps/pep-0001/) process, and
- The IETF's [RFC](https://www.ietf.org/standards/rfcs/) process.

These demonstrate that such a process can be used to effectively co-ordinate
community-driven change and ensure that large-scale changes are made with
precise plans documented and key stakeholders involved.

## Unresolved questions

The existing forums for discussion, the IRC channel and the mailing list, are
not necessarily the most accessible media for discussion and may not facilitate
the kind of discussion required by this process as well as other alternatives.
We may wish to utilise an alternative to compliment or replace these.

We may find that the process does require a more rigorous process for tracking
and approving changes to proposals or for more detailed discussion than what
this design anticipates. These requirements should be revisited at a later date
when the process has been under regular use to determine if the process should
be restructured.

## Disposition

This has been accepted and will be put into use. There has been little response
from the community, likely due to this being a new process.

Some of the details of this system, such as it's use of Jira over alternatives
may be revised at a later date. We won't really be sure until we start using it.

> [!NOTE]
> This is the original seL4 RFC process as proposed in 2018. Find the current
> RFC process [here][seL4 RFC repository].