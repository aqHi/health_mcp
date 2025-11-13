#!/usr/bin/env bash
# 基于 FastAPI 健康指标服务的 curl 测试脚本
# 使用方法：
#   1. 确保服务运行在 http://localhost:8000
#   2. 可通过 BASE_URL 环境变量自定义地址，例如：
#        BASE_URL="http://127.0.0.1:8000/api" ./curl_tests.sh
#   3. 需预装 curl；若缺少 jq 将自动使用 python3 进行 JSON 处理。

set -euo pipefail

BASE_URL=${BASE_URL:-"http://localhost:8000/api"}
HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
  HAS_JQ=1
elif ! command -v python3 >/dev/null 2>&1; then
  echo "缺少 jq，且未检测到 python3 无法解析 JSON，请先安装其中任意一个工具。" >&2
  exit 1
else
  echo "未检测到 jq，将使用 python3 处理 JSON 输出。" >&2
fi

pretty_json() {
  if [[ ${HAS_JQ} -eq 1 ]]; then
    jq .
  else
    python3 - <<'PY'
import json, sys

try:
    data = json.load(sys.stdin)
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"JSON 解析失败: {exc}\n")
    sys.stdout.write(sys.stdin.read())
else:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
PY
  fi
}

extract_json_field() {
  local field="$1"
  if [[ ${HAS_JQ} -eq 1 ]]; then
    jq -r "${field}"
  else
    python3 - "$field" <<'PY'
import json, sys

field = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)

current = data
for part in field.strip('.').split('.'):
    if isinstance(current, dict) and part in current:
        current = current[part]
    else:
        current = None
        break

if current is None:
    sys.exit(1)

if isinstance(current, (dict, list)):
    sys.stdout.write(json.dumps(current, ensure_ascii=False))
else:
    sys.stdout.write(str(current))
PY
  fi
}

log() {
  printf '\n===== %s =====\n' "$1"
}

log "获取支持的指标类型"
curl -sS "${BASE_URL}/metric-types" | pretty_json

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

echo "$CREATE_RESPONSE" | pretty_json
RECORD_ID=$(echo "$CREATE_RESPONSE" | extract_json_field '.record_id' 2>/dev/null || echo "")

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
  }' | pretty_json

log "按时间范围查询 user-001 的心率指标"
curl -sS "${BASE_URL}/metrics?user_id=user-001&type=heart_rate&start_time=2025-11-12T00:00:00Z&end_time=2025-11-14T00:00:00Z&order=desc" | pretty_json

log "计算心率的最近7日趋势 (平均值)"
curl -sS -X POST "${BASE_URL}/metrics/trend" \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user-001",
    "type": "heart_rate",
    "metric_field": "value",
    "group_by": "day",
    "lookback_days": 7
  }' | pretty_json

if [[ -n "${RECORD_ID}" && "${RECORD_ID}" != "null" ]]; then
  log "删除刚刚写入的心率指标"
  curl -sS -X DELETE "${BASE_URL}/metrics/${RECORD_ID}?user_id=user-001" | pretty_json
else
  echo "未能获取心率记录 ID，跳过删除步骤" >&2
fi

log "完成所有测试调用"
