# Agricultural Camera System Development Skill

## Purpose
为基于树莓派 + IMX708（Module 3）+ IMX477（Arducam M12）的农业巡检相机系统提供开发最佳实践。涵盖硬件控制、对焦策略、并发采集、边缘推理、断网容错。

---

## 1. 硬件配置总览

### 1.1 相机配置
| 组件 | 型号 | 用途 | 关键特性 |
|------|------|------|----------|
| **Cam-A** | IMX708 (官方 Module 3) | 巡检/引导/建 Profile | ✅ 自动对焦 (PDAF)<br>✅ 焦距范围 10cm–∞<br>✅ 对焦速度 0.5–1.5s |
| **Cam-B** | Arducam IMX477 + M12 16mm | 精检/数据资产 | ❌ 无自动对焦（固定焦距）<br>✅ 高分辨率 4056x3040<br>✅ 锁死在 45cm |

### 1.2 阶段差异
| 项目 | 阶段 1A | 阶段 1B |
|------|---------|---------|
| 主控 | Pi 4 | Pi 5 |
| 相机 | 仅 Cam-A | Cam-A + Cam-B |
| ToF | ❌ 无（全标 unknown） | ✅ 引入（判断近/中/远档） |
| 推理 | ❌ 不做 | ✅ 边缘 YOLO + 云端精检 |

### 1.3 距离档位定义
```yaml
distance_buckets:
  near:  [40, 52]   # cm - 唯一可标记"资产级"的档位
  mid:   [52, 85]   # cm
  far:   [85, 300]  # cm
```

---

## 2. Cam-A (IMX708) 对焦控制

### 2.1 硬件特性
- **对焦类型**：相位检测自动对焦 (PDAF)
- **对焦范围**：10cm 到无穷远
- **最佳工作距离**：40–52cm（近档巡检）
- **对焦速度**：Macro 模式下通常 **500ms–1.2s**

### 2.2 推荐配置
```python
from picamera2 import Picamera2
from libcamera import controls

picam_a = Picamera2(0)
config = picam_a.create_still_configuration(
    main={"size": (1920, 1080), "format": "RGB888"}
)
picam_a.configure(config)
picam_a.start()

# 针对 40-52cm 近距离优化
picam_a.set_controls({
    "AfMode": controls.AfModeEnum.Auto,      # 自动对焦
    "AfRange": controls.AfRangeEnum.Macro,   # 近距离模式
    "AfSpeed": controls.AfSpeedEnum.Fast     # 快速对焦
})
```

### 2.3 One-Shot 自动对焦（核心函数）
```python
import time

def one_shot_af(picam, timeout=3.0):
    """
    触发一次自动对焦并等待完成
    
    Returns:
        (success: bool, duration: float, lens_position: float|None)
    """
    picam.set_controls({
        "AfMode": controls.AfModeEnum.Auto,
        "AfTrigger": controls.AfTriggerEnum.Start
    })
    
    start = time.time()
    while time.time() - start < timeout:
        metadata = picam.capture_metadata()
        af_state = metadata.get("AfState", None)
        
        if af_state == controls.AfStateEnum.Focused:
            duration = time.time() - start
            lens_pos = metadata.get("LensPosition", None)
            return True, duration, lens_pos
        
        time.sleep(0.05)  # 50ms 轮询
    
    return False, timeout, None
```

### 2.4 锁定对焦
```python
def lock_focus(picam):
    """
    锁定当前焦距，禁止继续对焦（防止 hunting）
    
    使用场景：建立 Profile 后，在整个巡检过程中保持焦距不变
    """
    # 读取当前焦距位置
    metadata = picam.capture_metadata()
    lens_pos = metadata.get("LensPosition", None)
    
    # 切换到 Manual 模式并锁定焦距
    if lens_pos is not None:
        picam.set_controls({
            "AfMode": controls.AfModeEnum.Manual,
            "LensPosition": lens_pos
        })
        return lens_pos
    else:
        # 如果无法读取 LensPosition，仅切换模式
        picam.set_controls({"AfMode": controls.AfModeEnum.Manual})
        return None
```

