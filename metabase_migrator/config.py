"""Configuration management for Metabase Migrator."""

import os
import yaml
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Manages configuration for Metabase connections."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.

        Args:
            config_path: Path to YAML configuration file. If not provided,
                        will look for config.yaml in current directory.
        """
        # Load .env file if it exists
        load_dotenv()

        self.config_path = config_path or "config.yaml"
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from file or environment variables."""
        config = {}

        # Try to load from file
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}

        # Override with environment variables if present
        if os.getenv('METABASE_URL'):
            config['metabase_url'] = os.getenv('METABASE_URL')
        if os.getenv('METABASE_USERNAME'):
            config['username'] = os.getenv('METABASE_USERNAME')
        if os.getenv('METABASE_PASSWORD'):
            config['password'] = os.getenv('METABASE_PASSWORD')
        if os.getenv('METABASE_API_KEY'):
            config['api_key'] = os.getenv('METABASE_API_KEY')

        return config

    def get_metabase_url(self) -> str:
        """Get Metabase instance URL."""
        url = self.config.get('metabase_url', '').rstrip('/')
        if not url:
            raise ValueError("Metabase URL not configured. Set via config file or METABASE_URL env var.")
        return url

    def get_credentials(self) -> Dict[str, str]:
        """Get authentication credentials.

        Returns:
            Dict with 'username' and 'password' or 'api_key'
        """
        if 'api_key' in self.config:
            return {'api_key': self.config['api_key']}

        username = self.config.get('username')
        password = self.config.get('password')

        if not username or not password:
            raise ValueError(
                "Authentication not configured. Provide either:\n"
                "  - api_key in config file or METABASE_API_KEY env var\n"
                "  - username and password in config file or METABASE_USERNAME/METABASE_PASSWORD env vars"
            )

        return {'username': username, 'password': password}

    def get_mapping_rules(self) -> Dict:
        """Get custom mapping rules for tables/fields if configured."""
        return self.config.get('mapping_rules', {})


def create_example_config(output_path: str = "config.example.yaml"):
    """Create an example configuration file."""
    example_config = {
        'metabase_url': 'https://your-metabase-instance.com',
        'username': 'your-email@example.com',
        'password': 'your-password',
        '# Alternative: use API key instead of username/password': None,
        '# api_key': 'your-api-key',
        '# Optional: custom mapping rules': None,
        'mapping_rules': {
            'table_mappings': {
                '# source_table_name': 'target_table_name'
            },
            'field_mappings': {
                '# source_table.source_field': 'target_table.target_field'
            }
        }
    }

    with open(output_path, 'w') as f:
        yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)

    print(f"Example configuration created at: {output_path}")
    print("Copy this to config.yaml and fill in your details.")
