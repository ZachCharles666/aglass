#!/bin/bash
#
# 阶段 1A 采集启动脚本
#
# 功能：
# 1. 启动 API 服务器
# 2. 等待服务器就绪
# 3. 自动开始采集（interval=1.5s）
#
# 使用方法：
#   ./scripts/run_1a_capture.sh
#   ./scripts/run_1a_capture.sh --interval 2.0
#   ./scripts/run_1a_capture.sh --mock  # 开发机模式
#

set -e

# 默认参数
INTERVAL=${INTERVAL:-1.5}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
USE_MOCK=${USE_MOCK_CAMERA:-true}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --mock)
            USE_MOCK=true
            shift
            ;;
        --real)
            USE_MOCK=false
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 切换到项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "========================================"
echo "  AgriCam 阶段 1A 采集"
echo "========================================"
echo "项目目录: $PROJECT_ROOT"
echo "采集间隔: ${INTERVAL}s"
echo "服务端口: $PORT"
echo "Mock 模式: $USE_MOCK"
echo "========================================"

# 导出环境变量
export USE_MOCK_CAMERA=$USE_MOCK
export HOST=$HOST
export PORT=$PORT

# 清理函数
cleanup() {
    echo ""
    echo "正在停止采集..."
    curl -s -X POST "http://localhost:$PORT/capture/stop" > /dev/null 2>&1 || true
    echo "正在停止服务器..."
    kill $SERVER_PID 2>/dev/null || true
    echo "已退出"
}

trap cleanup EXIT INT TERM

# 启动 API 服务器（后台运行）
echo ""
echo "启动 API 服务器..."
python -m uvicorn src.api.server:app --host $HOST --port $PORT &
SERVER_PID=$!

# 等待服务器就绪
echo "等待服务器就绪..."
MAX_WAIT=30
WAITED=0
while ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; do
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "错误: 服务器启动超时"
        exit 1
    fi
done

echo "服务器已就绪"

# 显示健康状态
echo ""
echo "系统状态:"
curl -s "http://localhost:$PORT/health" | python -m json.tool 2>/dev/null || curl -s "http://localhost:$PORT/health"

# 启动采集
echo ""
echo "启动采集循环..."
RESPONSE=$(curl -s -X POST "http://localhost:$PORT/capture/start" \
    -H "Content-Type: application/json" \
    -d "{\"interval_sec\": $INTERVAL}")

echo "响应: $RESPONSE"

# 显示采集状态
echo ""
echo "采集状态:"
curl -s "http://localhost:$PORT/capture/status" | python -m json.tool 2>/dev/null || curl -s "http://localhost:$PORT/capture/status"

echo ""
echo "========================================"
echo "  采集已启动"
echo "  按 Ctrl+C 停止"
echo "========================================"
echo ""
echo "实时状态监控（每 10 秒刷新）:"
echo ""

# 持续显示状态
while true; do
    STATUS=$(curl -s "http://localhost:$PORT/capture/status")
    TOTAL=$(echo $STATUS | python -c "import sys, json; print(json.load(sys.stdin).get('total_count', 0))" 2>/dev/null || echo "?")
    LAST=$(echo $STATUS | python -c "import sys, json; print(json.load(sys.stdin).get('last_capture_time', 'N/A')[:19])" 2>/dev/null || echo "?")
    echo "[$(date '+%H:%M:%S')] 总采集: $TOTAL 张, 最后采集: $LAST"
    sleep 10
done
