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
            'tabs': dashboard.get('tabs', []),  # Store tab information
            'total_cards': 0,
            'questions': [],
            'migratable': [],
            'non_migratable': [],
            'statistics': {},
            'cards_info': []  # Will store layout info for each card
        }

        # Get dashcards - handle different Metabase versions
        # Newer versions with tabs might have cards in different locations
        dashcards = dashboard.get('ordered_cards', [])
        if not dashcards:
            # Try alternative locations (dashcards, tabs, etc.)
            dashcards = dashboard.get('dashcards', [])
        if not dashcards:
            # Some APIs return tabs with cards inside
            tabs = dashboard.get('tabs', [])
            if tabs:
                # Collect cards from all tabs
                for tab in tabs:
                    dashcards.extend(tab.get('cards', []))

        report['total_cards'] = len(dashcards)

        # Analyze each card on the dashboard
        for dashcard in dashcards:
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
                    'sizeX': dashcard.get('size_x') or dashcard.get('sizeX'),  # Handle both formats
                    'sizeY': dashcard.get('size_y') or dashcard.get('sizeY')
                },
                'parameter_mappings': dashcard.get('parameter_mappings', []),
                'visualization_settings': dashcard.get('visualization_settings', {}),
                'dashboard_tab_id': dashcard.get('dashboard_tab_id')  # Track which tab it's on
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
            'has_parameters': len(report['parameters']) > 0,
            'has_tabs': len(report['tabs']) > 0,
            'tab_count': len(report['tabs'])
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
            # Prepare tabs for dashboard creation
            tabs = None
            tab_mapping = {}  # Maps source tab ID to new tab ID
            parameter_mapping = {}  # Maps source parameter ID to new parameter ID

            print(f"\n=== Dashboard Creation Debug ===")
            print(f"Analysis has tabs: {bool(analysis.get('tabs'))}")
            if analysis.get('tabs'):
                print(f"Source tabs in analysis: {len(analysis['tabs'])}")
                for tab in analysis['tabs']:
                    print(f"  - {tab.get('name')} (ID: {tab.get('id')})")

                tabs = []
                for idx, source_tab in enumerate(analysis['tabs']):
                    tabs.append({
                        'name': source_tab.get('name', 'Tab'),
                        'position': idx
                    })
                print(f"Tabs to create: {tabs}")

            # Create dashboard with parameters and tabs only
            print(f"\nCalling create_dashboard with tabs={tabs}")
            dashboard = self.api_client.create_dashboard(
                name=target_dashboard_name,
                description=analysis.get('description', ''),
                collection_id=collection_id,
                parameters=analysis.get('parameters', []),
                tabs=tabs
            )
            report['target_dashboard_id'] = dashboard['id']

            print(f"Dashboard created with ID: {dashboard['id']}")
            print(f"Dashboard response has 'tabs' key: {'tabs' in dashboard}")
            if 'tabs' in dashboard:
                print(f"Dashboard response tabs: {dashboard.get('tabs')}")

            # Build tab mapping from created dashboard
            if tabs and dashboard.get('tabs'):
                created_tabs = dashboard['tabs']
                source_tabs = analysis['tabs']
                for idx, source_tab in enumerate(source_tabs):
                    if idx < len(created_tabs):
                        tab_mapping[source_tab['id']] = created_tabs[idx]['id']

                print(f"\n=== Tab Mapping Debug ===")
                print(f"Source tabs: {len(source_tabs)}")
                print(f"Created tabs: {len(created_tabs)}")
                for source_id, target_id in tab_mapping.items():
                    source_name = next((t['name'] for t in source_tabs if t['id'] == source_id), 'Unknown')
                    target_name = next((t['name'] for t in created_tabs if t['id'] == target_id), 'Unknown')
                    print(f"  {source_name} (ID:{source_id}) -> {target_name} (ID:{target_id})")

            # Build parameter mapping from created dashboard
            # Match parameters by slug or name since IDs will be different
            if analysis.get('parameters') and dashboard.get('parameters'):
                source_params = analysis['parameters']
                target_params = dashboard['parameters']

                print(f"\n=== Parameter Mapping Debug ===")
                print(f"Source parameters: {len(source_params)}")
                print(f"Target parameters: {len(target_params)}")

                for source_param in source_params:
                    source_id = source_param.get('id')
                    source_slug = source_param.get('slug')
                    source_name = source_param.get('name')

                    # Find matching parameter in target by slug or name
                    matched = False
                    for target_param in target_params:
                        if (target_param.get('slug') == source_slug or
                            target_param.get('name') == source_name):
                            parameter_mapping[source_id] = target_param['id']
                            print(f"  {source_name} ({source_id}) -> {target_param['name']} ({target_param['id']})")
                            matched = True
                            break

                    if not matched:
                        print(f"  WARNING: No match for parameter {source_name} ({source_id}, slug:{source_slug})")

            # Add cards to dashboard using PUT /api/dashboard/:id/cards (v0.47+)
            print(f"\n=== Adding {len(analysis['cards_info'])} cards to dashboard ===")
            cards_added_count = 0

            for card_info in analysis['cards_info']:
                source_question_id = card_info['id']

                # Only add if question was migrated successfully
                if source_question_id in question_mapping:
                    target_question_id = question_mapping[source_question_id]

                    try:
                        # Update parameter mappings with new card ID and parameter IDs
                        parameter_mappings = self._update_parameter_mappings(
                            card_info.get('parameter_mappings', []),
                            source_question_id,
                            target_question_id,
                            parameter_mapping
                        )

                        # Determine tab assignment
                        source_tab_id = card_info.get('dashboard_tab_id')
                        target_tab_id = tab_mapping.get(source_tab_id) if source_tab_id else None

                        # Debug output for first few cards
                        if cards_added_count < 5:
                            print(f"  Card {cards_added_count+1}: Q{source_question_id}, source_tab={source_tab_id}, target_tab={target_tab_id}, params={len(parameter_mappings)}/{len(card_info.get('parameter_mappings', []))}")

                        # Add card to dashboard
                        dashcard = self.api_client.add_card_to_dashboard(
                            dashboard_id=dashboard['id'],
                            card_id=target_question_id,
                            row=card_info['layout']['row'],
                            col=card_info['layout']['col'],
                            size_x=card_info['layout']['sizeX'],
                            size_y=card_info['layout']['sizeY'],
                            parameter_mappings=parameter_mappings,
                            visualization_settings=card_info.get('visualization_settings'),
                            dashboard_tab_id=target_tab_id
                        )

                        cards_added_count += 1

                        report['cards_added'].append({
                            'source_question_id': source_question_id,
                            'target_question_id': target_question_id,
                            'dashcard_id': dashcard.get('id'),
                            'position': card_info['layout'],
                            'tab_id': target_tab_id
                        })

                    except Exception as e:
                        report['failed_questions'].append({
                            'question_id': source_question_id,
                            'name': card_info['name'],
                            'error': f"Failed to add to dashboard: {e}"
                        })

            print(f"Successfully added {cards_added_count} cards to dashboard")

        # Verify dashboard was populated (if not dry run)
        if not dry_run and report.get('target_dashboard_id'):
            try:
                # Get the dashboard to verify cards were actually added
                dashboard = self.api_client.get_dashboard(report['target_dashboard_id'])
                actual_cards = dashboard.get('ordered_cards', dashboard.get('dashcards', []))
                actual_count = len(actual_cards) if actual_cards else 0

                if actual_count != len(report['cards_added']):
                    print(f"\n⚠ Warning: Expected {len(report['cards_added'])} cards but dashboard has {actual_count} cards")
                    print(f"  Dashboard may not have been populated correctly")
            except Exception as e:
                print(f"\n⚠ Warning: Could not verify dashboard cards: {e}")

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
                                   old_card_id: int, new_card_id: int,
                                   parameter_id_mapping: Dict[str, str] = None) -> List[Dict]:
        """Update parameter mappings to use new card ID and parameter IDs.

        Args:
            mappings: Original parameter mappings
            old_card_id: Old question card ID
            new_card_id: New question card ID
            parameter_id_mapping: Mapping from source parameter IDs to target parameter IDs

        Returns:
            Updated parameter mappings
        """
        if not mappings:
            return []

        parameter_id_mapping = parameter_id_mapping or {}

        # Parameter mappings reference the card_id and parameter_id
        # We need to update both to match the new dashboard
        updated_mappings = []
        for mapping in mappings:
            updated_mapping = mapping.copy()

            # Update card_id if present
            if 'card_id' in updated_mapping:
                updated_mapping['card_id'] = new_card_id

            # Update parameter_id to reference the new dashboard's parameter
            if 'parameter_id' in updated_mapping:
                old_param_id = updated_mapping['parameter_id']
                if old_param_id in parameter_id_mapping:
                    updated_mapping['parameter_id'] = parameter_id_mapping[old_param_id]
                else:
                    # If we can't map the parameter, skip this mapping to avoid "unknown filter" error
                    continue

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
