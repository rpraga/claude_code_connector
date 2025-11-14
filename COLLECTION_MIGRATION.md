# Collection-Based Migration Guide

Migrate entire collections of questions at once with automatic collection creation and database filtering.

## What is Collection Migration?

Instead of migrating questions one-by-one, you can migrate an entire collection:
- All questions from `"Old Reports"` collection
- Filter by source database (only migrate from DB 1)
- Create new collection `"Old Reports_migrated"`
- Place all migrated questions in the new collection
- Optionally verify all migrations

## Quick Start

```bash
# 1. List all collections
./metabase-migrator list-collections

# 2. Analyze a collection
./metabase-migrator analyze-collection 5

# 3. Migrate the collection
./metabase-migrator migrate-collection 5 2

# Where:
#   5 = source collection ID
#   2 = target database ID
```

## Commands

### 1. `list-collections` - List All Collections

```bash
./metabase-migrator list-collections
```

**Output:**
```
✓ Found 10 collection(s):

  ID  Name                Description
----  ------------------  ------------------------------
   1  Marketing Reports   Monthly marketing analytics
   5  Sales Dashboard     Sales team dashboards
  10  Old Reports         Legacy reports to migrate
  15  Finance             Financial reports
```

### 2. `analyze-collection` - Analyze Before Migrating

Analyze a collection to see what can be migrated:

```bash
./metabase-migrator analyze-collection COLLECTION_ID [OPTIONS]
```

**Options:**
- `--database-id ID` - Filter questions by database

**Example:**
```bash
# Analyze collection 10
./metabase-migrator analyze-collection 10

# Only show questions from database 1
./metabase-migrator analyze-collection 10 --database-id 1
```

**Output:**
```
ℹ Analyzing collection 10...

Collection: Old Reports
  Total Items: 25

Statistics:
  Total Questions: 20
  Migratable: 15
  Non-Migratable: 5
  Nested Questions: 3
  Other Items: 5

✓ 15 question(s) can be migrated:
  • 101: Monthly Sales Report
  • 102: Customer Analysis
  • 103: Product Performance [NESTED]
  ...

⚠ 5 question(s) cannot be migrated:
  • 201: Custom SQL Report - Query is in native SQL format
  • 202: External DB Report - Different database (ID: 3)
  ...
```

### 3. `migrate-collection` - Migrate Entire Collection

Migrate all questions from a collection to a new collection:

```bash
./metabase-migrator migrate-collection SOURCE_COLLECTION_ID TARGET_DATABASE_ID [OPTIONS]
```

**Arguments:**
- `SOURCE_COLLECTION_ID` - Source collection ID
- `TARGET_DATABASE_ID` - Target database ID

**Options:**
- `--target-collection-name NAME` - Custom name for target collection (default: source_name + "_migrated")
- `--parent-collection-id ID` - Parent collection ID where the new collection will be created (default: root level)
- `--source-database-id ID` - Only migrate questions from this database
- `--allow-nested` - Allow migration of nested questions
- `--name-suffix TEXT` - Suffix for question names (default: " (Migrated)")
- `--dry-run` - Preview without creating
- `--verify` - Verify all migrations after creation
- `--save-mapping FILE` - Save migration mapping to CSV

**Example:**
```bash
# Basic migration
./metabase-migrator migrate-collection 10 2

# With custom target collection name
./metabase-migrator migrate-collection 10 2 \
  --target-collection-name "Reports on Production DB"

# Create new collection inside a parent collection (e.g., inside collection 42)
./metabase-migrator migrate-collection 10 2 \
  --target-collection-name "Migrated Reports" \
  --parent-collection-id 42

# Only migrate from database 1
./metabase-migrator migrate-collection 10 2 \
  --source-database-id 1

# Include nested questions
./metabase-migrator migrate-collection 10 2 \
  --allow-nested

# With verification
./metabase-migrator migrate-collection 10 2 \
  --verify

# Save mapping for later verification
./metabase-migrator migrate-collection 10 2 \
  --save-mapping mappings.csv

# Dry run first
./metabase-migrator migrate-collection 10 2 \
  --dry-run
```

## Complete Workflow Example

### Scenario: Migrate "Old Reports" from staging DB to production DB

```bash
# Step 1: List collections to find the ID
./metabase-migrator list-collections

# Output shows:
#   ID: 10, Name: Old Reports

# Step 2: Analyze the collection
./metabase-migrator analyze-collection 10 --database-id 1

# Output shows:
#   Migratable: 15 questions
#   Nested Questions: 3

# Step 3: Preview with dry run
./metabase-migrator migrate-collection 10 2 \
  --source-database-id 1 \
  --allow-nested \
  --target-collection-name "Old Reports (Production)" \
  --parent-collection-id 5 \
  --dry-run

# Step 4: Perform migration (creates new collection inside collection 5)
./metabase-migrator migrate-collection 10 2 \
  --source-database-id 1 \
  --allow-nested \
  --parent-collection-id 5 \
  --target-collection-name "Old Reports (Production)" \
  --save-mapping migration_report.csv

# Step 5: Verify migrations
./metabase-migrator batch-verify migration_report.csv
```

