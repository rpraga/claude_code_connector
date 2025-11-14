# Metabase Widget Migrator

A powerful command-line tool to migrate Metabase questions (widgets) from one database to another, automatically mapping tables and fields while preserving Query Builder format.

## Features

- **Query Builder Only**: Works exclusively with Query Builder queries (not native SQL)
- **Nested Questions Support**: ✨ Automatically migrates questions based on other questions with `--allow-nested` flag
- **Result Verification**: ✨ NEW! Verify migrated questions produce correct results with random sampling
- **Automatic Field Mapping**: Intelligently maps tables and fields between databases
- **Dependency Resolution**: Detects and migrates question dependencies in the correct order
- **Structure Preservation**: Maintains all query components (filters, aggregations, breakouts, joins)
- **Visualization Settings**: Copies visualization settings and parameters
- **Dry Run Mode**: Preview migrations before executing them
- **Custom Mappings**: Support for custom table/field name mappings
- **Detailed Reporting**: Shows field mappings, type mismatches, and potential issues
- **Circular Reference Detection**: Prevents infinite loops in nested question chains
- **Batch Operations**: Migrate and verify multiple questions at once
- **Multiple Authentication Methods**: Supports username/password and API key authentication

## Requirements

- Python 3.7+
- Access to a Metabase instance
- Valid Metabase credentials (username/password or API key)
- Source and target databases must have similar structure

## Installation

### Option 1: Install from source

```bash
# Clone or download this repository
cd claude_code_connector

# Install dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x metabase-migrator

# Optionally, install as a package
pip install -e .
```

### Option 2: Direct usage

```bash
# Install dependencies
pip install requests pyyaml click python-dotenv tabulate colorama

# Run directly
python -m metabase_migrator.cli
```

## Configuration

### 1. Create Configuration File

```bash
# Generate example configuration
./metabase-migrator init-config

# Copy to config.yaml and edit
cp config.example.yaml config.yaml
```

### 2. Edit config.yaml

```yaml
# Metabase instance URL
metabase_url: https://your-metabase-instance.com

# Authentication (choose one method)

# Method 1: Username and password
username: your-email@example.com
password: your-password

# Method 2: API key (recommended for automation)
# api_key: your-api-key

# Optional: Custom mapping rules
mapping_rules:
  table_mappings:
    # Map table names that differ between databases
    # source_table_name: target_table_name
    old_customers: new_customers

  field_mappings:
    # Map field names that differ between databases
    # source_table.source_field: target_field
    customers.customer_id: customers.id
    orders.total_price: orders.total_amount
```

### 3. Environment Variables (Alternative)

You can also use environment variables instead of a config file:

```bash
export METABASE_URL="https://your-metabase-instance.com"
export METABASE_USERNAME="your-email@example.com"
export METABASE_PASSWORD="your-password"

# Or use API key
export METABASE_API_KEY="your-api-key"
```

## Usage

### Test Connection

Verify your Metabase connection and view available databases:

```bash
./metabase-migrator test-connection
```

### List Databases

View all available databases with their IDs:

```bash
./metabase-migrator list-databases
```

Output:
```
✓ Found 3 database(s):

  ID  Name              Engine     Available
----  ----------------  ---------  -------------
   1  Production DB     postgres   ✓
   2  Analytics DB      postgres   ✓
   3  Sample Dataset    h2         ✗ (sample)
```

### Get Question Information

View details about a question before migrating:

```bash
# Using question ID
./metabase-migrator info 123

# Using question URL
./metabase-migrator info "https://your-metabase.com/question/123"
```

Output:
```
Question Information:
  Name: Customer Orders Summary
  ID: 123
  Created: 2024-01-15T10:30:00Z

Query Type:
  Query Builder

Query Details:
  Database ID: 1
  Source Table ID: 42
  Referenced Fields: 5
  Has Filters: Yes
  Has Aggregations: Yes
  Has Breakouts: Yes

✓ This question can be migrated with this tool
```

### Migrate a Question (Dry Run)

Preview the migration without creating anything:

```bash
./metabase-migrator migrate 123 2 --dry-run
```

This will:
1. Fetch the source question
2. Validate it's Query Builder format
3. Map all tables and fields
4. Show a detailed report
5. Preview what would be created
6. **NOT create the question** (dry run mode)

### Migrate a Question

Perform the actual migration:

