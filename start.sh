#!/usr/bin/env bash
# ================================================================
# start.sh — Системаи ҳозиршавиро оғоз кун
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Рангҳо
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  🏫 Dahua Attendance System${NC}"
echo -e "${GREEN}======================================${NC}"

# Python version
PYTHON=$(which python3 || which python)
if [ -z "$PYTHON" ]; then
    echo -e "${RED}❌ Python топилмад!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python:${NC} $($PYTHON --version)"

# .env файл
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}⚠️  .env нашуд. .env.example-ро нусха мекунам...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}   Лутфан .env-ро танзим кунед!${NC}"
    else
        echo -e "${RED}❌ .env файл нест!${NC}"
        exit 1
    fi
fi

# Директорияҳо
mkdir -p logs data exports

# Dependencies
echo -e "${GREEN}📦 Installing dependencies...${NC}"
$PYTHON -m pip install -r requirements.txt -q

# Тест
if [ "$1" == "--test" ]; then
    echo -e "${GREEN}🧪 Running tests...${NC}"
    $PYTHON -m tests.test_system
    exit 0
fi

# Seed
if [ "$1" == "--seed" ]; then
    echo -e "${GREEN}🌱 Seeding test data...${NC}"
    $PYTHON run_all.py --seed
    exit 0
fi

# Run
echo -e "${GREEN}🚀 Starting system...${NC}"
echo ""

if [ "$1" == "--test-mode" ]; then
    $PYTHON run_all.py --test-mode "$@"
else
    $PYTHON run_all.py "$@"
fi
