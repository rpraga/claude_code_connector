# Migration Verification Guide

After migrating Metabase questions, it's crucial to verify that the migrated questions produce the same results as the source questions. This guide explains how to use the verification features.

## Why Verify?

Migrated questions might produce different results due to:
- **Data type differences** between databases
- **Rounding variations** in numeric calculations
- **Date/time format differences**
- **Collation differences** in string comparisons
- **Field mapping errors**
- **Database-specific behaviors**

**Verification ensures your migration was successful!**

## Quick Start

### Basic Verification

```bash
# Verify a single migrated question
./metabase-migrator verify 123 456

# Where:
#   123 = source question ID
#   456 = migrated question ID
```

### With Sampling

```bash
# Compare random sample of 100 rows (default)
./metabase-migrator verify 123 456 --sample-size 100

# Compare ALL rows
./metabase-migrator verify 123 456 --sample-size 0

# Compare first 1000 rows only
./metabase-migrator verify 123 456 --limit 1000
```

### Detailed Output

```bash
# Show detailed differences
./metabase-migrator verify 123 456 --show-details
```

## Commands

### 1. `verify` - Single Question Verification

Verifies that a migrated question produces the same results.

```bash
./metabase-migrator verify SOURCE_ID TARGET_ID [OPTIONS]
```

**Arguments:**
- `SOURCE_ID` - Original question ID
- `TARGET_ID` - Migrated question ID

**Options:**
- `--sample-size N` - Number of rows to sample (default: 100, use 0 for all)
- `--limit N` - Maximum rows to fetch from each question
- `--show-details` - Show detailed differences
- `--config PATH` - Path to configuration file

**Example Output (PASSED):**
```
ℹ Verifying migration: Question 123 → 456
ℹ Executing queries and comparing results...
ℹ Using random sample of 100 rows

Verification Results:
  Source Question: Monthly Sales Report (ID: 123)
  Target Question: Monthly Sales Report (Migrated) (ID: 456)

Execution Times:
  Source: 1.23s
  Target: 1.45s

Statistics:
  Source Rows: 1000
  Target Rows: 1000
  Source Columns: 5
  Target Columns: 5
  Rows Checked: 100

✓ VERIFICATION PASSED
  The migrated question produces the same results as the source.
```

**Example Output (FAILED):**
```
✗ VERIFICATION FAILED
  The migrated question produces different results.

⚠ Found 2 type(s) of differences:

  • row_count_mismatch:
    Source: 1000 rows
    Target: 998 rows
    Difference: 2 rows

  • data_value_mismatch:
    Total mismatched values: 5
    First 10 differences:
      Row 42, Column 'total_amount': 1234.56 → 1234.57
      Row 103, Column 'customer_name': 'John Doe' → 'JOHN DOE'

ℹ Use --show-details to see detailed differences
```

### 2. `batch-verify` - Multiple Questions

Verify multiple migrated questions at once using a CSV mapping file.

```bash
./metabase-migrator batch-verify MAPPING_FILE [OPTIONS]
```

**Arguments:**
- `MAPPING_FILE` - CSV file with source_id,target_id pairs

**Options:**
- `--sample-size N` - Number of rows to sample (default: 100)
- `--show-failures` - Show detailed failures
- `--config PATH` - Path to configuration file

**Mapping File Format (mappings.csv):**
```csv
123,456
124,457
125,458
126,459
```

**Example Usage:**
```bash
./metabase-migrator batch-verify mappings.csv --show-failures
```

**Example Output:**
```
ℹ Loaded 4 question pair(s) from mappings.csv
ℹ Verifying 4 question pair(s)...

Batch Verification Results:
  Total Verified: 4
  Passed: 3
  Failed: 1
  Errors: 0
  Pass Rate: 75.0%

⚠ Failed Verifications:

1. Monthly Sales Report (124 → 457)
   • row_count_mismatch
   • data_value_mismatch
```

## What Gets Compared

### 1. Row Count
Compares the total number of rows returned by each question.

### 2. Column Count
Verifies both questions return the same number of columns.

### 3. Column Names
Checks that column names match (exact match).

### 4. Column Types
Validates that column data types are compatible.

### 5. Data Values
Compares actual data values row-by-row:
- **Numeric values**: Uses tolerance for floating-point (1e-9)
- **Strings**: Exact match (case-sensitive)
- **Nulls**: Properly handled
- **Dates**: Exact match

## Sampling Strategies

### Full Comparison (Small Datasets)

