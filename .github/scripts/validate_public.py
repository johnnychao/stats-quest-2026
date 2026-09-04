#!/usr/bin/env python3
"""Validate the public-only release tree with Python's standard library."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


REPOSITORY = "johnnychao/stats-quest-2026"
BASE_SITE_URL = "https://johnnychao.github.io/stats-quest-2026/"
# v1.0.0／v1.1.0 的公開清單（沒有 PUBLIC_INVENTORY.json 的樹一律用這組常數驗證）。
# v1.2.0 起，新增的關卡與資料由樹內的 PUBLIC_INVENTORY.json 宣告，validator 再逐項核對實際內容；
# 宣告只能新增 notebooks/*.ipynb 與 data/*.csv，其餘 allowlist 與所有邊界檢查不變。
DEFAULT_NOTEBOOKS = {
    "L00_toolbox.ipynb", "L01_describe.ipynb", "L02_distributions.ipynb",
    "L03_sampling_tests.ipynb", "B1_boss_ab_test.ipynb", "L04_linear_regression.ipynb",
    "L05_overfitting.ipynb", "L06_classification.ipynb", "B2_boss_heart.ipynb",
    "L07_cv_forest.ipynb", "L08_regularization.ipynb", "L09_pca_kmeans.ipynb",
    "FINAL_boss_coffee2.ipynb", "S1_side_own_data.ipynb",
    "S2_side_multiple_testing.ipynb", "S3_side_gradient_descent.ipynb",
}
DEFAULT_INVENTORY = {
    "schema_version": 1,
    "notebooks": sorted(DEFAULT_NOTEBOOKS),
    "extra_data_files": [],
    "main_task_total": 69,
    "font_setup_count": 14,
    "csv_count": 12,
    "notebook_summary": "16 本 Colab 筆記本（13 本主線、3 本支線）",
    "csv_summary": "公開包共有 12 份固定種子合成 CSV",
}
# 先前正式版（v1.0.0～v1.1.0）所附 validator 的 SHA-256；讓新版 validator 仍能核對舊 tag 的公開樹。
KNOWN_PREVIOUS_VALIDATOR_SHA256 = {
    "3e2e583c97826c454207caa904302377a8799d4c984c97bfd850142f37b76b2c",
}
NOTEBOOKS = set(DEFAULT_NOTEBOOKS)
BASE_PUBLIC_FILES = {
    ".gitattributes",
    ".github/pages/holding.html",
    ".github/scripts/validate_public.py",
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/validate-public.yml",
    ".gitignore",
    ".nojekyll",
    "ENVIRONMENT.md",
    "README.md",
    "RELEASE_MANIFEST.json",
    "THIRD_PARTY_NOTICES.md",
    "index.html",
    "requirements.txt",
    "data/README.md",
    "data/SYNTHETIC_DATA_PROVENANCE.json",
    "data/advertising.csv",
    "data/coffee_ab_test.csv",
    "data/coffee_daily.csv",
    "data/coffee_members.csv",
    "data/coffee_sales_aug.csv",
    "data/default.csv",
    "data/final/coffee_daily_challenge.csv",
    "data/final/coffee_members_challenge.csv",
    "data/heart_check.csv",
    "data/public/auto.csv",
    "data/public/credit.csv",
    "data/public/wage.csv",
}
EXPECTED_PUBLIC_FILES = BASE_PUBLIC_FILES | {f"notebooks/{name}" for name in NOTEBOOKS}


def load_inventory(root: Path) -> dict:
    """讀取樹內宣告的公開清單；沒有就用 v1.0.0 的預設清單。宣告本身也會被逐項核對。"""
    global NOTEBOOKS, EXPECTED_PUBLIC_FILES
    path = root / "PUBLIC_INVENTORY.json"
    if not path.exists():
        return dict(DEFAULT_INVENTORY)
    inventory = json.loads(path.read_text(encoding="utf-8"))
    if inventory.get("schema_version") != 1:
        raise AssertionError("PUBLIC_INVENTORY.json schema_version must be 1")
    notebooks = inventory.get("notebooks")
    if not isinstance(notebooks, list) or not set(DEFAULT_NOTEBOOKS) <= set(notebooks):
        raise AssertionError("PUBLIC_INVENTORY.json must keep every original notebook")
    for name in notebooks:
        if not re.fullmatch(r"[A-Z0-9]+_[A-Za-z0-9_]+\.ipynb", name):
            raise AssertionError(f"invalid notebook name in inventory: {name}")
    extras = inventory.get("extra_data_files", [])
    for rel in extras:
        if not re.fullmatch(r"data/[a-z0-9_]+\.csv", rel):
            raise AssertionError(f"inventory may only add data/*.csv: {rel}")
    for key in ("main_task_total", "font_setup_count", "csv_count"):
        if not isinstance(inventory.get(key), int):
            raise AssertionError(f"PUBLIC_INVENTORY.json {key} must be an integer")
    for key in ("notebook_summary", "csv_summary"):
        if not isinstance(inventory.get(key), str) or not inventory[key]:
            raise AssertionError(f"PUBLIC_INVENTORY.json {key} must be a string")
    NOTEBOOKS = set(notebooks)
    EXPECTED_PUBLIC_FILES = BASE_PUBLIC_FILES | {"PUBLIC_INVENTORY.json"} | set(extras) | {f"notebooks/{name}" for name in NOTEBOOKS}
    return inventory


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def csv_shape(path: Path) -> tuple[int, list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        return sum(1 for _ in reader), header


def write_pages_manifest(root: Path) -> None:
    """Rewrite the copied manifest so it describes the actual Pages payload."""
    manifest_path = root / "RELEASE_MANIFEST.json"
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        relative_parts = path.relative_to(root).parts
        if ".git" in relative_parts or ".github" in relative_parts:
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        })
    output = {
        "package": f'{source.get("package", "stats-quest-2026")}-pages',
        "schema_version": 2,
        "scope": "pages-artifact",
        "release_tag": source["release_tag"],
        "release_channel": source["release_channel"],
        "site_base_url": source["site_base_url"],
        "files": files,
    }
    manifest_path.write_bytes(
        (json.dumps(output, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--expected-tag")
    parser.add_argument("--expected-channel", choices=("rc", "production"))
    parser.add_argument("--write-pages-manifest", action="store_true")
    args = parser.parse_args()
    requested_root = Path(args.root).absolute()
    candidates = [requested_root, *requested_root.rglob("*")]
    for path in candidates:
        if ".git" in path.relative_to(requested_root).parts:
            continue
        if path.is_symlink():
            raise AssertionError(f"symbolic link is not allowed in public payload: {path}")
    root = requested_root.resolve()

    if args.write_pages_manifest:
        write_pages_manifest(root)
        print(json.dumps({"status": "written", "root": str(root)}, ensure_ascii=False))
        return 0

    inventory = load_inventory(root)
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tag = manifest["release_tag"]
    channel = manifest["release_channel"]
    site_base_url = manifest["site_base_url"]
    if args.expected_tag and tag != args.expected_tag:
        raise AssertionError(f"manifest tag {tag!r} != requested tag {args.expected_tag!r}")
    if channel not in {"rc", "production"}:
        raise AssertionError(f"invalid release channel: {channel}")
    if args.expected_channel and channel != args.expected_channel:
        raise AssertionError(
            f"manifest channel {channel!r} != requested channel {args.expected_channel!r}"
        )
    expected_site = f"{BASE_SITE_URL}rc/{tag}/" if channel == "rc" else BASE_SITE_URL
    expected_key = f"statsquest2026:rc:{tag}" if channel == "rc" else "statsquest2026:prod"
    if site_base_url != expected_site:
        raise AssertionError(f"site base mismatch: {site_base_url}")

    records = {item["path"]: item for item in manifest["files"]}
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.name != "RELEASE_MANIFEST.json" and ".git" not in path.parts
    }
    actual_with_manifest = set(actual) | {"RELEASE_MANIFEST.json"}
    if actual_with_manifest != EXPECTED_PUBLIC_FILES:
        missing = sorted(EXPECTED_PUBLIC_FILES - actual_with_manifest)
        extra = sorted(actual_with_manifest - EXPECTED_PUBLIC_FILES)
        raise AssertionError(f"public file allowlist drift; missing={missing}, extra={extra}")
    if set(records) != set(actual):
        missing = sorted(set(records) - set(actual))
        extra = sorted(set(actual) - set(records))
        raise AssertionError(f"manifest inventory drift; missing={missing}, extra={extra}")
    for relative, path in actual.items():
        record = records[relative]
        if record["bytes"] != path.stat().st_size or record["sha256"] != digest(path):
            raise AssertionError(f"manifest hash drift: {relative}")

    forbidden_parts = {
        "tea" + "cher", "tea" + "chers", "solution", "solutions", "solved",
        "hid" + "den", "test", "tests", "build", "grader", "graders",
        "label", "labels", "private", "answer", "answers", "answer_key",
    }
    for path in root.rglob("*"):
        relative_parts = tuple(part.lower() for part in path.relative_to(root).parts)
        if forbidden_parts.intersection(relative_parts):
            raise AssertionError(f"forbidden public path: {path.relative_to(root)}")

    text_suffixes = {".html", ".md", ".ipynb", ".txt", ".json", ".csv", ".yml", ".yaml", ".py"}
    secret_patterns = {
        "GitHub classic token": re.compile(r"gh" + r"p_[A-Za-z0-9_]{10,}"),
        "GitHub fine-grained token": re.compile(r"github" + r"_pat_[A-Za-z0-9_]{10,}"),
        "Google API key": re.compile(r"AI" + r"za[0-9A-Za-z_-]{20,}"),
        "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
        "private key block": re.compile(r"BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
        "credential assignment": re.compile(r"(?i)\b(?:api[_-]?key|password|access[_-]?token)\b\s*[:=]\s*[\"'][^\"']{6,}[\"']"),
        "email address": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "Taiwan mobile number": re.compile(r"(?<!\d)09\d{8}(?!\d)"),
    }
    validator_path = Path(__file__).resolve()
    target_validator = root / ".github/scripts/validate_public.py"
    if target_validator.resolve() != validator_path:
        trusted_text = validator_path.read_text(encoding="utf-8")
        target_text = target_validator.read_text(encoding="utf-8")
        target_digest = hashlib.sha256(target_text.encode("utf-8")).hexdigest()
        # 工作流程永遠執行 main 上的（trusted）validator；tag 內的副本必須是 main 版或先前已發布的正式版。
        if target_text != trusted_text and target_digest not in KNOWN_PREVIOUS_VALIDATOR_SHA256:
            raise AssertionError("target release validator differs from trusted main validator")
    for relative, path in actual.items():
        if b"\r\n" in path.read_bytes():
            raise AssertionError(f"CRLF public payload would change Git hashes: {path.relative_to(root)}")
        if relative == ".github/scripts/validate_public.py" or path.suffix.lower() not in text_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise AssertionError(f"non-UTF-8 public text file: {path.relative_to(root)}") from error
        if "05_instructor_private" in content:
            raise AssertionError(f"private path marker: {path.relative_to(root)}")
        for label, pattern in secret_patterns.items():
            if pattern.search(content):
                raise AssertionError(f"{label} found in {path.relative_to(root)}")

    notebook_dir = root / "notebooks"
    found_notebooks = {path.name for path in notebook_dir.glob("*.ipynb")}
    if found_notebooks != NOTEBOOKS:
        raise AssertionError(f"public notebook inventory is not exactly {len(NOTEBOOKS)}")

    task_total = 0
    font_setup_count = 0
    scan_chunks: list[str] = [(root / "index.html").read_text(encoding="utf-8")]
    for path in sorted(notebook_dir.glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        if notebook.get("nbformat") != 4:
            raise AssertionError(f"unsupported nbformat: {path.name}")
        for cell in notebook["cells"]:
            if cell.get("cell_type") == "code":
                if cell.get("execution_count") is not None or cell.get("outputs"):
                    raise AssertionError(f"notebook contains executed output: {path.name}")
        text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
        scan_chunks.append(text)
        if "中文字型設定" in text:
            font_setup_count += 1
            for token in (
                "Noto Sans TC", "Noto Sans CJK TC", "Microsoft JhengHei",
                "font.sans-serif", "_available_fonts", "subprocess.run(", "check=True",
            ):
                if token not in text:
                    raise AssertionError(f"cross-platform Chinese font setup missing {token!r}: {path.name}")
            if 'subprocess.run("apt-get' in text or "shell=True" in text:
                raise AssertionError(f"unsafe or legacy Chinese font setup: {path.name}")
        if any(token in text for token in ("_HID" + "DEN", "base" + "64", "g" + "zip", "隱藏資料(")):
            raise AssertionError(f"embedded answer mechanism: {path.name}")
        if not path.name.startswith("S"):
            match = re.search(r"^_TASKS = (.+)$", text, flags=re.M)
            task_total += len(json.loads(match.group(1))) if match else 0
    if task_total != inventory["main_task_total"]:
        raise AssertionError(f"main task count is {task_total}, expected {inventory['main_task_total']}")
    if font_setup_count != inventory["font_setup_count"]:
        raise AssertionError(f"Chinese font setup count is {font_setup_count}, expected {inventory['font_setup_count']}")

    index = scan_chunks[0]
    scan_text = "\n".join(scan_chunks)
    expected_robots = "noindex,nofollow" if channel == "rc" else "index,follow"
    if f'<meta name="robots" content="{expected_robots}">' not in index:
        raise AssertionError(f"robots policy does not match {channel} channel")
    if f"{REPOSITORY}/main/" in scan_text or f"{REPOSITORY}/blob/main/" in scan_text:
        raise AssertionError("mutable main URL found")
    if re.search(r"(?:\bSALT\b|\bsalt\b|_SALT)", scan_text):
        raise AssertionError("public progress namespace is still labelled as salt")
    for marker in ("05_instructor_private", "TEACHER_PASS", "BEGIN PRIVATE KEY"):
        if marker in scan_text:
            raise AssertionError(f"private marker found: {marker}")

    stale_copy = (
        "Default（信用卡違約，ISLP）", "Default（ISLP）", "ISLP 公開資料",
        "用自己的一份資料", "帶自己的資料上山", "含隱藏測試集", "隱藏測試集評分",
        "老師密語", "勇者健檢中心（模擬）", "入山測驗（前測）",
        "三份勇者咖啡的資料", "另有三份公開資料",
    )
    for phrase in stale_copy:
        if phrase in index:
            raise AssertionError(f"stale public copy: {phrase}")
    public_visible_text = index + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(notebook_dir.glob("*.ipynb"))
    )
    for misleading in ("領取結業證書", "CERTIFICATE OF COMPLETION", "具備機器學習的統計基礎與建模能力"):
        if misleading in public_visible_text:
            raise AssertionError(f"unverified certificate claim: {misleading}")
    for required in (
        "學習完成紀錄", "不是補習班正式結業證書", "教師離線驗收",
        "function openModal", "function closeModal", 'event.key === "Escape"',
        'for="nick"', 'for="legacyCode"', 'aria-valuenow="0"',
        '<span class="slot-mark" aria-hidden="true">',
        '<fieldset class="q">', 'min-height:44px', '--on-sea:#102A38',
        '不含姓名、學號或電話', '自我學習紀錄，不是身分、成績或教師驗收證明',
        inventory["notebook_summary"],
        '這組題目與紙本的 6 分鐘前後測不同，不納入前後測比較',
        inventory["csv_summary"],
        '不作醫療診斷、個人風險判定或臨床效能宣稱',
        '紙本先介紹 S2，課外可完成',
        '.res-cat a,footer a{display:inline-flex;align-items:center;min-height:44px}',
        'state.cleared = {};', 'state.quiz = null;',
        '這會清除這台電腦現有的集章、暖身結果與第一部繼承紀錄',
    ):
        if required not in index:
            raise AssertionError(f"missing completion or accessibility boundary: {required}")

    links = set(re.findall(rf"blob/{re.escape(tag)}/notebooks/([^\"'\s<]+\.ipynb)", index))
    if links != NOTEBOOKS:
        raise AssertionError("homepage Colab links are not exactly the 16 notebooks")
    site_urls = set(
        re.findall(re.escape(BASE_SITE_URL) + r"(?:rc/[^/\"'\s<>)]+/)?", scan_text)
    )
    if site_urls != {site_base_url}:
        raise AssertionError(f"cross-channel site URLs: {sorted(site_urls)}")
    if f'const KEY = "{expected_key}";' not in index:
        raise AssertionError("localStorage key is not isolated by release channel")
    if "fonts.googleapis.com" in index:
        raise AssertionError("homepage must not make an undeclared Google Fonts request")
    for privacy_copy in (
        "本頁的暱稱與進度只儲存在這台電腦的瀏覽器",
        "Notebook 輸入的暱稱與執行內容則由 Google Colab 處理",
    ):
        if privacy_copy not in index:
            raise AssertionError(f"missing privacy boundary: {privacy_copy}")
    if ".playwright-cli/" not in (root / ".gitignore").read_text(encoding="utf-8"):
        raise AssertionError("local Playwright artifacts are not ignored")

    daily_rows, daily_columns = csv_shape(root / "data/final/coffee_daily_challenge.csv")
    member_rows, member_columns = csv_shape(root / "data/final/coffee_members_challenge.csv")
    if daily_rows != 21 or "營收" in daily_columns:
        raise AssertionError("daily FINAL challenge is not feature-only")
    if member_rows != 400 or "回購" in member_columns:
        raise AssertionError("member FINAL challenge is not feature-only")

    data_root = root / "data"
    expected_csvs = {
        relative.removeprefix("data/")
        for relative in EXPECTED_PUBLIC_FILES
        if relative.startswith("data/") and relative.endswith(".csv")
    }
    actual_csvs = {
        path.relative_to(data_root).as_posix()
        for path in data_root.rglob("*.csv")
        if path.is_file()
    }
    if actual_csvs != expected_csvs:
        raise AssertionError("public synthetic CSV inventory drift")
    provenance = json.loads((data_root / "SYNTHETIC_DATA_PROVENANCE.json").read_text(encoding="utf-8"))
    if provenance.get("schema_version") != 2 or provenance.get("generator_version") != tag:
        raise AssertionError("synthetic data provenance version mismatch")
    if provenance.get("serialization") != {"encoding": "utf-8", "newline": "LF", "csv_index": False}:
        raise AssertionError("synthetic data serialization contract mismatch")
    provenance_records = provenance.get("datasets", {})
    if len(expected_csvs) != inventory["csv_count"]:
        raise AssertionError(f"public CSV count is {len(expected_csvs)}, expected {inventory['csv_count']}")
    if set(provenance_records) != expected_csvs:
        raise AssertionError(f"synthetic data provenance must cover all {inventory['csv_count']} CSV files")
    for relative in sorted(expected_csvs):
        path = data_root / relative
        rows, columns = csv_shape(path)
        record = provenance_records[relative]
        if record.get("rows") != rows or record.get("columns") != columns:
            raise AssertionError(f"synthetic data provenance schema drift: {relative}")
        if record.get("sha256") != digest(path):
            raise AssertionError(f"synthetic data provenance hash drift: {relative}")
        if record.get("privacy_classification") != "fully_synthetic_no_real_person_records":
            raise AssertionError(f"synthetic data privacy classification missing: {relative}")
        if not isinstance(record.get("seed"), int) or not record.get("generator"):
            raise AssertionError(f"synthetic data seed/generator missing: {relative}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("source_module_sha256", ""))):
            raise AssertionError(f"synthetic generator source hash invalid: {relative}")
        if record.get("label_removed") != relative.startswith("final/"):
            raise AssertionError(f"synthetic challenge label metadata mismatch: {relative}")

    print(json.dumps({
        "status": "pass", "tag": tag, "channel": channel,
        "site_base_url": site_base_url, "notebooks": len(found_notebooks),
        "main_tasks": task_total, "manifest_files": len(records),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
