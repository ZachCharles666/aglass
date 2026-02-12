#!/bin/bash
#
# 硬件测试脚本
#
# 在树莓派上运行完整的硬件测试
#
# 使用方法：
#   ./scripts/hardware_test.sh
#

set -e

echo "========================================"
echo "  AgriCam 硬件测试"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 计数器
PASS=0
FAIL=0

# 用 python3 替代 bc 做浮点运算
pycalc() {
    python3 -c "print($1)"
}

# 测试函数
test_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    PASS=$((PASS + 1))
}

test_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    FAIL=$((FAIL + 1))
}

test_warn() {
    echo -e "${YELLOW}⚠️ WARN${NC}: $1"
}

# API 基础 URL
API_BASE="http://localhost:8000"

# 检查服务器是否运行
check_server() {
    echo "检查 API 服务器..."
    if curl -s "$API_BASE/health" > /dev/null 2>&1; then
        test_pass "API 服务器运行中"
        return 0
    else
        test_fail "API 服务器未运行"
        echo "请先启动服务器："
        echo "  USE_MOCK_CAMERA=false python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
}

# 测试1: 系统健康状态
test_health() {
    echo ""
    echo "=== 测试1: 系统健康状态 ==="

    HEALTH=$(curl -s "$API_BASE/health")

    # 检查相机状态
    CAM_A=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['cameras']['cam_a'])")
    if [[ "$CAM_A" == "ready" ]] || [[ "$CAM_A" == "capturing" ]]; then
        test_pass "Cam-A 状态: $CAM_A"
    else
        test_fail "Cam-A 状态异常: $CAM_A"
    fi

    # 检查 CPU 温度
    TEMP=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['system']['temperature']['cpu_celsius'] or 'N/A')")
    echo "  CPU 温度: ${TEMP}°C"
    if [[ "$TEMP" != "N/A" ]] && [[ $(pycalc "$TEMP < 80") == "True" ]]; then
        test_pass "CPU 温度正常"
    elif [[ "$TEMP" != "N/A" ]]; then
        test_warn "CPU 温度偏高: ${TEMP}°C"
    fi
}

# 测试2: 对焦功能
test_autofocus() {
    echo ""
    echo "=== 测试2: 自动对焦 ==="
    echo "请确保相机对准 45cm 处有纹理的目标"
    read -p "按 Enter 继续..."

    # 测试 10 次对焦
    SUCCESS=0
    TOTAL_DURATION=0

    for i in {1..10}; do
        echo -n "  Round $i/10: "
        RESULT=$(curl -s -X POST "$API_BASE/camera/cam-a/af/one-shot")

        IS_SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['success'])")
        DURATION=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['duration'])")

        if [[ "$IS_SUCCESS" == "True" ]]; then
            echo "成功 (${DURATION}s)"
            SUCCESS=$((SUCCESS + 1))
            TOTAL_DURATION=$(pycalc "$TOTAL_DURATION + $DURATION")
        else
            echo "失败"
        fi

        sleep 0.5
    done

    # 计算统计
    SUCCESS_RATE=$(pycalc "round($SUCCESS * 100 / 10, 1)")
    if [[ $SUCCESS -gt 0 ]]; then
        AVG_DURATION=$(pycalc "round($TOTAL_DURATION / $SUCCESS, 3)")
    else
        AVG_DURATION="N/A"
    fi

    echo ""
    echo "  成功率: ${SUCCESS_RATE}% (目标 ≥95%)"
    echo "  平均耗时: ${AVG_DURATION}s (目标 ≤1.5s)"

    # 验收判断
    if [[ $(pycalc "$SUCCESS_RATE >= 95") == "True" ]]; then
        test_pass "对焦成功率 ≥95%"
    else
        test_fail "对焦成功率 <95%"
    fi

    if [[ "$AVG_DURATION" != "N/A" ]] && [[ $(pycalc "$AVG_DURATION <= 1.5") == "True" ]]; then
        test_pass "对焦耗时 ≤1.5s"
    else
        test_fail "对焦耗时 >1.5s"
    fi
}

# 测试3: 焦距锁定
test_focus_lock() {
    echo ""
    echo "=== 测试3: 焦距锁定 ==="

    # 先对焦
    curl -s -X POST "$API_BASE/camera/cam-a/af/one-shot" > /dev/null

    # 锁定焦距
    LOCK_RESULT=$(curl -s -X POST "$API_BASE/camera/cam-a/af/lock")
    IS_LOCKED=$(echo "$LOCK_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['success'])")
    LENS_POS=$(echo "$LOCK_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['locked_position'])")

    if [[ "$IS_LOCKED" == "True" ]]; then
        test_pass "焦距锁定成功: $LENS_POS"
    else
        test_fail "焦距锁定失败"
    fi

    # 检查状态
    STATE=$(curl -s "$API_BASE/camera/cam-a/af/state")
    AF_MODE=$(echo "$STATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['af_mode'])")

    if [[ "$AF_MODE" == "locked" ]]; then
        test_pass "对焦模式已锁定"
    else
        test_fail "对焦模式未锁定: $AF_MODE"
    fi
}

