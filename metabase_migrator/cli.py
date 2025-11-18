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
from .nested_handler import NestedQuestionHandler
from .verifier import QuestionVerifier
from .collection_migrator import CollectionMigrator
from .dashboard_migrator import DashboardMigrator


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


def _migrate_single_question(client, question_id, target_database_id, mapper, migrator,
                            nested_handler, collection_id, name_suffix, dry_run, return_query_only=False):
    """Helper function to migrate a single question (for use in nested migrations).

    Returns:
        If return_query_only: (migrated_query, errors, warnings)
        Otherwise: created_question
    """
    # Fetch question
    question = client.get_question(question_id)
    query = question.get('dataset_query', {})

    # Check if this question is also nested
    is_nested = QueryAnalyzer.is_nested_query(query)
    migrated_card_id = None

    if is_nested:
        # Get the source card ID and look up its migrated version
        source_card_id = QueryAnalyzer.extract_source_card_id(query)
        if source_card_id and nested_handler:
            migrated_card_id = nested_handler.migration_cache.get(source_card_id)

    # Migrate the query
    migrated_query, errors, warnings = migrator.migrate_query(query, target_database_id, migrated_card_id)

    if errors:
        print_error(f"  Migration failed for question {question_id}:")
        for error in errors:
            print_error(f"    - {error}")
        if return_query_only:
            return migrated_query, errors, warnings
        return None

    if warnings:
        for warning in warnings:
            print_warning(f"    - {warning}")

    if return_query_only:
        return migrated_query, errors, warnings

    # Create the migrated question
    if not dry_run:
        creator = WidgetCreator(client)
        created = creator.create_widget(question, migrated_query, collection_id, name_suffix)
        print_success(f"  Created: Question {created['id']} - {created['name']}")

        # Cache the migration mapping
        if nested_handler:
            nested_handler.set_migration_mapping(question_id, created['id'])

        return created

    return None


