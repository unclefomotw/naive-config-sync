import logging
import os
import subprocess
from pathlib import Path

import yaml

from .rule import SyncRule, SyncRules

if os.getenv('NAIVE_CONFIG_SYNC_HOME'):
    CONFIG_HOME = Path(os.environ['NAIVE_CONFIG_SYNC_HOME'])
else:
    CONFIG_HOME = Path.home() / '.naive-config-sync'


class FileSync:
    def __init__(self, dry_run: bool,
                 config_path: Path = CONFIG_HOME / "sync_config.yaml"):
        self.config = self._load_config(config_path)

        self.device_name = self.config.get('device_name', "Unknown Device")

        self.local_repo_root: Path = CONFIG_HOME / 'sync_repo'
        self.backup_root: Path = CONFIG_HOME / 'backup'
        self.remote_repo_url = self._load_remote_repo()

        self.sync_rules: SyncRules = self._parse_rules()

        # Ensure local repo_path exists and remote repo is set up
        self._ensure_repo()

        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: Path) -> dict:
        """Load the sync configuration file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _load_remote_repo(self) -> str:
        if 'remote_url' not in self.config:
            raise ValueError("Remote URL not specified in config")

        return self.config['remote_url']


    def _parse_rules(self) -> SyncRules:
        """Parse sync rules from the configuration."""
        rules: dict[str, SyncRule] = {}
        _device_vars = self.config.get('device_vars', {})

        for name, rule in self.config.get('sync_rules', {}).items():
            _content_vars=rule.get('content_vars', [])
            for _content_var in _content_vars:
                if _content_var not in _device_vars:
                    raise ValueError(f"Invalid content variable: {_content_var}")

            rules[name] = SyncRule(
                source_path=rule['source_path'].format(**_device_vars),
                remote_template_path=rule['remote_template_path'],
                content_vars=_content_vars
            )
        return SyncRules(rules, _device_vars)

    def _ensure_repo(self):
        self.backup_root.mkdir(parents=True, exist_ok=True)

        if not self.local_repo_root.exists():
            self.local_repo_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'init'], cwd=self.local_repo_root, check=True)

            # Add remote if specified in config
            subprocess.run(
                ['git', 'remote', 'add', 'origin', self.remote_repo_url],
                cwd=self.local_repo_root, check=True
            )

    def _get_rules_to_run(self, rule_names_to_run: list[str] | None = None) -> dict[str, SyncRule]:
        if rule_names_to_run is None:
            return self.sync_rules.rules

        ret_rules: dict[str, SyncRule] = {}
        for rule_name in rule_names_to_run:
            if rule_name in self.sync_rules.rules:
                ret_rules[rule_name] = self.sync_rules.rules[rule_name]
            else:
                self.logger.warning(f"Invalid rule name: {rule_name}.  Skipping.")

        return ret_rules

    def _convert_source_to_repo_template(self, rule_name: str) -> None:
        rule = self.sync_rules.rules.get(rule_name)
        if not rule:
            raise ValueError(f"Invalid rule name: {rule_name}")

        source_path: Path = Path(rule.source_path)
        local_sync_path: Path = self.local_repo_root / rule.remote_template_path

        if source_path.exists():
            with open(source_path, 'r') as f:
                source_content = f.read()
                source_template = self.sync_rules.convert_to_template(source_content, rule_name)

            # ensure the directory of local_sync_path exists
            local_sync_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_sync_path, 'w') as f:
                f.write(source_template)

    def push(self, dry_run: bool = False, rule_names_to_run: list[str] | None = None):
        """
        Push local config files to the repository.
        """

        for rule_name in self._get_rules_to_run(rule_names_to_run):
            self._convert_source_to_repo_template(rule_name)

        # get files that would've been changed if added, including untracked files and files not staged for commit
        changed_files = []
        try:
            result = subprocess.check_output(
                ['git', 'status', '--short'], cwd=self.local_repo_root, text=True
            )
            for line in result.splitlines():
                # Untracked files start with '??', unstaged modified files start with ' M'
                if line.startswith('??') or line.startswith(' M') or line.startswith('AM'):
                    # The filename comes after the status
                    changed_files.append(line[3:].strip())
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get git status: {e.stderr}")

        if changed_files:
            self.logger.info("Changed/untracked files:")
            for f in changed_files:
                self.logger.info(f"  {f}")
        else:
            self.logger.info("No changed or untracked files detected.")


        # Commit and push if remote is set
        if not dry_run:
            subprocess.run(['git', 'add', '.'], cwd=self.local_repo_root, check=True)
            subprocess.run(
                ['git', 'commit', '-m', f'Sync configs from {self.device_name}'],
                cwd=self.local_repo_root, check=True)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=self.local_repo_root, check=True)
            self.logger.info("Pushed changes to repository")

    def pull(self, dry_run: bool = False, rule_names_to_run: list[str] | None = None):
        """
        Pull the latest changes from the repository and overwrite the local files.
        """

        # Pull from git remote
        subprocess.run(
            ["git", "pull", "origin", "main"], cwd=self.local_repo_root, check=True
        )

        # Convert the local sync repo to actual content, and compare with local source
        for rule_name, rule in self._get_rules_to_run(rule_names_to_run).items():
            local_sync_path: Path = self.local_repo_root / rule.remote_template_path
            backup_path: Path = self.backup_root / rule.remote_template_path
            source_path: Path = Path(rule.source_path)

            if not local_sync_path.exists():
                self.logger.warning(
                    "%s: The repo does not contain %s.  Skip, and the local source %s will not be deleted",
                    rule_name, local_sync_path, source_path
                )
                continue

            # Convert the local sync repo to actual content
            with open(local_sync_path, 'r') as f:
                repo_template = f.read()
                repo_content = self.sync_rules.get_interpolated_content(repo_template, rule_name)

            # Check if local file needs updating
            if source_path.exists():
                with open(source_path, 'r') as f:
                    source_content = f.read()

                if source_content == repo_content:
                    self.logger.info(f"No changes for {rule_name}")
                    continue

            # Backup local file!
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, 'w') as f:
                f.write(source_content)
                self.logger.info(f"{rule_name}: Back up to {backup_path}")

            # Write local file
            if not dry_run:
                source_path.parent.mkdir(parents=True, exist_ok=True)
                with open(source_path, 'w') as f:
                    f.write(repo_content)

                self.logger.info(f"Updated local file for {rule_name}")
            else:
                self.logger.info(f"Would update local file for {rule_name}")

    def status(self, rule_names_to_run: list[str] | None = None):
        """
        Show status of local config files vs remote repository.
        """

        # Pull from git remote
        subprocess.run(
            ["git", "pull", "origin", "main"], cwd=self.local_repo_root, check=True
        )

        for rule_name, rule in self._get_rules_to_run(rule_names_to_run).items():
            source_path: Path = Path(rule.source_path)
            local_sync_path: Path = self.local_repo_root / rule.remote_template_path

            print(f"=== {rule_name} ===")
            print(f"Source: {source_path}")
            print(f"Local sync repo: {local_sync_path}")

            if source_path.exists() and local_sync_path.exists():
                # Read both files and compare after transformation
                with open(source_path, 'r') as f:
                    source_content = f.read()

                with open(local_sync_path, 'r') as f:
                    repo_template = f.read()
                    repo_content = self.sync_rules.get_interpolated_content(repo_template, rule_name)

                if source_content == repo_content:
                    print("Status: In sync")
                else:
                    print("Status: Modified locally")
            elif source_path.exists():
                print("Status: The repo does not have the content")
            elif local_sync_path.exists():
                print("Status: The file you want to sync does not exist")
            else:
                print("Status: Both repo and local do not have this file")

            print()
