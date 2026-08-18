# 007 本地更新日志模板

> 007 收到 Manus 候选 ZIP 后，只生成本日志，**不自动应用**。

## 基本信息
- 收到时间: `{received_at}`
- package_id: `{package_id}`
- SHA-256: `{sha256}`
- 来源基线: `{source_baseline}`

## 变更文件清单
```
{changed_files}
```

## 测试结论
- typecheck: `{typecheck}`
- unit: `{unit}`
- dry_run: `{dry_run}`

## 外部动作清单
```
{external_actions}  # 必须为空
```

## 阻断项
```
{blockers}  # 无则写「无」
```

## 落地建议
```
{suggested_steps}
```

## 状态标记
**⛔ 未自动应用** — 需用户/IDE 人工审核后决定是否导入。