```bash
# Compare ALL rows (no sampling)
./metabase-migrator verify 123 456 --sample-size 0
```

**When to use:**
- Questions with < 1000 rows
- Critical questions requiring 100% verification
- Final validation before production

### Random Sampling (Large Datasets)

```bash
# Compare random sample of 100 rows (default)
./metabase-migrator verify 123 456

# Custom sample size
./metabase-migrator verify 123 456 --sample-size 500
```

**When to use:**
- Questions with > 1000 rows
- Quick verification during development
- Regular spot-checks

**How it works:**
1. Fetches all rows from both questions
2. Randomly selects N rows using the same indices
3. Compares only the sampled rows
4. Statistical confidence increases with sample size

### Limited Fetch (Very Large Datasets)

```bash
# Fetch only first 1000 rows, sample 100
./metabase-migrator verify 123 456 --limit 1000 --sample-size 100
```

**When to use:**
- Questions with millions of rows
- Network/performance constraints
- Quick smoke tests

## Interpretation Guide

### ✓ VERIFICATION PASSED

**Meaning**: Migrated question produces identical results

**Action**: Migration successful! Question is ready for use.

### ✗ row_count_mismatch

**Meaning**: Different number of rows returned

**Possible Causes:**
- Missing data in target database
- Filter differences
- Join behavior differences
- Database-specific query execution

**Investigation:**
1. Check target database has all data
2. Review filter conditions
3. Check join types and conditions
4. Verify aggregation logic

### ✗ column_count_mismatch

**Meaning**: Different number of columns

**Possible Causes:**
- Field mapping error
- Missing fields in target table
- Extra fields added during migration

**Investigation:**
1. Review field mappings
2. Check target table structure
3. Verify custom fields migrated correctly

### ✗ column_name_mismatch

**Meaning**: Column names don't match

**Possible Causes:**
- Field name mapping differences
- Case sensitivity differences

**Investigation:**
1. Review custom field mappings in config
2. Check if case-sensitivity matters
3. Verify field aliases

### ✗ data_value_mismatch

**Meaning**: Some data values are different

**Possible Causes:**
- **Numeric precision**: Floating-point rounding (123.456 vs 123.457)
- **String case**: Case differences ('John' vs 'JOHN')
- **Date formats**: Timezone or format differences
- **Data sync**: Source and target databases out of sync

**Investigation:**
1. Check data types match
2. Review numeric precision/rounding
3. Check string collation settings
4. Verify data is synchronized
5. Look at specific rows with differences

## Common Scenarios

### Scenario 1: Simple Table Migration

```bash
# Migrate
./metabase-migrator migrate 100 2

# Output: Created question ID 500

# Verify
./metabase-migrator verify 100 500
```

### Scenario 2: Nested Question Migration

```bash
# Migrate with dependencies
./metabase-migrator migrate 300 2 --allow-nested

# Output:
#   Created question 600 (dependency)
#   Created question 601 (dependency)
#   Created question 602 (main)

# Verify all
cat > verify.csv <<EOF
298,600
299,601
300,602
EOF

./metabase-migrator batch-verify verify.csv
```

### Scenario 3: Production Migration with Full Verification

```bash
#!/bin/bash
# production_migrate.sh

QUESTIONS=(101 102 103 104 105)
TARGET_DB=2
VERIFY_MAP="verify_$(date +%Y%m%d).csv"

echo "source_id,target_id" > $VERIFY_MAP

for Q in "${QUESTIONS[@]}"; do
  echo "Migrating question $Q..."

  # Migrate
  RESULT=$(./metabase-migrator migrate $Q $TARGET_DB --collection-id 10 2>&1)

  # Extract created ID
  TARGET_ID=$(echo "$RESULT" | grep "ID:" | awk '{print $2}')

  echo "$Q,$TARGET_ID" >> $VERIFY_MAP
done

echo "Verifying all migrations..."
./metabase-migrator batch-verify $VERIFY_MAP --show-failures
```

### Scenario 4: Continuous Verification

```bash
# Create mapping file during migration
./metabase-migrator migrate 200 2 | tee migration.log

# Extract IDs and verify later
# (Parse migration.log to build mapping file)

./metabase-migrator batch-verify mappings.csv
```

## Tolerance for Floating-Point Numbers

The verifier uses a tolerance of `1e-9` for floating-point comparisons.

**Examples:**
```
123.4567890 vs 123.4567891  ✓ MATCH (difference < 1e-9)
123.45 vs 123.46            ✗ MISMATCH (difference > 1e-9)
```

