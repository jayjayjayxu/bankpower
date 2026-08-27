#!/usr/bin/env python3
"""Load captured public compute product and price snapshots into MySQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".vendor"))
import pymysql


ROOT = Path(__file__).resolve().parent
SNAPSHOT_DIR = ROOT / "sources" / "compute" / "2026-08-25"
CNIX_CATEGORIES = {"bare-metal-gpu", "cloud-gpu", "cpu-vm", "gpu-baremetal", "light-gpu-vm"}
CNIX_PRODUCTS_API = "https://ai.cnix.cn/api/market/v1/products"
SZAICPP_API = "https://console.szaicpp.com/cpn/tenant/v1/recommend/list?paging.page=1&paging.perPage=100"


def connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD", ""),
        database=os.getenv("DB_NAME", "spdb_power_finance"), charset="utf8mb4",
        autocommit=False, cursorclass=pymysql.cursors.DictCursor,
    )


def sha(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def decimal(value):
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None


def number(text):
    if text is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(text).replace(",", ""))
    return Decimal(match.group()) if match else None


def memory_gb(text):
    if not text:
        return None
    text = str(text).upper().replace(" ", "")
    values = [Decimal(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if not values:
        return None
    value = values[-1]
    if "TB" in text:
        value *= 1024
    return value


def accelerator(fields, name):
    model = fields.get("gpu-model")
    count = number(fields.get("gpu-count"))
    summary = fields.get("summary-gpu", "")
    if not model and summary:
        cleaned = re.sub(r"^\s*\d+\s*[xX*×]\s*", "", summary).strip()
        model = cleaned or None
    if count is None and summary:
        match = re.match(r"\s*(\d+)\s*[xX*×]", summary)
        if match:
            count = Decimal(match.group(1))
    if not model:
        for token in ("H100", "H800", "H20", "A100", "A800", "L40", "L20", "RTX 4090", "RTX4090", "Ascend"):
            if token.lower() in name.lower():
                model = token
                break
    mem_text = fields.get("gpu-graphics-memory") or summary
    mem = memory_gb(mem_text)
    return model, count, mem


def ensure_source(cur, org, title, url):
    digest = hashlib.sha256(f"{org}|{title}|{url}".encode()).hexdigest()
    cur.execute(
        """INSERT INTO data_source
           (source_org,source_title,source_url,source_date,source_tier,data_quality,
            statistical_scope,source_hash,notes)
           VALUES (%s,%s,%s,'2026-08-25','B','PUBLIC_PLATFORM_SNAPSHOT',
                   '公开算力商品与报价快照；不代表成交价、库存或物理装机容量',%s,
                   '原始JSON及SHA-256保存在etl/sources/compute/2026-08-25。')
           ON DUPLICATE KEY UPDATE source_title=VALUES(source_title),source_url=VALUES(source_url),
             source_date=VALUES(source_date),data_quality=VALUES(data_quality),
             statistical_scope=VALUES(statistical_scope),notes=VALUES(notes)""",
        (org, title, url, digest),
    )
    cur.execute("SELECT source_id FROM data_source WHERE source_hash=%s", (digest,))
    return cur.fetchone()["source_id"]


def field_map(product):
    return {
        item.get("product_field", {}).get("key"): item.get("value")
        for item in product.get("field_values", [])
        if item.get("product_field", {}).get("key")
    }


def manifest_capture():
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text(encoding="utf-8"))
    captured = datetime.fromisoformat(manifest["captured_at"])
    return captured.replace(tzinfo=None)


def upsert_listing(cur, row):
    cur.execute(
        """INSERT INTO compute_platform_resource_listing_v1
           (platform_id,facility_v2_id,external_product_id,product_name,provider_name,resource_type,
            accelerator_model,accelerator_count,accelerator_memory_gb,cpu_cores,system_memory_gb,
            platform_region_label,available_zone,physical_region_text,locality_scope,availability_status,
            source_updated_at,source_api_url,captured_at,source_id,raw_record_hash,data_quality,notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE product_name=VALUES(product_name),provider_name=VALUES(provider_name),
             resource_type=VALUES(resource_type),accelerator_model=VALUES(accelerator_model),
             accelerator_count=VALUES(accelerator_count),accelerator_memory_gb=VALUES(accelerator_memory_gb),
             cpu_cores=VALUES(cpu_cores),system_memory_gb=VALUES(system_memory_gb),
             platform_region_label=VALUES(platform_region_label),available_zone=VALUES(available_zone),
             physical_region_text=VALUES(physical_region_text),locality_scope=VALUES(locality_scope),
             availability_status=VALUES(availability_status),source_updated_at=VALUES(source_updated_at),
             source_api_url=VALUES(source_api_url),data_quality=VALUES(data_quality),notes=VALUES(notes)""",
        row,
    )
    cur.execute(
        """SELECT listing_id FROM compute_platform_resource_listing_v1
           WHERE platform_id=%s AND external_product_id=%s AND captured_at=%s AND raw_record_hash=%s""",
        (row[0], row[2], row[18], row[20]),
    )
    return cur.fetchone()["listing_id"]


def insert_price(cur, listing_id, platform_id, product_key, scope, method, cycle, minimum_term,
                 value, unit, config, api_url, captured, source_id, record, validation, notes):
    if value is None:
        return
    record_hash = sha(record)
    cur.execute(
        """INSERT INTO compute_product_price_snapshot_v1
           (listing_id,platform_id,external_product_id,price_scope,billing_method,billing_cycle,minimum_term,
            price_value,currency,price_unit,promotion_flag,configuration_text,validation_status,source_api_url,
            captured_at,source_id,raw_record_hash,data_quality,notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'CNY',%s,0,%s,%s,%s,%s,%s,%s,'B',%s)
           ON DUPLICATE KEY UPDATE listing_id=VALUES(listing_id),billing_method=VALUES(billing_method),
             billing_cycle=VALUES(billing_cycle),minimum_term=VALUES(minimum_term),price_value=VALUES(price_value),
             price_unit=VALUES(price_unit),configuration_text=VALUES(configuration_text),
             validation_status=VALUES(validation_status),data_quality=VALUES(data_quality),notes=VALUES(notes)""",
        (listing_id, platform_id, product_key, scope, method, cycle, minimum_term, value, unit,
         config[:1000] if config else None, validation, api_url, captured, source_id, record_hash, notes),
    )


def load_cnix(cur, platform_id, source_id, captured):
    products = json.loads((SNAPSHOT_DIR / "cnix_products.json").read_text(encoding="utf-8"))
    products = [p for p in products if p.get("product_category", {}).get("key") in CNIX_CATEGORIES]
    stats = {"listings": 0, "prices": 0, "conflicts": 0}
    for summary in products:
        key = summary["key"]
        detail_path = SNAPSHOT_DIR / "cnix_product_details" / f"{key}.json"
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        fields = field_map(detail)
        category = detail.get("product_category", {})
        model, accel_count, accel_mem = accelerator(fields, detail.get("name", ""))
        region = fields.get("zone") or fields.get("deployment-region")
        zone = fields.get("available-zone")
        region_text = " / ".join(x for x in (region, zone) if x) or None
        locality = "LOCAL_SHENZHEN" if region_text and "深圳" in region_text else "UNDISCLOSED"
        provider = fields.get("vendor-type") or fields.get("supplier") or detail.get("supplier", {}).get("name")
        cpu = number(fields.get("summary-vcpu") or fields.get("CPU"))
        memory = memory_gb(fields.get("summary-memory") or fields.get("memory"))
        selected_config = {k: fields[k] for k in sorted(fields) if k in {
            "billing-model", "minimum-order-duration", "summary-gpu", "gpu-model", "gpu-count",
            "summary-vcpu", "CPU", "summary-memory", "memory", "zone", "available-zone", "specification"
        }}
        source_updated = detail.get("updated_at")
        if source_updated:
            source_updated = datetime.fromisoformat(source_updated.replace("Z", "+00:00")).replace(tzinfo=None)
        raw_hash = sha(detail)
        listing_id = upsert_listing(cur, (
            platform_id, None, key, detail.get("name") or key, provider, category.get("name"), model,
            accel_count, accel_mem, cpu, memory, region, zone, region_text, locality,
            "ON_DEMAND" if detail.get("stock_mode") == "on_demand" else ("ENABLED" if detail.get("enabled") else "DISABLED"),
            source_updated, f"https://ai.cnix.cn/api/market/v1/products/{key}", captured, source_id, raw_hash, "B",
            json.dumps(selected_config, ensure_ascii=False, sort_keys=True)[:1000],
        ))
        stats["listings"] += 1

        list_price = decimal(detail.get("proposed_price"))
        cycle = detail.get("primary_billing_cycle")
        minimum = str(detail.get("min_delivery_cycle")) if detail.get("min_delivery_cycle") is not None else None
        insert_price(cur, listing_id, platform_id, key, "LIST_REFERENCE", "PLATFORM_REFERENCE", cycle, minimum,
                     list_price, f"CNY/PRODUCT/{cycle or 'UNKNOWN'}", detail.get("name"), CNIX_PRODUCTS_API,
                     captured, source_id, {"key": key, "proposed_price": str(list_price), "cycle": cycle},
                     "OBSERVED", "平台列表参考价/起价，不代表成交价格。")
        if list_price is not None:
            stats["prices"] += 1

        detail_prices = []
        primary_group_keys = {"compute-instance", "instance", "cumpute-instance"}
        for group in detail.get("billing_item_groups", []):
            for item in group.get("items", []):
                price = decimal(item.get("unit_price"))
                item_cycle = item.get("billing_cycle")
                config = f"{group.get('name') or ''}: {item.get('name') or item.get('key') or ''}".strip()
                is_primary = group.get("key") in primary_group_keys
                validation = "OBSERVED"
                if is_primary and list_price is not None and price is not None and price != list_price:
                    validation = "CONFLICT_WITH_LIST_REFERENCE"
                elif not is_primary:
                    validation = "NOT_COMPARABLE_ADDON"
                insert_price(cur, listing_id, platform_id, key, "DETAIL_CONFIG" if is_primary else "DETAIL_ADDON",
                             item.get("billing_mode"), item_cycle,
                             minimum, price, f"CNY/{item.get('unit') or 'UNIT'}/{item_cycle or 'UNKNOWN'}", config,
                             f"https://ai.cnix.cn/api/market/v1/products/{key}", captured, source_id,
                             {"key": key, "group": group.get("key"), "item": item}, validation,
                             "详情页主实例或附加计费项；与列表价冲突时两者均保留。")
                if price is not None:
                    if is_primary:
                        detail_prices.append(price)
                    stats["prices"] += 1
        if list_price is not None and detail_prices and any(x != list_price for x in detail_prices):
            stats["conflicts"] += 1
    return stats


def load_szaicpp(cur, platform_id, facility_id, source_id, captured):
    payload = json.loads((SNAPSHOT_DIR / "szaicpp_recommend_ai.json").read_text(encoding="utf-8"))
    stats = {"listings": 0, "prices": 0}
    for product in payload["recommendList"]:
        count = None
        for item in product.get("specInfo", []):
            if item.get("key") in ("GPU", "NPU"):
                count = decimal(item.get("number"))
        product_hash = sha({k: v for k, v in product.items() if k != "logo"})
        listing_id = upsert_listing(cur, (
            platform_id, facility_id, product["uuid"], product.get("recommendProduct") or product.get("productName"),
            product.get("providerName"), "AI算力产品", product.get("acceleratorModel"), count, None,
            decimal(product.get("cpuCore")), decimal(product.get("memory")), "鹏城实验室", None, "深圳/鹏城实验室",
            "LOCAL_SHENZHEN", "RECOMMENDED_LISTING", datetime.fromtimestamp(int(product["updateTime"])),
            SZAICPP_API, captured, source_id, product_hash, "B",
            json.dumps({"specInfo": product.get("specInfo", []), "poolUuid": product.get("poolUuid")}, ensure_ascii=False)[:1000],
        ))
        stats["listings"] += 1
        cycle_map = {1: "hourly", 4: "monthly"}
        cycle = cycle_map.get(product.get("priceCycle"), f"code_{product.get('priceCycle')}")
        insert_price(cur, listing_id, platform_id, product["uuid"], "LIST_REFERENCE", "PUBLIC_API", cycle, None,
                     decimal(product.get("price")), f"CNY/PRODUCT/{cycle}", product.get("recommendProduct"), SZAICPP_API,
                     captured, source_id, {k: v for k, v in product.items() if k != "logo"}, "OBSERVED",
                     "公开推荐商品价格；卡数为商品配置，不代表可售库存。")
        stats["prices"] += 1
    return stats


def execute(execute_mode):
    if not SNAPSHOT_DIR.exists():
        raise SystemExit(f"Missing raw snapshot directory: {SNAPSHOT_DIR}")
    captured = manifest_capture()
    db = connect()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT platform_code,platform_id FROM compute_service_platform_v1")
            platforms = {r["platform_code"]: r["platform_id"] for r in cur.fetchall()}
            cur.execute("SELECT facility_code,facility_v2_id FROM enterprise_data_center_v2")
            facilities = {r["facility_code"]: r["facility_v2_id"] for r in cur.fetchall()}
            if not {"GBACPDP", "SZAICPP"}.issubset(platforms) or "SZCF007" not in facilities:
                raise RuntimeError("Run etl/24_compute_infrastructure_v1.py --execute first")

            cnix_source = ensure_source(cur, "粤港澳大湾区一体化算力服务平台", "2026-08-25公开算力商品API快照", CNIX_PRODUCTS_API)
            sz_source = ensure_source(cur, "深圳市智慧城市算力统筹调度平台", "2026-08-25推荐算力商品API快照", SZAICPP_API)
            cnix = load_cnix(cur, platforms["GBACPDP"], cnix_source, captured)
            szaicpp = load_szaicpp(cur, platforms["SZAICPP"], facilities["SZCF007"], sz_source, captured)
            cur.execute(
                """INSERT INTO compute_facility_platform_relation_v1
                   (facility_v2_id,platform_id,relation_type,capacity_scope,relation_status,
                    included_in_local_capacity_total,as_of_date,source_id,evidence_grade,notes,model_version)
                   VALUES (%s,%s,'LISTED','PRODUCT_LISTING','VERIFIED',0,'2026-08-25',%s,'B',
                           '公开API展示3个鹏城实验室/鹏城云脑Ⅱ商品；商品卡数不是设施库存。','V1.0')
                   ON DUPLICATE KEY UPDATE capacity_scope=VALUES(capacity_scope),relation_status=VALUES(relation_status),
                     as_of_date=VALUES(as_of_date),source_id=VALUES(source_id),evidence_grade=VALUES(evidence_grade),
                     notes=VALUES(notes)""",
                (facilities["SZCF007"], platforms["SZAICPP"], sz_source),
            )

            cur.execute("SELECT COUNT(*) AS c FROM compute_platform_resource_listing_v1")
            total_listings = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM compute_product_price_snapshot_v1")
            total_prices = cur.fetchone()["c"]

        if execute_mode:
            db.commit()
        else:
            db.rollback()
        print(("COMMIT" if execute_mode else "DRY-RUN ROLLBACK"), {
            "cnix": cnix, "szaicpp": szaicpp, "total_listings": total_listings, "total_prices": total_prices,
        })
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    execute(args.execute)
