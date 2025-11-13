#!/usr/bin/env bash
# 基于 FastAPI 健康指标服务的 curl 测试脚本
# 使用方法：
#   1. 确保服务运行在 http://localhost:8000
#   2. 可通过 BASE_URL 环境变量自定义地址，例如：
#        BASE_URL="http://127.0.0.1:8000/api" ./curl_tests.sh
#   3. 需预装 curl 与 jq。

set -euo pipefail

BASE_URL=${BASE_URL:-"http://localhost:8000/api"}

log() {
  printf '\n===== %s =====\n' "$1"
}

log "获取支持的指标类型"
curl -sS "${BASE_URL}/metric-types" | jq .

log "写入单条心率指标"
CREATE_RESPONSE=$(curl -sS -X POST "${BASE_URL}/metrics" \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user-001",
    "type": "heart_rate",
    "value": 72.5,
    "unit": "bpm",
    "recorded_at": "2025-11-13T09:00:00Z",
    "source": "watch",
    "metadata": {"sensor": "fitwatch"},
    "tags": ["resting", "morning"]
  }')

echo "$CREATE_RESPONSE" | jq .
RECORD_ID=$(echo "$CREATE_RESPONSE" | jq -r '.record_id')

log "批量写入体重指标"
curl -sS -X POST "${BASE_URL}/metrics/batch" \
  -H 'Content-Type: application/json' \
  -d '{
    "records": [
      {
        "user_id": "user-001",
        "type": "body_weight",
        "value": 68.2,
        "unit": "kg",
        "recorded_at": "2025-11-12T21:00:00Z",
        "source": "scale",
        "metadata": {"location": "home"},
        "tags": ["evening"]
      },
      {
        "user_id": "user-001",
        "type": "body_weight",
        "value": 67.9,
        "unit": "kg",
        "recorded_at": "2025-11-13T07:30:00Z",
        "source": "scale",
        "metadata": {"location": "home"},
        "tags": ["morning"]
      }
    ]
  }' | jq .

log "按时间范围查询 user-001 的心率指标"
curl -sS "${BASE_URL}/metrics?user_id=user-001&type=heart_rate&start_time=2025-11-12T00:00:00Z&end_time=2025-11-14T00:00:00Z&order=desc" | jq .

log "计算心率的最近7日趋势 (平均值)"
curl -sS -X POST "${BASE_URL}/metrics/trend" \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user-001",
    "type": "heart_rate",
    "metric_field": "value",
    "group_by": "day",
    "lookback_days": 7
  }' | jq .

if [[ -n "${RECORD_ID}" && "${RECORD_ID}" != "null" ]]; then
  log "删除刚刚写入的心率指标"
  curl -sS -X DELETE "${BASE_URL}/metrics/${RECORD_ID}?user_id=user-001" | jq .
else
  echo "未能获取心率记录 ID，跳过删除步骤" >&2
fi

log "完成所有测试调用"
