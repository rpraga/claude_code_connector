# Usage Examples

Real-world examples of using Metabase Migrator.

## Example 1: Simple Single Question Migration

**Scenario**: Migrate a sales dashboard question from staging to production.

```bash
# 1. Check the question
./metabase-migrator info 42

# Output:
# Question: Monthly Sales Report
# Query Type: Query Builder ✓
# Database: Staging DB (ID: 1)

# 2. List production databases
./metabase-migrator list-databases

# Output:
# ID: 2 - Production DB

# 3. Dry run
./metabase-migrator migrate 42 2 --dry-run

# Output:
# ✓ All fields mapped successfully
# Question would be created: "Monthly Sales Report (Migrated)"

# 4. Migrate
./metabase-migrator migrate 42 2

# Output:
# ✓ Question created successfully!
# URL: https://metabase.com/question/156
```

## Example 2: Migration with Custom Collection

**Scenario**: Migrate multiple questions to a specific collection in production.

```bash
# Migrate to collection ID 10 with custom naming
./metabase-migrator migrate 42 2 \
  --collection-id 10 \
  --name-suffix " (Production)"

./metabase-migrator migrate 43 2 \
  --collection-id 10 \
  --name-suffix " (Production)"

./metabase-migrator migrate 44 2 \
  --collection-id 10 \
  --name-suffix " (Production)"
```

## Example 3: Handling Different Table Names

**Scenario**: Source database has `legacy_customers` but target has `customers`.

**config.yaml**:
```yaml
metabase_url: https://metabase.company.com
username: admin@company.com
password: secretpassword

mapping_rules:
  table_mappings:
    legacy_customers: customers
    old_orders: orders
```

```bash
# Now migrate - table names will be automatically mapped
./metabase-migrator migrate 55 2
```

## Example 4: Handling Different Field Names

**Scenario**: Field names have changed between databases.

**config.yaml**:
```yaml
mapping_rules:
  field_mappings:
    customers.cust_id: customer_id
    customers.fname: first_name
    customers.lname: last_name
    orders.total_price: total_amount
    orders.order_date: created_at
```

```bash
# Field references will be automatically updated
./metabase-migrator migrate 66 2 --show-query
```

## Example 5: Using Environment Variables

**Scenario**: Running in CI/CD or automated environment.

```bash
# Set credentials via environment
export METABASE_URL="https://metabase.company.com"
export METABASE_API_KEY="mb_abc123def456"

# No config file needed
./metabase-migrator test-connection
./metabase-migrator migrate 77 2
```

## Example 6: Using URLs Instead of IDs

**Scenario**: Working with bookmarked Metabase questions.

```bash
# Use the full question URL
./metabase-migrator info "https://metabase.company.com/question/88-customer-analysis"

# Migrate using URL
./metabase-migrator migrate \
  "https://metabase.company.com/question/88-customer-analysis" \
  2 \
  --name-suffix " (Prod)"
```

## Example 7: Complex Query with Joins

**Scenario**: Migrating a question with multiple joins.

```bash
# Check the question first
./metabase-migrator info 99

# Output shows:
# - Source Table: customers
# - Referenced Fields: 12
# - Has Joins: Yes

# Preview the migration
./metabase-migrator migrate 99 2 --dry-run

# Review field mappings for all joined tables
# If everything looks good:
./metabase-migrator migrate 99 2
```

## Example 8: Batch Migration Script

**Scenario**: Migrate multiple questions at once.

**migrate_all.sh**:
```bash
#!/bin/bash

# Array of question IDs to migrate
QUESTIONS=(101 102 103 104 105)

# Target database
TARGET_DB=2

# Collection to place questions in
COLLECTION=15

# Migrate each question
for Q in "${QUESTIONS[@]}"; do
  echo "Migrating question $Q..."
  ./metabase-migrator migrate $Q $TARGET_DB \
    --collection-id $COLLECTION \
    --name-suffix " (Production)" \
    || echo "Failed to migrate $Q"
done

echo "Migration complete!"
```

```bash
chmod +x migrate_all.sh
./migrate_all.sh
```

## Example 9: Different Database Engines

**Scenario**: Migrating from PostgreSQL to MySQL.

```bash
# The tool will warn about engine differences
./metabase-migrator migrate 110 3

# Output:
# ⚠ Warning: Database engines differ (source: postgres, target: mysql)
# ⚠ Type mismatch for field 'created_at': type/DateTime -> type/Date
# ✓ Question created successfully!

# Always test the migrated question thoroughly
```

## Example 10: Programmatic Usage in Python

**Scenario**: Integrate migration into a Python script.

