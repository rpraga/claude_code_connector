# Nested Questions Support

This guide explains how to migrate nested questions (questions based on other questions) in Metabase.

## What are Nested Questions?

In Metabase, you can create a question based on another question's results instead of directly querying a database table. This is called a **nested question** or **multi-stage query**.

### Example Hierarchy

```
┌─────────────────────────────┐
│ Question A: "All Customers" │
│ SELECT * FROM customers     │
└─────────────┬───────────────┘
              │ (source)
              ▼
┌─────────────────────────────┐
│ Question B: "Top Customers" │
│ Based on Question A         │
│ WHERE total_orders > 100    │
└─────────────┬───────────────┘
              │ (source)
              ▼
┌─────────────────────────────┐
│ Question C: "VIP Dashboard" │
│ Based on Question B         │
│ Aggregations & Charts       │
└─────────────────────────────┘
```

Question C depends on Question B, which depends on Question A.

## How Metabase Stores Nested Questions

Instead of referencing a table like:
```json
{
  "source-table": 42
}
```

Nested questions reference another question (card):
```json
{
  "source-table": "card__123"
}
```

Where `123` is the ID of the source question.

## Migration Challenge

When migrating a nested question to a different database, you must:
1. First migrate all dependency questions
2. Update the card references to point to the new migrated questions
3. Maintain the correct dependency order

## Using the Migrator with Nested Questions

### 1. Check if a Question is Nested

```bash
# Get question information
./metabase-migrator info 789

# Output will show:
# Query Type: Query Builder (Nested)
# Is Nested: Yes (based on Question 456)
```

### 2. Analyze Dependencies

Before migrating, understand the full dependency tree:

```bash
./metabase-migrator dependencies 789
```

Example output:
```
Dependency Analysis for Question 789
Name: VIP Dashboard
Is Nested: True

Dependency Depth: 2
Direct Dependency: Question 456

Dependency Chain (from deepest to shallowest):
  └─ Question 123: All Customers
    └─ Question 456: Top Customers
      └─ Question 789: VIP Dashboard

Migration Order: 123 -> 456 -> 789
```

This shows:
- Question 789 depends on 456
- Question 456 depends on 123
- Question 123 is the root (queries a table directly)

### 3. Migrate with --allow-nested Flag

The migrator automatically handles the entire dependency chain:

```bash
# Migrate nested question with all dependencies
./metabase-migrator migrate 789 2 --allow-nested

# With custom collection
./metabase-migrator migrate 789 2 --allow-nested --collection-id 10
```

#### What Happens

1. **Dependency Analysis**: Analyzes the full dependency tree
2. **Detects Circular References**: Prevents infinite loops
3. **Determines Order**: Calculates migration order (dependencies first)
4. **Recursive Migration**:
   - Migrates Question 123 first
   - Then migrates Question 456 (updating reference to new Question 123)
   - Finally migrates Question 789 (updating reference to new Question 456)
5. **ID Mapping**: Tracks old→new question ID mappings
6. **Reference Updates**: Updates all `card__` references automatically

### 4. Dry Run for Nested Questions

Preview what will be migrated:

```bash
./metabase-migrator migrate 789 2 --allow-nested --dry-run
```

This shows:
- Full dependency tree
- Migration order
- What questions will be created
- **Without actually creating anything**

## Migration Process Details

### Step-by-Step Example

Migrating Question 789 to Database 2:

```
1. Analyze dependencies
   ✓ Found dependency chain: 123 -> 456 -> 789

2. Migration Order
   Will migrate 3 question(s):
   1. Question 123: All Customers
   2. Question 456: Top Customers
   3. Question 789: VIP Dashboard

3. Migrating dependencies
   [1/2] Migrating dependency: Question 123
   ✓ Created: Question 1001 - All Customers (Migrated)

   [2/2] Migrating dependency: Question 456
   ✓ Created: Question 1002 - Top Customers (Migrated)

4. Migrating main question 789
   ✓ Created: Question 1003 - VIP Dashboard (Migrated)

✓ Question created successfully!
  URL: https://metabase.com/question/1003
```

### ID Mapping Cache

The migrator maintains a cache during migration:

```
Source DB Questions → Target DB Questions
──────────────────────────────────────────
123                → 1001
456                → 1002
789                → 1003
```

When migrating Question 456:
- Original reference: `"source-table": "card__123"`
- Updated reference: `"source-table": "card__1001"`

When migrating Question 789:
- Original reference: `"source-table": "card__456"`
- Updated reference: `"source-table": "card__1002"`

## Advanced Scenarios

### Scenario 1: Partial Migration

If you've already migrated some dependencies manually:

```bash
# Question 123 already migrated as 1001

# The migrator detects this and skips re-migrating
./metabase-migrator migrate 789 2 --allow-nested
# Will migrate 456 and 789, using existing 1001
```

**Note**: Current version doesn't auto-detect existing migrations. You'll need to migrate the full chain or use manual ID mapping (advanced).

### Scenario 2: Deep Nesting

Questions can be nested multiple levels deep:

```
Table → Q1 → Q2 → Q3 → Q4 → Q5
```

The migrator handles any depth:

```bash
./metabase-migrator dependencies 5
# Shows full 5-level dependency chain

./metabase-migrator migrate 5 2 --allow-nested
# Migrates all 5 questions in correct order
```