@cli.command()
@click.argument('question_url_or_id')
@click.argument('target_database_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--collection-id', type=int, help='Collection ID to place the migrated question in')
@click.option('--name-suffix', default=' (Migrated)', help='Suffix to add to question name')
@click.option('--dry-run', is_flag=True, help='Preview migration without creating the question')
@click.option('--show-query', is_flag=True, help='Show the migrated query details')
@click.option('--allow-nested', is_flag=True, help='Allow migration of nested questions (questions based on other questions)')
def migrate(question_url_or_id, target_database_id, config, collection_id, name_suffix, dry_run, show_query, allow_nested):
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
            if summary.get('is_nested'):
                print_warning("  This is a NESTED question (based on another question)")
                click.echo(f"  Source Question ID: {summary.get('source_card_id')}")
            else:
                click.echo(f"  Source Table ID: {summary.get('source_table_id')}")
            click.echo(f"  Referenced Fields: {summary.get('field_count', 0)}")
            if summary.get('has_filters'):
                click.echo(f"  Has Filters: Yes")
            if summary.get('has_aggregations'):
                click.echo(f"  Has Aggregations: Yes")
            if summary.get('has_breakouts'):
                click.echo(f"  Has Breakouts: Yes")

            # Check if nested and handle accordingly
            is_nested = summary.get('is_nested', False)
            if is_nested and not allow_nested:
                print_error("\nThis question is based on another question (nested query).")
                print_info("To migrate nested questions, use the --allow-nested flag.")
                print_info("This will automatically migrate all dependencies.")
                sys.exit(1)

            # Create mapper and migrator
            mapper = DatabaseMapper(client, cfg.get_mapping_rules())
            nested_handler = NestedQuestionHandler(client) if allow_nested else None
            migrator = QueryMigrator(mapper, nested_handler)

            # Handle nested questions
            if is_nested:
                # Analyze dependencies
                print_info("\nAnalyzing dependencies...")
                dep_report = nested_handler.get_dependency_report(question_id)
                click.echo(dep_report)

                # Get migration order
                migration_order, error = nested_handler.get_migration_order(question_id)
                if error:
                    print_error(f"\nDependency analysis failed: {error}")
                    sys.exit(1)

                print_info(f"\nWill migrate {len(migration_order)} question(s) in order:")
                for i, qid in enumerate(migration_order, 1):
                    try:
                        q = client.get_question(qid)
                        click.echo(f"  {i}. Question {qid}: {q.get('name', 'Untitled')}")
                    except:
                        click.echo(f"  {i}. Question {qid}")

                # Migrate all dependencies
                if not dry_run:
                    print_info("\nMigrating dependencies...")
                    for i, dep_id in enumerate(migration_order[:-1], 1):  # All except last (which is the root)
                        print_info(f"\n[{i}/{len(migration_order)-1}] Migrating dependency: Question {dep_id}")
                        _migrate_single_question(client, dep_id, target_database_id, mapper, migrator,
                                                nested_handler, collection_id, name_suffix, False)

                # Now migrate the root question
                print_info(f"\nMigrating main question {question_id}...")
                migrated_query, errors, warnings = _migrate_single_question(
                    client, question_id, target_database_id, mapper, migrator,
                    nested_handler, collection_id, name_suffix, dry_run, return_query_only=True
                )
            else:
                # Check database compatibility
                is_compatible, compat_msg = mapper.validate_database_compatibility(source_db_id, target_database_id)
                if 'Warning' in compat_msg:
                    print_warning(compat_msg)
                else:
                    print_success(compat_msg)

                # Generate mapping report
                source_table_id = QueryAnalyzer.extract_source_table(source_query, allow_nested=False)
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

            if summary['type'] in ['Query Builder', 'Query Builder (Nested)']:
                click.echo(f"\n{Fore.CYAN}Query Details:{Style.RESET_ALL}")
                click.echo(f"  Database ID: {summary.get('database_id')}")

                if summary.get('is_nested'):
                    print_warning(f"  Is Nested: Yes (based on Question {summary.get('source_card_id')})")
                    click.echo(f"  Use 'dependencies' command to see full dependency tree")
                else:
                    click.echo(f"  Source Table ID: {summary.get('source_table_id')}")

                click.echo(f"  Referenced Fields: {summary.get('field_count', 0)}")
                click.echo(f"  Has Filters: {'Yes' if summary.get('has_filters') else 'No'}")
                click.echo(f"  Has Aggregations: {'Yes' if summary.get('has_aggregations') else 'No'}")
                click.echo(f"  Has Breakouts: {'Yes' if summary.get('has_breakouts') else 'No'}")
                click.echo(f"  Has Order By: {'Yes' if summary.get('has_order_by') else 'No'}")
                click.echo(f"  Has Limit: {'Yes' if summary.get('has_limit') else 'No'}")

                if summary.get('is_nested'):
                    print_success("\n✓ This question can be migrated with the --allow-nested flag")
                else:
                    print_success("\n✓ This question can be migrated with this tool")
            else:
                print_error("\n✗ This question uses native SQL and cannot be migrated")

    except Exception as e:
        print_error(f"Failed to get question info: {e}")
        sys.exit(1)


