#!/usr/bin/env python3
#
# AgriCam API 功能测试脚本 (v2 - 已修正端点)
#
# 使用方法:
#   1. 在一个终端启动 AgriCam API 服务。
#      (e.g., `sudo systemctl start agricam` 或手动启动)
#   2. 在第二个终端，激活虚拟环境并运行此脚本:
#      `source venv/bin/activate`
#      `python scripts/functional_test.py`
#
import requests
import time
import json
import random

# --- 配置 ---
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# --- 打印颜色 ---
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
ENDC = "\033[0m"

def print_test(name):
    """打印测试模块的标题"""
    print("\n" + YELLOW + "===== TESTING: " + name + " =====" + ENDC)

def print_pass(msg):
    """打印成功信息"""
    print(GREEN + "[PASS]" + ENDC + " " + msg)

def print_fail(msg):
    """打印失败信息"""
    print(RED + "[FAIL]" + ENDC + " " + msg)

def print_info(msg):
    """打印普通信息"""
    print(BLUE + "[INFO]" + ENDC + " " + msg)

def test_health():
    """测试 /health 端点"""
    print_test("Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200 and response.json().get("status") == "healthy":
            print_pass("API server is healthy.")
            return True
        else:
            print_fail(f"API server health check failed. Status: {response.status_code}, Body: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print_fail(f"Could not connect to API server at {BASE_URL}. Is it running?")
        print_fail(f"Error: {e}")
        return False

def test_profiles():
    """测试 /profile/* 端点 (CRUD)"""
    print_test("Profile System (CRUD)")
    # `focus_distance_cm` 是必须的 (在 routes_profile.py 的 ProfileCreateRequest 中定义)
    profile_data = {
        "operator_id": "test-user",
        "notes": "A temporary test profile",
        "focus_distance_cm": 26
    }

    profile_id = None
    try:
        # 1. 创建 (Create)
        print_info(f"Creating profile for operator: {profile_data['operator_id']}")
        response = requests.post(f"{BASE_URL}/profile/create", data=json.dumps(profile_data), headers=HEADERS)
        
        if response.status_code == 200:
            created_profile = response.json()
            profile_id = created_profile.get("profile_id")
            print_pass(f"Profile '{profile_id}' created successfully.")
        else:
            print_fail(f"Failed to create profile. Status: {response.status_code}, Body: {response.text}")
            return

        # 2. 读取 (Read)
        print_info(f"Fetching profile: {profile_id}")
        response = requests.get(f"{BASE_URL}/profile/{profile_id}")
        if response.status_code == 200:
            print_pass("Profile data can be fetched successfully.")
        else:
            print_fail(f"Failed to fetch profile. Status: {response.status_code}")

        # 3. 测试删除保护逻辑 (Delete Protection Logic)
        print_info(f"Testing deletion protection for active profile: {profile_id}")
        response = requests.delete(f"{BASE_URL}/profile/{profile_id}")
        if response.status_code == 400 and "不能删除当前激活的 Profile" in response.text:
            print_pass("API correctly prevented deletion of the active profile.")
        else:
            print_fail(f"Deletion protection test failed. Expected 400, got {response.status_code}. Body: {response.text}")

    except requests.exceptions.RequestException as e:
        print_fail(f"An error occurred during profile test: {e}")
    finally:
        # 4. 清理测试数据 (Cleanup)
        if profile_id:
            # 为了能删除，需要先创建一个新的profile让其成为"current"
            # 或者调用 /select/{another_id}。为保持测试简单，我们暂时不测试删除的happy-path。
            print_info("Skipping cleanup of test profile to keep test simple.")

def test_focus():
    """测试对焦相关端点"""
    print_test("Focus Control")
    try:
        # 触发自动对焦并从响应中获取分数
        print_info("Triggering one-shot auto-focus...")
        response = requests.post(f"{BASE_URL}/camera/cam-a/af/one-shot")
        if response.status_code == 200:
            result = response.json()
            score = result.get('clarity_score', 'N/A')
            lens_pos = result.get('lens_position', 'N/A')
            print_pass(f"Auto-focus successful. Final Lens Position: {lens_pos}, Score: {score}")
        else:
            print_fail(f"Auto-focus request failed. Status: {response.status_code}, Body: {response.text}")
            return

    except requests.exceptions.RequestException as e:
        print_fail(f"An error occurred during focus test: {e}")

def test_capture():
    """测试拍照端点"""
    print_test("Capture")
    try:
        # 修正：调用正确的单次拍照端点
        print_info("Requesting a single capture via /camera/cam-a/capture...")
        response = requests.post(f"{BASE_URL}/camera/cam-a/capture")
        if response.status_code == 200: # 修正：capture_image 成功时返回 200
            result = response.json()
            print_pass("Capture request successful.")
            print_info(f"  - Clarity Score: {result.get('clarity_score')}")
            print_info(f"  - Saved Path: {result.get('file_path')}")
        else:
            print_fail(f"Capture request failed. Status: {response.status_code}, Body: {response.text}")
    except requests.exceptions.RequestException as e:
        print_fail(f"An error occurred during capture test: {e}")


def main():
    """主函数，运行所有测试"""
    print(BLUE + "===== AgriCam API Functional Test (v2) =====" + ENDC)
    
    if not test_health():
        print("\n" + RED + "Health check failed. Aborting further tests." + ENDC)
        return

    test_profiles()
    test_focus()
    test_capture()

    print("\n" + BLUE + "===== Test Run Finished =====" + ENDC)
    print("Check the output above for any [FAIL] messages.")
    print("If capture was successful, please check the '" + YELLOW + "data/images/" + ENDC + "' directory on the Pi for a new photo.")


if __name__ == "__main__":
    main()