# 测试4: Profile 系统
test_profile() {
    echo ""
    echo "=== 测试4: Profile 系统 ==="

    # 创建 Profile
    CREATE_RESULT=$(curl -s -X POST "$API_BASE/profile/create" \
        -H "Content-Type: application/json" \
        -d '{"operator_id": "hw_test", "notes": "硬件测试"}')

    PROFILE_ID=$(echo "$CREATE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['profile_id'])")

    if [[ -n "$PROFILE_ID" ]] && [[ "$PROFILE_ID" != "null" ]]; then
        test_pass "Profile 创建成功: $PROFILE_ID"
    else
        test_fail "Profile 创建失败"
        return
    fi

    # 获取当前 Profile
    CURRENT=$(curl -s "$API_BASE/profile/current")
    CURRENT_ID=$(echo "$CURRENT" | python3 -c "import sys,json; print(json.load(sys.stdin)['profile_id'])")

    if [[ "$CURRENT_ID" == "$PROFILE_ID" ]]; then
        test_pass "当前 Profile 正确"
    else
        test_fail "当前 Profile 不匹配"
    fi
}

# 测试5: 采集循环
test_capture() {
    echo ""
    echo "=== 测试5: 采集循环（30秒测试） ==="

    # 启动采集
    START_RESULT=$(curl -s -X POST "$API_BASE/capture/start" \
        -H "Content-Type: application/json" \
        -d '{"interval_sec": 1.5}')

    IS_STARTED=$(echo "$START_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))")

    if [[ "$IS_STARTED" == "True" ]]; then
        test_pass "采集已启动"
    else
        test_fail "采集启动失败"
        return
    fi

    # 等待 30 秒
    echo "  采集中，请等待 30 秒..."
    for i in {1..30}; do
        echo -n "."
        sleep 1
    done
    echo ""

    # 获取状态
    STATUS=$(curl -s "$API_BASE/capture/status")
    TOTAL=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_count'])")
    ERRORS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['errors'])")

    echo "  采集数量: $TOTAL 张 (预期 ~20 张)"
    echo "  错误数: $ERRORS"

    # 停止采集
    curl -s -X POST "$API_BASE/capture/stop" > /dev/null

    # 验收
    if [[ $TOTAL -ge 15 ]]; then
        test_pass "采集数量正常"
    else
        test_fail "采集数量不足: $TOTAL"
    fi

    if [[ $ERRORS -eq 0 ]]; then
        test_pass "无采集错误"
    else
        test_warn "有 $ERRORS 个采集错误"
    fi
}

# 测试6: 图片质量
test_image_quality() {
    echo ""
    echo "=== 测试6: 图片质量 ==="

    # 获取摘要
    SUMMARY=$(curl -s "$API_BASE/capture/summary?minutes=5")

    AVG_QUALITY=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['average_quality'])")
    MIN_QUALITY=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['min_quality'])")
    MISSING=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['missing_files'])")

    echo "  平均清晰度: $AVG_QUALITY (目标 >100)"
    echo "  最低清晰度: $MIN_QUALITY"
    echo "  缺失文件: $MISSING"

    if [[ $(pycalc "$AVG_QUALITY > 100") == "True" ]]; then
        test_pass "图片清晰度正常"
    else
        test_warn "图片清晰度偏低"
    fi

    if [[ $MISSING -eq 0 ]]; then
        test_pass "无缺失文件"
    else
        test_fail "有 $MISSING 个文件缺失"
    fi
}

# 测试7: 数据持久化
test_persistence() {
    echo ""
    echo "=== 测试7: 数据持久化 ==="

    # 检查数据库（实际路径为 data/profiles/profiles.db）
    if [[ -f "data/profiles/profiles.db" ]]; then
        IMG_COUNT=$(sqlite3 data/profiles/profiles.db "SELECT COUNT(*) FROM images" 2>/dev/null || echo "0")
        PROFILE_COUNT=$(sqlite3 data/profiles/profiles.db "SELECT COUNT(*) FROM profiles" 2>/dev/null || echo "0")

        echo "  数据库图片记录: $IMG_COUNT"
        echo "  数据库 Profile 记录: $PROFILE_COUNT"

        if [[ $IMG_COUNT -gt 0 ]]; then
            test_pass "图片记录已持久化"
        else
            test_fail "无图片记录"
        fi

        if [[ $PROFILE_COUNT -gt 0 ]]; then
            test_pass "Profile 记录已持久化"
        else
            test_fail "无 Profile 记录"
        fi
    else
        test_fail "数据库文件不存在"
    fi
}

# 打印总结
print_summary() {
    echo ""
    echo "========================================"
    echo "  测试总结"
    echo "========================================"
    echo -e "  ${GREEN}通过: $PASS${NC}"
    echo -e "  ${RED}失败: $FAIL${NC}"
    echo "========================================"

    if [[ $FAIL -eq 0 ]]; then
        echo -e "${GREEN}🎉 所有测试通过！${NC}"
        exit 0
    else
        echo -e "${RED}⚠️ 有 $FAIL 个测试失败${NC}"
        exit 1
    fi
}

# 主函数
main() {
    check_server
    test_health
    test_autofocus
    test_focus_lock
    test_profile
    test_capture
    test_image_quality
    test_persistence
    print_summary
}

# 运行
main "$@"