### 2.5 清晰度计算
```python
import cv2
import numpy as np

def calculate_clarity_laplacian(image_path):
    """
    使用 Laplacian 方差计算清晰度分数
    
    Returns:
        float: 清晰度分数（越大越清晰，通常 >100 为可接受）
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    laplacian = cv2.Laplacian(img, cv2.CV_64F)
    return laplacian.var()

def calculate_clarity_tenengrad(image_path):
    """
    使用 Tenengrad 方法（Sobel 梯度平方和）
    
    Returns:
        float: 清晰度分数
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    
    gx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(gx**2 + gy**2)
    
    return np.sum(gradient_magnitude**2)
```

### 2.6 建立 Profile 的对焦流程
```python
def create_focus_profile(picam, operator_id, distance_cm=45):
    """
    建立 Mission Focus Profile
    
    流程：
    1. 将相机放置在目标距离（默认 45cm）
    2. 触发 one-shot AF
    3. 锁定焦距
    4. 保存 Profile（包含 LensPosition）
    """
    print(f"请将相机放置在距离目标 {distance_cm}cm 处...")
    input("按 Enter 开始对焦")
    
    success, duration, lens_pos = one_shot_af(picam)
    
    if not success:
        raise RuntimeError(f"对焦失败（超时 {duration}s）")
    
    print(f"✅ 对焦成功！耗时 {duration:.2f}s, LensPosition: {lens_pos}")
    
    # 锁定焦距
    locked_pos = lock_focus(picam)
    
    # 保存 Profile
    profile = {
        "profile_id": str(uuid.uuid4()),
        "operator_id": operator_id,
        "created_at": datetime.now().isoformat(),
        "cam_a_config": {
            "af_mode": "locked",
            "lens_position": locked_pos,
            "focus_distance_cm": distance_cm
        },
        "distance_policy": {
            "near": [40, 52],
            "mid": [52, 85],
            "far": [85, 300]
        }
    }
    
    return profile
```

### 2.7 ⚠️ Anti-patterns
- ❌ **不要在连续采集时每张都触发 AF**：会导致巡检速度慢且不稳定
  - ✅ 正确做法：建 Profile 时对焦一次，后续锁定焦距
- ❌ **不要用 `AfMode.Continuous`**：会持续 hunting，消耗算力
- ❌ **不要在暗光环境下对焦**：AF 成功率大幅下降
  - ✅ 正确做法：建 Profile 时确保光照充足（>300 lux）

---

## 3. Cam-B (IMX477 + M12) 精检控制

### 3.1 硬件特性
- **对焦类型**：无自动对焦（M12 镜头为固定焦距）
- **焦距**：16mm（已锁死在 45cm）
- **分辨率**：4056x3040 (12MP)
- **视场角**：约 25°（适合精检特写）

### 3.2 初始化配置
```python
picam_b = Picamera2(1)  # 假设 Cam-B 是 /dev/video1
config = picam_b.create_still_configuration(
    main={"size": (4056, 3040), "format": "RGB888"},
    buffer_count=2  # Burst 时需要缓冲
)
picam_b.configure(config)
picam_b.start()
```

### 3.3 Burst 采集（带补光）
```python
import RPi.GPIO as GPIO
import time

LED_PIN = 17  # BCM 引脚编号
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

def burst_capture(picam, count=5, interval_ms=150, warmup_ms=100):
    """
    Burst 采集 + 补光灯控制
    
    Args:
        count: 拍摄张数（固定 5 张）
        interval_ms: 每张间隔（100-200ms）
        warmup_ms: 补光灯预热时间（100ms）
    
    Returns:
        List[dict]: 每张图片的元数据
    """
    results = []
    
    try:
        # 开灯
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(warmup_ms / 1000)
        
        # Burst 拍摄
        for i in range(count):
            ts = datetime.now().isoformat()
            file_path = f"data/images/burst_{ts}_{i}.jpg"
            
            # 拍照
            picam.capture_file(file_path)
            
            # 计算清晰度
            clarity = calculate_clarity_laplacian(file_path)
            
            results.append({
                "index": i,
                "ts": ts,
                "file_path": file_path,
                "quality_score": clarity
            })
            
            if i < count - 1:
                time.sleep(interval_ms / 1000)
        
    finally:
        # 关灯（确保即使异常也能关灯）
        GPIO.output(LED_PIN, GPIO.LOW)
    
    return results
```

