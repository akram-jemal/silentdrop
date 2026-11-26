# SilentDrop dataset attribution

The bundled `domains.csv` is licensed under the Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International license
([CC BY-NC-SA 4.0 deed](https://creativecommons.org/licenses/by-nc-sa/4.0/),
[legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)).
The Python code is covered by the project's MIT license.

## Source and coverage

The primary source is *URL Testing Lists Intended for Discovering Website
Censorship* (2014), by Citizen Lab and Others.
[Upstream repository](https://github.com/citizenlab/test-lists)

The `source` column identifies the upstream CSV used for each adapted row.
`upstream_category` retains its original category code. The initial dataset
uses revision `e6cba46f8774922e112b11524999584a3cefa15f`.
[Source snapshot](https://github.com/citizenlab/test-lists/tree/e6cba46f8774922e112b11524999584a3cefa15f)
· [Upstream license notice](https://github.com/citizenlab/test-lists/blob/e6cba46f8774922e112b11524999584a3cefa15f/README.md#license)
· [Upstream category legend](https://github.com/citizenlab/test-lists/blob/e6cba46f8774922e112b11524999584a3cefa15f/lists/00-LEGEND-new_category_codes.csv)

The bundled list contains 129 public hostnames across ten categories. Of those,
83 come from the upstream test lists. SilentDrop removed schemes, paths and
duplicates from selected URLs, then assigned service categories. Rows marked
`silentdrop` are independently selected additions. The review covers hostname
selection for school-appropriate diagnostics. User-generated content on a
service can change.

## Updating the list

1. Review the operator and purpose of each proposed hostname. Choose public
   service endpoints suitable for general audiences. Leave out unsafe or
   unknown sites and links to individual pages or accounts.
2. Check the upstream global list and relevant country lists. For a selected
   upstream URL, use its normalized hostname, source CSV path prefixed by
   `citizenlab/`, and original category code. For an independently chosen
   addition, use `silentdrop` with an empty upstream category code.
3. Assign a SilentDrop category from `silentdrop/dataset.py`, submit the CSV
   diff for review, and update the source revision and license notice as needed.
   Update `DATASET_VERSION` whenever entries change.
4. Run `python -m pytest tests/test_dataset.py` and `silentdrop dataset info`.
   These checks load and validate the package data offline.
