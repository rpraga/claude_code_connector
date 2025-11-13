# Quick Start Guide

Get up and running with Metabase Migrator in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure

Create your configuration file:

```bash
# Generate example config
./metabase-migrator init-config

# Copy and edit
cp config.example.yaml config.yaml
nano config.yaml  # or use your preferred editor
```

Edit `config.yaml` with your Metabase details:

```yaml
metabase_url: https://your-metabase.com
username: your-email@example.com
password: your-password
```

## Step 3: Test Connection

```bash
./metabase-migrator test-connection
```

You should see:
```
ℹ Connecting to Metabase at https://your-metabase.com...
✓ Successfully connected to Metabase!
ℹ Found 3 database(s):
  - Production DB (ID: 1, Engine: postgres)
  - Analytics DB (ID: 2, Engine: postgres)
  - Sample Dataset (ID: 3, Engine: h2)
```

## Step 4: Find Your Question

You need two pieces of information:
1. **Question ID or URL** - The question you want to migrate
2. **Target Database ID** - Where you want to migrate it to

To get the Question ID:
- Open the question in Metabase
- Look at the URL: `https://metabase.com/question/123` → ID is `123`

To get Database IDs:
```bash
./metabase-migrator list-databases
```

## Step 5: Check the Question

Before migrating, verify the question is compatible:

```bash
./metabase-migrator info 123
```

Look for:
- ✓ "Query Type: Query Builder" (good!)
- ✗ "Query Type: Native SQL" (not supported)

## Step 6: Preview Migration (Dry Run)

See what will happen without making changes:

```bash
./metabase-migrator migrate 123 2 --dry-run
```

Review:
- Field mappings
- Any warnings or errors
- What the new question will look like

## Step 7: Migrate!

If the dry run looks good, do the real migration:

```bash
./metabase-migrator migrate 123 2
```

You'll get a URL to your new question:
```
✓ Question created successfully!
  Name: Sales Report (Migrated)
  ID: 456
  URL: https://your-metabase.com/question/456
```

## Common Options

### Put in a specific collection:
```bash
./metabase-migrator migrate 123 2 --collection-id 10
```

### Custom name suffix:
```bash
./metabase-migrator migrate 123 2 --name-suffix " (Production Copy)"
```

### Use question URL instead of ID:
```bash
./metabase-migrator migrate "https://metabase.com/question/123-sales-report" 2
```

## Troubleshooting

### "Authentication not configured"
- Check your config.yaml has correct credentials
- Or set environment variables:
  ```bash
  export METABASE_URL="https://your-metabase.com"
  export METABASE_USERNAME="your@email.com"
  export METABASE_PASSWORD="yourpassword"
  ```

### "Query is in native SQL format"
- This question uses SQL instead of Query Builder
- Cannot be migrated automatically
- Solution: Recreate using Query Builder

### "Table 'xyz' not found"
- The target database doesn't have this table
- Check the database structure
- Use custom mappings if the table has a different name

### "Field 'abc' not found"
- The target table doesn't have this field
- Check field names match
- Use custom mappings if needed

## Custom Mappings

If table or field names differ, add to config.yaml:

```yaml
mapping_rules:
  table_mappings:
    old_customers: customers
    legacy_orders: orders

  field_mappings:
    customers.cust_id: customer_id
    orders.total_price: total_amount
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for more examples
- Check out the API usage for programmatic migrations

## Need Help?

- Run any command with `--help` for details
- Example: `./metabase-migrator migrate --help`
- Open an issue on GitHub for bugs or questions
