"""Question verification to ensure migrated questions produce correct results."""

import random
from typing import Dict, List, Tuple, Optional, Set, Any
from .api_client import MetabaseAPIClient


class QuestionVerifier:
    """Verifies that migrated questions produce the same results as source questions."""

    def __init__(self, api_client: MetabaseAPIClient):
        """Initialize question verifier.

        Args:
            api_client: Metabase API client instance
        """
        self.api_client = api_client

    def execute_question(self, question_id: int, limit: Optional[int] = None) -> Dict:
        """Execute a question and get results.

        Args:
            question_id: Question ID to execute
            limit: Optional limit on number of rows to fetch

        Returns:
            Query results with metadata
        """
        # Execute the question using the query endpoint
        url = f"{self.api_client.base_url}/api/card/{question_id}/query"

        params = {}
        if limit:
            params['limit'] = limit

        response = self.api_client.session.post(url, json=params)
        response.raise_for_status()

        return response.json()

    def compare_results(self, source_results: Dict, target_results: Dict,
                       sample_size: Optional[int] = None) -> Dict:
        """Compare results from source and target questions.

        Args:
            source_results: Results from source question
            target_results: Results from target question
            sample_size: If provided, compare random sample of rows

        Returns:
            Comparison report with differences and statistics
        """
        report = {
            'match': True,
            'differences': [],
            'statistics': {},
            'sample_checked': sample_size is not None
        }

        # Extract data
        source_data = source_results.get('data', {})
        target_data = target_results.get('data', {})

        source_rows = source_data.get('rows', [])
        target_rows = target_data.get('rows', [])

        source_cols = source_data.get('cols', [])
        target_cols = target_data.get('cols', [])

        # Compare row counts
        report['statistics']['source_row_count'] = len(source_rows)
        report['statistics']['target_row_count'] = len(target_rows)

        if len(source_rows) != len(target_rows):
            report['match'] = False
            report['differences'].append({
                'type': 'row_count_mismatch',
                'source': len(source_rows),
                'target': len(target_rows),
                'difference': abs(len(source_rows) - len(target_rows))
            })

        # Compare column counts
        report['statistics']['source_column_count'] = len(source_cols)
        report['statistics']['target_column_count'] = len(target_cols)

        if len(source_cols) != len(target_cols):
            report['match'] = False
            report['differences'].append({
                'type': 'column_count_mismatch',
                'source': len(source_cols),
                'target': len(target_cols)
            })
            # Can't compare data if column counts differ
            return report

        # Compare column names/types
        column_diffs = []
        for i, (src_col, tgt_col) in enumerate(zip(source_cols, target_cols)):
            if src_col.get('name') != tgt_col.get('name'):
                column_diffs.append({
                    'column_index': i,
                    'source_name': src_col.get('name'),
                    'target_name': tgt_col.get('name')
                })

        if column_diffs:
            report['match'] = False
            report['differences'].append({
                'type': 'column_name_mismatch',
                'details': column_diffs
            })

        # Compare data rows
        if sample_size and len(source_rows) > sample_size:
            # Random sampling
            indices = random.sample(range(len(source_rows)), min(sample_size, len(source_rows)))
            rows_to_check = [(i, source_rows[i], target_rows[i] if i < len(target_rows) else None)
                            for i in indices]
            report['statistics']['rows_checked'] = len(rows_to_check)
        else:
            # Check all rows
            rows_to_check = [(i, src_row, tgt_row)
                            for i, (src_row, tgt_row) in enumerate(zip(source_rows, target_rows))]
            report['statistics']['rows_checked'] = len(rows_to_check)

        row_diffs = []
        for row_idx, src_row, tgt_row in rows_to_check:
            if tgt_row is None:
                row_diffs.append({
                    'row_index': row_idx,
                    'issue': 'missing_in_target'
                })
                continue

            for col_idx, (src_val, tgt_val) in enumerate(zip(src_row, tgt_row)):
                if not self._values_equal(src_val, tgt_val):
                    row_diffs.append({
                        'row_index': row_idx,
                        'column_index': col_idx,
                        'column_name': source_cols[col_idx].get('name') if col_idx < len(source_cols) else f'Column {col_idx}',
                        'source_value': src_val,
                        'target_value': tgt_val
                    })

        if row_diffs:
            report['match'] = False
            report['differences'].append({
                'type': 'data_value_mismatch',
                'count': len(row_diffs),
                'details': row_diffs[:10]  # Show first 10 differences
            })
            report['statistics']['mismatched_values'] = len(row_diffs)

        return report

    def _values_equal(self, val1: Any, val2: Any, tolerance: float = 1e-9) -> bool:
        """Check if two values are equal, with tolerance for floats.

        Args:
            val1: First value
            val2: Second value
            tolerance: Tolerance for floating point comparison

        Returns:
            True if values are considered equal
        """
        # Both None
        if val1 is None and val2 is None:
            return True

        # One None, one not
        if val1 is None or val2 is None:
            return False

        # Both numbers (with tolerance for floats)
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) < tolerance

        # String comparison (case-sensitive by default)
        return val1 == val2

    def verify_migration(self, source_question_id: int, target_question_id: int,
                        sample_size: Optional[int] = 100, limit: Optional[int] = None) -> Dict:
        """Verify that a migrated question produces the same results.

        Args:
            source_question_id: Source question ID
            target_question_id: Target question ID (migrated)
            sample_size: Number of rows to sample for comparison (None = all rows)
            limit: Maximum rows to fetch from each question

        Returns:
            Verification report
        """
        report = {
            'source_question_id': source_question_id,
            'target_question_id': target_question_id,
            'verified': False,
            'timestamp': None,
            'execution_times': {},
            'comparison': None,
            'errors': []
        }

        try:
            # Get question metadata
            source_question = self.api_client.get_question(source_question_id)
            target_question = self.api_client.get_question(target_question_id)

            report['source_question_name'] = source_question.get('name')
            report['target_question_name'] = target_question.get('name')

            # Execute source question
            import time
            start = time.time()
            source_results = self.execute_question(source_question_id, limit)
            report['execution_times']['source'] = time.time() - start

            # Execute target question
            start = time.time()
            target_results = self.execute_question(target_question_id, limit)
            report['execution_times']['target'] = time.time() - start

            # Compare results
            comparison = self.compare_results(source_results, target_results, sample_size)
            report['comparison'] = comparison
            report['verified'] = comparison['match']

            import datetime
            report['timestamp'] = datetime.datetime.now().isoformat()

        except Exception as e:
            report['errors'].append({
                'type': 'execution_error',
                'message': str(e)
            })
            report['verified'] = False

        return report

    def batch_verify(self, question_pairs: List[Tuple[int, int]],
                    sample_size: Optional[int] = 100) -> List[Dict]:
        """Verify multiple migrated questions.

        Args:
            question_pairs: List of (source_id, target_id) tuples
            sample_size: Number of rows to sample for comparison

        Returns:
            List of verification reports
        """
        reports = []

        for source_id, target_id in question_pairs:
            report = self.verify_migration(source_id, target_id, sample_size)
            reports.append(report)

        return reports

    def get_summary_report(self, reports: List[Dict]) -> Dict:
        """Generate summary statistics from multiple verification reports.

        Args:
            reports: List of verification reports

        Returns:
            Summary statistics
        """
        summary = {
            'total_verified': len(reports),
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'pass_rate': 0.0,
            'failed_questions': []
        }

        for report in reports:
            if report.get('errors'):
                summary['errors'] += 1
            elif report.get('verified'):
                summary['passed'] += 1
            else:
                summary['failed'] += 1
                summary['failed_questions'].append({
                    'source_id': report.get('source_question_id'),
                    'target_id': report.get('target_question_id'),
                    'source_name': report.get('source_question_name'),
                    'target_name': report.get('target_question_name'),
                    'differences': report.get('comparison', {}).get('differences', [])
                })

        if summary['total_verified'] > 0:
            summary['pass_rate'] = summary['passed'] / summary['total_verified'] * 100

        return summary

    def verify_with_auto_detect(self, source_question_id: int,
                                target_collection_id: Optional[int] = None,
                                name_suffix: str = " (Migrated)") -> Optional[Dict]:
        """Automatically find and verify a migrated question.

        Attempts to find the migrated question by matching name with suffix.

        Args:
            source_question_id: Source question ID
            target_collection_id: Collection to search in
            name_suffix: Expected suffix on migrated question name

        Returns:
            Verification report or None if target not found
        """
        # Get source question
        source_question = self.api_client.get_question(source_question_id)
        expected_name = source_question['name'] + name_suffix

        # Search for target question
        # Note: This would require a search API endpoint
        # For now, this is a placeholder for future enhancement
        raise NotImplementedError(
            "Auto-detection of migrated questions not yet implemented. "
            "Please provide both source and target question IDs."
        )
