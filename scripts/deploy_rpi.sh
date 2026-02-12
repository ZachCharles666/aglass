#!/bin/bash
#
# 树莓派部署脚本
#
# 使用方法：
#   1. 将项目上传到树莓派
#   2. cd ~/aglass
#   3. chmod +x scripts/deploy_rpi.sh
#   4. ./scripts/deploy_rpi.sh
#

set -e

echo "========================================"
echo "  AgriCam 树莓派部署脚本"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查是否在树莓派上运行
check_platform() {
    log_info "检查运行平台..."
    if [[ ! -f /proc/device-tree/model ]]; then
        log_error "此脚本仅支持在树莓派上运行"
        exit 1
    fi

    MODEL=$(cat /proc/device-tree/model)
    log_info "检测到: $MODEL"
}

# 检查相机是否启用
check_camera() {
    log_info "检查相机状态..."

    # 检查相机是否启用
    if ! vcgencmd get_camera 2>/dev/null | grep -q "detected=1"; then
        log_warn "相机未检测到，请确保："
        log_warn "  1. 相机已正确连接到 CAM 端口"
        log_warn "  2. 已通过 raspi-config 启用相机"
        log_warn "  运行: sudo raspi-config → Interface Options → Camera → Enable"
        read -p "是否继续部署？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_info "相机已检测到"
    fi
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖..."

    sudo apt update
    sudo apt install -y \
        python3-pip \
        python3-venv \
        python3-picamera2 \
        python3-libcamera \
        libcap-dev \
        sqlite3

    log_info "系统依赖安装完成"
}

# 创建虚拟环境
setup_venv() {
    log_info "设置 Python 虚拟环境..."

    # 获取项目根目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_ROOT"

    # 创建虚拟环境（使用系统 site-packages 以访问 picamera2）
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv --system-site-packages
        log_info "虚拟环境已创建"
    else
        log_info "虚拟环境已存在"
    fi

    # 激活虚拟环境
    source venv/bin/activate

    # 升级 pip
    pip install --upgrade pip
}

# 安装项目依赖
install_project_deps() {
    log_info "安装项目依赖..."

    # 安装核心依赖
    pip install -e .

    # 关键修复：卸载由 pip 安装的 numpy，强制使用系统版本以兼容 picamera2
    log_info "卸载 pip 安装的 numpy 以确保与系统 picamera2 兼容..."
    pip uninstall -y numpy

    log_info "项目依赖安装完成"
}

# 配置环境
configure_env() {
    log_info "配置环境..."

    # 创建 .env 文件
    if [[ ! -f ".env" ]]; then
        cat > .env << EOF
# AgriCam 环境配置
# 生产环境：使用真实相机
USE_MOCK_CAMERA=false

# API 配置
HOST=0.0.0.0
PORT=8000

# 云端 API（可选）
CLOUD_API_BASE=http://localhost:8080
CLOUD_API_KEY=test_key_12345
EOF
        log_info ".env 文件已创建"
    else
        log_info ".env 文件已存在"
    fi

    # 创建数据目录
    mkdir -p data/images data/profiles data/logs data/uploads_queue data/exports

    log_info "环境配置完成"
}

# 测试相机
test_camera() {
    log_info "测试相机..."

    # 使用 libcamera 测试
    if command -v libcamera-hello &> /dev/null; then
        log_info "运行 libcamera-hello（3秒预览）..."
        timeout 3 libcamera-hello -t 3000 2>/dev/null || true
    fi

    # 使用 picamera2 测试
    log_info "测试 picamera2..."
    python3 << 'PYEOF'
try:
    from picamera2 import Picamera2
    cameras = Picamera2.global_camera_info()
    print(f"检测到 {len(cameras)} 个相机:")
    for i, cam in enumerate(cameras):
        print(f"  [{i}] {cam.get('Model', 'Unknown')}")
    print("✅ picamera2 测试通过")
except Exception as e:
    print(f"❌ picamera2 测试失败: {e}")
    exit(1)
PYEOF

    log_info "相机测试完成"
}

# 创建 systemd 服务
create_service() {
    log_info "创建 systemd 服务..."

    PROJECT_ROOT="$(pwd)"
    USER=$(whoami)

    sudo tee /etc/systemd/system/agricam.service > /dev/null << EOF
[Unit]
Description=AgriCam API Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
Environment="PATH=$PROJECT_ROOT/venv/bin:/usr/bin"
Environment="USE_MOCK_CAMERA=false"
ExecStart=$PROJECT_ROOT/venv/bin/python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    log_info "systemd 服务已创建"
    log_info "  启动: sudo systemctl start agricam"
    log_info "  停止: sudo systemctl stop agricam"
    log_info "  开机启动: sudo systemctl enable agricam"
}

# 运行快速测试
run_quick_test() {
    log_info "运行快速测试..."

    # 启动服务器（后台）
    USE_MOCK_CAMERA=false timeout 15 python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!

    # 等待服务器启动
    sleep 5

    # 测试健康端点
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        log_info "✅ API 服务器正常"
    else
        log_error "❌ API 服务器测试失败"
    fi

    # 停止服务器
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true

    log_info "快速测试完成"
}

# 主函数
main() {
    check_platform
    check_camera
    install_system_deps
    setup_venv
    install_project_deps
    configure_env
    test_camera
    create_service
    run_quick_test

    echo ""
    echo "========================================"
    echo "  部署完成！"
    echo "========================================"
    echo ""
    echo "后续步骤："
    echo "  1. 启动服务: sudo systemctl start agricam"
    echo "  2. 查看日志: journalctl -u agricam -f"
    echo "  3. 访问 API: http://$(hostname -I | awk '{print $1}'):8000/health"
    echo ""
    echo "或手动启动："
    echo "  source venv/bin/activate"
    echo "  USE_MOCK_CAMERA=false python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000"
    echo ""
}

# 运行
main "$@"