```bash
# Basic migration
./metabase-migrator migrate 123 2

# Specify collection
./metabase-migrator migrate 123 2 --collection-id 5

# Custom name suffix
./metabase-migrator migrate 123 2 --name-suffix " (Production Copy)"

# Show full query details
./metabase-migrator migrate 123 2 --show-query
```

### Verify Migration Results

Ensure migrated questions produce the same results:

```bash
# Verify a single question (compares 100 random rows)
./metabase-migrator verify 123 456

# Compare ALL rows
./metabase-migrator verify 123 456 --sample-size 0

# Show detailed differences
./metabase-migrator verify 123 456 --show-details

# Batch verify multiple questions
./metabase-migrator batch-verify mappings.csv
```

See [VERIFICATION.md](VERIFICATION.md) for complete verification guide.

### Complete Example

```bash
# 1. Test connection
./metabase-migrator test-connection

# 2. Find the database IDs
./metabase-migrator list-databases

# 3. Check the question details
./metabase-migrator info "https://metabase.com/question/456"

# 4. Preview the migration
./metabase-migrator migrate 456 2 --dry-run

# 5. Perform the migration
./metabase-migrator migrate 456 2 --collection-id 10
```

## Migration Process

The migrator performs the following steps:

1. **Fetch Source Question**: Retrieves the question definition from Metabase
2. **Validate Query Format**: Ensures it's a Query Builder query (not native SQL)
3. **Extract Components**: Identifies source table, fields, filters, aggregations, etc.
4. **Map Tables**: Finds the corresponding table in the target database
5. **Map Fields**: Maps each field reference to the target database
6. **Validate Types**: Checks for type mismatches and compatibility issues
7. **Transform Query**: Rebuilds the query with target database IDs
8. **Create Question**: Creates a new question in the target database
9. **Copy Settings**: Transfers visualization settings and parameters

## Field Mapping Report

During migration, you'll see a detailed field mapping report:

```
Field Mappings:

Source Field    Target Field    Source Type           Target Type
--------------  --------------  -------------------   -------------------
customer_id     customer_id     type/Integer          type/Integer
customer_name   customer_name   type/Text             type/Text
order_date      order_date      type/DateTime         type/DateTime
total_amount    total_amount    type/Decimal          type/Decimal

⚠ Warning: Type mismatch for field 'created_at': type/DateTime -> type/Date
```

## Custom Mappings

When table or field names differ between databases, use custom mappings:

### Table Mapping Example

```yaml
mapping_rules:
  table_mappings:
    # Old name: new name
    legacy_orders: orders
    customer_data: customers
```

### Field Mapping Example

```yaml
mapping_rules:
  field_mappings:
    # table.old_field: new_field
    customers.cust_id: customers.customer_id
    orders.order_total: orders.total_amount
```

## Supported Query Features

### ✅ Fully Supported

- Simple field selection
- Filters (all types)
- Aggregations (count, sum, avg, etc.)
- Grouping (breakout)
- Sorting (order-by)
- Limits
- Joins between tables
- Custom columns (expressions)
- Multiple aggregations
- Nested filters (AND/OR)
- **Nested questions** (questions based on other questions) - Use `--allow-nested` flag

### ❌ Not Supported

- Native SQL queries
- Custom SQL snippets
- Database-specific functions

## Troubleshooting

### "Query is in native SQL format"

**Problem**: The question uses native SQL instead of Query Builder.

**Solution**: Recreate the question using Query Builder, or manually migrate the SQL query.

### "This question is based on another question (nested query)"

**Problem**: The question is nested and `--allow-nested` flag was not used.

**Solution**: Use the `--allow-nested` flag to automatically migrate all dependencies:
```bash
./metabase-migrator migrate 123 2 --allow-nested
```

See [NESTED_QUESTIONS.md](NESTED_QUESTIONS.md) for detailed nested question migration guide.

### "Table 'xyz' not found in target database"

**Problem**: The source table doesn't exist in the target database.

**Solutions**:
1. Ensure the target database has the same table
2. Use custom table mappings if the table has a different name
3. Check the table schema matches

### "Field 'abc' not found in target table"

**Problem**: A field from the source query doesn't exist in the target table.

**Solutions**:
1. Verify the field exists in the target database
2. Use custom field mappings if the field has a different name
3. Check for typos in custom mappings

### "Type mismatch" warnings

