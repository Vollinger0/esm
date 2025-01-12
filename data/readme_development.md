# Development of the ESM tool itself

## running locally 

- once: install requirements: `pip install -r requirements.txt`
- start esm: `py -m esm`

Alternatively, you can enable the virtual environment, like below, or create one and install the requirements.

### on linux/macOs for development

- install venv: `py -m venv .venv`
- activate venv: `.\\.venv\Scripts\activate`
- install requirements: `pip install -r requirements.txt`
- start esm: `esm`

### on windows for development

- start standard cmd console (not powershell!)
- install venv: `py -m venv .venv`
- activate venv: `.\\.venv\Scripts\activate.bat`
- install requirements: `pip install -r requirements.txt`
- start esm: `esm`

## releasing

- execute a `pip freeze | sort -u > requirements.txt`
  - check the computed requirements, clean up as necessary. In doubt, start with a fresh venv to check if all is there.
- create a distribution once: `pyinstaller esm.spec --noconfirm`, to make sure it works properly, this will also generate the default config
- make sure all changes are in the main branch in github
- create a tag with the version number, e.g. "0.4.0" and push it
- the github action "release worklow" will start automatically and create a release with a "v" prefixed, so it ends up as "v0.4.0"
- edit the release and add documentation about what changed. *especially* required changes in configuration files!
- profit!

### creating new example configuration file
- `python generate-default-config.py`

This will create a configuration file with all defaults and example values defined in the config models (`ConfigModels.py`). This file is also auto-generated when creating a new distribution.

### creating new binary distribution

Make sure you are in the current env of the script, then execute:

- `pip install -e .` to make sure the module builds correctly
- `pyinstaller esm.spec --noconfirm` creates the distribution

This will create the distributable files with all its dependencies in `dist/esm`. Pack it up and distribute if you don't use the release workflow

### upgrading dependencies
The requirements.txt file, if generated like above, will contain all (incl. transitive) dependencies and pin their versions. To update the version use:
- `pip install --upgrade -r requirements_top.txt`
Then regenerate the requirements.txt to have a "frozen" reproducible state of dependencies.

## TODOS

[here](todos.md)

#### copyright by Vollinger 2023-2025
