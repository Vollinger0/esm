# Development of the ESM tool itself

## running locally 

- once: install requirements: `pip install -r requirements.txt`
- start esm: `py -m esm`

Alternatively, you can enable the virtual environment, like below, or create one and install the requirements.

### on linux/macOs for development:

- install venv: `py -m venv .venv`
- activate venv: `.\\.venv\Scripts\activate`
- install requirements: `pip install -r requirements.txt`
- start esm: `esm`

### on windows for development:

- start standard cmd console (not powershell!)
- install venv: `py -m venv .venv`
- activate venv: `.\\.venv\Scripts\activate.bat`
- install requirements: `pip install -r requirements.txt`
- start esm: `esm`

## releasing

- execute a `pip freeze | sort -u >> requirements.txt`
  - check the computed requirements, clean up as necessary. In doubt, start with a fresh venv to check if all is there.

### creating new binary distribution

Make sure you are in the current env of the script, then execute:

- `pip install -e .` to make sure the module builds correctly
- `pyinstaller esm.spec --noconfirm` creates the distribution

This will create the distributable files with all its dependencies in `dist/esm`. Pack it up and distribute.

## TODOS

[here](todos.md)

#### copyright by Vollinger 2023-2024
