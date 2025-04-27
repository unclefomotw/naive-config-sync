import logging

import click

from .filesync import FileSync


@click.command()
@click.argument('command', type=click.Choice(['push', 'pull', 'status']))
@click.option('--dry-run', is_flag=True, help='Show what would be done')
@click.option('--rules', default=None, help='Comma-separated list of rules to sync (default: all)')
def main(dry_run, command, rules):
    """Config file synchronization tool"""
    try:
        rule_names_to_run: list[str] | None = [r.strip() for r in rules.split(',')] if rules else None
        sync: FileSync = FileSync(dry_run=dry_run)
        if command == "push":
            sync.push(dry_run, rule_names_to_run=rule_names_to_run)
        elif command == "pull":
            sync.pull(dry_run, rule_names_to_run=rule_names_to_run)
        elif command == "status":
            sync.status(rule_names_to_run=rule_names_to_run)
    except Exception as e:
        logging.error(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    main()