#!/usr/bin/env python3
"""Debug script to examine dashboard structure."""

import json
from metabase_migrator.config import Config
from metabase_migrator.api_client import MetabaseAPIClient

def main():
    config = Config('config.yaml')
    metabase_url = config.get_metabase_url()
    credentials = config.get_credentials()

    with MetabaseAPIClient(metabase_url, credentials) as client:
        # Get the source dashboard that we know has cards
        dashboard_id = int(input("Enter source dashboard ID (the one with 91 cards): "))

        dashboard = client.get_dashboard(dashboard_id)

        print("\n=== Dashboard Top-Level Keys ===")
        print(json.dumps(list(dashboard.keys()), indent=2))

        # Get cards
        cards = dashboard.get('ordered_cards', dashboard.get('dashcards', []))

        print(f"\n=== Found {len(cards)} cards ===")

        if cards:
            print("\n=== First Card Structure ===")
            first_card = cards[0]
            print(json.dumps(first_card, indent=2, default=str))

            print("\n=== First Card Keys ===")
            print(json.dumps(list(first_card.keys()), indent=2))

            # Check what field name is used for cards
            if 'ordered_cards' in dashboard:
                print("\n=== Cards field name: 'ordered_cards' ===")
            elif 'dashcards' in dashboard:
                print("\n=== Cards field name: 'dashcards' ===")

            # Check tabs
            if dashboard.get('tabs'):
                print(f"\n=== Dashboard has {len(dashboard['tabs'])} tabs ===")
                print(json.dumps(dashboard['tabs'], indent=2, default=str))

if __name__ == '__main__':
    main()
