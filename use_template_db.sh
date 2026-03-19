#!/bin/bash
# Back up walks.db and replace it with walks_template.db for testing.
# Restore with: cp walks.db.bak walks.db

set -e
cd "$(dirname "$0")"

if [ ! -f walks_template.db ]; then
    echo "Error: walks_template.db not found. Run: python create_template_db.py"
    exit 1
fi

if [ -f walks.db ]; then
    cp walks.db walks.db.bak2
    echo "Backed up walks.db → walks.db.bak2"
fi

cp walks_template.db walks.db
echo "Copied walks_template.db → walks.db"
echo "Restore with: cp walks.db.bak2 walks.db"
