"""Dashboard migration for migrating entire dashboards with all their questions."""

from typing import Dict, List, Tuple, Optional
from .api_client import MetabaseAPIClient
from .database_mapper import DatabaseMapper
from .query_migrator import QueryMigrator
from .widget_creator import WidgetCreator
from .nested_handler import NestedQuestionHandler
from .query_analyzer import QueryAnalyzer


class DashboardMigrator:
    """Migrates dashboards and all their questions to a new database."""

    def __init__(self, api_client: MetabaseAPIClient, custom_mappings: Optional[Dict] = None):
        """Initialize dashboard migrator.

        Args:
            api_client: Metabase API client instance
            custom_mappings: Optional custom mapping rules from config
        """
        self.api_client = api_client
        self.custom_mappings = custom_mappings or {}

    def analyze_dashboard(self, dashboard_id: int, source_database_id: Optional[int] = None) -> Dict:
        """Analyze a dashboard and identify questions to migrate.

        Args:
            dashboard_id: Dashboard ID to analyze
            source_database_id: Filter questions by source database (None = all)

        Returns:
            Analysis report with questions and statistics
        """
        dashboard = self.api_client.get_dashboard(dashboard_id)

        report = {
            'dashboard_name': dashboard.get('name'),
            'dashboard_id': dashboard_id,
            'description': dashboard.get('description', ''),
            'parameters': dashboard.get('parameters', []),
            'total_cards': len(dashboard.get('ordered_cards', [])),
            'questions': [],
            'migratable': [],
            'non_migratable': [],
            'statistics': {},
            'cards_info': []  # Will store layout info for each card
        }

        # Analyze each card on the dashboard
        for dashcard in dashboard.get('ordered_cards', []):
            card = dashcard.get('card')
            if not card:
                continue

            card_id = card.get('id')
            card_info = {
                'id': card_id,
                'name': card.get('name'),
                'database_id': card.get('database_id'),
                'query': card.get('dataset_query', {}),
                'layout': {
                    'row': dashcard.get('row'),
                    'col': dashcard.get('col'),
                    'sizeX': dashcard.get('sizeX'),
                    'sizeY': dashcard.get('sizeY')
                },
                'parameter_mappings': dashcard.get('parameter_mappings', []),
                'visualization_settings': dashcard.get('visualization_settings', {})
            }

            report['cards_info'].append(card_info)
            report['questions'].append(card_info)

            # Check if it should be migrated
            if source_database_id is None or card.get('database_id') == source_database_id:
                # Check if it's Query Builder
                is_valid, error = QueryAnalyzer.validate_query_builder_format(card_info['query'])

                if is_valid:
                    # Check if nested
                    is_nested = QueryAnalyzer.is_nested_query(card_info['query'])
                    card_info['is_nested'] = is_nested
                    report['migratable'].append(card_info)
                else:
                    card_info['error'] = error
                    report['non_migratable'].append(card_info)
            else:
                card_info['skip_reason'] = f"Different database (ID: {card.get('database_id')})"
                report['non_migratable'].append(card_info)

        # Statistics
        report['statistics'] = {
            'total_questions': len(report['questions']),
            'migratable': len(report['migratable']),
            'non_migratable': len(report['non_migratable']),
            'nested_questions': sum(1 for q in report['migratable'] if q.get('is_nested')),
            'has_parameters': len(report['parameters']) > 0
        }

        return report

    def migrate_dashboard(self, source_dashboard_id: int, target_database_id: int,
                         target_dashboard_name: Optional[str] = None,
                         source_database_id: Optional[int] = None,
                         collection_id: Optional[int] = None,
                         allow_nested: bool = False,
                         name_suffix: str = " (Migrated)",
                         dry_run: bool = False) -> Dict:
        """Migrate an entire dashboard to a new database.

        Args:
            source_dashboard_id: Source dashboard ID
            target_database_id: Target database ID for migrated questions
            target_dashboard_name: Name for target dashboard (default: source_name + "_migrated")
            source_database_id: Only migrate questions from this database (None = all)
            collection_id: Collection to place new dashboard in
            allow_nested: Allow migration of nested questions
            name_suffix: Suffix to add to question names
            dry_run: If True, don't create anything

        Returns:
            Migration report with results
        """
        # Analyze source dashboard
        analysis = self.analyze_dashboard(source_dashboard_id, source_database_id)

        # Determine target dashboard name
        if target_dashboard_name is None:
            target_dashboard_name = analysis['dashboard_name'] + "_migrated"

        report = {
            'source_dashboard': analysis['dashboard_name'],
            'source_dashboard_id': source_dashboard_id,
            'target_dashboard_name': target_dashboard_name,
            'target_database_id': target_database_id,
            'analysis': analysis,
            'target_dashboard_id': None,
            'question_migrations': [],
            'failed_questions': [],
            'skipped_questions': [],
            'cards_added': [],
            'statistics': {}
        }

        # Filter questions that need --allow-nested
        if not allow_nested:
            nested_questions = [q for q in analysis['migratable'] if q.get('is_nested')]
            if nested_questions:
                for q in nested_questions:
                    report['skipped_questions'].append({
                        'question_id': q['id'],
                        'name': q['name'],
                        'reason': 'Nested question (use --allow-nested flag)'
                    })
                # Remove from migratable list
                analysis['migratable'] = [q for q in analysis['migratable'] if not q.get('is_nested')]

        if not analysis['migratable']:
            report['statistics'] = {
                'total': 0,
                'questions_migrated': 0,
                'questions_failed': 0,
                'questions_skipped': len(report['skipped_questions']),
                'cards_added': 0
            }
            return report

        # Setup migration components
        mapper = DatabaseMapper(self.api_client, self.custom_mappings)
        nested_handler = NestedQuestionHandler(self.api_client) if allow_nested else None
        migrator = QueryMigrator(mapper, nested_handler)
        creator = WidgetCreator(self.api_client)

        # Track question ID mappings (source_id -> target_id)
        question_mapping = {}

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
                        migrated_card_id = nested_handler.migration_cache.get(source_card_id)
                        if not migrated_card_id:
                            report['skipped_questions'].append({
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
                    report['failed_questions'].append({
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
                        collection_id=collection_id,
                        name_suffix=name_suffix
                    )

                    # Update cache for nested questions
                    if nested_handler:
                        nested_handler.set_migration_mapping(question_id, created['id'])

                    # Store mapping
                    question_mapping[question_id] = created['id']

                    report['question_migrations'].append({
                        'source_id': question_id,
                        'target_id': created['id'],
                        'source_name': question['name'],
                        'target_name': created['name'],
                        'warnings': warnings
                    })
                else:
                    report['question_migrations'].append({
                        'source_id': question_id,
                        'source_name': question['name'],
                        'would_migrate': True,
                        'warnings': warnings
                    })

            except Exception as e:
                report['failed_questions'].append({
                    'question_id': question_id,
                    'name': question_info['name'],
                    'error': str(e)
                })

        # Create dashboard (if not dry run and we have questions)
        if not dry_run and report['question_migrations']:
            # Create dashboard with parameters from original
            dashboard = self.api_client.create_dashboard(
                name=target_dashboard_name,
                description=analysis.get('description', ''),
                collection_id=collection_id,
                parameters=analysis.get('parameters', [])
            )
            report['target_dashboard_id'] = dashboard['id']

            # Add cards to dashboard with original layout
            for card_info in analysis['cards_info']:
                source_question_id = card_info['id']

                # Only add if question was migrated successfully
                if source_question_id in question_mapping:
                    target_question_id = question_mapping[source_question_id]

                    try:
                        # Update parameter mappings with new card ID
                        parameter_mappings = self._update_parameter_mappings(
                            card_info.get('parameter_mappings', []),
                            source_question_id,
                            target_question_id
                        )

                        # Add card to dashboard
                        dashcard = self.api_client.add_card_to_dashboard(
                            dashboard_id=dashboard['id'],
                            card_id=target_question_id,
                            row=card_info['layout']['row'],
                            col=card_info['layout']['col'],
                            size_x=card_info['layout']['sizeX'],
                            size_y=card_info['layout']['sizeY'],
                            parameter_mappings=parameter_mappings,
                            visualization_settings=card_info.get('visualization_settings')
                        )

                        report['cards_added'].append({
                            'source_question_id': source_question_id,
                            'target_question_id': target_question_id,
                            'dashcard_id': dashcard.get('id'),
                            'position': card_info['layout']
                        })

                    except Exception as e:
                        report['failed_questions'].append({
                            'question_id': source_question_id,
                            'name': card_info['name'],
                            'error': f"Failed to add to dashboard: {e}"
                        })

        # Statistics
        report['statistics'] = {
            'total': len(analysis['migratable']),
            'questions_migrated': len(report['question_migrations']),
            'questions_failed': len(report['failed_questions']),
            'questions_skipped': len(report['skipped_questions']),
            'cards_added': len(report['cards_added'])
        }

        return report

    def _update_parameter_mappings(self, mappings: List[Dict],
                                   old_card_id: int, new_card_id: int) -> List[Dict]:
        """Update parameter mappings to use new card ID.

        Args:
            mappings: Original parameter mappings
            old_card_id: Old question card ID
            new_card_id: New question card ID

        Returns:
            Updated parameter mappings
        """
        if not mappings:
            return []

        # Parameter mappings reference the card_id in their target
        # We need to update card_id references
        updated_mappings = []
        for mapping in mappings:
            updated_mapping = mapping.copy()
            # The structure is typically: {parameter_id: ..., card_id: ..., target: ...}
            # card_id might not be present in all versions, but we'll update it if it is
            if 'card_id' in updated_mapping:
                updated_mapping['card_id'] = new_card_id

            updated_mappings.append(updated_mapping)

        return updated_mappings

    def get_migration_mapping_csv(self, report: Dict) -> str:
        """Generate CSV mapping file from migration report.

        Args:
            report: Migration report from migrate_dashboard

        Returns:
            CSV content as string
        """
        lines = ["source_question_id,target_question_id,source_name,target_name"]

        for migration in report.get('question_migrations', []):
            if 'target_id' in migration:
                lines.append(
                    f"{migration['source_id']},{migration['target_id']},"
                    f"\"{migration['source_name']}\",\"{migration['target_name']}\""
                )

        return "\n".join(lines)
