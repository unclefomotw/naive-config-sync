# naive-config-sync

Simple CLI tool to synchronize local configuration files with a remote Git repository via template substitution.

## Features

- Push local files to a Git repo with variable interpolation
- Pull remote templates and update local config with backups
- Show sync status per rule

## Installation

Requires Python 3.10+ , and installing in a virtual environment is recommended

Currently you install from git

```bash
pip install git+https://github.com/unclefomotw/naive-config-sync.git
```

... or install from source:

```bash
git clone https://github.com/unclefomotw/naive-config-sync.git
cd naive-config-sync
pip install -e .
```

## Configuration

By default all the config, backups, and local repo are stored in `~/.naive-config-sync`.
This can be changed by setting the `NAIVE_CONFIG_SYNC_HOME` environment variable.

Copy and edit the example config:

```bash
mkdir -p ~/.naive-config-sync
cp sync_config.yaml.example ~/.naive-config-sync/sync_config.yaml
```

Edit `~/.naive-config-sync/sync_config.yaml`:

- **remote_url**: Git repository URL to store your config templates.
- **device_name**: Friendly name for this device.
- **device_vars**: Key-value pairs of content and path replacements for your local computer
- **sync_rules**: Mapping of rule names to source paths and repo templates.
    - **source_path**: Absolute path to the local config file, which can be interpolated with `device_vars`
    - **remote_template_path**: Path to the file in the remote repo (and local sync repo)
    - **content_vars**: List of variables to be replaced in the content

## Usage

```bash
naive-config-sync [OPTIONS] <command>
```

Commands:

- `push`   : Push local config to remote repo
- `pull`   : Pull remote templates and overwrite local config
- `status` : Show sync status for each rule

Options:

- `--dry-run` : Preview actions without making changes
- `--rules`   : Comma-separated list of rule names (default: all)

### Examples

```bash
naive-config-sync status
naive-config-sync --dry-run push
naive-config-sync pull --rules cursor_settings,windsurf_keybindings
```

## Environment Variables

- `NAIVE_CONFIG_SYNC_HOME`: Override config directory (default: `~/.naive-config-sync`)

## License

MIT