## Output Example

```bash
./metabase-migrator migrate-collection 10 2 --verify
```

**Output:**
```
ℹ Analyzing source collection...

Source Collection: Old Reports
  Questions to migrate: 15

ℹ Migrating collection...

Migration Results:
  Target Collection: Old Reports_migrated (ID: 25)
  Total: 15
  Migrated: 15
  Failed: 0
  Skipped: 0

✓ 15 question(s) migrated:
  • Monthly Sales Report (101 → 501)
  • Customer Analysis (102 → 502)
  • Product Performance (103 → 503)
  ...

ℹ Verifying migrated questions...

Verification Results:
  Passed: 15
  Failed: 0
  Pass Rate: 100.0%

✓ Collection migration completed!
View target collection: https://metabase.com/collection/25
```

## Features

### Automatic Collection Creation

The migrator automatically creates a new collection for migrated questions:

```
Source: "Old Reports"
Target: "Old Reports_migrated"  (auto-created)
```

Or specify a custom name:

```bash
--target-collection-name "Production Reports"
```

### Database Filtering

Only migrate questions from a specific database:

```bash
# Collection has questions from DB 1, 2, and 3
# Only migrate from DB 1 to DB 2
./metabase-migrator migrate-collection 10 2 --source-database-id 1
```

### Nested Question Support

Include nested questions (questions based on other questions):

```bash
./metabase-migrator migrate-collection 10 2 --allow-nested
```

**Note:** Nested questions within the same collection will be migrated in dependency order automatically.

### Automatic Verification

Verify all migrated questions immediately:

```bash
./metabase-migrator migrate-collection 10 2 --verify
```

This:
1. Migrates all questions
2. Executes both source and target questions
3. Compares results (100 row sample)
4. Reports pass/fail for each

### Migration Mapping

Save a CSV file mapping source → target IDs:

```bash
./metabase-migrator migrate-collection 10 2 --save-mapping report.csv
```

**report.csv:**
```csv
source_id,target_id,source_name,target_name
101,501,"Monthly Sales","Monthly Sales (Migrated)"
102,502,"Customer Report","Customer Report (Migrated)"
```

Use this for:
- Documentation
- Later verification: `./metabase-migrator batch-verify report.csv`
- Tracking migrations

## Advanced Scenarios

### Scenario 1: Migrate Only Non-Nested Questions

```bash
# First analyze
./metabase-migrator analyze-collection 10

# Shows: 15 migratable, 3 nested

# Migrate without --allow-nested
./metabase-migrator migrate-collection 10 2

# Result: 12 migrated, 3 skipped (nested)
```

### Scenario 2: Multi-Database Collection

Collection has questions from multiple databases:

```bash
# Collection 10 has:
#   - 10 questions from DB 1 (staging)
#   - 5 questions from DB 3 (archive)
#   - 5 dashboards

# Migrate only DB 1 questions to DB 2 (production)
./metabase-migrator migrate-collection 10 2 \
  --source-database-id 1

# Result: 10 migrated, 10 skipped (different DB or not questions)
```

### Scenario 3: Iterative Migration

Migrate, review, fix issues, migrate again:

```bash
# First attempt - dry run
./metabase-migrator migrate-collection 10 2 --dry-run

# Looks good, migrate
./metabase-migrator migrate-collection 10 2 \
  --save-mapping attempt1.csv

# Some questions failed due to missing fields
# Fix custom field mappings in config.yaml

# Analyze what's left
./metabase-migrator analyze-collection 10 --database-id 1

# Migrate remaining (will create new questions in same collection)
./metabase-migrator migrate-collection 10 2 \
  --save-mapping attempt2.csv
```

### Scenario 4: Production Migration with Full Verification

```bash
#!/bin/bash
# production_collection_migration.sh

COLLECTION_ID=10
TARGET_DB=2
MAPPING_FILE="migration_$(date +%Y%m%d_%H%M%S).csv"

echo "Starting collection migration..."

# Dry run first
./metabase-migrator migrate-collection $COLLECTION_ID $TARGET_DB \
  --source-database-id 1 \
  --dry-run

read -p "Proceed with migration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted"
  exit 1
fi

# Perform migration
./metabase-migrator migrate-collection $COLLECTION_ID $TARGET_DB \
  --source-database-id 1 \
  --save-mapping $MAPPING_FILE

# Verify with full data (not sample)
echo "Verifying all migrations (full data)..."
while IFS=, read -r source_id target_id name; do
  if [ "$source_id" != "source_id" ]; then  # Skip header
    ./metabase-migrator verify $source_id $target_id --sample-size 0
    if [ $? -ne 0 ]; then
      echo "FAILED: Question $source_id → $target_id"
      exit 1
    fi
  fi
done < $MAPPING_FILE

echo "✓ All migrations verified successfully!"
```