@cli.command()
@click.argument('question_url_or_id')
@click.option('--config', default='config.yaml', help='Path to configuration file')
def dependencies(question_url_or_id, config):
    """Analyze and display question dependencies (nested questions).

    QUESTION_URL_OR_ID: The question ID or URL
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            question_id = client.extract_question_id(question_url_or_id)
            question = client.get_question(question_id)

            print_info(f"Analyzing dependencies for Question {question_id}: {question['name']}\n")

            # Create nested handler
            nested_handler = NestedQuestionHandler(client)

            # Get dependency report
            report = nested_handler.get_dependency_report(question_id)
            click.echo(report)

            # Get migration order
            migration_order, error = nested_handler.get_migration_order(question_id)

            if error:
                print_error(f"\n{error}")
                sys.exit(1)

            if len(migration_order) > 1:
                print_info(f"\nTo migrate this question, {len(migration_order)} question(s) need to be migrated:")
                print_info("Use: ./metabase-migrator migrate --allow-nested to automatically migrate all dependencies")

    except Exception as e:
        print_error(f"Failed to analyze dependencies: {e}")
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
@click.argument('source_question_id', type=int)
@click.argument('target_question_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--sample-size', type=int, default=100, help='Number of rows to sample for comparison (default: 100, use 0 for all rows)')
@click.option('--limit', type=int, help='Maximum rows to fetch from each question')
@click.option('--show-details', is_flag=True, help='Show detailed differences')
def verify(source_question_id, target_question_id, config, sample_size, limit, show_details):
    """Verify that a migrated question produces the same results as the source.

    SOURCE_QUESTION_ID: The original question ID

    TARGET_QUESTION_ID: The migrated question ID
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        print_info(f"Verifying migration: Question {source_question_id} → {target_question_id}")

        with MetabaseAPIClient(metabase_url, credentials) as client:
            verifier = QuestionVerifier(client)

            # Execute verification
            sample = sample_size if sample_size > 0 else None
            print_info(f"Executing queries and comparing results...")

            if sample:
                print_info(f"Using random sample of {sample} rows")
            else:
                print_info("Comparing all rows")

            report = verifier.verify_migration(
                source_question_id,
                target_question_id,
                sample_size=sample,
                limit=limit
            )

            # Display results
            click.echo(f"\n{Fore.CYAN}Verification Results:{Style.RESET_ALL}")
            click.echo(f"  Source Question: {report.get('source_question_name')} (ID: {source_question_id})")
            click.echo(f"  Target Question: {report.get('target_question_name')} (ID: {target_question_id})")

            if report.get('errors'):
                print_error("\nVerification Errors:")
                for error in report['errors']:
                    click.echo(f"  - {error['type']}: {error['message']}")
                sys.exit(1)

            # Execution times
            exec_times = report.get('execution_times', {})
            if exec_times:
                click.echo(f"\n{Fore.CYAN}Execution Times:{Style.RESET_ALL}")
                click.echo(f"  Source: {exec_times.get('source', 0):.2f}s")
                click.echo(f"  Target: {exec_times.get('target', 0):.2f}s")

            # Statistics
            comparison = report.get('comparison', {})
            stats = comparison.get('statistics', {})

            click.echo(f"\n{Fore.CYAN}Statistics:{Style.RESET_ALL}")
            click.echo(f"  Source Rows: {stats.get('source_row_count', 0)}")
            click.echo(f"  Target Rows: {stats.get('target_row_count', 0)}")
            click.echo(f"  Source Columns: {stats.get('source_column_count', 0)}")
            click.echo(f"  Target Columns: {stats.get('target_column_count', 0)}")
            click.echo(f"  Rows Checked: {stats.get('rows_checked', 0)}")

            if stats.get('mismatched_values'):
                click.echo(f"  Mismatched Values: {stats['mismatched_values']}")

            # Result
            if report.get('verified'):
                print_success(f"\n✓ VERIFICATION PASSED")
                click.echo("  The migrated question produces the same results as the source.")
            else:
                print_error(f"\n✗ VERIFICATION FAILED")
                click.echo("  The migrated question produces different results.")

                # Show differences
                differences = comparison.get('differences', [])
                if differences:
                    print_warning(f"\nFound {len(differences)} type(s) of differences:")

                    for diff in differences:
                        diff_type = diff.get('type')
                        click.echo(f"\n  • {diff_type}:")

                        if diff_type == 'row_count_mismatch':
                            click.echo(f"    Source: {diff['source']} rows")
                            click.echo(f"    Target: {diff['target']} rows")
                            click.echo(f"    Difference: {diff['difference']} rows")

                        elif diff_type == 'column_count_mismatch':
                            click.echo(f"    Source: {diff['source']} columns")
                            click.echo(f"    Target: {diff['target']} columns")

                        elif diff_type == 'column_name_mismatch' and show_details:
                            click.echo(f"    Mismatched columns:")
                            for detail in diff.get('details', [])[:10]:
                                click.echo(f"      Column {detail['column_index']}: "
                                         f"'{detail['source_name']}' → '{detail['target_name']}'")

                        elif diff_type == 'data_value_mismatch':
                            click.echo(f"    Total mismatched values: {diff['count']}")
                            if show_details:
                                click.echo(f"    First 10 differences:")
                                for detail in diff.get('details', []):
                                    click.echo(f"      Row {detail['row_index']}, "
                                             f"Column '{detail['column_name']}': "
                                             f"{detail['source_value']} → {detail['target_value']}")

                if not show_details:
                    print_info("\nUse --show-details to see detailed differences")

                sys.exit(1)

    except Exception as e:
        print_error(f"Verification failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('mapping_file', type=click.Path(exists=True))
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--sample-size', type=int, default=100, help='Number of rows to sample for comparison')
@click.option('--show-failures', is_flag=True, help='Show detailed failures')
def batch_verify(mapping_file, config, sample_size, show_failures):
    """Verify multiple migrated questions from a mapping file.

    MAPPING_FILE: CSV file with source_id,target_id pairs (one per line)

    Example mapping file:
      123,456
      124,457
      125,458
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        # Load mapping file
        import csv
        question_pairs = []

        with open(mapping_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    try:
                        source_id = int(row[0].strip())
                        target_id = int(row[1].strip())
                        question_pairs.append((source_id, target_id))
                    except ValueError:
                        print_warning(f"Skipping invalid row: {row}")

        if not question_pairs:
            print_error("No valid question pairs found in mapping file")
            sys.exit(1)

        print_info(f"Loaded {len(question_pairs)} question pair(s) from {mapping_file}")

        with MetabaseAPIClient(metabase_url, credentials) as client:
            verifier = QuestionVerifier(client)

            # Batch verify
            sample = sample_size if sample_size > 0 else None
            print_info(f"Verifying {len(question_pairs)} question pair(s)...\n")

            reports = verifier.batch_verify(question_pairs, sample_size=sample)

            # Generate summary
            summary = verifier.get_summary_report(reports)

            # Display results
            click.echo(f"{Fore.CYAN}Batch Verification Results:{Style.RESET_ALL}")
            click.echo(f"  Total Verified: {summary['total_verified']}")
            click.echo(f"  Passed: {Fore.GREEN}{summary['passed']}{Style.RESET_ALL}")
            click.echo(f"  Failed: {Fore.RED}{summary['failed']}{Style.RESET_ALL}")
            click.echo(f"  Errors: {Fore.YELLOW}{summary['errors']}{Style.RESET_ALL}")
            click.echo(f"  Pass Rate: {summary['pass_rate']:.1f}%")

            # Show failures if requested
            if show_failures and summary['failed_questions']:
                print_warning(f"\nFailed Verifications:")

                for i, failed in enumerate(summary['failed_questions'], 1):
                    click.echo(f"\n{i}. {failed['source_name']} ({failed['source_id']} → {failed['target_id']})")

                    for diff in failed.get('differences', []):
                        click.echo(f"   • {diff.get('type')}")

            # Exit code based on results
            if summary['failed'] > 0 or summary['errors'] > 0:
                sys.exit(1)
            else:
                print_success(f"\n✓ All verifications passed!")

    except Exception as e:
        print_error(f"Batch verification failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--config', default='config.yaml', help='Path to configuration file')
def list_collections(config):
    """List all collections."""
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            collections = client.list_collections()

            if not collections:
                print_warning("No collections found")
                return

            print_success(f"Found {len(collections)} collection(s):\n")

            table_data = []
            for col in collections:
                table_data.append([
                    col.get('id', 'N/A'),
                    col.get('name', 'Untitled'),
                    col.get('description', '')[:50] if col.get('description') else ''
                ])

            click.echo(tabulate(table_data, headers=['ID', 'Name', 'Description']))

    except Exception as e:
        print_error(f"Failed to list collections: {e}")
        sys.exit(1)


@cli.command()
@click.argument('collection_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--database-id', type=int, help='Filter by database ID')
def analyze_collection(collection_id, config, database_id):
    """Analyze a collection and show which questions can be migrated.

    COLLECTION_ID: The ID of the collection to analyze
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()
        custom_mappings = cfg.get_mapping_rules()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            migrator = CollectionMigrator(client, custom_mappings)

            print_info(f"Analyzing collection {collection_id}...\n")

            analysis = migrator.analyze_collection(collection_id, database_id)

            click.echo(f"{Fore.CYAN}Collection: {analysis['collection_name']}{Style.RESET_ALL}")
            click.echo(f"  Total Items: {analysis['total_items']}")

            stats = analysis['statistics']
            click.echo(f"\n{Fore.CYAN}Statistics:{Style.RESET_ALL}")
            click.echo(f"  Total Questions: {stats['total_questions']}")
            click.echo(f"  Migratable: {Fore.GREEN}{stats['migratable']}{Style.RESET_ALL}")
            click.echo(f"  Non-Migratable: {Fore.RED}{stats['non_migratable']}{Style.RESET_ALL}")
            click.echo(f"  Nested Questions: {Fore.YELLOW}{stats['nested_questions']}{Style.RESET_ALL}")
            click.echo(f"  Other Items: {stats['other_items']}")

            if analysis['migratable']:
                print_success(f"\n{len(analysis['migratable'])} question(s) can be migrated:")
                for q in analysis['migratable']:
                    status = " [NESTED]" if q.get('is_nested') else ""
                    click.echo(f"  • {q['id']}: {q['name']}{status}")

            if analysis['non_migratable']:
                print_warning(f"\n{len(analysis['non_migratable'])} question(s) cannot be migrated:")
                for q in analysis['non_migratable'][:10]:
                    reason = q.get('error', q.get('skip_reason', 'Unknown'))
                    click.echo(f"  • {q['id']}: {q['name']} - {reason}")
                if len(analysis['non_migratable']) > 10:
                    click.echo(f"  ... and {len(analysis['non_migratable']) - 10} more")

    except Exception as e:
        print_error(f"Failed to analyze collection: {e}")
        sys.exit(1)


@cli.command()
@click.argument('source_collection_id', type=int)
@click.argument('target_database_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--target-collection-name', help='Name for the target collection')
@click.option('--parent-collection-id', type=int, help='Parent collection ID where the new collection will be created')
@click.option('--source-database-id', type=int, help='Only migrate questions from this database')
@click.option('--allow-nested', is_flag=True, help='Allow migration of nested questions')
@click.option('--name-suffix', default=' (Migrated)', help='Suffix to add to question names')
@click.option('--dry-run', is_flag=True, help='Preview migration without creating anything')
@click.option('--verify', is_flag=True, help='Verify migrated questions after creation')
@click.option('--save-mapping', help='Save migration mapping to CSV file')
def migrate_collection(source_collection_id, target_database_id, config, target_collection_name,
                       parent_collection_id, source_database_id, allow_nested, name_suffix, dry_run, verify, save_mapping):
    """Migrate all questions from a collection to a new collection.

    SOURCE_COLLECTION_ID: The source collection ID

    TARGET_DATABASE_ID: The target database ID for migrated questions
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()
        custom_mappings = cfg.get_mapping_rules()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            migrator = CollectionMigrator(client, custom_mappings)

            # Analyze first
            print_info("Analyzing source collection...")
            analysis = migrator.analyze_collection(source_collection_id, source_database_id)

            click.echo(f"\n{Fore.CYAN}Source Collection:{Style.RESET_ALL} {analysis['collection_name']}")
            click.echo(f"  Questions to migrate: {len(analysis['migratable'])}")

            if not analysis['migratable']:
                print_warning("No questions to migrate!")
                sys.exit(0)

            # Check for nested questions
            nested_count = sum(1 for q in analysis['migratable'] if q.get('is_nested'))
            if nested_count > 0 and not allow_nested:
                print_warning(f"\n{nested_count} nested question(s) found. Use --allow-nested to migrate them.")

            # Perform migration
            if dry_run:
                print_info("\n--- DRY RUN MODE ---")

            print_info("\nMigrating collection...")

            report = migrator.migrate_collection(
                source_collection_id=source_collection_id,
                target_database_id=target_database_id,
                target_collection_name=target_collection_name,
                source_database_id=source_database_id,
                allow_nested=allow_nested,
                name_suffix=name_suffix,
                dry_run=dry_run,
                parent_collection_id=parent_collection_id
            )

            # Show results
            stats = report['statistics']

            click.echo(f"\n{Fore.CYAN}Migration Results:{Style.RESET_ALL}")
            if not dry_run:
                click.echo(f"  Target Collection: {report['target_collection_name']} (ID: {report['target_collection_id']})")
            click.echo(f"  Total: {stats['total']}")
            click.echo(f"  Migrated: {Fore.GREEN}{stats['migrated']}{Style.RESET_ALL}")
            click.echo(f"  Failed: {Fore.RED}{stats['failed']}{Style.RESET_ALL}")
            click.echo(f"  Skipped: {Fore.YELLOW}{stats['skipped']}{Style.RESET_ALL}")

            if report['migrations']:
                print_success(f"\n{len(report['migrations'])} question(s) migrated:")
                for m in report['migrations']:
                    if 'target_id' in m:
                        click.echo(f"  • {m['source_name']} ({m['source_id']} → {m['target_id']})")
                    else:
                        click.echo(f"  • {m['source_name']} (would migrate)")

            if report['failed']:
                print_error(f"\n{len(report['failed'])} question(s) failed:")
                for f in report['failed']:
                    click.echo(f"  • {f['name']} (ID: {f['question_id']})")
                    if 'errors' in f:
                        for err in f['errors']:
                            click.echo(f"    - {err}")

            if report['skipped']:
                print_warning(f"\n{len(report['skipped'])} question(s) skipped:")
                for s in report['skipped']:
                    click.echo(f"  • {s['name']} (ID: {s['question_id']}): {s['reason']}")

            # Save mapping
            if save_mapping and not dry_run:
                csv_content = migrator.get_migration_mapping_csv(report)
                with open(save_mapping, 'w') as f:
                    f.write(csv_content)
                print_success(f"\nMapping saved to: {save_mapping}")

            # Verify if requested
            if verify and not dry_run and report['migrations']:
                print_info("\nVerifying migrated questions...")
                from .verifier import QuestionVerifier

                verifier = QuestionVerifier(client)
                pairs = [(m['source_id'], m['target_id']) for m in report['migrations'] if 'target_id' in m]

                verify_reports = verifier.batch_verify(pairs, sample_size=100)
                summary = verifier.get_summary_report(verify_reports)

                click.echo(f"\n{Fore.CYAN}Verification Results:{Style.RESET_ALL}")
                click.echo(f"  Passed: {Fore.GREEN}{summary['passed']}{Style.RESET_ALL}")
                click.echo(f"  Failed: {Fore.RED}{summary['failed']}{Style.RESET_ALL}")
                click.echo(f"  Pass Rate: {summary['pass_rate']:.1f}%")

                if summary['failed'] > 0:
                    print_warning("\nSome verifications failed. Review the migrations above.")

            if dry_run:
                print_success("\nDry run completed. No questions were created.")
            elif stats['migrated'] > 0:
                print_success(f"\n✓ Collection migration completed!")
                if not dry_run:
                    click.echo(f"View target collection: {metabase_url}/collection/{report['target_collection_id']}")

    except Exception as e:
        print_error(f"Collection migration failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()
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


@cli.command()
@click.argument('dashboard_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--database-id', type=int, help='Filter questions by source database ID')
def analyze_dashboard(dashboard_id, config, database_id):
    """Analyze a dashboard and show which questions can be migrated.

    DASHBOARD_ID: The ID of the dashboard to analyze
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()
        custom_mappings = cfg.get_mapping_rules()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            migrator = DashboardMigrator(client, custom_mappings)

            print_info(f"Analyzing dashboard {dashboard_id}...\n")

            analysis = migrator.analyze_dashboard(dashboard_id, database_id)

            click.echo(f"{Fore.CYAN}Dashboard: {analysis['dashboard_name']}{Style.RESET_ALL}")
            if analysis['description']:
                click.echo(f"Description: {analysis['description']}")
            click.echo(f"  Total Cards: {analysis['total_cards']}")
            if analysis['parameters']:
                click.echo(f"  Dashboard Filters: {len(analysis['parameters'])}")
            if analysis.get('tabs'):
                click.echo(f"  Dashboard Tabs: {len(analysis['tabs'])} ({', '.join(t.get('name', 'Tab') for t in analysis['tabs'])})")

            stats = analysis['statistics']
            click.echo(f"\n{Fore.CYAN}Statistics:{Style.RESET_ALL}")
            click.echo(f"  Total Questions: {stats['total_questions']}")
            click.echo(f"  Migratable: {Fore.GREEN}{stats['migratable']}{Style.RESET_ALL}")
            click.echo(f"  Non-Migratable: {Fore.YELLOW}{stats['non_migratable']}{Style.RESET_ALL}")
            click.echo(f"  Nested Questions: {stats['nested_questions']}")

            if analysis['migratable']:
                print_success(f"\n{stats['migratable']} question(s) can be migrated:")
                for q in analysis['migratable']:
                    nested_label = " [NESTED]" if q.get('is_nested') else ""
                    click.echo(f"  • {q['name']} (ID: {q['id']}){nested_label}")

            if analysis['non_migratable']:
                print_warning(f"\n{stats['non_migratable']} question(s) cannot be migrated:")
                for q in analysis['non_migratable']:
                    reason = q.get('error') or q.get('skip_reason', 'Unknown reason')
                    click.echo(f"  • {q['name']} (ID: {q['id']}) - {reason}")

    except Exception as e:
        print_error(f"Failed to analyze dashboard: {e}")
        sys.exit(1)


@cli.command()
@click.argument('source_dashboard_id', type=int)
@click.argument('target_database_id', type=int)
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--target-dashboard-name', help='Name for the target dashboard')
@click.option('--collection-id', type=int, help='Collection ID to place the dashboard in')
@click.option('--source-database-id', type=int, help='Only migrate questions from this database')
@click.option('--allow-nested', is_flag=True, help='Allow migration of nested questions')
@click.option('--name-suffix', default=' (Migrated)', help='Suffix to add to question names')
@click.option('--dry-run', is_flag=True, help='Preview migration without creating anything')
@click.option('--save-mapping', help='Save migration mapping to CSV file')
def migrate_dashboard(source_dashboard_id, target_database_id, config, target_dashboard_name,
                     collection_id, source_database_id, allow_nested, name_suffix, dry_run, save_mapping):
    """Migrate an entire dashboard to a new database.

    SOURCE_DASHBOARD_ID: The source dashboard ID

    TARGET_DATABASE_ID: The target database ID for migrated questions
    """
    try:
        cfg = Config(config)
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()
        custom_mappings = cfg.get_mapping_rules()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            migrator = DashboardMigrator(client, custom_mappings)

            # Analyze first
            print_info("Analyzing source dashboard...")
            analysis = migrator.analyze_dashboard(source_dashboard_id, source_database_id)

            click.echo(f"\n{Fore.CYAN}Source Dashboard:{Style.RESET_ALL} {analysis['dashboard_name']}")
            click.echo(f"  Questions to migrate: {len(analysis['migratable'])}")
            if analysis['parameters']:
                click.echo(f"  Dashboard filters: {len(analysis['parameters'])}")

            if not analysis['migratable']:
                print_warning("No questions to migrate!")
                sys.exit(0)

            # Check for nested questions
            nested_count = sum(1 for q in analysis['migratable'] if q.get('is_nested'))
            if nested_count > 0 and not allow_nested:
                print_warning(f"\n{nested_count} nested question(s) found. Use --allow-nested to migrate them.")

            # Perform migration
            if dry_run:
                print_info("\n--- DRY RUN MODE ---")

            print_info("\nMigrating dashboard...")

            report = migrator.migrate_dashboard(
                source_dashboard_id=source_dashboard_id,
                target_database_id=target_database_id,
                target_dashboard_name=target_dashboard_name,
                source_database_id=source_database_id,
                collection_id=collection_id,
                allow_nested=allow_nested,
                name_suffix=name_suffix,
                dry_run=dry_run
            )

            # Show results
            stats = report['statistics']

            click.echo(f"\n{Fore.CYAN}Migration Results:{Style.RESET_ALL}")
            if not dry_run and report['target_dashboard_id']:
                click.echo(f"  Target Dashboard: {report['target_dashboard_name']} (ID: {report['target_dashboard_id']})")
            click.echo(f"  Total: {stats['total']}")
            click.echo(f"  Questions Migrated: {Fore.GREEN}{stats['questions_migrated']}{Style.RESET_ALL}")
            click.echo(f"  Questions Failed: {Fore.RED}{stats['questions_failed']}{Style.RESET_ALL}")
            click.echo(f"  Questions Skipped: {Fore.YELLOW}{stats['questions_skipped']}{Style.RESET_ALL}")
            if not dry_run:
                click.echo(f"  Cards Added to Dashboard: {stats['cards_added']}")

            # Show successful migrations
            if report['question_migrations']:
                print_success(f"\n{len(report['question_migrations'])} question(s) migrated:")
                for m in report['question_migrations']:
                    if 'target_id' in m:
                        warnings_str = f" (with {len(m['warnings'])} warnings)" if m.get('warnings') else ""
                        click.echo(f"  • {m['source_name']} (ID: {m['source_id']} → {m['target_id']}){warnings_str}")

            # Show failures
            if report['failed_questions']:
                print_error(f"\n{len(report['failed_questions'])} question(s) failed:")
                for f in report['failed_questions']:
                    errors = f.get('errors', [f.get('error', 'Unknown error')])
                    if isinstance(errors, list):
                        error_str = '; '.join(errors[:2])  # Show first 2 errors
                    else:
                        error_str = str(errors)
                    click.echo(f"  • {f['name']} (ID: {f['question_id']})")
                    click.echo(f"    - {error_str}")

            # Show skipped
            if report['skipped_questions']:
                print_warning(f"\n{len(report['skipped_questions'])} question(s) skipped:")
                for s in report['skipped_questions'][:10]:  # Show first 10
                    click.echo(f"  • {s['name']} (ID: {s['question_id']}): {s['reason']}")
                if len(report['skipped_questions']) > 10:
                    click.echo(f"  ... and {len(report['skipped_questions']) - 10} more")

            # Save mapping if requested
            if save_mapping and report['question_migrations']:
                csv_content = migrator.get_migration_mapping_csv(report)
                with open(save_mapping, 'w') as f:
                    f.write(csv_content)
                print_success(f"\nMapping saved to: {save_mapping}")

            if dry_run:
                print_success("\nDry run completed. No questions or dashboard were created.")
            elif stats['questions_migrated'] > 0:
                print_success(f"\n✓ Dashboard migration completed!")
                if not dry_run and report['target_dashboard_id']:
                    click.echo(f"View dashboard: {metabase_url}/dashboard/{report['target_dashboard_id']}")

    except Exception as e:
        print_error(f"Dashboard migration failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def list_dashboards():
    """List all dashboards."""
    try:
        cfg = Config()
        metabase_url = cfg.get_metabase_url()
        credentials = cfg.get_credentials()

        with MetabaseAPIClient(metabase_url, credentials) as client:
            dashboards = client.list_dashboards()

            if not dashboards:
                print_warning("No dashboards found.")
                return

            print_success(f"Found {len(dashboards)} dashboard(s):\n")

            # Prepare table data
            table_data = []
            for dashboard in dashboards:
                table_data.append([
                    dashboard['id'],
                    dashboard['name'],
                    dashboard.get('description', '')[:50]  # Truncate long descriptions
                ])

            headers = ['ID', 'Name', 'Description']
            click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))

    except Exception as e:
        print_error(f"Failed to list dashboards: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
