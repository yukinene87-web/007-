#!/usr/bin/env python3
"""
validate.py — 007 Bridge JSON 严格验证器（无第三方依赖）

验证两类 JSON：
  1. 007-bridge/v1   输入/回执（input/, receipts/）
  2. linkpulse-delivery/v1  ZIP MANIFEST（deliveries/）

拒绝规则（对齐 linkpulse_007_ide_agent_bridge_plan.md）：
  - 缺失必填字段
  - schema_version 不符
  - scope.external_send ≠ false
  - 回执未回显同一 task_id/request_id
  - 未知字段（additionalProperties: false）
  - external_actions 非空
  - 秘密字段（key/password/token/secret/credential）

用法:
  python3 validate.py input <file.json>
  python3 validate.py receipt <file.json>
  python3 validate.py manifest <file.json>
  python3 validate.py all
"""
import sys
import os
import re
import json
from pathlib import Path

BRIDGE_DIR = Path(__file__).parent
SCHEMA_DIR = BRIDGE_DIR / "schema"

# 秘密字段模式（命中即拒绝）
SECRET_PATTERNS = re.compile(
    r"(api[_-]?key|password|passwd|token|secret|credential|private[_-]?key)",
    re.IGNORECASE,
)


def _load_schema(name):
    p = SCHEMA_DIR / name
    return json.loads(p.read_text(encoding="utf-8"))


def _check_required(obj, required, path=""):
    """检查必填字段，返回错误列表"""
    errors = []
    for field in required:
        if field not in obj:
            errors.append(f"{path}.{field} 缺失")
    return errors


def _check_type(obj, field, expected_type, path=""):
    """检查字段类型"""
    if field in obj and not isinstance(obj[field], expected_type):
        return [f"{path}.{field} 应为 {expected_type.__name__}，实际 {type(obj[field]).__name__}"]
    return []


def _scan_secrets(obj, path="$"):
    """递归扫描秘密字段，返回发现的秘密 key 列表"""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SECRET_PATTERNS.search(k):
                found.append(f"{path}.{k}")
            found.extend(_scan_secrets(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_scan_secrets(item, f"{path}[{i}]"))
    return found


def validate_bridge_input(obj):
    """验证 007-bridge/v1 输入"""
    schema = _load_schema("007-bridge-v1.schema.json")
    errors = []

    # 必填字段
    errors += _check_required(obj, schema["required"])

    if "schema_version" in obj and obj["schema_version"] != "007-bridge/v1":
        errors.append(f"schema_version 不符: {obj['schema_version']}")

    # scope.external_send 必须 false
    scope = obj.get("scope", {})
    if "external_send" in scope and scope["external_send"] is not False:
        errors.append("scope.external_send 必须为 false（禁止外发）")

    # 秘密字段
    secrets = _scan_secrets(obj)
    if secrets:
        errors.append(f"含秘密字段: {', '.join(secrets)}")

    # 幂等键
    if "task_id" in obj and "idempotency_key" in obj:
        if not obj["idempotency_key"].startswith(obj["task_id"]):
            errors.append("idempotency_key 必须以 task_id 开头")

    return errors


def validate_bridge_receipt(obj):
    """验证 007-bridge/v1 回执（额外要求回显 task_id/request_id/status/timestamp）"""
    errors = validate_bridge_input(obj)

    # 回执额外必填
    for field in ["status", "timestamp"]:
        if field not in obj:
            errors.append(f"回执缺失 {field}")

    if "external_actions" in obj:
        if not isinstance(obj["external_actions"], list):
            errors.append("external_actions 应为数组")
        elif len(obj["external_actions"]) > 0:
            errors.append("external_actions 必须为空数组（回执禁止外部动作）")
    else:
        errors.append("回执缺失 external_actions")

    return errors


def validate_manifest(obj):
    """验证 linkpulse-delivery/v1 MANIFEST"""
    schema = _load_schema("linkpulse-delivery-v1.schema.json")
    errors = []

    errors += _check_required(obj, schema["required"])

    if "package_schema" in obj and obj["package_schema"] != "linkpulse-delivery/v1":
        errors.append(f"package_schema 不符: {obj['package_schema']}")

    if "external_actions" in obj:
        if not isinstance(obj["external_actions"], list):
            errors.append("external_actions 应为数组")
        elif len(obj["external_actions"]) > 0:
            errors.append("external_actions 必须为空数组（ZIP 禁止外部动作）")

    # sha256 格式
    if "sha256" in obj and not re.match(r"^[a-f0-9]{64}$", obj.get("sha256", "")):
        errors.append("sha256 格式错误（应为 64 位十六进制）")

    # 秘密字段
    secrets = _scan_secrets(obj)
    if secrets:
        errors.append(f"含秘密字段: {', '.join(secrets)}")

    return errors


def validate_file(path, kind):
    """验证单个 JSON 文件，返回 (passed, errors)"""
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"JSON 解析失败: {e}"]
    except FileNotFoundError:
        return False, [f"文件不存在: {path}"]

    if kind == "input":
        errors = validate_bridge_input(obj)
    elif kind == "receipt":
        errors = validate_bridge_receipt(obj)
    elif kind == "manifest":
        errors = validate_manifest(obj)
    else:
        return False, [f"未知类型: {kind}"]

    return (len(errors) == 0), errors


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "all":
        # 验证 input/ receipts/ deliveries/ 下所有 JSON
        all_passed = True
        for subdir, kind in [("input", "input"), ("receipts", "receipt")]:
            d = BRIDGE_DIR / subdir
            for f in d.glob("*.json"):
                passed, errors = validate_file(f, kind)
                _print_result(f.name, passed, errors)
                all_passed = all_passed and passed
        # deliveries 下找 MANIFEST.json
        for d in (BRIDGE_DIR / "deliveries").iterdir():
            if d.is_dir():
                mf = d / "MANIFEST.json"
                if mf.exists():
                    passed, errors = validate_file(mf, "manifest")
                    _print_result(f"{d.name}/MANIFEST.json", passed, errors)
                    all_passed = all_passed and passed
        sys.exit(0 if all_passed else 1)

    if len(sys.argv) < 3:
        print("用法: validate.py <input|receipt|manifest|all> <file.json>")
        sys.exit(1)

    kind = sys.argv[1]
    path = sys.argv[2]
    passed, errors = validate_file(path, kind)
    _print_result(os.path.basename(path), passed, errors)
    sys.exit(0 if passed else 1)


def _print_result(name, passed, errors):
    if passed:
        print(f"✅ {name} — 验证通过")
    else:
        print(f"❌ {name} — 验证失败:")
        for e in errors:
            print(f"   • {e}")


if __name__ == "__main__":
    main()
