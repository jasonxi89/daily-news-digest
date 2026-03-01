#!/bin/sh

# Dump environment variables to a file that cron jobs can source
env | sed 's/^\(.*\)=\(.*\)$/export \1="\2"/' > /app/.env.sh
echo "Environment variables saved to /app/.env.sh"

# Optionally run the script once on startup for testing
if [ "$RUN_ON_START" = "true" ]; then
  echo "RUN_ON_START=true, running script now..."
  cd /app && python src/main.py
fi

# Start crond in foreground
echo "Starting cron daemon..."
exec crond -f -l 2
