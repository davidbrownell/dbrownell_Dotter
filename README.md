**Project:**
[![License](https://img.shields.io/github/license/davidbrownell/dbrownell_Dotter?color=dark-green)](https://github.com/davidbrownell/dbrownell_Dotter/blob/master/LICENSE)

**Package:**
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dbrownell_Dotter?color=dark-green)](https://pypi.org/project/dbrownell_Dotter/)
[![PyPI - Version](https://img.shields.io/pypi/v/dbrownell_Dotter?color=dark-green)](https://pypi.org/project/dbrownell_Dotter/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/dbrownell_Dotter)](https://pypistats.org/packages/dbrownell-dotter)

**Development:**
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![pytest](https://img.shields.io/badge/pytest-enabled-brightgreen)](https://docs.pytest.org/)
[![CI](https://github.com/davidbrownell/dbrownell_Dotter/actions/workflows/CICD.yml/badge.svg)](https://github.com/davidbrownell/dbrownell_Dotter/actions/workflows/CICD.yml)
[![Code Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/davidbrownell/f15146b1b8fdc0a5d45ac0eb786a84f7/raw/dbrownell_Dotter_code_coverage.json)](https://github.com/davidbrownell/dbrownell_Dotter/actions)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/y/davidbrownell/dbrownell_Dotter?color=dark-green)](https://github.com/davidbrownell/dbrownell_Dotter/commits/main/)

<!-- Content above this delimiter will be copied to the generated README.md file. DO NOT REMOVE THIS COMMENT, as it will cause regeneration to fail. -->

## Contents
- [Overview](#overview)
- [Installation](#installation)
- [Development](#development)
- [Additional Information](#additional-information)
- [License](#license)

## Overview
`dbrownell_Dotter` is a declarative dotfile management tool that helps you install, synchronize, and manage configuration files across your system. It supports:

- **File installation** via copying, symlinking, or template rendering
- **Jinja2 templating** for dynamic configuration files
- **Variable substitution** from command-line arguments or environment variables
- **Regex-based substitutions** for modifying existing files in-place
- **Reverse synchronization** to push manual changes back to source files

Configuration is defined in YAML or JSON5 files, making it easy to version control and share your dotfile setup. See [davidbrownell/dotfiles](https://github.com/davidbrownell/dotfiles) for an example of such a configuration.

### How to use `dbrownell_Dotter`

#### Basic Commands

**Install dotfiles:**
```bash
uvx dbrownell_Dotter Install <config_file(s)> [OPTIONS]
```

**Reverse sync changes back to source:**
```bash
uvx dbrownell_Dotter ReverseSync <config_file(s)> [OPTIONS]
```

**Common options:**
- `--var key=value` - Pass template variables (can be used multiple times)
- `--dry-run` - Preview changes without modifying files
- `--verbose` - Show verbose output
- `--debug` - Show debug information

#### Variables

Variables can be used in configuration files and jinja templates.

| Variable Type | Format |
| --- | --- |
| Environment Variable | `${VAR_NAME}` |
| Command Line Variable | `{{ VAR_NAME }}` |

#### Configuration File Format

```yaml
variable_definitions:
  username: "Your username (ex: `john`)"
  email: "Your email address (ex: `john@example.com`)"

entries:
  # Simple file copy/link
  - source: my_config.txt
    dest: ~/.config/myapp/config.txt

  # Jinja2 template (auto-detected by .jinja, .jinja2, or .j2 extension)
  - source: bashrc.jinja
    dest: ~/.bashrc

  # Regex substitution on existing file
  - source: null
    dest: /etc/myapp/config.conf
    substitutions:
      - pattern: "^EMAIL=.*$"
        replacement: "EMAIL={{ email }}"
```

#### Examples

**Install with variables:**
```bash
uvx dbrownell_Dotter Install config.yaml --var username=john --var email=john@example.com
```

**Preview changes before installing:**
```bash
uvx dbrownell_Dotter Install config.yaml --dry-run
```

**Sync manual edits back to source files:**
```bash
uvx dbrownell_Dotter ReverseSync config.yaml --var username=john
```

<!-- Content below this delimiter will be copied to the generated README.md file. DO NOT REMOVE THIS COMMENT, as it will cause regeneration to fail. -->

## Installation

Note that these steps are not required when invoking `dbrownell_Dotter` via `uvx`.

| Installation Method | Command |
| --- | --- |
| Via [uv](https://github.com/astral-sh/uv) | `uv add dbrownell_Dotter` |
| Via [pip](https://pip.pypa.io/en/stable/) | `pip install dbrownell_Dotter` |

### Verifying Signed Artifacts
Artifacts are signed and verified using [py-minisign](https://github.com/x13a/py-minisign) and the public key in the file `./minisign_key.pub`.

To verify that an artifact is valid, visit [the latest release](https://github.com/davidbrownell/dbrownell_Dotter/releases/latest) and download the `.minisign` signature file that corresponds to the artifact, then run the following command, replacing `<filename>` with the name of the artifact to be verified:

```shell
uv run --with py-minisign python -c "import minisign; minisign.PublicKey.from_file('minisign_key.pub').verify_file('<filename>'); print('The file has been verified.')"
```

## Development
Please visit [Contributing](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/CONTRIBUTING.md) and [Development](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/DEVELOPMENT.md) for information on contributing to this project.

## Additional Information
Additional information can be found at these locations.

| Title | Document | Description |
| --- | --- | --- |
| Code of Conduct | [CODE_OF_CONDUCT.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/CODE_OF_CONDUCT.md) | Information about the norms, rules, and responsibilities we adhere to when participating in this open source community. |
| Contributing | [CONTRIBUTING.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/CONTRIBUTING.md) | Information about contributing to this project. |
| Development | [DEVELOPMENT.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/DEVELOPMENT.md) | Information about development activities involved in making changes to this project. |
| Governance | [GOVERNANCE.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/GOVERNANCE.md) | Information about how this project is governed. |
| Maintainers | [MAINTAINERS.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/MAINTAINERS.md) | Information about individuals who maintain this project. |
| Security | [SECURITY.md](https://github.com/davidbrownell/dbrownell_Dotter/blob/main/SECURITY.md) | Information about how to privately report security issues associated with this project. |

## License
`dbrownell_Dotter` is licensed under the <a href="https://choosealicense.com/licenses/MIT/" target="_blank">MIT</a> license.
