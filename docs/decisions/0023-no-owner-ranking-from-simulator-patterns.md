# 0023 No owner ranking from patterns seen only in simulator data

- Status: Accepted
- Date: 2026-10-05

## Context

Session 14 (decision 0022) noted that on Medium dev seeds the ground truth
owner of a flow between two applications is always the owner of the source
side application, and asked whether palimp should name that owner first.
Candidates of a two-application flow were already never stated as certain,
but they were ordered by support (number of sources, then reasons), which is
an implicit ranking.

The source-side pattern is a property of how the simulator assigns owners,
not something seen in real companies: a database team often owns the access
to its database, a monitoring team owns the flows from its probes, and so on.
Tuning on it would score well on the simulator and mislead real engineers.

## Decision

- palimp never ranks owners, applications or intents by a pattern observed
  only in simulator data (for example "the source-side owner is always
  right"). A rule must be justified by how real firewalls and organizations
  work, independently of the simulator.
- For a flow between two applications, the candidates of both applications
  are listed in alphabetical order, unranked, and the ask line says so ("not
  ranked"). Support counts stay visible in the reasons of each candidate.
- Flows involving one application keep the decision 0022 order (most
  supported first), since that order reflects evidence, not flow direction.

## Alternatives considered

- Source side first: rejected, it encodes a simulator convention.
- Keep ordering by support for two-application flows: rejected, ticket counts
  of two different applications are not comparable (one application may simply
  have more change requests), so the order would still read as a ranking.

## Consequences

- No measured change in "right owner among candidates" (order does not count)
  and no change to owners stated as certain.
- Simulator backlog (v2): a service desk that files tickets on behalf of
  owners, to test that palimp does not take the requester as the owner
  (the real-world risk named in decision 0022).

## Challenged by Nathan

Yes. Nathan asked that palimp not rank owners by patterns seen only in
simulator data, and that both owners of a two-application flow be listed
unranked. Accepted as stated.
