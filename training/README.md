# AgriCam Training — 阿里云 PAI-DSW 训练指南

在 PAI-DSW (Data Science Workshop) 上训练 YOLOv8n 模型，用于树莓派边缘部署。

## Models

| Model | Dataset | Classes | Purpose |
|-------|---------|---------|---------|
| plant_detector | PlantDoc (~2600 images) | 13 plant species | Daily monitoring with Cam-A |
| flower_detector | Flower Detection | 2 (flower, bud) | Trigger Cam-B burst capture |

## PAI-DSW 环境配置

### 1. 创建 DSW 实例

- 登录 [PAI 控制台](https://pai.console.aliyun.com/) → 交互式建模 (DSW)
- **镜像**: 选择 `pytorch-2.x` 官方镜像（自带 CUDA + PyTorch）
- **GPU**: V100 (16GB) 或 A10 (24GB)，YOLOv8n 轻量训练 V100 即可
- **磁盘**: 默认 100GB 足够

### 2. 在 DSW Terminal 中执行

```bash
# 克隆项目
cd /mnt/workspace
git clone <repo-url> aglass && cd aglass

# 安装训练依赖（DSW 已有 PyTorch，只需额外装这些）
pip install -r training/requirements.txt

# 设置 Roboflow API Key
# 获取地址: https://app.roboflow.com/settings/api
export ROBOFLOW_API_KEY="your_key_here"
```

### 3. 运行训练流水线

```bash
# Step 1: 下载数据集
python training/download_datasets.py

# Step 2: 训练 Model A（植物种类检测）
python training/train_plant_detector.py

# Step 3: 训练 Model B（花朵检测）
python training/train_flower_detector.py

# Step 4: 导出 ONNX + NCNN
python training/export_models.py

# Step 5: 验证模型指标
python training/validate_models.py
```

### 4. 下载训练产出

训练完成后，从 DSW 下载以下文件到本地 aglass 项目：

```
models/plant_detector_v1.pt
models/flower_detector_v1.pt
training/validation_report.json
```

DSW 文件面板 → 右键文件 → Download，或用 `ossutil cp` 传到 OSS。

## PAI-DSW 注意事项

- **工作目录**: DSW 持久化目录为 `/mnt/workspace`，实例停止后数据保留
- **费用**: 不用时记得 **停止实例**，GPU 按时计费
- **Tensorboard**: DSW 自带 Tensorboard，训练时可在 DSW 面板中查看 loss 曲线
- **网络**: DSW 可直接访问 Roboflow API，无需额外代理

## Expected Results

- mAP@50 > 0.5 for both models
- Model size < 15MB (YOLOv8n standard)
- Exported ONNX/NCNN models ready for RPi4 deployment
