#!/usr/bin/env python3
"""
new-task.py — 007 快速生成合法输入 JSON（007-bridge/v1）

自动生成 task_id、request_id(uuid)、idempotency_key、content_hash(sha256)。
外部发送强制 false，不含任何秘密。

用法:
  python3 bin/new-task.py <task_id> <tenant_db_id> <device_id> \
      --outcome verify_a1_ui_anchor \
      --checks target_app_boundary,anchor_confidence \
      --paths "src/,tests/"

示例:
  python3 bin/new-task.py lp-a1-anchor-check-001 db_msonpy3o Ayla_test001 \
      --outcome verify_a1_ui_anchor \
      --checks target_app_boundary,anchor_confidence,stop_condition \
      --paths "src/,tests/docs/contract/"

输出: input/<task_id>.json
"""
import sys
import json
import uuid
import hashlib
import argparse
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BRIDGE_DIR / "input"


def main():
    ap = argparse.ArgumentParser(description="生成 007-bridge/v1 合法输入 JSON")
    ap.add_argument("task_id", help="任务 ID，如 lp-a1-anchor-check-001")
    ap.add_argument("tenant_db_id", help="租户 DB ID，如 db_msonpy3o")
    ap.add_argument("device_id", help="设备 ID，如 Ayla_test001")
    ap.add_argument("--outcome", default="verify_a1_ui_anchor", help="期望结果")
    ap.add_argument("--checks", default="target_app_boundary,anchor_confidence,stop_condition",
                    help="逗号分隔的检查项")
    ap.add_argument("--paths", default="src/,tests/", help="逗号分隔的源路径")
    ap.add_argument("--revision", default="local-ide-export-id", help="源快照 revision")
    ap.add_argument("--attempt", type=int, default=1, help="尝试次数")
    args = ap.parse_args()

    task_id = args.task_id
    request_id = str(uuid.uuid4())
    checks = [c.strip() for c in args.checks.split(",") if c.strip()]
    paths = [p.strip() for p in args.paths.split(",") if p.strip()]

    # 源快照哈希（这里用 revision 哈希占位；真实场景应哈希实际导出内容）
    content_hash = "sha256:" + hashlib.sha256(args.revision.encode()).hexdigest()

    payload = {
        "schema_version": "007-bridge/v1",
        "task_id": task_id,
        "request_id": request_id,
        "scope": {
            "tenant_db_id": args.tenant_db_id,
            "device_id": args.device_id,
            "external_send": False,  # ★ 强制 false
        },
        "source_snapshot": {
            "revision": args.revision,
            "content_hash": content_hash,
            "included_paths": paths,
        },
        "requested_outcome": args.outcome,
        "expected_checks": checks,
        "idempotency_key": f"{task_id}:attempt-{args.attempt}",
    }

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = INPUT_DIR / f"{task_id}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"✅ 输入已生成: {out_file}")
    print(f"   task_id:      {task_id}")
    print(f"   request_id:   {request_id}")
    print(f"   external_send: false（已强制）")
    print(f"\n下一步验证: python3 validate.py input input/{task_id}.json")


if __name__ == "__main__":
    main()
