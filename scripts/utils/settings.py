import logging
import tomli

from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_settings_path = Path(__file__).parent.parent.parent / 'settings'


class Settings:
    def __init__(self) -> None:
        self.toml: Mapping[str, Any] | None = self.load_toml()

        if self.toml is None:
            self.fields: list[str] = []
            self.csv_header: str = ''
            return

        self.fields = self.get_fields()
        self.csv_header = ','.join(self.fields)

    def get_fields(self) -> list[str]:
        fields: list[str] = []

        if self.toml is None:
            return fields

        for group in self.toml.get('fields', {}):
            if group == 'betfair' and not self.toml.get('betfair_data', False):
                continue
            for field, enabled in self.toml['fields'][group].items():
                if enabled:
                    fields.append(field)

        return fields

    def load_toml(self) -> Mapping[str, Any] | None:
        default_path = _settings_path / 'default_settings.toml'
        user_path = _settings_path / 'user_settings.toml'

        path = user_path if user_path.is_file() else default_path
        if path == default_path and not default_path.is_file():
            raise FileNotFoundError(f'{default_path} does not exist')

        try:
            with open(path, 'rb') as f:
                return tomli.load(f)
        except tomli.TOMLDecodeError:
            logger.error(f'TomlParseError: {path}')
            return None
