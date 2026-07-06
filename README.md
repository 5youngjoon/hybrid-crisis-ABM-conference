# hybrid-crisis-ABM-conference
v.1.88 for Conference (Young Joon Oh)

Replication archive for the papers "How a Hybrid Crisis ABM's Parameters Were Found and Decided" and "After the Shooting Stops."

## Start

```bash
python extract_literals.py Hormuz_Escalation_ver_1_88_conference.nlogox --out ./scan
```

OutputS: 18 interface controls, 114 declared globals, 134 procedures, 1,161 numeric-literal occurrences, 938 consequential occurrences, and 128 distinct consequential numeric values. 

To run the model itself, open `Hormuz_Escalation_ver_1_88_conference.nlogox` in NetLogo 7.0 or later with The BehaviorSpace experiments.

## In this Repository

- `extract_literals.py`
- `scan/` — Raw and de-duplicated literal lists, declared globals, interface widgets, and the summary counts.
- `audit/validation_sample.csv` — The manual audit ledger
- `tables/` — The summary tables cited in Sections 4 and 5 and in Supplement S1.
- `results/` — States for the six experiment families (baseline, neutral, H1, H2, H3, diplomacy).
