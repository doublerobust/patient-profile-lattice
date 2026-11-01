# Imported synthetic scenario

`fixtures/keynote189-synthetic/` contains a synthetic patient dataset modelled on a real
trial design. It is not real trial data and it is not submission-ready.

- Upstream: `pzhang724/patient-profile-linkage`
- Pinned commit: `be3744cd7768373552e87201ea0efe90578c094f`
- Upstream licence at that commit: none declared. With no licence file, upstream rights are
  reserved by default.
- What we hold: permission from the project owner to use this dataset for internal
  demonstration. That is a data-use authorisation from the requester. It is **not**
  upstream permission to redistribute, and it must not be described as one.
- Provenance: `fixtures/keynote189-synthetic/provenance.json` records the commit, the
  extraction method and the raw hashes. Keep it with the data.

## What this means in practice

1. No licence applied to this repository's source code extends to these fixtures.
2. The published clinical results this scenario is modelled on are background, not an
   acceptance target. The dataset was not calibrated to reproduce them, and its planted
   anomalies were deliberately left in.
3. If the dataset ever needs to leave this project, get upstream permission or a
   compatible upstream licence first, or replace the fixtures with a fetch script that
   never stores the rows here.

## Permission status

Upstream permission: **not yet obtained.** The dataset is published here under the project
owner's data-use authorisation while a permission request is pending.

When a reply arrives, record it here in the following form, quoting the reply verbatim:

    Granted: <date> by <name>, via <channel>
    Scope: republish the generated synthetic dataset at
           fixtures/keynote189-synthetic/raw.json, commit be3744c, with attribution
    Excluded: generator code, licence to the code
    Text: "<their words>"

Record the scope, not just the fact, and keep the quoted file path so the permission trail
names what was granted.

## On the copyright status of generated output

The rows here were emitted by running a seeded generator; the human contribution was the
design of the scenario, not the individual records. Under current US Copyright Office
guidance, material whose expressive elements are determined by a machine is not the
product of human authorship and is not protected by copyright, while a human-designed
selection and arrangement can still be argued to be. How that applies to a synthetic
dataset of this kind is unsettled, and this note is not legal advice. The practical effect
is that the redistribution question is smaller than "all rights reserved" would suggest,
but it is not zero, which is why asking the upstream author is the clean resolution rather
than a formality.
