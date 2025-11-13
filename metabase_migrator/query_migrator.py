"""Query migrator to transform queries from source to target database."""

import copy
from typing import Dict, List, Tuple, Any
from .database_mapper import DatabaseMapper
from .query_analyzer import QueryAnalyzer


class QueryMigrator:
    """Migrates Metabase queries from one database to another."""

    def __init__(self, database_mapper: DatabaseMapper):
        """Initialize query migrator.

        Args:
            database_mapper: DatabaseMapper instance for table/field mapping
        """
        self.mapper = database_mapper
        self.errors = []
        self.warnings = []

    def migrate_query(self, source_query: Dict, target_database_id: int) -> Tuple[Dict, List[str], List[str]]:
        """Migrate a query from source database to target database.

        Args:
            source_query: Original query from source database
            target_database_id: Target database ID

        Returns:
            Tuple of (migrated_query, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Deep copy to avoid modifying original
        migrated = copy.deepcopy(source_query)

        # Validate it's a Query Builder query
        is_valid, error = QueryAnalyzer.validate_query_builder_format(source_query)
        if not is_valid:
            self.errors.append(error)
            return migrated, self.errors, self.warnings

        # Extract source table
        try:
            source_table_id = QueryAnalyzer.extract_source_table(source_query)
        except Exception as e:
            self.errors.append(f"Failed to extract source table: {e}")
            return migrated, self.errors, self.warnings

        # Find target table
        target_table_id, result = self.mapper.find_target_table(source_table_id, target_database_id)
        if target_table_id is None:
            self.errors.append(result)
            return migrated, self.errors, self.warnings

        # Update database ID
        migrated['database'] = target_database_id
        if 'dataset_query' in migrated:
            migrated['dataset_query']['database'] = target_database_id

        # Update source table in query
        query_dict = migrated.get('dataset_query', {}).get('query', migrated.get('query', {}))
        query_dict['source-table'] = target_table_id

        # Migrate all field references
        self._migrate_query_components(query_dict, source_table_id, target_table_id)

        return migrated, self.errors, self.warnings

    def _migrate_query_components(self, query_dict: Dict, source_table_id: int, target_table_id: int):
        """Migrate all components of a query (fields, filters, aggregations, etc.).

        Args:
            query_dict: The query dictionary to modify
            source_table_id: Source table ID
            target_table_id: Target table ID
        """
        # Migrate fields
        if 'fields' in query_dict:
            query_dict['fields'] = self._migrate_field_list(
                query_dict['fields'], source_table_id, target_table_id
            )

        # Migrate filters
        if 'filter' in query_dict:
            query_dict['filter'] = self._migrate_clause(
                query_dict['filter'], source_table_id, target_table_id
            )

        # Migrate aggregations
        if 'aggregation' in query_dict:
            query_dict['aggregation'] = self._migrate_aggregations(
                query_dict['aggregation'], source_table_id, target_table_id
            )

        # Migrate breakouts
        if 'breakout' in query_dict:
            query_dict['breakout'] = self._migrate_field_list(
                query_dict['breakout'], source_table_id, target_table_id
            )

        # Migrate order-by
        if 'order-by' in query_dict:
            query_dict['order-by'] = self._migrate_order_by(
                query_dict['order-by'], source_table_id, target_table_id
            )

        # Migrate joins
        if 'joins' in query_dict:
            query_dict['joins'] = self._migrate_joins(
                query_dict['joins'], source_table_id, target_table_id
            )

    def _migrate_field_list(self, fields: List, source_table_id: int, target_table_id: int) -> List:
        """Migrate a list of field references.

        Args:
            fields: List of field references
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Migrated field list
        """
        migrated_fields = []

        for field_ref in fields:
            migrated_ref, error = self._migrate_field_reference(
                field_ref, source_table_id, target_table_id
            )
            if error:
                self.errors.append(f"Field migration error: {error}")
            else:
                migrated_fields.append(migrated_ref)

        return migrated_fields

    def _migrate_field_reference(self, field_ref: Any, source_table_id: int,
                                 target_table_id: int) -> Tuple[Any, str]:
        """Migrate a single field reference.

        Args:
            field_ref: Field reference (can be list, string, or other format)
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Tuple of (migrated_reference, error_message)
        """
        if not isinstance(field_ref, list):
            return field_ref, ""

        if len(field_ref) < 2:
            return field_ref, ""

        # Handle ["field", <id>, {...}] format
        if field_ref[0] == "field" and isinstance(field_ref[1], int):
            return self.mapper.map_field_reference(field_ref, source_table_id, target_table_id)

        # Handle other field reference types (like aggregation references)
        # These might contain nested field references
        migrated = copy.deepcopy(field_ref)
        for i, item in enumerate(field_ref):
            if isinstance(item, list):
                migrated[i], error = self._migrate_field_reference(
                    item, source_table_id, target_table_id
                )
                if error:
                    return migrated, error

        return migrated, ""

    def _migrate_clause(self, clause: Any, source_table_id: int, target_table_id: int) -> Any:
        """Migrate a clause (like filter) that may contain field references.

        Args:
            clause: The clause to migrate
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Migrated clause
        """
        if not isinstance(clause, list):
            return clause

        migrated = []
        for item in clause:
            if isinstance(item, list):
                # Check if it's a field reference
                if len(item) >= 2 and item[0] == "field" and isinstance(item[1], int):
                    migrated_item, error = self._migrate_field_reference(
                        item, source_table_id, target_table_id
                    )
                    if error:
                        self.errors.append(f"Filter migration error: {error}")
                        migrated.append(item)  # Keep original on error
                    else:
                        migrated.append(migrated_item)
                else:
                    # Recursively process nested clauses
                    migrated.append(self._migrate_clause(item, source_table_id, target_table_id))
            else:
                migrated.append(item)

        return migrated

    def _migrate_aggregations(self, aggregations: List, source_table_id: int,
                             target_table_id: int) -> List:
        """Migrate aggregation clauses.

        Args:
            aggregations: List of aggregation definitions
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Migrated aggregations
        """
        migrated = []

        for agg in aggregations:
            if isinstance(agg, list):
                migrated_agg = []
                for item in agg:
                    if isinstance(item, list):
                        migrated_item, error = self._migrate_field_reference(
                            item, source_table_id, target_table_id
                        )
                        if error:
                            self.errors.append(f"Aggregation migration error: {error}")
                            migrated_agg.append(item)
                        else:
                            migrated_agg.append(migrated_item)
                    else:
                        migrated_agg.append(item)
                migrated.append(migrated_agg)
            else:
                migrated.append(agg)

        return migrated

    def _migrate_order_by(self, order_by: List, source_table_id: int,
                         target_table_id: int) -> List:
        """Migrate order-by clauses.

        Args:
            order_by: List of order-by definitions
            source_table_id: Source table ID
            target_table_id: Target table ID

        Returns:
            Migrated order-by clauses
        """
        migrated = []

        for order_clause in order_by:
            if isinstance(order_clause, list) and len(order_clause) >= 2:
                # Format: [["field", <id>, {...}], "asc"|"desc"]
                field_ref = order_clause[0]
                direction = order_clause[1] if len(order_clause) > 1 else "asc"

                migrated_ref, error = self._migrate_field_reference(
                    field_ref, source_table_id, target_table_id
                )
                if error:
                    self.errors.append(f"Order-by migration error: {error}")
                    migrated.append(order_clause)
                else:
                    migrated.append([migrated_ref, direction])
            else:
                migrated.append(order_clause)

        return migrated

    def _migrate_joins(self, joins: List, source_table_id: int, target_table_id: int) -> List:
        """Migrate join clauses.

        Args:
            joins: List of join definitions
            source_table_id: Source table ID (of main query)
            target_table_id: Target table ID (of main query)

        Returns:
            Migrated joins
        """
        migrated_joins = []

        for join in joins:
            migrated_join = copy.deepcopy(join)

            # Migrate source table of the join
            if 'source-table' in join:
                join_source_table = join['source-table']
                if isinstance(join_source_table, int):
                    # Find target table for this joined table
                    join_target_table_id, result = self.mapper.find_target_table(
                        join_source_table, target_table_id  # Using target_table_id's database
                    )
                    if join_target_table_id:
                        migrated_join['source-table'] = join_target_table_id
                    else:
                        self.warnings.append(f"Could not map joined table: {result}")

            # Migrate join conditions
            if 'condition' in join:
                migrated_join['condition'] = self._migrate_clause(
                    join['condition'], source_table_id, target_table_id
                )

            # Migrate fields in join
            if 'fields' in join:
                # For joined fields, we need to use the join's source table
                join_source = migrated_join.get('source-table', source_table_id)
                migrated_join['fields'] = self._migrate_field_list(
                    join['fields'], join_source, migrated_join.get('source-table', join_source)
                )

            migrated_joins.append(migrated_join)

        return migrated_joins

    def get_migration_summary(self) -> Dict:
        """Get a summary of the migration process.

        Returns:
            Dictionary with migration statistics and messages
        """
        return {
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'errors': self.errors,
            'warnings': self.warnings,
            'success': len(self.errors) == 0
        }
