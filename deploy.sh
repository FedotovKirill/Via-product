#!/usr/bin/env bash
# Zero-Config запуск Via
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

echo "[DEPLOY] 🚀 Запуск Via..."

# Генерируем .env если нет или пустой (без зависимости от python3 на хосте)
if [ ! -f "$ENV_FILE" ] || ! grep -q "APP_MASTER_KEY=" "$ENV_FILE" 2>/dev/null; then
    echo "[DEPLOY] 🔑 Generating credentials..."
    # Пробуем python3, если нет — python, иначе openssl fallback
    if command -v python3 &>/dev/null; then
        ENV_FILE_PATH="$ENV_FILE" python3 "${SCRIPT_DIR}/scripts/init_env.py" 2>/dev/null
    elif command -v python &>/dev/null; then
        ENV_FILE_PATH="$ENV_FILE" python "${SCRIPT_DIR}/scripts/init_env.py" 2>/dev/null
    else
        # Fallback без python: генерируем через openssl
        PG_PASS=$(openssl rand -base64 32)
        MASTER_KEY=$(openssl rand -hex 16)
        cat > "$ENV_FILE" << EOF
POSTGRES_PASSWORD=${PG_PASS}
APP_MASTER_KEY=${MASTER_KEY}
EOF
        echo "[DEPLOY] ✅ Credentials generated (openssl fallback)"
    fi
else
    echo "[DEPLOY] ✅ .env exists, skipping credential generation"
fi

# Запускаем сервисы
echo "[DEPLOY] 📦 Building and starting containers..."
docker compose up --build -d

# Ждём healthy status
echo "[DEPLOY] ⏳ Waiting for services to be ready..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker compose ps --format json 2>/dev/null | grep -q '"HealthStatus":"healthy"' || \
       docker compose ps 2>/dev/null | grep -q "healthy"; then
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done

echo ""
echo "[DEPLOY] ✅ Via is running!"
echo ""
echo "  Web UI:   http://localhost:8080/setup"
echo "  Status:   docker compose ps"
echo "  Logs:     docker compose logs -f"
echo ""

