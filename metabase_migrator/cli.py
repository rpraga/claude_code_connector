#!/usr/bin/env python3
"""Command-line interface for Metabase Widget Migrator."""

import sys
import click
from tabulate import tabulate
from colorama import Fore, Style, init as colorama_init

from .config import Config
from .api_client import MetabaseAPIClient
from .query_analyzer import QueryAnalyzer
from .database_mapper import DatabaseMapper
from .query_migrator import QueryMigrator
from .widget_creator import WidgetCreator


# Initialize colorama for cross-platform colored output
colorama_init(autoreset=True)


def print_success(message):
    """Print success message in green."""
    click.echo(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")


def print_error(message):
    """Print error message in red."""
    click.echo(f"{Fore.RED}✗ {message}{Style.RESET_ALL}", err=True)


def print_warning(message):
    """Print warning message in yellow."""
    click.echo(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")


def print_info(message):
    """Print info message in blue."""
    click.echo(f"{Fore.CYAN}ℹ {message}{Style.RESET_ALL}")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Metabase Widget Migrator - Migrate questions between databases.

    This tool helps you migrate Metabase questions (widgets) from one database
    to another, automatically mapping tables and fields while preserving
    Query Builder format.
    """
    pass


@cli.command()
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--url', envvar='METABASE_URL', help='Metabase instance URL')
@click.option('--username', envvar='METABASE_USERNAME', help='Metabase username')
@click.option('--password', envvar='METABASE_PASSWORD', help='Metabase password')
@click.option('--api-key', envvar='METABASE_API_KEY', help='Metabase API key')
def test_connection(config, url, username, password, api_key):
    """Test connection to Metabase instance."""
    try:
        # Load config
        cfg = Config(config)

        # Override with command line args if provided
        if url:
            cfg.config['metabase_url'] = url
        if api_key:
            cfg.config['api_key'] = api_key
        elif username and password:
            cfg.config['username'] = username
            cfg.config['password'] = password

        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        print_info(f"Connecting to Metabase at {metabase_url}...")

        with MetabaseAPIClient(metabase_url, credentials) as client:
            databases = client.list_databases()
            print_success(f"Successfully connected to Metabase!")
            print_info(f"Found {len(databases)} database(s):")

            for db in databases:
                click.echo(f"  - {db['name']} (ID: {db['id']}, Engine: {db.get('engine', 'unknown')})")

    except Exception as e:
        print_error(f"Connection failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument('question_url_or_id')
@click.argument('target_database_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--collection-id', type=int, help='Collection ID to place the migrated question in')
@click.option('--name-suffix', default=' (Migrated)', help='Suffix to add to question name')
@click.option('--dry-run', is_flag=True, help='Preview migration without creating the question')
@click.option('--show-query', is_flag=True, help='Show the migrated query details')
def migrate(question_url_or_id, target_database_id, config, collection_id, name_suffix, dry_run, show_query):
    """Migrate a question to a different database.

    QUESTION_URL_OR_ID: The question ID or URL (e.g., "123" or "https://metabase.com/question/123")

    TARGET_DATABASE_ID: The ID of the target database
    """
    try:
        # Load config
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        print_info(f"Connecting to Metabase...")

        with MetabaseAPIClient(metabase_url, credentials) as client:
            # Extract question ID
            question_id = client.extract_question_id(question_url_or_id)
            print_info(f"Fetching question ID {question_id}...")

            # Get source question
            source_question = client.get_question(question_id)
            print_success(f"Found question: {source_question['name']}")

            # Validate it's Query Builder format
            source_query = source_question.get('dataset_query', {})
            is_valid, error = QueryAnalyzer.validate_query_builder_format(source_query)

            if not is_valid:
                print_error(f"Question cannot be migrated: {error}")
                print_error("This tool only supports Query Builder queries, not native SQL.")
                sys.exit(1)

            print_success("Query is in Query Builder format")

            # Get source database info
            source_db_id = source_query.get('database')
            source_db = client.get_database(source_db_id)
            print_info(f"Source database: {source_db['name']} (ID: {source_db_id})")

            # Get target database info
            target_db = client.get_database(target_database_id)
            print_info(f"Target database: {target_db['name']} (ID: {target_database_id})")

            # Show query summary
            summary = QueryAnalyzer.get_query_summary(source_question)
            print_info("\nQuery Summary:")
            click.echo(f"  Source Table ID: {summary.get('source_table_id')}")
            click.echo(f"  Referenced Fields: {summary.get('field_count', 0)}")
            if summary.get('has_filters'):
                click.echo(f"  Has Filters: Yes")
            if summary.get('has_aggregations'):
                click.echo(f"  Has Aggregations: Yes")
            if summary.get('has_breakouts'):
                click.echo(f"  Has Breakouts: Yes")

            # Create mapper and migrator
            mapper = DatabaseMapper(client, cfg.get_mapping_rules())
            migrator = QueryMigrator(mapper)

            # Check database compatibility
            is_compatible, compat_msg = mapper.validate_database_compatibility(source_db_id, target_database_id)
            if 'Warning' in compat_msg:
                print_warning(compat_msg)
            else:
                print_success(compat_msg)

            # Generate mapping report
            source_table_id = QueryAnalyzer.extract_source_table(source_query)
            field_ids = list(QueryAnalyzer.extract_referenced_fields(source_query))

            print_info("\nGenerating field mapping report...")
            mapping_report = mapper.get_mapping_report(source_table_id, target_database_id, field_ids)

            if mapping_report['errors']:
                print_error("\nMapping Errors:")
                for error in mapping_report['errors']:
                    click.echo(f"  - {error}")

            if mapping_report['warnings']:
                print_warning("\nMapping Warnings:")
                for warning in mapping_report['warnings']:
                    click.echo(f"  - {warning}")

            if mapping_report['mappings']:
                print_success("\nField Mappings:")
                table_data = []
                for mapping in mapping_report['mappings']:
                    table_data.append([
                        mapping['source_field'],
                        mapping['target_field'],
                        mapping.get('source_type', 'N/A'),
                        mapping.get('target_type', 'N/A')
                    ])
                click.echo(tabulate(table_data, headers=['Source Field', 'Target Field', 'Source Type', 'Target Type']))

            # Perform migration
            print_info("\nMigrating query...")
            migrated_query, errors, warnings = migrator.migrate_query(source_query, target_database_id)

            if errors:
                print_error("\nMigration Errors:")
                for error in errors:
                    click.echo(f"  - {error}")
                print_error("\nMigration failed!")
                sys.exit(1)

            if warnings:
                print_warning("\nMigration Warnings:")
                for warning in warnings:
                    click.echo(f"  - {warning}")

            print_success("Query migration completed successfully!")

            if show_query:
                import json
                print_info("\nMigrated Query:")
                click.echo(json.dumps(migrated_query, indent=2))

            # Create or preview widget
            creator = WidgetCreator(client)

            if dry_run:
                print_info("\n--- DRY RUN MODE ---")
                preview = creator.preview_widget_creation(source_question, migrated_query, collection_id, name_suffix)
                print_info("Question would be created with:")
                click.echo(f"  Name: {preview['name']}")
                click.echo(f"  Display: {preview['display']}")
                click.echo(f"  Target Database ID: {preview['target_database']}")
                if preview.get('collection_id'):
                    click.echo(f"  Collection ID: {preview['collection_id']}")
                if preview.get('description'):
                    click.echo(f"  Description: {preview['description']}")
                print_success("\nDry run completed. No question was created.")
            else:
                print_info("\nCreating migrated question...")
                created = creator.create_widget(source_question, migrated_query, collection_id, name_suffix)

                print_success(f"\nQuestion created successfully!")
                click.echo(f"  Name: {created['name']}")
                click.echo(f"  ID: {created['id']}")
                click.echo(f"  URL: {metabase_url}/question/{created['id']}")

    except Exception as e:
        print_error(f"Migration failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('question_url_or_id')
@click.option('--config', default='config.yaml', help='Path to configuration file')
def info(question_url_or_id, config):
    """Show information about a question.

    QUESTION_URL_OR_ID: The question ID or URL
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            question_id = client.extract_question_id(question_url_or_id)
            question = client.get_question(question_id)

            click.echo(f"\n{Fore.CYAN}Question Information:{Style.RESET_ALL}")
            click.echo(f"  Name: {question['name']}")
            click.echo(f"  ID: {question['id']}")
            click.echo(f"  Created: {question.get('created_at', 'N/A')}")

            if question.get('description'):
                click.echo(f"  Description: {question['description']}")

            query = question.get('dataset_query', {})
            summary = QueryAnalyzer.get_query_summary(question)

            click.echo(f"\n{Fore.CYAN}Query Type:{Style.RESET_ALL}")
            click.echo(f"  {summary['type']}")

            if summary['type'] == 'Query Builder':
                click.echo(f"\n{Fore.CYAN}Query Details:{Style.RESET_ALL}")
                click.echo(f"  Database ID: {summary.get('database_id')}")
                click.echo(f"  Source Table ID: {summary.get('source_table_id')}")
                click.echo(f"  Referenced Fields: {summary.get('field_count', 0)}")
                click.echo(f"  Has Filters: {'Yes' if summary.get('has_filters') else 'No'}")
                click.echo(f"  Has Aggregations: {'Yes' if summary.get('has_aggregations') else 'No'}")
                click.echo(f"  Has Breakouts: {'Yes' if summary.get('has_breakouts') else 'No'}")
                click.echo(f"  Has Order By: {'Yes' if summary.get('has_order_by') else 'No'}")
                click.echo(f"  Has Limit: {'Yes' if summary.get('has_limit') else 'No'}")

                print_success("\n✓ This question can be migrated with this tool")
            else:
                print_error("\n✗ This question uses native SQL and cannot be migrated")

    except Exception as e:
        print_error(f"Failed to get question info: {e}")
        sys.exit(1)


@cli.command()
@click.option('--config', default='config.yaml', help='Path to configuration file')
def list_databases(config):
    """List all available databases."""
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            databases = client.list_databases()

            if not databases:
                print_warning("No databases found")
                return

            print_success(f"Found {len(databases)} database(s):\n")

            table_data = []
            for db in databases:
                table_data.append([
                    db['id'],
                    db['name'],
                    db.get('engine', 'unknown'),
                    '✓' if not db.get('is_sample', False) else '✗ (sample)'
                ])

            click.echo(tabulate(table_data, headers=['ID', 'Name', 'Engine', 'Available']))

    except Exception as e:
        print_error(f"Failed to list databases: {e}")
        sys.exit(1)


@cli.command()
def init_config():
    """Create an example configuration file."""
    from .config import create_example_config

    try:
        create_example_config('config.example.yaml')
        print_success("Example configuration created: config.example.yaml")
        print_info("Copy this file to config.yaml and fill in your Metabase details.")
    except Exception as e:
        print_error(f"Failed to create example config: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
