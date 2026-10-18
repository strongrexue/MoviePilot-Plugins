dk() { echo 'Ldb456090' | sudo -S -p '' docker "$@" 2>/dev/null; }
echo "=== /config/logs"
dk exec moviepilot-v3 sh -c "ls -la /config/logs | tail -n 12"
echo
echo "=== 最近 30 分钟：这个任务的日志（去重前的原始行，最多 60 行）"
dk exec moviepilot-v3 sh -c "grep -h '恢复订阅搜索队列' /config/logs/*.log 2>/dev/null | tail -n 40"
echo
echo "=== 最近出现的「正在运行 ...」重叠告警"
dk exec moviepilot-v3 sh -c "grep -h '正在运行' /config/logs/*.log 2>/dev/null | tail -n 30"
echo
echo "=== 订阅搜索相关关键行（开始处理 / 任务结束 / 结束本轮）"
dk exec moviepilot-v3 sh -c "grep -hE 'subscribesearch|订阅搜索|开始处理订阅搜索任务|本轮搜索任务结束|本轮搜索已' /config/logs/*.log 2>/dev/null | tail -n 60"
