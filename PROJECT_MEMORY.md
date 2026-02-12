# AgriCam (aglass) 项目记录

## 项目概述
农业相机系统，运行在 Raspberry Pi 4 Model B 上，使用 IMX708 (Camera Module 3) 摄像头。

## 硬件配置
- **主板**: Raspberry Pi 4 Model B
- **摄像头**: IMX708 (Camera Module 3)，支持 PDAF 自动对焦
- **系统**: Raspberry Pi OS Bookworm 64-bit Lite
- **登录信息**:
  - 用户名: `pi`
  - 密码: `aglass666`
  - WiFi: `Lunatic666` / `wcnmsyr987654321@gun`

## 项目结构
```
aglass/
├── src/
│   ├── api/           # FastAPI 服务
│   │   ├── server.py
│   │   ├── routes_health.py
│   │   ├── routes_camera.py
│   │   ├── routes_profile.py
│   │   └── routes_capture.py
│   ├── camera/        # 相机控制
│   │   ├── cam_base.py    # 基类 + MockCamera
│   │   ├── cam_a.py       # IMX708 控制
│   │   └── af_control.py  # 自动对焦控制器
│   ├── pipeline/      # 采集流水线
│   │   └── capture_loop.py
│   ├── store/         # 数据存储
│   │   ├── models.py      # Pydantic 模型
│   │   ├── db.py          # SQLite (WAL模式)
│   │   ├── repo.py        # ProfileRepository
│   │   └── file_store.py  # 双写 JSON + SQLite
│   ├── inference/     # 推理 (待实现)
│   └── utils/         # 工具
│       ├── logger.py
│       ├── time_id.py
│       └── sysinfo.py
├── configs/
│   └── device.yaml
├── scripts/
│   ├── deploy_rpi.sh      # 树莓派部署脚本
│   ├── hardware_test.sh   # 硬件测试脚本
│   ├── test_af_lock.py    # 对焦稳定性测试
│   └── export_summary.py  # 数据导出
├── data/
│   ├── images/        # 图片存储
│   ├── profiles/      # Profile 配置
│   ├── logs/
│   └── profiles/profiles.db  # SQLite 数据库
└── pyproject.toml
```

## 已完成功能 (4轮开发)

### 第1轮: 项目初始化
- 目录结构
- pyproject.toml 依赖配置
- 基础模块 (logger, time_id, sysinfo)
- FastAPI 服务器框架
- /health 端点

### 第2轮: Cam-A 对焦控制
- CamA 类 (IMX708 控制)
- MockCamA (开发测试用)
- one_shot_af() 单次自动对焦
- lock_focus() 焦距锁定
- get_clarity_score() 清晰度评分
- AFController 包装类
- /camera/cam-a/af/* API 端点

### 第3轮: Profile 系统
- FocusProfile 模型 (Pydantic)
- SQLite 数据库 (WAL模式)
- ProfileRepository CRUD
- /profile/* API 端点

### 第4轮: 采集循环
- CaptureLoop 后台线程采集
- FileStore 双写元数据 (JSON + SQLite)
- /capture/* API 端点
- export_summary.py 导出脚本

## 测试状态

### 软件测试 (Mac Mock模式) ✅
- 第1轮: /health 端点 ✅
- 第2轮: 对焦 API ✅
- 第3轮: Profile CRUD ✅
- 第4轮: 采集循环 ✅

### 硬件测试 (树莓派) ✅
- 树莓派系统烧录 ✅
- 相机连接 ✅
- 项目部署 ✅ (已修复 numpy 依赖冲突)
- 硬件测试脚本 ⏳ 待运行

## 关键技术点

### WiFi配置 (Bookworm)
新版 Raspberry Pi OS Bookworm 不再支持 boot 分区的 `wpa_supplicant.conf`，需要使用 `firstrun.sh` 脚本在首次启动时通过 NetworkManager 配置。

### CSI摄像头
- **不支持热插拔**，必须关机后连接
- 使用 picamera2 库控制
- PDAF 自动对焦，不使用连续对焦模式

### 依赖管理
- picamera2 和 RPi.GPIO 为可选依赖 `[rpi]`
- Mac 开发使用 MockCamera
- opencv-python-headless 避免 GUI 依赖

## 常用命令

### 树莓派
```bash
# SSH 连接
ssh pi@192.168.31.132

# 启动服务
cd ~/aglass
source venv/bin/activate
USE_MOCK_CAMERA=false python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# 使用 systemd
sudo systemctl start agricam
sudo systemctl status agricam
journalctl -u agricam -f

# 硬件测试
./scripts/hardware_test.sh
```

### Mac 开发
```bash
cd /Users/zc/ai-hardware/aglass
source venv/bin/activate
USE_MOCK_CAMERA=true python -m uvicorn src.api.server:app --port 8000

# 上传到树莓派
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' . pi@192.168.31.132:~/aglass/
```

## 下一步
1. **运行硬件测试脚本**: 运行 `./scripts/hardware_test.sh` 来全面检测硬件功能。
2. **测试核心 API 功能**:
   - **拍照**: 调用 `/capture` 相关端点，确认照片成功保存在 `data/images/`。
   - **配置**: 调用 `/profile` 相关端点 (增、删、改、查)，确认配置正确保存。
   - **对焦**: 调用 `/camera/cam-a/af` 相关端点，测试自动和手动对焦功能。
3. **验证数据存储**: 检查图片文件和 `data/db.sqlite` 数据库中的元数据是否一致。
4. **(可选) 对焦稳定性测试**: 运行 `scripts/test_af_lock.py` 脚本，长时间测试对焦锁定是否稳定。

---
最后更新: 2026-02-12
