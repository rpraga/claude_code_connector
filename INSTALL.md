# Installation Guide

## Quick Start (Recommended)

```bash
cd /home/rpraga/migrator/claude_code_connector

# Run setup script
./setup_venv.sh

# Activate virtual environment
source venv/bin/activate

# You're ready!
./metabase-migrator test-connection
```

## Why Virtual Environment?

Modern Python systems (Debian 12+, Ubuntu 23.04+) protect the system Python environment. You must use a **virtual environment** to install packages.

## Manual Setup

### Step 1: Create Virtual Environment

```bash
cd /home/rpraga/migrator/claude_code_connector

# Create venv
python3 -m venv venv
```

### Step 2: Activate Virtual Environment

```bash
# Activate (Linux/Mac)
source venv/bin/activate

# Your prompt will change to show (venv)
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
# Test the migrator
./metabase-migrator --version

# Should output: version 1.0.0
```

## Configuration

### Create Config File

```bash
# Generate example config
./metabase-migrator init-config

# Copy and edit
cp config.example.yaml config.yaml
nano config.yaml
```

### Edit config.yaml

```yaml
metabase_url: https://your-metabase-instance.com
username: your-email@example.com
password: your-password
```

### Test Connection

```bash
./metabase-migrator test-connection
```

## Using the Migrator

### Always Activate First

```bash
# Every time you open a new terminal
cd /home/rpraga/migrator/claude_code_connector
source venv/bin/activate

# Now run commands
./metabase-migrator list-databases
```

### When Done

```bash
# Deactivate virtual environment
deactivate
```

## Alternative: System-Wide Installation with pipx

If you want to use the migrator from anywhere without activating venv:

```bash
# Install pipx
sudo apt install pipx
pipx ensurepath

# Install migrator globally
cd /home/rpraga/migrator/claude_code_connector
pipx install -e .

# Now run from anywhere
metabase-migrator test-connection
```

## Alternative: System Packages (Not Recommended)

System packages may be outdated:

```bash
sudo apt install \
  python3-requests \
  python3-yaml \
  python3-click \
  python3-dotenv \
  python3-tabulate \
  python3-colorama
```

## Troubleshooting

### "externally-managed-environment" Error

This means you tried to install without a virtual environment.

**Solution:** Use the virtual environment as shown above.

### "python3: command not found"

Install Python 3:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

### "No module named 'venv'"

Install python3-venv:

```bash
sudo apt install python3-venv
```

### Permission Errors

Don't use `sudo pip`. Always use virtual environment.

### Virtual Environment Not Activating

Make sure you're in the correct directory:

```bash
cd /home/rpraga/migrator/claude_code_connector
ls venv/  # Should show bin/ lib/ etc.
source venv/bin/activate
```

## Development Setup

If you want to modify the code:

```bash
# Create venv and install in editable mode
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Now changes to the code take effect immediately
```

## Updating

```bash
# Activate venv
source venv/bin/activate

# Update dependencies
pip install --upgrade -r requirements.txt

# Or reinstall everything
pip install --force-reinstall -r requirements.txt
```

## Uninstall

```bash
# Remove virtual environment
rm -rf venv/

# Remove config (if desired)
rm config.yaml

# Keep the code for later use
```

## Helper Scripts

### Create Activation Alias

Add to your `~/.bashrc`:

```bash
alias metabase-migrator='cd /home/rpraga/migrator/claude_code_connector && source venv/bin/activate'
```

Then:

```bash
# Activate from anywhere
metabase-migrator

# Run commands
./metabase-migrator test-connection
```

### Create Wrapper Script

Create `/usr/local/bin/metabase-migrator`:

```bash
#!/bin/bash
cd /home/rpraga/migrator/claude_code_connector
source venv/bin/activate
exec python -m metabase_migrator.cli "$@"
```

```bash
sudo chmod +x /usr/local/bin/metabase-migrator
```

Now run from anywhere:

```bash
metabase-migrator test-connection
```

## Docker Alternative

If you prefer Docker:

```bash
# Build image
docker build -t metabase-migrator .

# Run with config
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml \
  metabase-migrator test-connection
```

See `Dockerfile` for details.

## Summary

**Recommended workflow:**

```bash
# One-time setup
cd /home/rpraga/migrator/claude_code_connector
./setup_venv.sh

# Every time you use it
source venv/bin/activate
./metabase-migrator <command>
deactivate  # when done
```

**Why this error happens:**
- Python 3.11+ on Debian/Ubuntu protects system packages
- Prevents conflicts with system tools
- Virtual environments are isolated and safe
- This is Python best practice

**The fix:**
- Always use `venv` (virtual environment)
- Never use `sudo pip`
- Activate before running commands