**Problem**: A field has different data types in source vs target.

**Impact**: The query will still be created, but may behave differently or produce errors at runtime.

**Solution**: Review the query results after migration to ensure correctness.

### Authentication errors

**Problem**: "Authentication not configured" or "401 Unauthorized"

**Solutions**:
1. Check your config.yaml has correct credentials
2. Verify environment variables are set correctly
3. Ensure your Metabase account has sufficient permissions
4. Try using API key instead of username/password

## Command Reference

### Global Options

- `--config PATH`: Path to configuration file (default: config.yaml)
- `--version`: Show version information
- `--help`: Show help message

### Commands

#### `test-connection`
Test connection to Metabase and list databases.

Options:
- `--url TEXT`: Override Metabase URL
- `--username TEXT`: Override username
- `--password TEXT`: Override password
- `--api-key TEXT`: Override API key

#### `list-databases`
List all available databases.

#### `info QUESTION_URL_OR_ID`
Show detailed information about a question.

#### `migrate QUESTION_URL_OR_ID TARGET_DATABASE_ID`
Migrate a question to a different database.

Options:
- `--collection-id INTEGER`: Target collection ID
- `--name-suffix TEXT`: Suffix for question name (default: " (Migrated)")
- `--dry-run`: Preview without creating
- `--show-query`: Display migrated query JSON

#### `init-config`
Create an example configuration file.

## Examples

### Example 1: Simple Migration

```bash
# Migrate question 123 from database 1 to database 2
./metabase-migrator migrate 123 2
```

### Example 2: Migration with Custom Collection

```bash
# Migrate and place in collection 10
./metabase-migrator migrate 456 3 --collection-id 10 --name-suffix " (Production)"
```

### Example 3: Using URL

```bash
# Migrate using full question URL
./metabase-migrator migrate "https://metabase.company.com/question/789-sales-report" 2
```

### Example 4: Preview First

```bash
# Check what will happen before migrating
./metabase-migrator info 123
./metabase-migrator migrate 123 2 --dry-run
./metabase-migrator migrate 123 2
```

## API Usage

You can also use the migrator as a Python library:

```python
from metabase_migrator.config import Config
from metabase_migrator.api_client import MetabaseAPIClient
from metabase_migrator.database_mapper import DatabaseMapper
from metabase_migrator.query_migrator import QueryMigrator
from metabase_migrator.widget_creator import WidgetCreator

# Load configuration
config = Config('config.yaml')

# Create API client
with MetabaseAPIClient(config.get_metabase_url(), config.get_credentials()) as client:
    # Fetch source question
    question = client.get_question(123)

    # Set up mapper and migrator
    mapper = DatabaseMapper(client, config.get_mapping_rules())
    migrator = QueryMigrator(mapper)

    # Migrate query
    migrated_query, errors, warnings = migrator.migrate_query(
        question['dataset_query'],
        target_database_id=2
    )

    # Create new question
    if not errors:
        creator = WidgetCreator(client)
        new_question = creator.create_widget(
            question,
            migrated_query,
            name_suffix=" (Migrated)"
        )
        print(f"Created question: {new_question['id']}")
```

## Architecture

### Components

- **api_client.py**: Metabase API interactions
- **config.py**: Configuration management
- **query_analyzer.py**: Query validation and analysis
- **database_mapper.py**: Table and field mapping
- **query_migrator.py**: Query transformation
- **widget_creator.py**: Question creation
- **cli.py**: Command-line interface

### Data Flow

```
Source Question → Query Analyzer → Database Mapper → Query Migrator → Widget Creator → New Question
```

## Security Considerations

- **API Keys**: Store API keys securely, never commit to version control
- **Config Files**: Add config.yaml to .gitignore
- **Permissions**: Ensure your Metabase account has necessary permissions
- **HTTPS**: Always use HTTPS for Metabase connections in production

## Contributing

Contributions are welcome! Areas for improvement:

- Support for nested questions (questions based on other questions)
- Batch migration of multiple questions
- Migration history tracking
- Rollback capabilities
- Advanced expression migration
- Support for more complex join scenarios

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or feature requests, please open an issue on the GitHub repository.

## Changelog

### Version 1.0.0 (2024)

- Initial release
- Query Builder migration support
- Automatic field mapping
- Custom mapping rules
- Dry run mode
- Comprehensive CLI interface
- Field type validation
- Join support
