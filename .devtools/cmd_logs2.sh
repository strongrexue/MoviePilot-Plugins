dk() { echo 'Ldb456090' | sudo -S -p '' docker "$@" 2>/dev/null; }
echo "=== 最新日志文件"
dk exec moviepilot-v3 sh -c "ls -t /config/logs/ | head -n 5"
echo
echo "=== 最新日志尾部 60 行"
dk exec moviepilot-v3 sh -c "f=\$(ls -t /config/logs/*.log* | head -n1); echo \"file=\$f\"; tail -n 60 \"\$f\""
