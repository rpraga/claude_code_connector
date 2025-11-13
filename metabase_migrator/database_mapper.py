"""Database mapper to map tables and fields between databases."""

from typing import Dict, List, Optional, Tuple
from .api_client import MetabaseAPIClient


class DatabaseMapper:
    """Maps tables and fields from source database to target database."""

    def __init__(self, api_client: MetabaseAPIClient, custom_mappings: Optional[Dict] = None):
        """Initialize database mapper.

        Args:
            api_client: Metabase API client instance
            custom_mappings: Optional custom mapping rules from config
        """
        self.api_client = api_client
        self.custom_mappings = custom_mappings or {}
        self.table_cache = {}
        self.field_cache = {}

    def get_table_by_id(self, table_id: int) -> Dict:
        """Get table metadata, using cache.

        Args:
            table_id: Table ID to fetch

        Returns:
            Table metadata
        """
        if table_id not in self.table_cache:
            self.table_cache[table_id] = self.api_client.get_table(table_id)
        return self.table_cache[table_id]

    def get_table_fields(self, table_id: int) -> List[Dict]:
        """Get fields for a table, using cache.

        Args:
            table_id: Table ID

        Returns:
            List of field metadata
        """
        if table_id not in self.field_cache:
            table_metadata = self.api_client.get_table_metadata(table_id)
            self.field_cache[table_id] = table_metadata.get('fields', [])
        return self.field_cache[table_id]

    def find_target_table(self, source_table_id: int, target_database_id: int) -> Tuple[Optional[int], str]:
        """Find the corresponding table in the target database.

        Args:
            source_table_id: Source table ID
            target_database_id: Target database ID

        Returns:
            Tuple of (target_table_id, table_name) or (None, error_message)
        """
        # Get source table info
        source_table = self.get_table_by_id(source_table_id)
        source_table_name = source_table['name']
        source_schema = source_table.get('schema', '')

        # Check for custom mapping
        custom_key = f"{source_table_name}"
        if source_schema:
            custom_key = f"{source_schema}.{source_table_name}"

        table_mappings = self.custom_mappings.get('table_mappings', {})
        if custom_key in table_mappings:
            target_table_name = table_mappings[custom_key]
            # Extract schema if provided
            if '.' in target_table_name:
                target_schema, target_table_name = target_table_name.split('.', 1)
            else:
                target_schema = source_schema
        else:
            target_table_name = source_table_name
            target_schema = source_schema

        # Search for table in target database
        target_metadata = self.api_client.get_database_metadata(target_database_id)
        target_tables = target_metadata.get('tables', [])

        # Try exact match first
        for table in target_tables:
            if table['name'] == target_table_name:
                # Check schema if present
                if target_schema:
                    if table.get('schema', '') == target_schema:
                        return table['id'], table['name']
                else:
                    return table['id'], table['name']

        # Try case-insensitive match
        for table in target_tables:
            if table['name'].lower() == target_table_name.lower():
                if target_schema:
                    if table.get('schema', '').lower() == target_schema.lower():
                        return table['id'], table['name']
                else:
                    return table['id'], table['name']

        return None, f"Table '{target_table_name}' not found in target database"

    def find_target_field(self, source_field_id: int, source_table_id: int,
                         target_table_id: int) -> Tuple[Optional[int], str]:
        """Find the corresponding field in the target table.

        Args:
            source_field_id: Source field ID
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Tuple of (target_field_id, field_name) or (None, error_message)
        """
        # Get source field info
        source_fields = self.get_table_fields(source_table_id)
        source_field = None

        for field in source_fields:
            if field['id'] == source_field_id:
                source_field = field
                break

        if not source_field:
            return None, f"Source field ID {source_field_id} not found"

        source_field_name = source_field['name']
        source_table = self.get_table_by_id(source_table_id)

        # Check for custom mapping
        custom_key = f"{source_table['name']}.{source_field_name}"
        field_mappings = self.custom_mappings.get('field_mappings', {})

        if custom_key in field_mappings:
            target_field_name = field_mappings[custom_key]
        else:
            target_field_name = source_field_name

        # Search for field in target table
        target_fields = self.get_table_fields(target_table_id)

        # Try exact match
        for field in target_fields:
            if field['name'] == target_field_name:
                return field['id'], field['name']

        # Try case-insensitive match
        for field in target_fields:
            if field['name'].lower() == target_field_name.lower():
                return field['id'], field['name']

        return None, f"Field '{target_field_name}' not found in target table"

    def map_field_reference(self, field_ref: List, source_table_id: int,
                           target_table_id: int) -> Tuple[Optional[List], str]:
        """Map a field reference from source to target database.

        Args:
            field_ref: Field reference like ["field", 123, {...}]
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Tuple of (mapped_field_ref, error_message)
        """
        if not isinstance(field_ref, list) or len(field_ref) < 2:
            return field_ref, ""

        if field_ref[0] != "field":
            return field_ref, ""

        source_field_id = field_ref[1]
        if not isinstance(source_field_id, int):
            return field_ref, ""

        target_field_id, error = self.find_target_field(
            source_field_id, source_table_id, target_table_id
        )

        if target_field_id is None:
            return None, error

        # Reconstruct field reference with new ID
        new_field_ref = [field_ref[0], target_field_id]
        if len(field_ref) > 2:
            new_field_ref.extend(field_ref[2:])

        return new_field_ref, ""

    def validate_database_compatibility(self, source_db_id: int, target_db_id: int) -> Tuple[bool, str]:
        """Check if source and target databases are compatible for migration.

        Args:
            source_db_id: Source database ID
            target_db_id: Target database ID

        Returns:
            Tuple of (is_compatible, message)
        """
        source_db = self.api_client.get_database(source_db_id)
        target_db = self.api_client.get_database(target_db_id)

        source_engine = source_db.get('engine', 'unknown')
        target_engine = target_db.get('engine', 'unknown')

        # Warn if engines are different (but don't block)
        if source_engine != target_engine:
            return True, (
                f"Warning: Database engines differ (source: {source_engine}, target: {target_engine}). "
                f"Migration may require adjustments."
            )

        return True, "Databases appear compatible"

    def get_mapping_report(self, source_table_id: int, target_database_id: int,
                          field_ids: List[int]) -> Dict:
        """Generate a report of how tables and fields will be mapped.

        Args:
            source_table_id: Source table ID
            target_database_id: Target database ID
            field_ids: List of field IDs to map

        Returns:
            Dictionary with mapping details
        """
        report = {
            'source_table': self.get_table_by_id(source_table_id),
            'mappings': [],
            'errors': [],
            'warnings': []
        }

        # Map table
        target_table_id, result = self.find_target_table(source_table_id, target_database_id)
        if target_table_id:
            report['target_table'] = self.get_table_by_id(target_table_id)
        else:
            report['errors'].append(f"Table mapping failed: {result}")
            return report

        # Map fields
        for field_id in field_ids:
            target_field_id, result = self.find_target_field(
                field_id, source_table_id, target_table_id
            )

            source_field = None
            for f in self.get_table_fields(source_table_id):
                if f['id'] == field_id:
                    source_field = f
                    break

            if target_field_id:
                target_field = None
                for f in self.get_table_fields(target_table_id):
                    if f['id'] == target_field_id:
                        target_field = f
                        break

                report['mappings'].append({
                    'source_field': source_field['name'] if source_field else f"ID:{field_id}",
                    'target_field': target_field['name'] if target_field else f"ID:{target_field_id}",
                    'source_type': source_field.get('base_type') if source_field else None,
                    'target_type': target_field.get('base_type') if target_field else None,
                })

                # Check type compatibility
                if source_field and target_field:
                    if source_field.get('base_type') != target_field.get('base_type'):
                        report['warnings'].append(
                            f"Type mismatch for field '{source_field['name']}': "
                            f"{source_field.get('base_type')} -> {target_field.get('base_type')}"
                        )
            else:
                report['errors'].append(
                    f"Field mapping failed for '{source_field['name'] if source_field else field_id}': {result}"
                )

        return report
