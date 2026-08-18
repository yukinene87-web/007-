# 007 Bridge — 共享工作区（单向协作，不写代码）

> 007 工程 Agent 与 Manus 之间的**结构化 JSON 文件交换**工作区。
> 007 只导出事实、请求与非秘密证据引用；Manus 只读输入、产出候选 ZIP。
> **绝不自动写入代码、绝不外发、绝不建远程控制接口。**

## 工作区路径

```
~/Documents/linkpulse-bridge/
```

绝对路径：`/Users/macbook/Documents/linkpulse-bridge/`

> 独立于 `soap-outreach-system` 项目，不含 `.env`、凭据、客户数据。这是「不含秘密」的桥接区。

## 目录结构

```
~/Documents/linkpulse-bridge/
├── README.md                          # 本文档
├── .gitignore                         # 排除秘密/大文件/审计证据
├── validate.py                        # JSON Schema 严格验证器（无第三方依赖）
├── schema/
│   ├── 007-bridge-v1.schema.json      # 输入/回执契约
│   └── linkpulse-delivery-v1.schema.json  # ZIP MANIFEST 契约
├── examples/                          # 合法 + 非法样例（模板 + 测试）
│   ├── input.valid.json               # 合法输入样例
│   ├── input.invalid.json             # 非法样例（external_send=true）
│   ├── receipt.valid.json             # 合法回执样例
│   └── manifest.valid.json            # 合法 MANIFEST 样例
├── bin/
│   └── new-task.py                    # 007 快速生成合法输入 JSON
├── input/                             # 007/本地 IDE → Manus 的事实输入 JSON
├── receipts/                          # Manus → 007 的回执 JSON
├── deliveries/                        # Manus 交付的候选 ZIP（每任务一个）
└── evidence/                          # 审计证据（正向链/拒绝链/零外发模拟）
    └── _update_log_template.md        # 007 收到 ZIP 后的更新日志模板
```

## 快速开始

```bash
# 1. 生成一个合法输入
python3 bin/new-task.py lp-a1-anchor-check-001 db_msonpy3o Ayla_test001 \
    --outcome verify_a1_ui_anchor \
    --checks target_app_boundary,anchor_confidence,stop_condition

# 2. 验证生成的输入
python3 validate.py input input/lp-a1-anchor-check-001.json

# 3. 用样例自测验证器
python3 validate.py input examples/input.valid.json      # → ✅ 通过
python3 validate.py input examples/input.invalid.json    # → ❌ 拒绝（external_send=true）
```

## 目录语义

| 目录 | 方向 | 内容 | 谁写 |
|------|------|------|------|
| `input/` | 007 → Manus | 事实输入 JSON（`007-bridge/v1`） | 007 / 本地 IDE |
| `receipts/` | Manus → 007 | 回执 JSON（回显 task_id/request_id） | Manus |
| `deliveries/` | Manus → 007 | 候选 ZIP + `MANIFEST.json` | Manus |
| `evidence/` | 双方 | 审计证据（模拟/拒绝链/失败关闭） | 双方 |

## 接口契约（两套 JSON Schema）

### 1. `007-bridge/v1` — 输入/回执

**必填字段**：`schema_version`、`task_id`、`request_id`、`scope`、`source_snapshot`、`requested_outcome`、`expected_checks`、`idempotency_key`

**严格拒绝规则**：
- `scope.external_send` 必须为 `false`（任何 true 一律拒绝）
- 含秘密字段（api_key/password/token/secret/credential）→ 拒绝
- 回执必须回显同一 `task_id` + `request_id`
- 回执 `external_actions` 必须为空数组
- 未知字段（additionalProperties: false）→ 拒绝

### 2. `linkpulse-delivery/v1` — ZIP MANIFEST

**必填字段**：`package_schema`、`package_id`、`created_at`、`source_baseline`、`task_ids`、`allowed_changed_paths`、`excluded`、`test_summary`、`external_actions`、`sha256`、`rollback_reference`

**严格拒绝规则**：
- `external_actions` 必须为空数组
- `sha256` 必须 64 位十六进制，且与 ZIP 实际哈希一致
- 变更路径越界（超出 `allowed_changed_paths`）→ 拒绝
- 包内含 `.env`/凭据/`node_modules`/构建产物/客户数据/未声明文件 → 拒绝

## 验证器用法

```bash
cd ~/Documents/linkpulse-bridge

# 验证单个输入
python3 validate.py input input/<file>.json

# 验证单个回执
python3 validate.py receipt receipts/<file>.json

# 验证 MANIFEST
python3 validate.py manifest deliveries/<package>/MANIFEST.json

# 验证全部（input + receipts + deliveries）
python3 validate.py all
```

退出码：`0` = 通过，`1` = 有拒绝项。

## 协作流程

```
007/IDE 写 input/<task>.json（外部发送=false，含源快照哈希）
        ↓
Manus 读 input → 受限实施 → 测试 → 审计
        ↓
Manus 写 receipts/<task>.json（回显 task_id/request_id/status/证据引用/空 external_actions）
Manus 产 deliveries/<package>/MANIFEST.json + 候选 ZIP
        ↓
007 读 ZIP → 校验哈希/路径/SHA → 只写本地更新日志（evidence/）
        ↓
用户/IDE 人工决定是否导入（不自动应用）
```

## 明确边界（红线）

| 主体 | 允许 | 禁止 |
|------|------|------|
| 007 | 导出事实 JSON、写本地日志 | 改代码、自动解压合并 ZIP、改服务器/Nginx/DNS/DB、发消息 |
| Manus | 读输入、产出候选 ZIP、审计 | 读本地密钥、控制 Android、执行未知 IDE 命令、外发客户消息 |
| 用户 | 审核 ZIP、人工导入、维持红米连接 | 把 ZIP 当自动上线 |

## 幂等与可追溯

- 每次任务一个 `task_id`，`idempotency_key = <task_id>:attempt-N`
- 重复提交同 `task_id` 幂等拒绝
- 所有 JSON 含 `request_id`（uuid）+ `timestamp`（回执）
- 源快照含 `content_hash`（sha256）+ `included_paths`，可复核基线

## Git 私有库部署

本工作区是一个独立的 Git 仓库，可直接推送到私有库。

### 首次部署

```bash
cd ~/Documents/linkpulse-bridge

# 1. 初始化仓库
git init
git add -A
git commit -m "init: 007 bridge 共享工作区（007-bridge/v1 + linkpulse-delivery/v1）"

# 2. 关联你的私有库（替换成实际地址）
git remote add origin git@github.com:<你的组织>/linkpulse-bridge.git

# 3. 推送
git branch -M main
git push -u origin main
```

### 日常使用

```bash
# 007 写输入后提交
python3 bin/new-task.py lp-a1-anchor-check-001 db_xxx device_xxx
python3 validate.py input input/lp-a1-anchor-check-001.json
git add input/ receipts/ evidence/_update_log_template.md
git commit -m "task: lp-a1-anchor-check-001 输入"

# 收到 Manus ZIP 后，只提交 MANIFEST.json（ZIP 已被 .gitignore 排除）
git add deliveries/*/MANIFEST.json
git commit -m "delivery: <package_id> MANIFEST（未自动应用）"
```

### .gitignore 保护

| 忽略项 | 原因 |
|--------|------|
| `.env` / `*.key` / `*secret*` / `*password*` | 秘密绝不进库 |
| `deliveries/**/*.zip` | 二进制大文件，只提交 MANIFEST.json |
| `evidence/*.jsonl` / `*.log` | 审计证据可能含敏感内容，按需手动 add |
| `__pycache__/` / `*.pyc` | 运行时产物 |
