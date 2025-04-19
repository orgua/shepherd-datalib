# History of Changes

## v2025.04.2

- drop python 3.8 support
- supported python is now 3.9 - 3.13
- heavy changes in typesystem
- pathlib now has .with_stem() to simplify code

## v2025.04.1

- Core.Reader.read_buffers()
  - safer access to data
  - allow custom segmentation
- avoid usage of os-package in favor of pathlib
  - also transforms get_files() into one-liner
- CLI commands that take h5-files can now search recursively if path is given
- improve link visualizer script (draws nodes and links on map)
- fix bugs discovered by mypy (and use clearer types)
- generalize function-arguments if possible (dict -> Mapping, list -> Sequence or Iterable)
- update deps

## v2025.02.2

- task programmer - reduce default data rate
- firmware verification - properly detect ARM as nRF52 and reduce rejection-rate of hex-detector for nRF52

## v2025.02.1

- Core.Reader
  - bugfix to properly detect `None` voltage steps in artificial static energy-environments (mainly relevant for emulation on sheep)
  - added typecasting to prevent overflow in u64-format while calculating file-duration in ._refresh_file_stats() (relevant for non-valid test-data)
- update deps

## v2024.11.3

- Core.Reader can now determine voltage_step from source-file
- HarvesterPRUConfig.from_vhrv() needs voltage_step IF input is IVCurve for emulation
  - same for init() of VirtualSourceModel
  - this fixes a bug that could ruin emulations with ivcurves (#72)

## v2024.11.2

- adapt fixtures to recent testbed-restructure
- update tooling

## v2024.11.1

- CLI
  - add cutting to extraction-command
  - add cutting to downsampling-command
  - add version-command
  - fix console-output (not appearing)
  - update unittests
- Core.Writer
  - fixed unwanted modification of params (cal, mode, dtype, windows_size)
  - update unittests to prevent similar behavior
- Data.Reader - add cut_and_downsample_to_file()
- vTarget - fix diode model
- vSrc
  - fix pwr_good not enabling when c_out is too large
  - converter is now disabled at startup
- vHrv - emulate the VOC-search-window, include currents (before: output voltage stayed at MPP with current = 0)

## v2024.9.1

- virtual harvester
  - allow direct pass-through
  - cv-harvester can now extrapolate (linear around current set-point) which makes it more responsive and reduces error
- virtual source
  - add feedback-path to harvester (to control cv-harvester) when no boost-converter is used
  - bring changes from pru-code to py
  - simulation can now plot several internal states
  - simulation example now runs several models through the jogging-dataset and creates plots and data
- virtual targets
  - improve current targets
  - add diode+resistor target (to emulate a diode for burning energy)
  - add exemplary instantiations of some targets
- shp-reader - improve calculation of file-stats

## v2024.8.2

- add hdf5-file based simulations
  - targets: resistive, constant-current and constant-power; each controllable by pwr_good
  - source / emulation
  - harvest
  - update examples accordingly `shepherd_core/example/simulation_xyz.py`
- remove progress-bar when task is finished

## v2024.8.1

- plotting: disable creation of tick-offset
- cal: add si-unit
- add `shepherd_core/example/vsource_emulation.py` that processes hdf5-recordings and also generates them
- add `shepherd_core/examples/eenv_generator.py` to create static energy environments
- virtual source model
  - fix off-by-1 error in rows of efficiency-LUTs
  - remove limiting-behavior of boost-regulator
  - add residue-feature to calibration-converters
  - bq25504 - to not cut-off output, increase capacity to 100 uF and adapt pwr-good-voltages (close to DK)
- harvester model
  - fix voc-harvesting
  - improve windowing setting for ingested ivcurve
  - port behavior from PRU
  - port behavior from PRU
- ivcurve-harvesting-fixture: make 110 Hz version the new default
- isc-voc-harvesting-fixture: give 4x more time to settle
- hdf5-writer: only modify non-None elements
- hdf5-reader: improve samplerate calculation

## v2024.7.4

- fix two bugs in calibration
- plotting
  - re-enable plotting of ivcurves (but still warn about it)
  - add plot for power (IV combined)
  - add option to only plot power
  - switch from uA & uW to mA & mW for plots

## v2024.7.3

- fixture-cache -> limit usage to sheep / bbone
- include lib-version in experiment- and wrapper-data
- tb-client - improve query of data
- create AbstractBaseClass for tb-client to allow dedicated Clients like `FixturesClient`, `WebClient`, `DbClient`
- `extra/gen_firmwares.py` shows size of different firmwares (elf, hex, embedded-yaml, embedded-json)
  - yaml / json does embed elf with zstd-compression level20 and base64-encoding

```
saved FW ./content/fw/nes_lab/nrf52_rf_test/build.elf
 -> size-stat: {'elf': 860904, 'hex': 4340, 'yaml': 232007, 'json': 231932}
saved FW ./content/fw/nes_lab/nrf52_deep_sleep/build.elf
 -> size-stat: {'elf': 619088, 'hex': 799, 'yaml': 170395, 'json': 170320}
saved FW ./content/fw/nes_lab/nrf52_rf_survey/build.elf
 -> size-stat: {'elf': 799636, 'hex': 123517, 'yaml': 287927, 'json': 287852}
 ```

## v2024.7.2

- inventory - bugfix for beagle-info
- extract - more robust file-handling
- extract-uart - more robust waveform decoding
- extract-meta - more robust operation
- add script to generate plot of link-matrix

## v2024.7.1

- core - replace scipy-code with numpy to remove dependency
- inventory - add storage-stats and beagle-version-info
- ivonny - explain parameters, obfuscated shockley diode equation
- update deps & tooling

## v2024.5.1

- move config to root-level
- add newest log-names to meta-extractor
- fix advice in error-text
- update deps

## v2024.4.2

- fix import-bug regarding fixtures
- warn when fixtures are empty
- fix relative imports (be as specific as possible)
- fix lots of lint warnings
- improve documentation
- improve error-handling

## v2024.4.1

- add UUID to models
- improve docstrings to be used by shepherd-doc
- improved docs
- switch fully to pyproject.toml
- update deps
- (extra) testbed-layout-table: add fields
- represent current testbed-structure

## v2023.12.1

- optimize reader.read_buffers() to allow omitting timestamp (less overhead)
- change default compression to lzf
- weaken errors / warnings for missing timestamps
- toolchain: replace isort, black, flake8, pylint by ruff

## v2023.11.1

- warn about errors during test-run during validation (default when opening shepherd-files)
- update testbed-structure (changed positions, composition and added two nodes)
- extend GH-Actions (with unittests) to windows & macOS
- fix inventory

## v2023.10.3

- add warning-system for errors in log
- improve verbosity and messages

## v2023.10.2

- fix exit-fn
- allow checking presence of variables in model (if X in Y)
- more efficient coding
- cleanup try-import-code
- cleanup singletons

## v2023.10.1

- updated extraction of included data
- improved handling of faulty files
- supported python is now 3.8 - 3.12
- lots of linting, more pythonic style and interface-improvements
- add timezone to datetime-objects
- more explicit typing

## v2023.9.9

- lots of bugfix
- validate data vs data_type on firmware
- offer example for generic experiment definitions
- shepherd_data: also export stdout-log


## v2023.9.8

- new example and generators
- lots of small bugfixes

## v2023.9.7

- refine content-paths and path-handling of the testbed
- rework data-generators in '/extra'
- testbed-client - add ownership-data if none was provided
- observer-task now has optional start-time and the other models can react to that
- update content-fixtures
- file-based content now has a local-flag to show it has to be copied to the testbed
- discard older fixture-buffer (1 day)

## v2023.9.6

- fix workflows
- latest pydantic-update 2.4 brings some speed improvement for sheep (<10%)

## v2023.9.4

- update fixtures with real testbed-data
- refine testbed-models
  - objects with active=False can't be used in experiment
  - target.id is now used as selector and is also encouraged to be dynamic to shape the testbed (see layout-map in doc)
- integrate gpio-decoder into reader
  - .gpio_to_waveforms()
  - .gpio_to_uart()
- rework GitHub workflow to all release and publish by tagging a commit

## v2023.9.3

- uart-decoder: baudrate-detection more robust
- shpModel: change export to make sure set-parameters get exported
- generators: enable rec of uart
- refactor verbosity-system
- GitHubWorkflow refactoring
- add waveform-extraction for shepherd-data - cmd: extract-uart

## v2023.9.2

- breaking change: cores BaseReader and BaseWriter just become Reader & Writer

## v2023.09.0

- allow negative values when converting raw to SI-units
- lift restriction for pandas < v2
- update dependencies and fix incompats & warnings
- warn when files are not overwritten
- create data-generators for the testbed (./extra)
- improve file-handling
- bugfixes for task-handling
- update documentation
- update IPv4-representation
- extend model with more representation-types (yaml, str, dict, ...)

## v2023.08.8

- further fixes for datetimes
- make shpModel even more like a dict
- fix name-collisions
- add CapeData from Sheep
- extend User.active
- add output_paths to task-sets and make them compatible with prepare_tasks() & extract_tasks()

## v2023.08.7

- move to pydantic V2 with `bump-pydantic`
  - disadvantage 1: min-string-size for models had to be reduced from 4 to 1, due to different local overwriting-rules
  - disadvantage 2: its 60% slower on BBone

```Shell
sudo python3 -X importtime -c 'from shepherd_core.data_models.task import EmulationTask' 2> importtime.log
#  8.4 s on v2023.8.6, pydantic 1.10
# 13.9 s on v2023.8.7, pydantic 2.2.1, core 2.6.1
# 13.7 s with defer_build=True ⇾ triggers bug?
# 12.8 s on v2024.4.1, pydantic 2.7.0, core 2.18.1
# 10.3 s on v2024.5.1, pydantic 2.7.4, core 2.18.4 - debian 12.5
# 10.4 s on v2024.5.1, pydantic 2.8.0, core 2.20.0
# 12.3 s on v2024.8.2, pydantic 2.8.2, core 2.20.1
# 11.7 s on v2024.8.2, pydantic 2.9.0, core 2.23.2
# 18.7 s on v2024.9.1, pydantic 2.9.2, core 2.23.4 - python 3.13 via uv
# 12.2 s on v2024.11.3, pydantic 2.10.6, core 2.27.2
#  8.9 s on v2024.11.3, pydantic 2.11.0a1, core 2.28.0
#  9.5 s on v2025.2.2, pydantic 2.11.1, core 2.33.0
```

## v2023.08.6

- add zstd-compression for embedded fw
- derive fw-name if not provided
- only mock uninstalled modules / packages
- speedup on BBone from 47 s to ~10 s
  - hash-default-value in user-model took 25 s
  - loading fixtures took 6 s (now pickled on first use)
  - scipy.stats takes 4.4 s to import in cal_measurement
  - requests takes 1.3 s to import in testbed_client
  - next slowest external module are: numpy 1.5 s, pwnlib.elf 1.4 s

## v2023.08.5

- ELF-support by default

## v2023.08.4

- add and use fw-helper-fn: compare_hash(), base64_to_hash()
- allow to generate fw-mod from fw-model
- cleanup import-system for pwntools (dependencies caused trouble on windows & BBone)

## v2023.08.3

- improve handling of uninstalled submodules (elf, inventory)
- add helper FNs for fw_tools, including utests
- fix missing imports
- add hash to fw-model

## v2023.08.2

- fix missing imports
- better handle uninstalled sub-modules

## v2023.08.1

- add inventory-functionality
- add uart-waveform decoder
- improve codequality & extend unittests
- update dependencies
- add this changelog