**If you need custom tolerance**, modify `verifier.py`:
```python
def _values_equal(self, val1, val2, tolerance=1e-6):  # Looser tolerance
    ...
```

## Best Practices

### 1. Always Verify After Migration

```bash
# Bad: Migrate and assume it worked
./metabase-migrator migrate 123 2

# Good: Migrate and verify
./metabase-migrator migrate 123 2
# Created: Question 456
./metabase-migrator verify 123 456
```

### 2. Use Appropriate Sample Size

```
Rows in Question    Recommended Sample Size
─────────────────────────────────────────────
< 100               0 (all rows)
100 - 1,000         100
1,000 - 10,000      500
10,000 - 100,000    1,000
> 100,000           1,000 with --limit
```

### 3. Document Your Verification Results

```bash
# Save verification output
./metabase-migrator verify 123 456 > verification_123_456.log

# Batch verify and save summary
./metabase-migrator batch-verify mappings.csv > batch_verification.log
```

### 4. Investigate ALL Failures

Don't assume minor differences are acceptable:
- Check each failure
- Understand root cause
- Fix mapping/data issues
- Re-migrate if necessary

### 5. Verify Production Migrations Twice

```bash
# First: Sample verification (quick)
./metabase-migrator verify 123 456 --sample-size 100

# If passed, full verification (thorough)
./metabase-migrator verify 123 456 --sample-size 0
```

## Troubleshooting

### "Execution error: 403 Forbidden"

**Problem**: Don't have permission to execute questions

**Solution**: Ensure your Metabase credentials have permission to run queries

### "Timeout errors"

**Problem**: Questions take too long to execute

**Solution**: Use `--limit` to fetch fewer rows:
```bash
./metabase-migrator verify 123 456 --limit 1000
```

### "Row count matches but data differs"

**Problem**: Same number of rows but different data

**Possible causes**:
- Data changed between executions
- Different sort orders (use ORDER BY in questions)
- Time-dependent queries (NOW(), CURRENT_DATE)

**Solution**:
- Add explicit ORDER BY to questions
- Use fixed date ranges instead of relative dates
- Ensure databases are synchronized

### "Memory errors with large datasets"

**Problem**: Not enough memory to compare large result sets

**Solution**: Use sampling and limits:
```bash
./metabase-migrator verify 123 456 --limit 10000 --sample-size 1000
```

## Automated Verification in CI/CD

### GitHub Actions Example

```yaml
name: Verify Metabase Migration

on: [push]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Verify migrations
        env:
          METABASE_URL: ${{ secrets.METABASE_URL }}
          METABASE_API_KEY: ${{ secrets.METABASE_API_KEY }}
        run: |
          ./metabase-migrator batch-verify mappings.csv --show-failures
```

## API Usage

Programmatic verification in Python:

```python
from metabase_migrator.api_client import MetabaseAPIClient
from metabase_migrator.verifier import QuestionVerifier
from metabase_migrator.config import Config

config = Config('config.yaml')

with MetabaseAPIClient(config.get_metabase_url(), config.get_credentials()) as client:
    verifier = QuestionVerifier(client)

    # Single verification
    report = verifier.verify_migration(
        source_question_id=123,
        target_question_id=456,
        sample_size=100
    )

    if report['verified']:
        print("✓ Verification passed!")
    else:
        print("✗ Verification failed!")
        for diff in report['comparison']['differences']:
            print(f"  - {diff['type']}")

    # Batch verification
    pairs = [(123, 456), (124, 457), (125, 458)]
    reports = verifier.batch_verify(pairs, sample_size=100)

    summary = verifier.get_summary_report(reports)
    print(f"Pass rate: {summary['pass_rate']:.1f}%")
```

## Verification Checklist

Before deploying migrated questions to production:

- [ ] Verified with random sample (--sample-size 100)
- [ ] Reviewed any warnings or differences
- [ ] Verified with full dataset (--sample-size 0) for critical questions
- [ ] Checked execution times are acceptable
- [ ] Tested with current production data
- [ ] Documented verification results
- [ ] Investigated and resolved any failures
- [ ] Re-verified after making fixes

## Summary

✅ **Always verify migrations** - Don't assume they work

✅ **Use appropriate sampling** - Balance speed vs thoroughness

✅ **Investigate failures** - Understand root causes

✅ **Document results** - Keep verification records

✅ **Automate when possible** - CI/CD integration

The verification system gives you confidence that your migrated questions produce correct results! 🎯
