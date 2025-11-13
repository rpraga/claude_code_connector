"""Query analyzer to validate and understand Metabase queries."""

from typing import Dict, List, Set, Tuple


class QueryAnalyzer:
    """Analyzes Metabase queries to validate format and extract information."""

    @staticmethod
    def is_query_builder_query(query: Dict) -> bool:
        """Check if a query is in Query Builder format (not native SQL).

        Args:
            query: The query object from a Metabase question

        Returns:
            True if it's a Query Builder query, False if it's native SQL

        Raises:
            ValueError: If query format is invalid or unrecognized
        """
        if not isinstance(query, dict):
            raise ValueError("Query must be a dictionary")

        # Check query type
        query_type = query.get('type')

        if query_type == 'native':
            return False
        elif query_type == 'query':
            return True
        elif query_type is None:
            # Legacy format - check for 'native' key
            if 'native' in query:
                return False
            elif 'query' in query or 'source-table' in query:
                return True

        raise ValueError(f"Unrecognized query format. Type: {query_type}")

    @staticmethod
    def validate_query_builder_format(query: Dict) -> Tuple[bool, str]:
        """Validate that a query is in Query Builder format.

        Args:
            query: The query object from a Metabase question

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not QueryAnalyzer.is_query_builder_query(query):
                return False, "Query is in native SQL format, not Query Builder"

            # Additional validation
            dataset_query = query.get('dataset_query', query)
            query_dict = dataset_query.get('query', {})

            if not query_dict and 'source-table' not in dataset_query:
                return False, "Query Builder query must have a source table"

            return True, ""

        except Exception as e:
            return False, str(e)

    @staticmethod
    def extract_source_table(query: Dict) -> int:
        """Extract the source table ID from a query.

        Args:
            query: The query object

        Returns:
            Source table ID

        Raises:
            ValueError: If source table cannot be determined
        """
        # Handle both formats: direct query and wrapped in dataset_query
        dataset_query = query.get('dataset_query', query)
        query_dict = dataset_query.get('query', dataset_query)

        source_table = query_dict.get('source-table')

        if source_table is None:
            raise ValueError("Could not find source-table in query")

        # Handle string IDs (convert to int)
        if isinstance(source_table, str):
            # Some source tables might be card references like "card__123"
            if source_table.startswith('card__'):
                raise ValueError(
                    "Query uses another question as source (nested query). "
                    "This migrator currently only supports direct table queries."
                )
            source_table = int(source_table)

        return source_table

    @staticmethod
    def extract_referenced_fields(query: Dict) -> Set[int]:
        """Extract all field IDs referenced in the query.

        Args:
            query: The query object

        Returns:
            Set of field IDs used in the query
        """
        field_ids = set()
        dataset_query = query.get('dataset_query', query)
        query_dict = dataset_query.get('query', dataset_query)

        def extract_from_clause(clause):
            """Recursively extract field IDs from a clause."""
            if isinstance(clause, list):
                for item in clause:
                    if isinstance(item, list) and len(item) > 0:
                        # Field reference like ["field", 123, {...}]
                        if item[0] == "field" and len(item) > 1:
                            if isinstance(item[1], int):
                                field_ids.add(item[1])
                    extract_from_clause(item)
            elif isinstance(clause, dict):
                for value in clause.values():
                    extract_from_clause(value)

        # Extract from different query components
        for key in ['fields', 'breakout', 'filter', 'aggregation', 'order-by']:
            if key in query_dict:
                extract_from_clause(query_dict[key])

        return field_ids

    @staticmethod
    def get_query_summary(question: Dict) -> Dict:
        """Get a summary of a question's query structure.

        Args:
            question: Complete question object from Metabase

        Returns:
            Dictionary with query summary information
        """
        query = question.get('dataset_query', {})
        is_qb = QueryAnalyzer.is_query_builder_query(query)

        summary = {
            'name': question.get('name', 'Untitled'),
            'id': question.get('id'),
            'type': 'Query Builder' if is_qb else 'Native SQL',
            'database_id': query.get('database'),
        }

        if is_qb:
            try:
                summary['source_table_id'] = QueryAnalyzer.extract_source_table(query)
                summary['referenced_fields'] = list(QueryAnalyzer.extract_referenced_fields(query))
                summary['field_count'] = len(summary['referenced_fields'])

                query_dict = query.get('query', {})
                summary['has_filters'] = 'filter' in query_dict
                summary['has_aggregations'] = 'aggregation' in query_dict
                summary['has_breakouts'] = 'breakout' in query_dict
                summary['has_order_by'] = 'order-by' in query_dict
                summary['has_limit'] = 'limit' in query_dict
            except Exception as e:
                summary['error'] = str(e)

        return summary

    @staticmethod
    def extract_query_components(query: Dict) -> Dict:
        """Extract all components of a Query Builder query.

        Args:
            query: The query object

        Returns:
            Dictionary with all query components organized
        """
        dataset_query = query.get('dataset_query', query)
        query_dict = dataset_query.get('query', dataset_query)

        components = {
            'source_table': query_dict.get('source-table'),
            'fields': query_dict.get('fields', []),
            'filter': query_dict.get('filter'),
            'aggregation': query_dict.get('aggregation', []),
            'breakout': query_dict.get('breakout', []),
            'order_by': query_dict.get('order-by', []),
            'limit': query_dict.get('limit'),
            'joins': query_dict.get('joins', []),
        }

        return components
