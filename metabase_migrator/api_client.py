"""Metabase API client for interacting with Metabase instances."""

import requests
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs


class MetabaseAPIClient:
    """Client for Metabase API operations."""

    def __init__(self, base_url: str, credentials: Dict[str, str]):
        """Initialize Metabase API client.

        Args:
            base_url: Base URL of Metabase instance
            credentials: Dict containing either 'api_key' or 'username' and 'password'
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session_token = None

        # Authenticate
        if 'api_key' in credentials:
            self.session.headers['X-API-KEY'] = credentials['api_key']
        else:
            self._login(credentials['username'], credentials['password'])

    def _login(self, username: str, password: str):
        """Authenticate with username and password."""
        response = self.session.post(
            f"{self.base_url}/api/session",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        self.session_token = response.json()['id']
        self.session.headers['X-Metabase-Session'] = self.session_token

    def extract_question_id(self, url_or_id: str) -> int:
        """Extract question ID from URL or return the ID directly.

        Args:
            url_or_id: Either a Metabase question URL or question ID

        Returns:
            Question ID as integer

        Examples:
            - "123" -> 123
            - "https://metabase.com/question/456" -> 456
            - "https://metabase.com/question/456-my-question" -> 456
        """
        # If it's already a number, return it
        if isinstance(url_or_id, int):
            return url_or_id

        if str(url_or_id).isdigit():
            return int(url_or_id)

        # Extract from URL
        patterns = [
            r'/question/(\d+)',  # /question/123 or /question/123-slug
            r'[?&]question[_-]?id=(\d+)',  # ?question_id=123
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return int(match.group(1))

        raise ValueError(
            f"Could not extract question ID from: {url_or_id}\n"
            "Expected a question ID (e.g., '123') or URL (e.g., 'https://metabase.com/question/123')"
        )

    def get_question(self, question_id: int) -> Dict:
        """Fetch a question/card by ID.

        Args:
            question_id: The ID of the question to fetch

        Returns:
            Question data including query definition
        """
        response = self.session.get(f"{self.base_url}/api/card/{question_id}")
        response.raise_for_status()
        return response.json()

    def get_database(self, database_id: int) -> Dict:
        """Fetch database metadata.

        Args:
            database_id: The ID of the database

        Returns:
            Database metadata
        """
        response = self.session.get(f"{self.base_url}/api/database/{database_id}")
        response.raise_for_status()
        return response.json()

    def get_database_metadata(self, database_id: int) -> Dict:
        """Fetch detailed database metadata including tables and fields.

        Args:
            database_id: The ID of the database

        Returns:
            Complete database metadata with tables and fields
        """
        response = self.session.get(f"{self.base_url}/api/database/{database_id}/metadata")
        response.raise_for_status()
        return response.json()

    def list_databases(self) -> List[Dict]:
        """List all available databases.

        Returns:
            List of database objects
        """
        response = self.session.get(f"{self.base_url}/api/database")
        response.raise_for_status()
        return response.json().get('data', [])

    def get_table(self, table_id: int) -> Dict:
        """Fetch table metadata.

        Args:
            table_id: The ID of the table

        Returns:
            Table metadata including fields
        """
        response = self.session.get(f"{self.base_url}/api/table/{table_id}")
        response.raise_for_status()
        return response.json()

    def get_table_metadata(self, table_id: int) -> Dict:
        """Fetch detailed table metadata with field information.

        Args:
            table_id: The ID of the table

        Returns:
            Detailed table metadata
        """
        response = self.session.get(f"{self.base_url}/api/table/{table_id}/query_metadata")
        response.raise_for_status()
        return response.json()

    def create_question(self, question_data: Dict) -> Dict:
        """Create a new question/card.

        Args:
            question_data: Question definition including name, query, visualization settings

        Returns:
            Created question data with ID
        """
        response = self.session.post(
            f"{self.base_url}/api/card",
            json=question_data
        )
        response.raise_for_status()
        return response.json()

    def update_question(self, question_id: int, question_data: Dict) -> Dict:
        """Update an existing question.

        Args:
            question_id: ID of question to update
            question_data: Updated question data

        Returns:
            Updated question data
        """
        response = self.session.put(
            f"{self.base_url}/api/card/{question_id}",
            json=question_data
        )
        response.raise_for_status()
        return response.json()

    def search_tables(self, database_id: int, table_name: str) -> List[Dict]:
        """Search for tables by name in a database.

        Args:
            database_id: Database to search in
            table_name: Name of table to search for

        Returns:
            List of matching tables
        """
        metadata = self.get_database_metadata(database_id)
        tables = metadata.get('tables', [])

        matching = []
        for table in tables:
            if table['name'].lower() == table_name.lower():
                matching.append(table)

        return matching

    def find_field_by_name(self, table_id: int, field_name: str) -> Optional[Dict]:
        """Find a field by name within a table.

        Args:
            table_id: Table to search in
            field_name: Name of field to find

        Returns:
            Field metadata or None if not found
        """
        table_metadata = self.get_table_metadata(table_id)
        fields = table_metadata.get('fields', [])

        for field in fields:
            if field['name'].lower() == field_name.lower():
                return field

        return None

    def get_collection(self, collection_id: int) -> Dict:
        """Fetch a collection by ID.

        Args:
            collection_id: The ID of the collection

        Returns:
            Collection data
        """
        response = self.session.get(f"{self.base_url}/api/collection/{collection_id}")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the session and cleanup."""
        if self.session_token:
            try:
                self.session.delete(f"{self.base_url}/api/session")
            except:
                pass
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