## Handling Failures

### What Gets Skipped

Questions are skipped if:
- Native SQL (not Query Builder)
- Different source database (when using `--source-database-id`)
- Nested and `--allow-nested` not specified
- Dependencies not yet migrated (nested questions)

### What Causes Failures

Migrations fail if:
- Table not found in target database
- Field not found in target table
- Query transformation errors
- API errors

### Retry Failed Migrations

```bash
# Initial migration
./metabase-migrator migrate-collection 10 2

# Output shows:
#   Migrated: 12
#   Failed: 3

# Fix issues (add custom mappings, fix data)

# Re-analyze to see what's left
./metabase-migrator analyze-collection 10 --database-id 1

# Migrate again (only unmigrated questions)
./metabase-migrator migrate-collection 10 2
```

## Best Practices

### 1. Always Analyze First

```bash
# Don't do this
./metabase-migrator migrate-collection 10 2

# Do this
./metabase-migrator analyze-collection 10
./metabase-migrator migrate-collection 10 2 --dry-run
./metabase-migrator migrate-collection 10 2
```

### 2. Use Database Filtering

```bash
# If collection has mixed databases, filter
./metabase-migrator migrate-collection 10 2 --source-database-id 1
```

### 3. Save Mappings

```bash
# Always save for documentation and verification
./metabase-migrator migrate-collection 10 2 \
  --save-mapping "migration_$(date +%Y%m%d).csv"
```

### 4. Verify Critical Collections

```bash
# For important collections, verify everything
./metabase-migrator migrate-collection 10 2 --verify
```

### 5. Use Meaningful Target Names

```bash
# Bad: "Old Reports_migrated"
# Good: "Reports - Production DB"

./metabase-migrator migrate-collection 10 2 \
  --target-collection-name "Reports - Production DB"
```

## Comparison: Single vs Collection Migration

### Single Question Migration

```bash
./metabase-migrator migrate 101 2
./metabase-migrator migrate 102 2
./metabase-migrator migrate 103 2
# ... repeat for each question
```

**Pros:**
- Full control over each question
- Can handle complex nested dependencies
- Can set different target collections

**Cons:**
- Time-consuming for many questions
- Manual tracking needed
- No automatic collection creation

### Collection Migration

```bash
./metabase-migrator migrate-collection 10 2 --verify
```

**Pros:**
- Migrate many questions at once
- Automatic collection creation
- Built-in verification option
- Automatic mapping CSV generation
- Database filtering

**Cons:**
- All questions go to same target collection
- Less control over individual questions
- Nested questions with external dependencies may be skipped

## Troubleshooting

### "No questions to migrate"

**Cause:** All questions filtered out or wrong collection

**Solution:**
```bash
# Check what's in the collection
./metabase-migrator analyze-collection 10

# Try without database filter
./metabase-migrator migrate-collection 10 2
```

### "Collection already exists"

**Cause:** Target collection name already exists

**Solution:** The migrator will use the existing collection. To create a new one:
```bash
./metabase-migrator migrate-collection 10 2 \
  --target-collection-name "Reports Migration 2024-01-15"
```

### "Nested question dependency not migrated"

**Cause:** Nested question depends on question outside the collection

**Solution:**
1. Migrate the dependency first using single question migration
2. Then migrate the collection

### Some questions failed

**Cause:** Various (missing tables, fields, etc.)

**Solution:**
1. Check the error messages
2. Fix custom mappings if needed
3. Re-run migration (only failed questions will be attempted)

## Summary

Collection migration is perfect for:
- ✅ Migrating many questions at once
- ✅ Maintaining collection organization
- ✅ Bulk migrations with filtering
- ✅ Quick verification of entire collections

Use single question migration for:
- Complex nested question hierarchies
- Questions that need different target collections
- Fine-grained control

**Complete Workflow:**
```bash
# 1. Analyze
./metabase-migrator analyze-collection 10

# 2. Dry run
./metabase-migrator migrate-collection 10 2 --dry-run

# 3. Migrate
./metabase-migrator migrate-collection 10 2 \
  --source-database-id 1 \
  --verify \
  --save-mapping report.csv

# 4. Done! ✓
```
