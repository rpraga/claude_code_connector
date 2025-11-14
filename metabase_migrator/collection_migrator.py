"""Collection-based migration for migrating all questions from one collection to another."""

from typing import Dict, List, Tuple, Optional
from .api_client import MetabaseAPIClient
from .database_mapper import DatabaseMapper
from .query_migrator import QueryMigrator
from .widget_creator import WidgetCreator
from .nested_handler import NestedQuestionHandler
from .query_analyzer import QueryAnalyzer


class CollectionMigrator:
    """Migrates all questions from a source collection to a target collection."""

    def __init__(self, api_client: MetabaseAPIClient):
        """Initialize collection migrator.

        Args:
            api_client: Metabase API client instance
        """
        self.api_client = api_client

    def analyze_collection(self, collection_id: int, source_database_id: Optional[int] = None) -> Dict:
        """Analyze a collection and identify questions to migrate.

        Args:
            collection_id: Collection ID to analyze
            source_database_id: Filter questions by source database (None = all)

        Returns:
            Analysis report with questions and statistics
        """
        collection = self.api_client.get_collection(collection_id)
        items = self.api_client.get_collection_items(collection_id)

        report = {
            'collection_name': collection.get('name'),
            'collection_id': collection_id,
            'total_items': len(items),
            'questions': [],
            'other_items': [],
            'migratable': [],
            'non_migratable': [],
            'statistics': {}
        }

        # Filter questions
        for item in items:
            if item.get('model') == 'card':  # card = question
                question_id = item.get('id')
                try:
                    # Get full question details
                    question = self.api_client.get_question(question_id)
                    item_info = {
                        'id': question_id,
                        'name': question.get('name'),
                        'database_id': question.get('database_id'),
                        'query': question.get('dataset_query', {})
                    }

                    report['questions'].append(item_info)

                    # Check if it should be migrated
                    if source_database_id is None or question.get('database_id') == source_database_id:
                        # Check if it's Query Builder
                        is_valid, error = QueryAnalyzer.validate_query_builder_format(item_info['query'])

                        if is_valid:
                            # Check if nested
                            is_nested = QueryAnalyzer.is_nested_query(item_info['query'])
                            item_info['is_nested'] = is_nested
                            report['migratable'].append(item_info)
                        else:
                            item_info['error'] = error
                            report['non_migratable'].append(item_info)
                    else:
                        item_info['skip_reason'] = f"Different database (ID: {question.get('database_id')})"
                        report['non_migratable'].append(item_info)

                except Exception as e:
                    report['non_migratable'].append({
                        'id': question_id,
                        'name': item.get('name', 'Unknown'),
                        'error': str(e)
                    })
            else:
                report['other_items'].append(item)

        # Statistics
        report['statistics'] = {
            'total_questions': len(report['questions']),
            'migratable': len(report['migratable']),
            'non_migratable': len(report['non_migratable']),
            'other_items': len(report['other_items']),
            'nested_questions': sum(1 for q in report['migratable'] if q.get('is_nested'))
        }

        return report

    def migrate_collection(self, source_collection_id: int, target_database_id: int,
                          target_collection_name: Optional[str] = None,
                          source_database_id: Optional[int] = None,
                          allow_nested: bool = False,
                          name_suffix: str = " (Migrated)",
                          dry_run: bool = False) -> Dict:
        """Migrate all questions from a source collection to a new target collection.

        Args:
            source_collection_id: Source collection ID
            target_database_id: Target database ID for migrated questions
            target_collection_name: Name for target collection (default: source_name + "_migrated")
            source_database_id: Only migrate questions from this database (None = all)
            allow_nested: Allow migration of nested questions
            name_suffix: Suffix to add to question names
            dry_run: If True, don't create anything

        Returns:
            Migration report with results
        """
        # Analyze source collection
        analysis = self.analyze_collection(source_collection_id, source_database_id)

        # Determine target collection name
        if target_collection_name is None:
            target_collection_name = analysis['collection_name'] + "_migrated"

        report = {
            'source_collection': analysis['collection_name'],
            'source_collection_id': source_collection_id,
            'target_collection_name': target_collection_name,
            'target_database_id': target_database_id,
            'analysis': analysis,
            'target_collection_id': None,
            'migrations': [],
            'failed': [],
            'skipped': [],
            'statistics': {}
        }

        # Filter questions that need --allow-nested
        if not allow_nested:
            nested_questions = [q for q in analysis['migratable'] if q.get('is_nested')]
            if nested_questions:
                for q in nested_questions:
                    report['skipped'].append({
                        'question_id': q['id'],
                        'name': q['name'],
                        'reason': 'Nested question (use --allow-nested flag)'
                    })
                # Remove from migratable list
                analysis['migratable'] = [q for q in analysis['migratable'] if not q.get('is_nested')]

        if not analysis['migratable']:
            report['statistics'] = {
                'total': 0,
                'migrated': 0,
                'failed': 0,
                'skipped': len(report['skipped'])
            }
            return report

        # Create target collection (if not dry run)
        if not dry_run:
            # Check if collection already exists
            existing = self.api_client.search_collections(target_collection_name)
            if existing:
                target_collection = existing[0]
                report['target_collection_id'] = target_collection['id']
                report['target_collection_existed'] = True
            else:
                target_collection = self.api_client.create_collection(
                    name=target_collection_name,
                    description=f"Migrated from '{analysis['collection_name']}' to database {target_database_id}"
                )
                report['target_collection_id'] = target_collection['id']
                report['target_collection_existed'] = False

        # Setup migration components
        mapper = DatabaseMapper(self.api_client)
        nested_handler = NestedQuestionHandler(self.api_client) if allow_nested else None
        migrator = QueryMigrator(mapper, nested_handler)
        creator = WidgetCreator(self.api_client)

        # Migrate each question
        for question_info in analysis['migratable']:
            question_id = question_info['id']

            try:
                # Get full question
                question = self.api_client.get_question(question_id)
                query = question.get('dataset_query', {})

                # Handle nested questions
                migrated_card_id = None
                if question_info.get('is_nested') and nested_handler:
                    source_card_id = QueryAnalyzer.extract_source_card_id(query)
                    if source_card_id:
                        # Check if dependency was already migrated
                        migrated_card_id = nested_handler.migration_cache.get(source_card_id)

                        # If not in cache, it might not be in this collection
                        # For now, skip (user should use regular migrate with --allow-nested)
                        if not migrated_card_id:
                            report['skipped'].append({
                                'question_id': question_id,
                                'name': question['name'],
                                'reason': f'Dependency (question {source_card_id}) not yet migrated'
                            })
                            continue

                # Migrate query
                migrated_query, errors, warnings = migrator.migrate_query(
                    query, target_database_id, migrated_card_id
                )

                if errors:
                    report['failed'].append({
                        'question_id': question_id,
                        'name': question['name'],
                        'errors': errors
                    })
                    continue

                # Create migrated question
                if not dry_run:
                    created = creator.create_widget(
                        question,
                        migrated_query,
                        collection_id=report['target_collection_id'],
                        name_suffix=name_suffix
                    )

                    # Update cache for nested questions
                    if nested_handler:
                        nested_handler.set_migration_mapping(question_id, created['id'])

                    report['migrations'].append({
                        'source_id': question_id,
                        'target_id': created['id'],
                        'source_name': question['name'],
                        'target_name': created['name'],
                        'warnings': warnings
                    })
                else:
                    report['migrations'].append({
                        'source_id': question_id,
                        'source_name': question['name'],
                        'would_migrate': True,
                        'warnings': warnings
                    })

            except Exception as e:
                report['failed'].append({
                    'question_id': question_id,
                    'name': question_info['name'],
                    'error': str(e)
                })

        # Statistics
        report['statistics'] = {
            'total': len(analysis['migratable']),
            'migrated': len(report['migrations']),
            'failed': len(report['failed']),
            'skipped': len(report['skipped'])
        }

        return report

    def get_migration_mapping_csv(self, report: Dict) -> str:
        """Generate CSV mapping file from migration report.

        Args:
            report: Migration report from migrate_collection

        Returns:
            CSV content as string
        """
        lines = ["source_id,target_id,source_name,target_name"]

        for migration in report.get('migrations', []):
            if 'target_id' in migration:
                lines.append(
                    f"{migration['source_id']},{migration['target_id']},"
                    f"\"{migration['source_name']}\",\"{migration['target_name']}\""
                )

        return "\n".join(lines)
