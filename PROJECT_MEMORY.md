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
│   ├── inference/     # 推理模块 (占位，Phase 2 实现边缘推理)
│   │   └── __init__.py
│   └── utils/         # 工具
│       ├── logger.py
│       ├── time_id.py
│       └── sysinfo.py
├── training/          # 云端训练 (Phase 1 新增)
│   ├── README.md              # PAI-DSW 训练指南
│   ├── requirements.txt       # ultralytics, roboflow, onnx
│   ├── download_datasets.py   # 数据集下载/打包/解包
│   ├── train_plant_detector.py  # Model A 训练
│   ├── train_flower_detector.py # Model B 训练
│   ├── export_models.py       # 导出 ONNX/NCNN
│   ├── validate_models.py     # 验证 mAP + 速度
│   └── configs/
│       ├── plant_detector.yaml  # Model A 超参数
│       └── flower_detector.yaml # Model B 超参数
├── configs/
│   └── device.yaml    # 含双模型推理配置
├── models/            # 训练产出 (.gitignore 忽略 .pt/.onnx)
│   └── .gitkeep
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

## Phase 1 推理模块：云端训练 (进行中)

### 双模型架构
| 模型 | 数据集 | 类别 | 用途 |
|------|--------|------|------|
| plant_detector (Model A) | PlantDoc (~2600张, 13类) | Apple, Blueberry, Cherry 等叶片/果实 | Cam-A 日常监测：植物种类识别 |
| flower_detector (Model B) | 花朵检测 (二分类) | flower, bud | 检测到花朵 → 触发 Cam-B burst 拍摄 |

### device.yaml 推理配置
```yaml
inference:
  plant_detector:
    model_path: "models/plant_detector_v1.pt"
    conf_threshold: 0.3
    camera: cam_a
  flower_detector:
    model_path: "models/flower_detector_v1.pt"
    conf_threshold: 0.4
    camera: cam_a
    trigger_burst: true  # 触发 Cam-B 高分辨率拍摄
```

### 训练环境
- **平台**: 阿里云 PAI-DSW (Jupyter + GPU)
- **GPU**: V100 (16GB) 或 A10
- **工作目录**: `/mnt/workspace/aglass`
- **注意**: PAI-DSW 访问 Roboflow 网络不稳定，使用 `--pack`/`--unpack` 模式本地下载数据集后上传

### 训练流水线
```bash
# 本地 Mac 下载并打包数据集
export ROBOFLOW_API_KEY="your_key"
python training/download_datasets.py          # 下载
python training/download_datasets.py --pack   # 打包 → datasets.tar.gz

# 上传 datasets.tar.gz 到 PAI-DSW，然后：
python training/download_datasets.py --unpack # 解包
python training/train_plant_detector.py       # 训练 Model A
python training/train_flower_detector.py      # 训练 Model B
python training/export_models.py              # 导出 ONNX + NCNN
python training/validate_models.py            # 验证 mAP + 速度报告
```

### 训练参数 (两个模型共用基础配置)
- 架构: YOLOv8n, imgsz=640, epochs=100, batch=16, patience=20
- 支持 `--epochs`, `--batch`, `--resume` CLI 参数覆盖

### 验收标准
- mAP@50 > 0.5
- 模型大小 < 15MB
- 导出 ONNX + NCNN 格式供 RPi4 部署

### GitHub 仓库
- **地址**: https://github.com/ZachCharles666/aglass.git
- **Remote**: SSH (`git@github.com:ZachCharles666/aglass.git`)
- **SSH Key**: ed25519, 邮箱 nobbynoraphyskv@gmail.com

## 下一步
1. **完成 Phase 1 训练**: 在 PAI-DSW 上跑通训练流水线，拿到两个 .pt 模型
2. **Phase 2 边缘推理**: 实现 `src/inference/` 模块，在 RPi4 上加载模型做实时推理
3. **花朵触发逻辑**: flower_detector 检测到花朵 → 自动触发 Cam-B burst 拍摄

---
最后更新: 2026-02-13
