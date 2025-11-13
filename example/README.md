# 示例接口测试脚本

该目录提供使用 `curl` 测试健康指标 API 的脚本：

- `curl_tests.sh`：串行调用指标类型查询、单条写入、批量写入、查询、趋势分析与删除操作，适合快速验证服务功能。

## 使用方式

```bash
cd example
chmod +x curl_tests.sh   # 首次下载后若未赋予执行权限
./curl_tests.sh
```

默认脚本将 API 地址设为 `http://localhost:8000/api`。若需调整，可在执行前指定 `BASE_URL` 环境变量：

```bash
BASE_URL="http://127.0.0.1:8000/api" ./curl_tests.sh
```

> 依赖：需要本地安装 `curl`。若未安装 `jq`，脚本会自动使用 `python3` 处理 JSON。
