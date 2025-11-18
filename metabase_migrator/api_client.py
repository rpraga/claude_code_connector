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

    def list_collections(self) -> List[Dict]:
        """List all available collections.

        Returns:
            List of collection objects
        """
        response = self.session.get(f"{self.base_url}/api/collection")
        response.raise_for_status()
        return response.json()

    def get_collection_items(self, collection_id: int) -> List[Dict]:
        """Get all items (questions, dashboards) in a collection.

        Args:
            collection_id: The ID of the collection

        Returns:
            List of items in the collection
        """
        response = self.session.get(f"{self.base_url}/api/collection/{collection_id}/items")
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])

    def create_collection(self, name: str, description: str = "", parent_id: Optional[int] = None,
                         color: str = "#509EE3") -> Dict:
        """Create a new collection.

        Args:
            name: Collection name
            description: Collection description
            parent_id: Parent collection ID (None for root level)
            color: Collection color hex code

        Returns:
            Created collection data with ID
        """
        collection_data = {
            'name': name,
            'description': description,
            'color': color
        }

        if parent_id is not None:
            collection_data['parent_id'] = parent_id

        response = self.session.post(
            f"{self.base_url}/api/collection",
            json=collection_data
        )
        response.raise_for_status()
        return response.json()

    def search_collections(self, name: str) -> List[Dict]:
        """Search for collections by name.

        Args:
            name: Collection name to search for

        Returns:
            List of matching collections
        """
        collections = self.list_collections()

        matching = []
        for collection in collections:
            if collection['name'].lower() == name.lower():
                matching.append(collection)

        return matching

    # Dashboard methods
    def get_dashboard(self, dashboard_id: int) -> Dict:
        """Get dashboard details including all cards.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            Dashboard data with cards, parameters, etc.
        """
        response = self.session.get(f"{self.base_url}/api/dashboard/{dashboard_id}")
        response.raise_for_status()
        return response.json()

    def list_dashboards(self) -> List[Dict]:
        """List all dashboards.

        Returns:
            List of dashboard summaries
        """
        response = self.session.get(f"{self.base_url}/api/dashboard")
        response.raise_for_status()
        return response.json()

    def create_dashboard(self, name: str, description: str = "",
                        collection_id: Optional[int] = None,
                        parameters: Optional[List[Dict]] = None) -> Dict:
        """Create a new dashboard.

        Args:
            name: Dashboard name
            description: Dashboard description
            collection_id: Collection to place dashboard in
            parameters: Dashboard parameters/filters

        Returns:
            Created dashboard data
        """
        dashboard_data = {
            'name': name,
            'description': description
        }

        if collection_id is not None:
            dashboard_data['collection_id'] = collection_id

        if parameters:
            dashboard_data['parameters'] = parameters

        response = self.session.post(
            f"{self.base_url}/api/dashboard",
            json=dashboard_data
        )
        response.raise_for_status()
        return response.json()

    def add_card_to_dashboard(self, dashboard_id: int, card_id: int,
                             row: int = 0, col: int = 0,
                             size_x: int = 4, size_y: int = 4,
                             parameter_mappings: Optional[List[Dict]] = None,
                             visualization_settings: Optional[Dict] = None,
                             dashboard_tab_id: Optional[int] = None) -> Dict:
        """Add a question card to a dashboard.

        Args:
            dashboard_id: Dashboard ID
            card_id: Question/card ID to add
            row: Row position
            col: Column position
            size_x: Width in grid units
            size_y: Height in grid units
            parameter_mappings: Parameter mappings for dashboard filters
            visualization_settings: Visualization settings for this card
            dashboard_tab_id: Optional tab ID to assign card to

        Returns:
            Created dashcard data
        """
        dashcard_data = {
            'card_id': card_id,
            'row': row,
            'col': col,
            'size_x': size_x,
            'size_y': size_y
        }

        if parameter_mappings:
            dashcard_data['parameter_mappings'] = parameter_mappings

        if visualization_settings:
            dashcard_data['visualization_settings'] = visualization_settings

        if dashboard_tab_id is not None:
            dashcard_data['dashboard_tab_id'] = dashboard_tab_id

        # Try the standard endpoint first
        try:
            response = self.session.post(
                f"{self.base_url}/api/dashboard/{dashboard_id}/cards",
                json=dashcard_data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try alternative endpoint (used in some Metabase versions)
                response = self.session.post(
                    f"{self.base_url}/api/dashboard/{dashboard_id}/dashcard",
                    json=dashcard_data
                )
                response.raise_for_status()
                return response.json()
            else:
                raise

    def update_dashboard(self, dashboard_id: int, updates: Dict) -> Dict:
        """Update dashboard properties.

        Args:
            dashboard_id: Dashboard ID
            updates: Dictionary of fields to update

        Returns:
            Updated dashboard data
        """
        response = self.session.put(
            f"{self.base_url}/api/dashboard/{dashboard_id}",
            json=updates
        )
        response.raise_for_status()
        return response.json()

    def create_dashboard_tab(self, dashboard_id: int, name: str, position: int = 0) -> Dict:
        """Create a new tab on a dashboard.

        Args:
            dashboard_id: Dashboard ID
            name: Tab name
            position: Tab position/order

        Returns:
            Created tab data with ID
        """
        # Get current dashboard to preserve existing data
        dashboard = self.get_dashboard(dashboard_id)

        # Build new tab object
        new_tab = {
            'name': name,
            'position': position
        }

        # Get existing tabs or initialize empty list
        tabs = dashboard.get('tabs', [])
        tabs.append(new_tab)

        # Update dashboard with new tabs
        response = self.session.put(
            f"{self.base_url}/api/dashboard/{dashboard_id}",
            json={'tabs': tabs}
        )
        response.raise_for_status()
        result = response.json()

        # Return the newly created tab
        created_tabs = result.get('tabs', [])
        if created_tabs:
            return created_tabs[-1]  # Return last tab
        return new_tab

    def update_dashcard_tab(self, dashcard_id: int, tab_id: int) -> Dict:
        """Assign a dashcard to a specific tab.

        Args:
            dashcard_id: Dashcard ID
            tab_id: Dashboard tab ID

        Returns:
            Updated dashcard data
        """
        response = self.session.put(
            f"{self.base_url}/api/dashcard/{dashcard_id}",
            json={'dashboard_tab_id': tab_id}
        )
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
