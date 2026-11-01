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