### 3.4 选择最佳帧
```python
def select_best_frame(burst_results):
    """
    从 Burst 结果中选择质量最佳的一张
    
    Returns:
        dict: 最佳帧的元数据（标记 asset_candidate=True）
    """
    if not burst_results:
        return None
    
    # 按清晰度排序
    sorted_results = sorted(burst_results, key=lambda x: x["quality_score"], reverse=True)
    
    best = sorted_results[0]
    best["asset_candidate"] = True
    
    # 其余帧标记为备份
    for frame in sorted_results[1:]:
        frame["asset_candidate"] = False
        frame["is_backup"] = True
    
    return best, sorted_results[1:]
```

### 3.5 ⚠️ 注意事项
- ⚠️ **M12 镜头焦距固定**：如果目标距离不是 45cm，需要重新调整镜头（需要工具）
- ⚠️ **补光灯功率 <1W**：如果效果不佳，需要更换大功率灯 + 继电器
- ⚠️ **Burst 期间不要重启相机**：会导致首张图片曝光异常

---

## 4. 实时采集 + 推理并发架构

### 4.1 架构原则
```
┌─────────────────────────────────────────────────────┐
│  主采集线程 (Cam-A)                                   │
│  每 1.5s 拍一张 → 保存图片 + 元数据 → 入队            │
└─────────────────┬───────────────────────────────────┘
                  │
                  ↓
          ┌───────────────┐
          │  推理队列       │
          │  (queue.Queue) │
          └───────┬────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────────┐
│  推理消费者线程                                       │
│  取图 → YOLO 推理 → 判断是否触发 Burst                │
└─────────────────┬───────────────────────────────────┘
                  │
                  ↓ (命中"疑似病虫害")
          ┌───────────────┐
          │  Burst 队列    │
          └───────┬────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────────┐
│  Burst 线程 (Cam-B)                                  │
│  开灯 → 拍 5 张 → 选最佳帧 → 入上传队列               │
└─────────────────────────────────────────────────────┘
```

### 4.2 实现模板
```python
import threading
import queue
from datetime import datetime

# 全局队列
capture_queue = queue.Queue(maxsize=50)
burst_queue = queue.Queue(maxsize=10)
upload_queue = queue.Queue(maxsize=100)

# 全局状态
is_running = False
current_profile = None

def capture_loop(picam, interval_sec=1.5):
    """
    主采集循环（Cam-A）
    """
    global is_running
    while is_running:
        try:
            ts = datetime.now().isoformat()
            file_path = f"data/images/{ts}_cam_a.jpg"
            
            # 拍照
            picam.capture_file(file_path)
            
            # 元数据
            metadata = {
                "profile_id": current_profile["profile_id"] if current_profile else "unknown",
                "camera_id": "cam_a",
                "ts": ts,
                "distance_bucket": "unknown",  # 阶段 1A 固定
                "focus_state": "locked",
                "quality_score": calculate_clarity_laplacian(file_path),
                "file_path": file_path
            }
            
            # 保存元数据
            save_metadata(metadata)
            
            # 入推理队列
            capture_queue.put((file_path, metadata))
            
            time.sleep(interval_sec)
            
        except Exception as e:
            logging.error(f"采集错误: {e}")

def inference_worker(yolo_model):
    """
    推理消费者线程
    """
    global is_running
    while is_running:
        try:
            file_path, metadata = capture_queue.get(timeout=1)
            
            # YOLO 推理（阶段 1A 用占位模型）
            results = yolo_model.predict(file_path, conf=0.3)
            
            # 判断是否命中"疑似病虫害"（阶段 1A 用 person/car 占位）
            if len(results[0].boxes) > 0:
                logging.info(f"检测到疑似目标，触发 Burst")
                burst_queue.put(metadata)
            
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"推理错误: {e}")

def burst_worker(picam_b):
    """
    Burst 处理线程（Cam-B）
    """
    global is_running
    while is_running:
        try:
            trigger_metadata = burst_queue.get(timeout=1)
            
            # 执行 Burst
            burst_results = burst_capture(picam_b, count=5, interval_ms=150)
            
            # 选最佳帧
            best_frame, backups = select_best_frame(burst_results)
            
            if best_frame:
                # 标记为资产候选（阶段 1B 才会根据 distance_bucket 过滤）
                best_frame["triggered_by"] = trigger_metadata["file_path"]
                upload_queue.put(best_frame)
            
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"Burst 错误: {e}")

# 启动系统
def start_system(picam_a, picam_b, yolo_model):
    global is_running
    is_running = True
    
    threading.Thread(target=capture_loop, args=(picam_a, 1.5), daemon=True).start()
    threading.Thread(target=inference_worker, args=(yolo_model,), daemon=True).start()
    threading.Thread(target=burst_worker, args=(picam_b,), daemon=True).start()
```

