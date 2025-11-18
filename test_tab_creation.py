#!/usr/bin/env python3
"""Debug script to test tab creation."""

import json
from metabase_migrator.config import Config
from metabase_migrator.api_client import MetabaseAPIClient

def main():
    config = Config('config.yaml')
    metabase_url = config.get_metabase_url()
    credentials = config.get_credentials()

    with MetabaseAPIClient(metabase_url, credentials) as client:
        source_dashboard_id = int(input("Enter source dashboard ID: "))

        # Get source dashboard
        print("\n=== Source Dashboard ===")
        source_dashboard = client.get_dashboard(source_dashboard_id)
        source_tabs = source_dashboard.get('tabs', [])
        print(f"Source has {len(source_tabs)} tabs:")
        for tab in source_tabs:
            print(f"  - {tab.get('name')} (ID: {tab.get('id')}, pos: {tab.get('position')})")

        # Prepare tabs for creation
        tabs_to_create = []
        for idx, source_tab in enumerate(source_tabs):
            tabs_to_create.append({
                'name': source_tab.get('name', 'Tab'),
                'position': idx
            })

        print(f"\n=== Creating Test Dashboard ===")
        print(f"Tabs to create: {json.dumps(tabs_to_create, indent=2)}")

        # Create dashboard with tabs
        new_dashboard = client.create_dashboard(
            name="Test Dashboard with Tabs",
            description="Testing tab creation",
            tabs=tabs_to_create if tabs_to_create else None
        )

        print(f"\n=== Created Dashboard (ID: {new_dashboard['id']}) ===")
        print(f"Dashboard keys: {list(new_dashboard.keys())}")

        created_tabs = new_dashboard.get('tabs', [])
        print(f"Created dashboard has {len(created_tabs)} tabs:")
        for tab in created_tabs:
            print(f"  - {tab.get('name')} (ID: {tab.get('id')}, pos: {tab.get('position')})")

        # Fetch dashboard again to verify
        print(f"\n=== Fetching Dashboard Again ===")
        fetched_dashboard = client.get_dashboard(new_dashboard['id'])
        fetched_tabs = fetched_dashboard.get('tabs', [])
        print(f"Fetched dashboard has {len(fetched_tabs)} tabs:")
        for tab in fetched_tabs:
            print(f"  - {tab.get('name')} (ID: {tab.get('id')}, pos: {tab.get('position')})")

        print(f"\n✓ Test complete. Created dashboard ID: {new_dashboard['id']}")
        print(f"You can delete it manually if needed.")

if __name__ == '__main__':
    main()
