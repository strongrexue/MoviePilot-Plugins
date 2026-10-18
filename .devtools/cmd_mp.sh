dk() { echo 'Ldb456090' | sudo -S -p '' docker "$@" 2>/dev/null; }
echo "=== 首次启动时间 / 版本"
dk inspect moviepilot-v3 --format '{{.State.StartedAt}} | {{.Config.Image}}'
echo "=== 容器内宿主版本"
dk exec moviepilot-v3 sh -c "grep -o '\"version\":.*' /app/package.json 2>/dev/null | head -n1; grep -rn 'APP_VERSION\\|__version__' /app/app/__init__.py 2>/dev/null | head -n3"
echo "=== 插件版本"
dk exec moviepilot-v3 sh -c "grep -o 'plugin_version = \"[^\"]*\"' /app/app/plugins/tgmediacenter/__init__.py 2>/dev/null; grep -o \"FRONTEND_VERSION = '[^']*'\" /app/app/plugins/tgmediacenter/src/components/version.js 2>/dev/null"
echo "=== 数据库环境"
dk exec moviepilot-v3 sh -c "env | grep -iE '^DB_|^PG|POSTGRES' | sort"
echo "=== /config 目录"
dk exec moviepilot-v3 sh -c "ls -la /config | head -n 20"