### 4.3 ⚠️ Anti-patterns
- ❌ **不要用 asyncio 包装 picamera2**：picamera2 是同步 API，会卡死
- ❌ **不要在回调里做推理**：会阻塞采集主线程
- ❌ **不要无限制入队**：设置 `maxsize` 防止内存爆炸

---

## 5. Mission Focus Profile 系统

### 5.1 Profile 数据模型
```python
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import uuid

class CameraConfig(BaseModel):
    af_mode: str  # "auto" | "locked"
    lens_position: Optional[float] = None
    focus_distance_cm: Optional[int] = None

class DistancePolicy(BaseModel):
    near: list[int] = [40, 52]
    mid: list[int] = [52, 85]
    far: list[int] = [85, 300]

class FocusProfile(BaseModel):
    profile_id: str = str(uuid.uuid4())
    operator_id: str
    created_at: datetime = datetime.now()
    cam_a_config: CameraConfig
    distance_policy: DistancePolicy
    notes: Optional[str] = None
```

### 5.2 Profile 持久化（SQLite）
```python
import sqlite3

def init_profile_db(db_path="data/profiles/profiles.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            operator_id TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            cam_a_config TEXT NOT NULL,
            distance_policy TEXT NOT NULL,
            notes TEXT,
            is_current INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn

def save_profile(conn, profile: FocusProfile):
    conn.execute("""
        INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (
        profile.profile_id,
        profile.operator_id,
        profile.created_at.isoformat(),
        profile.cam_a_config.json(),
        profile.distance_policy.json(),
        profile.notes
    ))
    conn.commit()

def set_current_profile(conn, profile_id: str):
    # 清除旧的 current
    conn.execute("UPDATE profiles SET is_current = 0")
    # 设置新的 current
    conn.execute("UPDATE profiles SET is_current = 1 WHERE profile_id = ?", (profile_id,))
    conn.commit()

def get_current_profile(conn) -> Optional[FocusProfile]:
    row = conn.execute("SELECT * FROM profiles WHERE is_current = 1").fetchone()
    if row:
        return FocusProfile(
            profile_id=row[0],
            operator_id=row[1],
            created_at=datetime.fromisoformat(row[2]),
            cam_a_config=CameraConfig.parse_raw(row[3]),
            distance_policy=DistancePolicy.parse_raw(row[4]),
            notes=row[5]
        )
    return None
```

---

## 6. 断网上传队列

### 6.1 队列表设计
```sql
CREATE TABLE upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    metadata TEXT NOT NULL,  -- JSON 格式
    status TEXT DEFAULT 'pending',  -- pending/uploading/done/failed
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_status ON upload_queue(status);
```

