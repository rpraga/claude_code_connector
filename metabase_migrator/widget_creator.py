"""Widget/Question creator for target database."""

import copy
from typing import Dict, Optional, List
from .api_client import MetabaseAPIClient
from .query_migrator import QueryMigrator


class WidgetCreator:
    """Creates widgets/questions in the target database."""

    def __init__(self, api_client: MetabaseAPIClient):
        """Initialize widget creator.

        Args:
            api_client: Metabase API client instance
        """
        self.api_client = api_client

    def create_widget(self, source_question: Dict, migrated_query: Dict,
                     collection_id: Optional[int] = None,
                     name_suffix: str = " (Migrated)") -> Dict:
        """Create a new widget/question in the target database.

        Args:
            source_question: Original question from source
            migrated_query: Migrated query for target database
            collection_id: Optional collection ID to place the question in
            name_suffix: Suffix to add to the question name (default: " (Migrated)")

        Returns:
            Created question data with ID
        """
        # Prepare question data
        question_data = self._prepare_question_data(
            source_question, migrated_query, collection_id, name_suffix
        )

        # Create the question
        created = self.api_client.create_question(question_data)

        return created

    def _prepare_question_data(self, source_question: Dict, migrated_query: Dict,
                               collection_id: Optional[int], name_suffix: str) -> Dict:
        """Prepare question data for creation.

        Args:
            source_question: Original question
            migrated_query: Migrated query
            collection_id: Target collection ID
            name_suffix: Suffix for question name

        Returns:
            Question data ready for creation
        """
        # Start with basic fields
        question_data = {
            'name': source_question.get('name', 'Untitled') + name_suffix,
            'dataset_query': migrated_query.get('dataset_query', migrated_query),
            'display': source_question.get('display', 'table'),
            'visualization_settings': source_question.get('visualization_settings', {}),
        }

        # Add description if present
        if source_question.get('description'):
            question_data['description'] = source_question['description']

        # Set collection
        if collection_id is not None:
            question_data['collection_id'] = collection_id
        elif 'collection_id' in source_question and source_question['collection_id']:
            # Try to keep in same collection (might fail if doesn't exist)
            question_data['collection_id'] = source_question['collection_id']

        # Copy result metadata if present (field information for results)
        if 'result_metadata' in source_question:
            # Note: This might need adjustment if field IDs changed
            question_data['result_metadata'] = source_question['result_metadata']

        # Copy parameters if present
        if source_question.get('parameters'):
            question_data['parameters'] = source_question['parameters']

        if source_question.get('parameter_mappings'):
            question_data['parameter_mappings'] = source_question['parameter_mappings']

        return question_data

    def preview_widget_creation(self, source_question: Dict, migrated_query: Dict,
                               collection_id: Optional[int] = None,
                               name_suffix: str = " (Migrated)") -> Dict:
        """Preview what the created widget would look like without actually creating it.

        Args:
            source_question: Original question
            migrated_query: Migrated query
            collection_id: Target collection ID
            name_suffix: Suffix for question name

        Returns:
            Dictionary with preview information
        """
        question_data = self._prepare_question_data(
            source_question, migrated_query, collection_id, name_suffix
        )

        preview = {
            'name': question_data['name'],
            'description': question_data.get('description', ''),
            'display': question_data['display'],
            'collection_id': question_data.get('collection_id'),
            'target_database': migrated_query.get('database'),
            'has_visualization_settings': bool(question_data.get('visualization_settings')),
            'has_parameters': bool(question_data.get('parameters')),
            'query_type': migrated_query.get('dataset_query', {}).get('type', 'unknown'),
        }

        return preview

    def copy_widget_settings(self, source_question: Dict, target_question_id: int,
                            include_visualization: bool = True,
                            include_parameters: bool = True) -> Dict:
        """Copy additional settings from source to an existing target question.

        Args:
            source_question: Source question with settings to copy
            target_question_id: ID of target question to update
            include_visualization: Whether to copy visualization settings
            include_parameters: Whether to copy parameter settings

        Returns:
            Updated question data
        """
        # Get current target question
        target_question = self.api_client.get_question(target_question_id)

        # Prepare updates
        updates = {}

        if include_visualization and source_question.get('visualization_settings'):
            updates['visualization_settings'] = source_question['visualization_settings']

        if include_parameters:
            if source_question.get('parameters'):
                updates['parameters'] = source_question['parameters']
            if source_question.get('parameter_mappings'):
                updates['parameter_mappings'] = source_question['parameter_mappings']

        # Apply updates
        if updates:
            updated = self.api_client.update_question(target_question_id, updates)
            return updated

        return target_question

    def validate_widget_name(self, name: str, collection_id: Optional[int] = None) -> bool:
        """Check if a widget name is available (doesn't conflict).

        Note: This is a best-effort check. Metabase doesn't prevent duplicate names.

        Args:
            name: Proposed name for the widget
            collection_id: Collection to check in

        Returns:
            Always True (Metabase allows duplicate names)
        """
        # Metabase allows duplicate names, so we always return True
        # This method is here for potential future use or custom validation
        return True

    def get_recommended_name(self, source_name: str, target_database_name: str) -> str:
        """Generate a recommended name for the migrated widget.

        Args:
            source_name: Original question name
            target_database_name: Name of target database

        Returns:
            Recommended name
        """
        return f"{source_name} (on {target_database_name})"

    def batch_create_widgets(self, migrations: List[Dict]) -> List[Dict]:
        """Create multiple widgets in batch.

        Args:
            migrations: List of dicts with 'source_question', 'migrated_query', 'collection_id', 'name_suffix'

        Returns:
            List of created questions with their results
        """
        results = []

        for migration in migrations:
            try:
                created = self.create_widget(
                    source_question=migration['source_question'],
                    migrated_query=migration['migrated_query'],
                    collection_id=migration.get('collection_id'),
                    name_suffix=migration.get('name_suffix', ' (Migrated)')
                )
                results.append({
                    'success': True,
                    'question': created,
                    'source_name': migration['source_question'].get('name')
                })
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e),
                    'source_name': migration['source_question'].get('name')
                })

        return results
