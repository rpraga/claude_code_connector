"""Nested question handler for managing questions based on other questions."""

from typing import Dict, List, Optional, Tuple, Set
from .api_client import MetabaseAPIClient
from .query_analyzer import QueryAnalyzer


class NestedQuestionHandler:
    """Handles migration of nested questions (questions based on other questions)."""

    def __init__(self, api_client: MetabaseAPIClient):
        """Initialize nested question handler.

        Args:
            api_client: Metabase API client instance
        """
        self.api_client = api_client
        self.migration_cache = {}  # Cache of migrated question IDs: {source_id: target_id}
        self.processing_stack = []  # Track questions being processed to detect circular refs

    def analyze_dependencies(self, question_id: int, visited: Optional[Set[int]] = None) -> Dict:
        """Analyze the dependency tree of a question.

        Args:
            question_id: Question ID to analyze
            visited: Set of already visited question IDs (for circular reference detection)

        Returns:
            Dictionary with dependency information:
            {
                'question_id': int,
                'name': str,
                'is_nested': bool,
                'depends_on': int or None,
                'dependency_chain': List[int],
                'max_depth': int,
                'circular_reference': bool
            }
        """
        if visited is None:
            visited = set()

        if question_id in visited:
            return {
                'question_id': question_id,
                'circular_reference': True,
                'dependency_chain': list(visited) + [question_id]
            }

        visited.add(question_id)

        # Fetch the question
        question = self.api_client.get_question(question_id)
        query = question.get('dataset_query', {})

        analysis = {
            'question_id': question_id,
            'name': question.get('name', 'Untitled'),
            'is_nested': QueryAnalyzer.is_nested_query(query),
            'depends_on': None,
            'dependency_chain': [],
            'max_depth': 0,
            'circular_reference': False
        }

        if analysis['is_nested']:
            # Extract the source card ID
            source_card_id = QueryAnalyzer.extract_source_card_id(query)
            analysis['depends_on'] = source_card_id

            # Recursively analyze the dependency
            if source_card_id:
                dependency_analysis = self.analyze_dependencies(source_card_id, visited.copy())

                if dependency_analysis.get('circular_reference'):
                    analysis['circular_reference'] = True
                    analysis['dependency_chain'] = dependency_analysis['dependency_chain']
                else:
                    analysis['dependency_chain'] = [source_card_id] + dependency_analysis.get('dependency_chain', [])
                    analysis['max_depth'] = dependency_analysis.get('max_depth', 0) + 1

        return analysis

    def get_migration_order(self, question_id: int) -> Tuple[List[int], str]:
        """Determine the order in which questions should be migrated.

        Args:
            question_id: Root question ID to migrate

        Returns:
            Tuple of (ordered_list_of_question_ids, error_message)
            The list is ordered from deepest dependency to the root question
        """
        analysis = self.analyze_dependencies(question_id)

        if analysis.get('circular_reference'):
            chain = analysis.get('dependency_chain', [])
            return [], f"Circular reference detected: {' -> '.join(map(str, chain))}"

        # Build migration order (dependencies first)
        migration_order = []

        if analysis['is_nested']:
            # Add all dependencies in order
            for dep_id in reversed(analysis['dependency_chain']):
                if dep_id not in migration_order:
                    migration_order.append(dep_id)

        # Add the root question last
        if question_id not in migration_order:
            migration_order.append(question_id)

        return migration_order, ""

    def find_or_migrate_dependency(self, source_card_id: int, target_database_id: int,
                                   migrate_callback, collection_id: Optional[int] = None) -> Tuple[Optional[int], str]:
        """Find existing migrated version of a dependency or migrate it.

        Args:
            source_card_id: Source question ID
            target_database_id: Target database ID
            migrate_callback: Function to call to migrate a question
                             Signature: migrate_callback(question_id, target_db_id, collection_id) -> created_question
            collection_id: Optional collection ID for migrated questions

        Returns:
            Tuple of (migrated_card_id, error_message)
        """
        # Check cache first
        if source_card_id in self.migration_cache:
            return self.migration_cache[source_card_id], ""

        # Check if already being processed (circular reference protection)
        if source_card_id in self.processing_stack:
            return None, f"Circular reference detected: Question {source_card_id} is already being processed"

        try:
            self.processing_stack.append(source_card_id)

            # Migrate the dependency
            created_question = migrate_callback(source_card_id, target_database_id, collection_id)

            if created_question:
                migrated_id = created_question['id']
                self.migration_cache[source_card_id] = migrated_id
                return migrated_id, ""
            else:
                return None, f"Failed to migrate dependency question {source_card_id}"

        except Exception as e:
            return None, f"Error migrating dependency {source_card_id}: {str(e)}"

        finally:
            self.processing_stack.remove(source_card_id)

    def replace_source_card_reference(self, query: Dict, new_card_id: int) -> Dict:
        """Replace the source card reference in a nested query.

        Args:
            query: Query object with card reference
            new_card_id: New card ID to reference

        Returns:
            Updated query with new card reference
        """
        import copy
        updated_query = copy.deepcopy(query)

        # Update the source-table reference
        dataset_query = updated_query.get('dataset_query', updated_query)
        query_dict = dataset_query.get('query', dataset_query)

        # Replace card reference
        query_dict['source-table'] = f"card__{new_card_id}"

        return updated_query

    def get_dependency_report(self, question_id: int) -> str:
        """Generate a human-readable dependency report.

        Args:
            question_id: Question ID to analyze

        Returns:
            Formatted dependency report string
        """
        analysis = self.analyze_dependencies(question_id)

        report_lines = []
        report_lines.append(f"Dependency Analysis for Question {question_id}")
        report_lines.append(f"Name: {analysis['name']}")
        report_lines.append(f"Is Nested: {analysis['is_nested']}")

        if analysis.get('circular_reference'):
            report_lines.append("\n⚠ CIRCULAR REFERENCE DETECTED!")
            chain = analysis.get('dependency_chain', [])
            report_lines.append(f"Chain: {' -> '.join(map(str, chain))}")
            return "\n".join(report_lines)

        if analysis['is_nested']:
            report_lines.append(f"\nDependency Depth: {analysis['max_depth']}")
            report_lines.append(f"Direct Dependency: Question {analysis['depends_on']}")

            if analysis['dependency_chain']:
                report_lines.append("\nDependency Chain (from deepest to shallowest):")
                for i, dep_id in enumerate(reversed(analysis['dependency_chain'])):
                    indent = "  " * i
                    try:
                        dep_question = self.api_client.get_question(dep_id)
                        dep_name = dep_question.get('name', 'Untitled')
                        report_lines.append(f"{indent}└─ Question {dep_id}: {dep_name}")
                    except:
                        report_lines.append(f"{indent}└─ Question {dep_id}")

                report_lines.append(f"{'  ' * len(analysis['dependency_chain'])}└─ Question {question_id}: {analysis['name']}")

            # Get migration order
            migration_order, error = self.get_migration_order(question_id)
            if not error:
                report_lines.append(f"\nMigration Order: {' -> '.join(map(str, migration_order))}")
        else:
            report_lines.append("\nNo dependencies (direct table query)")

        return "\n".join(report_lines)

    def clear_cache(self):
        """Clear the migration cache."""
        self.migration_cache.clear()
        self.processing_stack.clear()

    def set_migration_mapping(self, source_id: int, target_id: int):
        """Manually set a migration mapping (useful when dependency already migrated).

        Args:
            source_id: Source question ID
            target_id: Target question ID in target database
        """
        self.migration_cache[source_id] = target_id