### Scenario 3: Circular Reference Detection

If questions reference each other circularly (rare, but possible through API):

```
Q1 depends on Q2
Q2 depends on Q3
Q3 depends on Q1  ← Circular!
```

The migrator detects and prevents this:

```bash
./metabase-migrator migrate 1 2 --allow-nested
# Error: Circular reference detected: 1 -> 2 -> 3 -> 1
```

### Scenario 4: Multiple Dependencies

If you're migrating several nested questions:

```bash
# Migrate multiple nested questions to same database
for q in 789 790 791; do
  ./metabase-migrator migrate $q 2 --allow-nested
done
```

**Note**: If questions share dependencies, they'll be re-migrated each time. Future versions may optimize this.

## Field References in Nested Questions

### Regular Table-Based Questions

Field references use numeric IDs:
```json
["field", 123, null]  // Direct field ID from table
```

These are mapped to target database field IDs.

### Nested Questions

Field references may use string names:
```json
["field", "CUSTOMER_NAME", {"base-type": "type/Text"}]
```

These reference **output columns** from the source question, not database fields.

**Important**: Nested query field references are **not** remapped because they refer to the source question's output structure, which remains the same.

## Troubleshooting

### Error: "This question is based on another question (nested query)"

You tried to migrate without `--allow-nested`:

```bash
# ❌ Without flag
./metabase-migrator migrate 789 2
# Error: Use --allow-nested flag

# ✓ With flag
./metabase-migrator migrate 789 2 --allow-nested
```

### Error: "Circular reference detected"

Questions form a circular dependency:

**Solution**: Fix the circular reference in Metabase first, then migrate.

### Error: "Source question must be migrated first"

A dependency wasn't migrated:

**Solution**: Use `--allow-nested` to automatically migrate all dependencies.

### Warning: "Field references are based on source question output"

This is informational, not an error. Nested questions use different field reference formats.

## Best Practices

### 1. Always Analyze First

```bash
# Before migrating, understand dependencies
./metabase-migrator dependencies 789
```

### 2. Use Dry Run

```bash
# Preview the migration plan
./metabase-migrator migrate 789 2 --allow-nested --dry-run
```

### 3. Migrate to Same Collection

Keep related questions together:

```bash
./metabase-migrator migrate 789 2 --allow-nested --collection-id 10
```

All dependencies and the root question go to collection 10.

### 4. Test Incrementally

For complex dependency trees:
1. Migrate the root dependency first
2. Test it works
3. Migrate the next level
4. Continue up the tree

### 5. Document Mappings

Keep track of migrated question IDs:

```
Source → Target
───────────────
123    → 1001
456    → 1002
789    → 1003
```

## Limitations

### Current Limitations

1. **No Deduplication**: If migrating multiple questions with shared dependencies, shared deps are migrated multiple times
2. **No Manual Mapping**: Cannot manually specify existing migrated question IDs
3. **Same Database Only**: All nested questions must migrate to the same target database

### Future Enhancements

Planned improvements:
- [ ] Dependency deduplication across multiple migrations
- [ ] Manual ID mapping configuration
- [ ] Cross-database nested questions
- [ ] Batch migration optimization
- [ ] Migration history tracking

## API Usage

Programmatic nested question migration:

```python
from metabase_migrator.api_client import MetabaseAPIClient
from metabase_migrator.nested_handler import NestedQuestionHandler
from metabase_migrator.query_migrator import QueryMigrator
from metabase_migrator.database_mapper import DatabaseMapper
from metabase_migrator.widget_creator import WidgetCreator
from metabase_migrator.config import Config

config = Config('config.yaml')

with MetabaseAPIClient(config.get_metabase_url(), config.get_credentials()) as client:
    # Analyze dependencies
    nested_handler = NestedQuestionHandler(client)

    # Get migration order
    migration_order, error = nested_handler.get_migration_order(789)

    if error:
        print(f"Error: {error}")
    else:
        # Migrate each question in order
        mapper = DatabaseMapper(client)
        migrator = QueryMigrator(mapper, nested_handler)
        creator = WidgetCreator(client)

        for question_id in migration_order:
            question = client.get_question(question_id)
            query = question['dataset_query']

            # Get migrated card ID if nested
            migrated_card_id = None
            if nested_handler.is_nested_query(query):
                source_card_id = nested_handler.extract_source_card_id(query)
                migrated_card_id = nested_handler.migration_cache.get(source_card_id)

            # Migrate
            migrated_query, errors, warnings = migrator.migrate_query(
                query, target_database_id=2, migrated_card_id=migrated_card_id
            )

            # Create
            new_question = creator.create_widget(question, migrated_query)

            # Cache the mapping
            nested_handler.set_migration_mapping(question_id, new_question['id'])

            print(f"Migrated {question_id} → {new_question['id']}")
```

## Summary

✅ **Nested questions are fully supported** with the `--allow-nested` flag

✅ **Automatic dependency resolution** handles the full tree

✅ **Circular reference detection** prevents infinite loops

✅ **Preserves question relationships** by updating card references

✅ **Works with any nesting depth** from simple to complex hierarchies

To migrate nested questions:
1. Use `dependencies` command to analyze
2. Use `--allow-nested` flag when migrating
3. All dependencies are automatically migrated in the correct order
4. Card references are automatically updated

Happy migrating! 🚀
