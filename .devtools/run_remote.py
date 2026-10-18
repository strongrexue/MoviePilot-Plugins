"""在 NAS 上执行一段远程 shell（读命令文件，避免 PowerShell 引号地狱）。

用法：python .devtools/run_remote.py .devtools/cmd.sh
凭据取自 AGENTS.md（192.168.50.134 / DBOND）。
"""
import sys
from pathlib import Path

import paramiko

HOST = sys.argv[2] if len(sys.argv) > 2 else "192.168.50.134"
USER = "DBOND"
PASSWORD = "Ldb456090"

command = Path(sys.argv[1]).read_text(encoding="utf-8")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=20,
               look_for_keys=False, allow_agent=False)
try:
    stdin, stdout, stderr = client.exec_command(command, timeout=300)
    sys.stdout.write(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        sys.stdout.write("\n[stderr]\n" + err)
    sys.exit(stdout.channel.recv_exit_status())
finally:
    client.close()