```python
#!/usr/bin/env python3
"""Automated question migration script."""

from metabase_migrator.config import Config
from metabase_migrator.api_client import MetabaseAPIClient
from metabase_migrator.database_mapper import DatabaseMapper
from metabase_migrator.query_migrator import QueryMigrator
from metabase_migrator.widget_creator import WidgetCreator
from metabase_migrator.query_analyzer import QueryAnalyzer

def migrate_question(question_id, target_db_id):
    """Migrate a single question."""
    config = Config('config.yaml')

    with MetabaseAPIClient(config.get_metabase_url(),
                          config.get_credentials()) as client:

        # Fetch question
        question = client.get_question(question_id)
        print(f"Migrating: {question['name']}")

        # Validate
        query = question.get('dataset_query', {})
        is_valid, error = QueryAnalyzer.validate_query_builder_format(query)

        if not is_valid:
            print(f"  ✗ Cannot migrate: {error}")
            return None

        # Migrate
        mapper = DatabaseMapper(client, config.get_mapping_rules())
        migrator = QueryMigrator(mapper)

        migrated_query, errors, warnings = migrator.migrate_query(
            query, target_db_id
        )

        if errors:
            print(f"  ✗ Migration failed:")
            for e in errors:
                print(f"    - {e}")
            return None

        # Create
        creator = WidgetCreator(client)
        new_question = creator.create_widget(
            question,
            migrated_query,
            collection_id=10,
            name_suffix=" (Production)"
        )

        print(f"  ✓ Created: {new_question['id']}")
        return new_question

# Migrate multiple questions
questions_to_migrate = [101, 102, 103, 104, 105]
target_database = 2

for qid in questions_to_migrate:
    migrate_question(qid, target_database)
```

## Example 11: Pre-flight Validation

**Scenario**: Check if questions can be migrated before starting.

```bash
#!/bin/bash

# List of questions
QUESTIONS=(101 102 103 104 105)

echo "Pre-flight validation..."

# Check each question
for Q in "${QUESTIONS[@]}"; do
  echo -n "Question $Q: "

  # Get info and check if it's Query Builder
  if ./metabase-migrator info $Q 2>/dev/null | grep -q "Query Builder"; then
    echo "✓ Can migrate"
  else
    echo "✗ Cannot migrate (Native SQL or error)"
  fi
done
```

## Example 12: Migration with Error Handling

**Scenario**: Robust migration script with error handling.

```bash
#!/bin/bash

set -e  # Exit on error

# Configuration
QUESTION_ID=120
TARGET_DB=2
COLLECTION=10

echo "Starting migration of question $QUESTION_ID..."

# Test connection first
echo "Testing connection..."
./metabase-migrator test-connection || {
  echo "Connection failed!"
  exit 1
}

# Check question
echo "Validating question..."
./metabase-migrator info $QUESTION_ID || {
  echo "Question not found or invalid!"
  exit 1
}

# Dry run
echo "Performing dry run..."
./metabase-migrator migrate $QUESTION_ID $TARGET_DB --dry-run || {
  echo "Dry run failed! Check the errors above."
  exit 1
}

# Ask for confirmation
read -p "Proceed with migration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Migration cancelled."
  exit 0
fi

# Perform migration
echo "Migrating..."
./metabase-migrator migrate $QUESTION_ID $TARGET_DB \
  --collection-id $COLLECTION \
  --name-suffix " (Production)" || {
  echo "Migration failed!"
  exit 1
}

echo "Migration completed successfully!"
```

## Example 13: Using with Docker

**Scenario**: Run migrator in a Docker container.

**Dockerfile**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x metabase-migrator

ENTRYPOINT ["./metabase-migrator"]
```

**Build and run**:
```bash
# Build image
docker build -t metabase-migrator .

# Run with environment variables
docker run --rm \
  -e METABASE_URL="https://metabase.com" \
  -e METABASE_API_KEY="your-key" \
  metabase-migrator test-connection

# Run migration
docker run --rm \
  -e METABASE_URL="https://metabase.com" \
  -e METABASE_API_KEY="your-key" \
  metabase-migrator migrate 123 2
```

## Example 14: Migrating Between Different Metabase Instances

**Scenario**: Migrate from one Metabase instance to another (different servers).

This requires two separate runs:

```bash
# Step 1: Export from source (save query details)
./metabase-migrator info 123 > question_123.txt

# Step 2: Note the database and table names from source
# Update config.yaml with target instance credentials

# Step 3: Find target database with similar structure
./metabase-migrator list-databases

# Step 4: Migrate (will use API to fetch from source)
# Note: Both instances need to be accessible
./metabase-migrator migrate 123 2
```

## Tips and Best Practices

1. **Always dry run first**: Use `--dry-run` to preview
2. **Check field mappings**: Review the field mapping report
3. **Test migrated questions**: Always verify the results
4. **Use custom mappings**: When table/field names differ
5. **Batch migrations**: Write scripts for multiple questions
6. **Version control**: Keep config.yaml in version control (without credentials)
7. **Use API keys**: More secure than username/password
8. **Document migrations**: Keep track of what was migrated where

## Common Patterns

### Pattern: Progressive Migration
```bash
# 1. Test on one question
./metabase-migrator migrate 1 2 --dry-run
./metabase-migrator migrate 1 2

# 2. Test the result thoroughly

# 3. If successful, migrate more
for i in {2..10}; do
  ./metabase-migrator migrate $i 2
done
```

### Pattern: Staging to Production
```bash
# Migrate all staging questions to production
# with proper naming and collection

for Q in $(seq 100 150); do
  ./metabase-migrator migrate $Q 2 \
    --collection-id 20 \
    --name-suffix "" \
    2>/dev/null || continue
done
```

### Pattern: Database Upgrade
```bash
# When upgrading database versions
# Migrate all questions to new database

OLD_DB=1
NEW_DB=5

for Q in {1..100}; do
  ./metabase-migrator migrate $Q $NEW_DB \
    --name-suffix " (v2)" \
    || echo "Skipped $Q"
done
```