### 6.2 上传 Worker
```python
import requests
import json
import time

def upload_worker(api_base, api_key, db_conn):
    """
    后台上传线程
    """
    while True:
        try:
            # 获取待上传任务
            rows = db_conn.execute("""
                SELECT id, image_id, file_path, metadata, retry_count
                FROM upload_queue
                WHERE status = 'pending'
                ORDER BY created_at
                LIMIT 10
            """).fetchall()
            
            for row in rows:
                task_id, image_id, file_path, metadata_json, retry_count = row
                
                try:
                    # 标记为上传中
                    db_conn.execute("UPDATE upload_queue SET status='uploading' WHERE id=?", (task_id,))
                    db_conn.commit()
                    
                    # 上传图片
                    with open(file_path, 'rb') as f:
                        files = {'image': f}
                        data = {'metadata': metadata_json}
                        headers = {'Authorization': f'Bearer {api_key}'}
                        
                        resp = requests.post(
                            f"{api_base}/api/v1/inspect",
                            files=files,
                            data=data,
                            headers=headers,
                            timeout=30
                        )
                        resp.raise_for_status()
                    
                    # 成功：标记为 done
                    result = resp.json()
                    db_conn.execute("""
                        UPDATE upload_queue
                        SET status='done', updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (task_id,))
                    db_conn.commit()
                    
                    logging.info(f"✅ 上传成功: {image_id}")
                    
                except Exception as e:
                    # 失败：重试逻辑
                    retry_count += 1
                    if retry_count >= 3:
                        status = 'failed'
                    else:
                        status = 'pending'
                    
                    db_conn.execute("""
                        UPDATE upload_queue
                        SET status=?, retry_count=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (status, retry_count, task_id))
                    db_conn.commit()
                    
                    logging.error(f"❌ 上传失败: {image_id}, 重试 {retry_count}/3, 错误: {e}")
            
            # 等待 30 秒后继续
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"上传 Worker 错误: {e}")
            time.sleep(10)
```

---

## 7. 双摄枚举与稳定绑定

### 7.1 问题
`/dev/video0` 和 `/dev/video1` 在重启后可能交换顺序

### 7.2 解决方案：用 Serial Number 绑定
```python
from picamera2 import Picamera2

def find_camera_by_serial(serial: str):
    """
    根据序列号查找相机
    """
    for i in range(10):
        try:
            cam = Picamera2(i)
            properties = cam.camera_properties
            cam_serial = properties.get('Model', '')  # 或 'Serial'
            
            if serial in cam_serial:
                logging.info(f"✅ 找到相机: {serial} 在 /dev/video{i}")
                return cam
            
            cam.close()
        except Exception as e:
            continue
    
    raise RuntimeError(f"❌ 未找到相机: {serial}")

# 在 device.yaml 中配置：
# cam_a_identifier: "imx708"  # IMX708 的标识符
# cam_b_identifier: "imx477"  # IMX477 的标识符
```

---

## 8. 边缘推理（YOLO）

### 8.1 模型选择
- **阶段 1A**：YOLOv8n（占位，用 person/car 类别测试触发逻辑）
- **阶段 1B**：自定义模型（病斑、虫洞分类）

### 8.2 初始化
```python
from ultralytics import YOLO

# 阶段 1A：使用预训练模型
yolo_model = YOLO("yolov8n.pt")

# 阶段 1B：加载自定义模型
# yolo_model = YOLO("models/agri_disease_v1.pt")
```

### 8.3 推理流程
```python
def run_inference(image_path, model, conf_threshold=0.3):
    """
    运行 YOLO 推理
    
    Returns:
        bool: 是否命中目标（触发 Burst）
    """
    results = model.predict(
        image_path,
        conf=conf_threshold,
        verbose=False,
        imgsz=640  # 降分辨率加速
    )
    
    # 阶段 1A：检测到任何目标就触发（占位逻辑）
    if len(results[0].boxes) > 0:
        return True
    
    # 阶段 1B：检测到特定类别才触发
    # target_classes = ["disease_spot", "pest_hole"]
    # for box in results[0].boxes:
    #     class_name = model.names[int(box.cls)]
    #     if class_name in target_classes:
    #         return True
    
    return False
```

---

## 9. 云端 Mock 接口（阶段 1A/1B）

### 9.1 Mock Server（FastAPI）
```python
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import random

app = FastAPI()

class InspectResult(BaseModel):
    disease_type: str
    confidence: float
    action: str

@app.post("/api/v1/inspect", response_model=InspectResult)
async def inspect(image: UploadFile = File(...)):
    """
    Mock 云端精检接口
    """
    # 模拟处理时间
    await asyncio.sleep(0.5)
    
    # 随机返回结果
    diseases = ["健康", "叶斑病", "虫洞", "缺素症"]
    disease = random.choice(diseases)
    confidence = random.uniform(0.7, 0.95)
    
    action = "继续监测" if disease == "健康" else "建议人工复查"
    
    return InspectResult(
        disease_type=disease,
        confidence=confidence,
        action=action
    )

# 启动：uvicorn mock_server:app --host 0.0.0.0 --port 8080
```

