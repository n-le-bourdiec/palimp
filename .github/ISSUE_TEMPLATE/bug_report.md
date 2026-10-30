---
name: Bug report
about: palimp misread an artifact, crashed, or wrote something that looks wrong
labels: bug
---

<!--
Before you attach anything: never post your real configuration, logs, commit
history, hit counts or tickets. Make an anonymized copy first and attach that
copy only:

    palimp anonymize -a ARTIFACTS -o shared-copy --key ~/palimp.key --strip-text

--strip-text removes free text (descriptions, annotations, commit comments,
ticket summaries) instead of rewriting it. Keep the key file private, and never
attach the key or a *.PRIVATE-mapping.json file.

Then READ THE COPY before you post it. Anonymization is keyed pseudonymization,
not encryption: check every file for leftover words (a hostname, a person, a
customer or site name in a line palimp does not read, a comment). The copy also
keeps the structure of your rule base, ports and protocols. Remove or replace
anything that is still recognizable, or attach only the few lines needed to
show the problem.
-->

**What happened**

**What you expected**

**Command and output**

```
palimp --version
palimp ...
```

**Artifacts**

- Which files you gave (config.set, rollbacks, commits.txt, hitcount.txt,
  logs/rt_flow.log, tickets.csv):
- Configuration format (set, hierarchical, saved terminal session):
- Junos version, if known:
- [ ] The attached copy was made with `palimp anonymize --strip-text`, and I
      read it for leftover words before posting.

**Environment**

- OS and Python version:
- Installed with (pipx, pip, from source):
