from dataclasses import dataclass


@dataclass
class SyncRule:
    """Represents how a file is synced."""
    source_path: str
    remote_template_path: str
    content_vars: list[str]


class SyncRules:
    # The template key contains non-readable, special characters
    KEY_PATTERN = "\x00\x01<|{keyname}|>\x01\x00"

    def __init__(self,
                 rules: dict[str, SyncRule],
                 device_vars: dict[str, str]):
        self.rules = rules
        self.device_vars = device_vars

    def get_interpolated_content(self, template: str, rule_name: str) -> str:
        rule = self.rules.get(rule_name)
        if not rule:
            raise ValueError(f"Invalid rule name: {rule_name}")

        for content_var in rule.content_vars:
            template_key = self.KEY_PATTERN.format(keyname=content_var)
            template = template.replace(template_key, self.device_vars[content_var])

        return template

    def convert_to_template(self, content: str, rule_name: str) -> str:
        rule = self.rules.get(rule_name)
        if not rule:
            raise ValueError(f"Invalid rule name: {rule_name}")

        for content_var in rule.content_vars:
            template_key = self.KEY_PATTERN.format(keyname=content_var)
            content = content.replace(self.device_vars[content_var], template_key)

        return content