---

## 10. 配置文件模板

### 10.1 device.yaml
```yaml
camera:
  cam_a:
    identifier: "imx708"  # 用于枚举时匹配
    resolution: [1920, 1080]
    af_mode: "auto"
    af_range: "macro"
    af_speed: "fast"
  
  cam_b:
    identifier: "imx477"
    resolution: [4056, 3040]
    fixed_focus_distance_cm: 45
    burst_count: 5
    burst_interval_ms: 150

capture:
  interval_sec: 1.5
  storage_path: "data/images"

distance_buckets:
  near: [40, 52]
  mid: [52, 85]
  far: [85, 300]

led:
  gpio_pin: 17  # BCM 编号
  warmup_ms: 100

inference:
  model_path: "models/yolov8n.pt"  # 阶段 1A 占位
  conf_threshold: 0.3
  imgsz: 640

cloud:
  api_base: "http://localhost:8080"  # Mock Server
  api_key: "test_key_12345"
  upload_interval_sec: 30

storage:
  db_path: "data/db.sqlite"
  max_storage_gb: 50  # 预留空间
  auto_cleanup: false  # 阶段 1 不自动清理

logging:
  level: "INFO"
  file_path: "data/logs/app.log"
  format: "json"
```

---

## 11. 测试脚本模板

### 11.1 对焦稳定性测试
```python
# scripts/test_af_lock.py
import csv
from camera.cam_a import one_shot_af, lock_focus, calculate_clarity_laplacian

results = []
for i in range(10):
    print(f"\n=== Round {i+1}/10 ===")
    
    # 触发对焦
    success, duration, lens_pos = one_shot_af(picam_a)
    
    # 锁定
    locked_pos = lock_focus(picam_a)
    
    # 等待 3 秒
    time.sleep(3)
    
    # 拍照并计算清晰度
    test_path = f"test_af_{i}.jpg"
    picam_a.capture_file(test_path)
    clarity = calculate_clarity_laplacian(test_path)
    
    results.append({
        "round": i + 1,
        "success": success,
        "duration": duration,
        "lens_position": lens_pos,
        "clarity": clarity
    })
    
    print(f"✅ 成功: {success}, 耗时: {duration:.2f}s, 清晰度: {clarity:.1f}")

# 输出 CSV
with open("af_test.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=["round", "success", "duration", "lens_position", "clarity"])
    writer.writeheader()
    writer.writerows(results)

# 验收
success_rate = sum(r['success'] for r in results) / len(results)
avg_duration = sum(r['duration'] for r in results if r['success']) / sum(r['success'] for r in results)

print(f"\n=== 验收结果 ===")
print(f"成功率: {success_rate*100:.1f}% (目标 ≥95%)")
print(f"平均耗时: {avg_duration:.2f}s (目标 ≤1.5s)")

assert success_rate >= 0.95, f"❌ 成功率 {success_rate} < 0.95"
assert avg_duration <= 1.5, f"❌ 平均耗时 {avg_duration} > 1.5s"
print("✅ 验收通过！")
```

