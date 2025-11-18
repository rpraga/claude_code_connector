#!/usr/bin/env python3
"""Test script to debug adding a card to a dashboard."""

import json
from metabase_migrator.config import Config
from metabase_migrator.api_client import MetabaseAPIClient

def main():
    config = Config('config.yaml')
    metabase_url = config.get_metabase_url()
    credentials = config.get_credentials()

    with MetabaseAPIClient(metabase_url, credentials) as client:
        dashboard_id = int(input("Enter dashboard ID to test: "))
        card_id = int(input("Enter card/question ID to add: "))

        # Get current dashboard
        print("\n=== Getting current dashboard ===")
        dashboard = client.get_dashboard(dashboard_id)
        existing_cards = dashboard.get('dashcards', [])
        print(f"Dashboard has {len(existing_cards)} existing cards")

        # Build minimal new card
        new_card = {
            'id': -1,
            'card_id': card_id,
            'row': 0,
            'col': 0,
            'size_x': 4,
            'size_y': 4
        }

        # Build payload
        cards_payload = []
        for card in existing_cards:
            cards_payload.append({
                'id': card['id'],
                'card_id': card.get('card_id'),
                'row': card.get('row', 0),
                'col': card.get('col', 0),
                'size_x': card.get('size_x', 4),
                'size_y': card.get('size_y', 4)
            })
        cards_payload.append(new_card)

        print(f"\n=== Sending PUT request ===")
        print(f"URL: {client.base_url}/api/dashboard/{dashboard_id}/cards")
        print(f"Payload (array with {len(cards_payload)} cards):")
        print(json.dumps(cards_payload[-1], indent=2))  # Show just the new card

        # Make the request
        response = client.session.put(
            f"{client.base_url}/api/dashboard/{dashboard_id}/cards",
            json=cards_payload
        )

        print(f"\n=== Response ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"\nResponse body keys: {list(result.keys())}")

            result_cards = result.get('dashcards', result.get('ordered_cards', []))
            print(f"Dashboard now has {len(result_cards)} cards")

            # Verify by fetching dashboard again
            print("\n=== Verifying by fetching dashboard again ===")
            updated_dashboard = client.get_dashboard(dashboard_id)
            final_cards = updated_dashboard.get('dashcards', [])
            print(f"Dashboard has {len(final_cards)} cards after verification")

            if len(final_cards) > len(existing_cards):
                print("✓ Card was successfully added!")
            else:
                print("✗ Card was NOT added")
        else:
            print(f"Error: {response.text}")

if __name__ == '__main__':
    main()
