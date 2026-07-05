#!/bin/sh

# Dump environment variables to a file that cron jobs can source.
# 用 python shlex.quote 做正确转义（值里的引号/$/反引号/换行都安全），
# 避免 sed 拼接被特殊字符拆错；文件含密钥，umask + chmod 600 双保险。
umask 077
python - <<'PYEOF' > /app/.env.sh
import os
import re
import shlex

NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
for key, value in sorted(os.environ.items()):
    if NAME_PATTERN.match(key):
        print(f"export {key}={shlex.quote(value)}")
PYEOF
chmod 600 /app/.env.sh
echo "Environment variables saved to /app/.env.sh (mode 600)"

# Optionally run the script once on startup for testing
if [ "$RUN_ON_START" = "true" ]; then
  echo "RUN_ON_START=true, running script now..."
  cd /app && python src/main.py
fi

# Start crond in foreground
echo "Starting cron daemon..."
exec crond -f -l 2