### 11.2 Burst 质量测试
```python
# scripts/test_burst.py
import csv

test_scenarios = [
    {"name": "室内充足光", "led": False},
    {"name": "室内低光", "led": True},
    {"name": "室外阴天", "led": False}
]

all_results = []

for scenario in test_scenarios:
    print(f"\n=== 测试场景: {scenario['name']} ===")
    
    for i in range(20):
        # 执行 Burst
        burst_results = burst_capture(picam_b, count=5, interval_ms=150)
        
        # 选最佳帧
        best_frame, backups = select_best_frame(burst_results)
        
        # 计算平均质量
        avg_quality = sum(r['quality_score'] for r in burst_results) / len(burst_results)
        
        # 判断最佳帧是否明显优于平均
        improvement = (best_frame['quality_score'] - avg_quality) / avg_quality
        
        all_results.append({
            "scenario": scenario['name'],
            "round": i + 1,
            "best_quality": best_frame['quality_score'],
            "avg_quality": avg_quality,
            "improvement": improvement
        })
        
        print(f"Round {i+1}: 最佳 {best_frame['quality_score']:.1f}, 平均 {avg_quality:.1f}, 提升 {improvement*100:.1f}%")

# 输出 CSV
with open("burst_test.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=["scenario", "round", "best_quality", "avg_quality", "improvement"])
    writer.writeheader()
    writer.writerows(all_results)

# 验收
improved_count = sum(1 for r in all_results if r['improvement'] > 0.05)
success_rate = improved_count / len(all_results)

print(f"\n=== 验收结果 ===")
print(f"最佳帧明显优于平均的比例: {success_rate*100:.1f}% (目标 ≥80%)")
assert success_rate >= 0.8, f"❌ 成功率 {success_rate} < 0.8"
print("✅ 验收通过！")
```

---

## 12. 常见问题排查

### 12.1 Cam-A 对焦失败
**症状**：`one_shot_af()` 超时，返回 False

**可能原因**：
1. 光线不足（<200 lux）
2. 目标距离超出范围（<10cm 或 >2m）
3. 目标无纹理（如纯白墙）

**解决方案**：
```python
# 增加超时时间
success, duration, lens_pos = one_shot_af(picam_a, timeout=5.0)

# 检查环境光
# 如果失败，切换到 Manual 模式并使用历史 LensPosition
if not success:
    logging.warning("对焦失败，使用 Profile 中的历史焦距")
    picam_a.set_controls({
        "AfMode": controls.AfModeEnum.Manual,
        "LensPosition": profile.cam_a_config.lens_position
    })
```

### 12.2 Burst 期间系统卡顿
**症状**：Burst 时主采集循环暂停

**可能原因**：
1. SD 卡写入速度慢（<20 MB/s）
2. Burst 线程阻塞主线程

**解决方案**：
```python
# 使用更快的 SD 卡（UHS-I Class 10）
# 降低 Burst count
burst_results = burst_capture(picam_b, count=3)  # 从 5 降到 3

# 确保 Burst 在独立线程
threading.Thread(target=burst_worker, daemon=True).start()
```

### 12.3 上传队列堆积
**症状**：`upload_queue` 表中 pending 数量持续增长

**可能原因**：
1. 网络带宽不足
2. 云端接口响应慢

**解决方案**：
```python
# 压缩图片后再上传
from PIL import Image

def compress_image(input_path, output_path, quality=85):
    img = Image.open(input_path)
    img.save(output_path, "JPEG", quality=quality, optimize=True)

# 在上传前调用
compress_image(file_path, f"{file_path}.compressed", quality=80)
```

---

## 13. 项目检查清单

### 阶段 1A 验收标准
- [ ] Cam-A 对焦成功率 ≥95%，平均耗时 ≤1.5s
- [ ] Profile 创建、持久化、加载功能正常
- [ ] 巡检采集稳定运行 30 分钟不掉线
- [ ] 元数据完整（profile_id、ts、quality_score 等）
- [ ] 断网时采集不报错，数据本地缓存
- [ ] 导出脚本能生成 summary.csv

### 阶段 1B 验收标准
- [ ] 双摄同时在线，/health 能正确显示
- [ ] Cam-B Burst 在 80% 的场景中最佳帧明显优于平均
- [ ] 边缘推理不阻塞巡检（主循环延迟 <200ms）
- [ ] 精检触发逻辑可配置（conf_threshold）
- [ ] 上传队列在断网 10 分钟后能自动恢复
- [ ] Mock 云端接口返回格式正确

---

**🎯 核心原则总结**

1. **对焦先行**：阶段 1A 优先验证 Cam-A 对焦稳定性（最高风险）
2. **异步解耦**：采集、推理、Burst、上传各自独立线程，不阻塞
3. **断网容错**：本地队列 + 重试机制，确保数据不丢
4. **数据可追溯**：每张图片必绑定 profile_id，元数据结构化存储
5. **渐进迭代**：1A 先跑通单摄，1B 再扩展双摄 + 云端

---

END OF SKILL
