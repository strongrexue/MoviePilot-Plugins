echo "=== sudo -n"; sudo -n true 2>&1 | head -n 2
echo "=== docker ps (sudo -S)"
echo 'Ldb456090' | sudo -S -p '' docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>&1 | head -n 30
