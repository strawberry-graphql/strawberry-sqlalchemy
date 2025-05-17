#!/bin/bash

echo "🔍 Checking PostgreSQL service status..."
if ! pg_isready > /dev/null 2>&1; then
  echo "⚠️  PostgreSQL is not ready. Starting the service..."
  sudo service postgresql start
  echo "✅ PostgreSQL running."
else
  echo "✅ PostgreSQL is already running."
fi
