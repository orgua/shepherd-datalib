# Shepherd - Datalib

[![PyPiVersion](https://img.shields.io/pypi/v/shepherd_data.svg)](https://pypi.org/project/shepherd_data)
[![image](https://img.shields.io/pypi/pyversions/shepherd_data.svg)](https://pypi.python.org/pypi/shepherd-data)
[![Pytest](https://github.com/orgua/shepherd-datalib/actions/workflows/py_unittest.yml/badge.svg)](https://github.com/orgua/shepherd-datalib/actions/workflows/py_unittest.yml)
[![CodeStyle](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Data-Package**: <https://pypi.org/project/shepherd_data>

**Core-library**: <https://pypi.org/project/shepherd_core>

**Main Documentation**: <https://orgua.github.io/shepherd>

**Main Project**: <https://github.com/orgua/shepherd>

**Source Code**: <https://github.com/orgua/shepherd-datalib>

---

The Repository contains python packages for the [shepherd](https://github.com/orgua/shepherd)-testbed

- `/shepherd_core` bundles functionality that is used by multiple tools and the community
- `/shepherd_data` holds the data-module that is designed for users of the testbed

Navigate there to get an in depth view for the tools.

## Development

### PipEnv

The environment brings everything needed for dev-work, steps for installing are described below also as shell-commands (OS-independent).

- clone repository
- navigate shell into directory
- install environment
- activate shell
- optional
  - update pipenv (optional)
  - add special packages with `-dev` switch

```Shell
git clone https://github.com/orgua/shepherd-datalib
cd .\shepherd-datalib

pipenv install --dev
pipenv shell

pipenv update
pipenv install --dev pytest
```

### Update dynamic Fixtures

When external dependencies ([Target-Lib](https://github.com/orgua/shepherd-targets/)) or core-models change, the fixtures should be also updated for the testbed.

```shell
python3 extra/gen_firmwares.py
python3 extra/gen_energy_envs.py
python3 extra/prime_database.py
# commit the updated 'shepherd_core/shepherd_core/data_models/content/_external_fixtures.yaml'
# delete (optional) 'extra/content'
```

### Running Testbench

- run pytest in ``_core``- or ``_data``-subdirectory
- alternative (bottom-cmd) is running from failed test to next fail (if any)

```shell
pytest
pytest --stepwise
```

### Code Coverage (with pytest)

- run coverage in ``_core``- or ``_data``-subdirectory
- check results (in browser `./htmlcov/index.html`)

```shell
coverage run -m pytest

coverage html
# or simpler
coverage report
```

## Release-Procedure

- if models were changed run all scripts in `/extra` to update pseudo-database
- increase version number by executing ``bump2version`` (see cmds below)
- install and run ``pre-commit`` for QA-Checks, see steps below
- run unittests from both packages locally
  - additionally every commit gets automatically tested by GitHub workflows
- update changelog in ``CHANGELOG.md``
- move code from dev-branch to main by PR
- add tag to commit - reflecting current version number - i.e. ``v2023.9.0``
  - GitHub automatically creates a release & pushes the release to pypi
- update release-text with latest Changelog (from `CHANGELOG.md`)
- rebase dev-branch

```shell
pipenv shell

bump2version --allow-dirty --new-version 2025.04.2 patch
# ⤷ format: year.month.patch_release

pre-commit run --all-files

# additional QA-Tests (currently with open issues)
cd shepherd_core
mypy .

# inside sub-modules unittests
cd shepherd_core
pytest --stepwise
cd ../shepherd_data
pytest --stepwise
# when developers add code they should make sure its covered by the testsuite
coverage run -m pytest
coverage html
```

## Open Tasks / TODO

- remove db-specific fields
- add map-generator
- add tests for broken h5-files
- divide h5-tests in valid and healthy
- add multi-processing
- divide core into sub-libs:
  - shepherd_models: data_models + vsource
  - shepherd_fw_tools
  - shepherd_decoders
  - shepherd_core:
- allow combining measurements (data_0...data_#)
  - either hostname, date or seq. number after data_
  - shepherd-dataset must be explained more clearly
  - common time-vector for all? or can hdf5 compress 5 copies of the same vector? TEST
- clearer rules on how delta-time can be generated
  - generally: t[1:] - t[:-1], but last sample is missing (fill with min or mean dt)
  - more advanced integration methods (trapezoidal, polynomial, ..)
  - resulting energy-vectors can be base for more precise upsampling-routines
- more generalized hdf5-structure-explorer (yaml-export) to allow opening all variants
  - currently it faults when expecting shepherd-conform structure
  - additional features: show 1..10 of front and tail from dataset
- monitors & recorder should move here
  - add fn for validation, export, visualization
  - also add basic IV-group as recorder

- [click progressbar](https://click.palletsprojects.com/en/8.1.x/api/#click.progressbar) ⇾ could replace tqdm
- implementations for this lib
  - generalize up- and down-sampling, use out_sample_rate instead of ds-factor
    - lib samplerate (tested) ⇾ promising, but designed for float32 and range of +-1.0
    - lib resampy (tested) ⇾ could be problematic with slice-iterator
    - https://stackoverflow.com/questions/29085268/resample-a-numpy-array
    - scipy.signal.resample, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample.html
    - scipy.signal.decimate, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.decimate.html
    - scipy.signal.resample_poly, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html#scipy.signal.resample_poly
    - timestamps could be regenerated with np.arange( tmin, tmax, 1e9/samplerate)
  - generalize converters (currently in IVonne)
    - isc&voc <-> ivcurve
    - ivcurve ⇾ ivsample
  - plotting and downsampling for IVCurves ()
  - plotting more generalized (power, cpu-util, ..., if IV then offer power as well)
  - some metadata is calculated wrong (non-scalar datasets)
  - unittests & codecoverage ⇾ 79% with v22.5.4, https://pytest-cov.readthedocs.io/en/latest/config.html
    - test example: https://github.com/kvas-it/pytest-console-scripts
    - use coverage to test some edge-cases
  - sub-divide valid() into healthy()
  - add gain/factor to time, with repair-code
  - add https://pypi.org/project/nessie-recorder/#files
- main shepherd-code
  - proper validation first
  - update commentary
  - pin-description should be in yaml (and other descriptions for cpu, io, ...)
  - datatype-hint in h5-file (ivcurve, ivsample, isc_voc), add mechanism to prevent misuse
  - hostname for emulation
  - full and minimal config into h5
  - use the datalib as a base
  - isc-voc-harvesting
  - directly process isc-voc ⇾ resample to ivcurve?
