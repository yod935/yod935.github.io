"""
Build final index.html by generating separate JSON data files.
Reads Buyer_Catalog.xlsx and all Excel files in Organized_Products_V2/,
parses them (including extracting images), and outputs:
  - data/tree.json        (category tree)
  - data/search.json      (search index)
  - data/products.json   (product data, filtered: only rows with images)
  - images/               (extracted images)
  - index.html            (main page, loads JSON via fetch)
"""
import json, os, openpyxl, sys, base64, zipfile, xml.etree.ElementTree as ET, shutil
from PIL import Image
import math

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
HTML_TEMPLATE = os.path.join(PROJECT_ROOT, "Product_Catalog.template.html")
HTML_OUTPUT  = os.path.join(PROJECT_ROOT, "index.html")
CATALOG_XLSX = os.path.join(HERE, "Buyer_Catalog.xlsx")
PRODUCTS_DIR = os.path.join(PROJECT_ROOT, "Organized_Products_V2")
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")
IMAGES_DIR   = os.path.join(PROJECT_ROOT, "images")
# --- Build to temp directories first, then atomically swap on success ---
TEMP_DATA_DIR   = os.path.join(PROJECT_ROOT, "data_temp")
TEMP_IMAGES_DIR = os.path.join(PROJECT_ROOT, "images_temp")

# ============================================================
# Step 0: Prepare temp output directories
# ============================================================
print("[0/7] Preparing temp output directories ...")
for d in [TEMP_DATA_DIR, TEMP_IMAGES_DIR]:
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)
print("  (existing data/ and images/ are preserved until swap)")

# ============================================================
# Step 1: Read Buyer_Catalog.xlsx to get file list
# ============================================================
print("[1/6] Reading Buyer_Catalog.xlsx ...")
wb = openpyxl.load_workbook(CATALOG_XLSX)
ws = wb.active
rows = []
for r in range(2, ws.max_row + 1):
    no_val = ws.cell(row=r, column=1).value
    if no_val is None:
        continue
    try:
        no = int(no_val)
    except:
        continue
    levels = []
    for c in range(2, 7):
        v = ws.cell(row=r, column=c).value
        if v and str(v).strip():
            levels.append(str(v).strip())
    fname = str(ws.cell(row=r, column=7).value or "").strip()
    fpath = str(ws.cell(row=r, column=8).value or "").strip()
    rows.append({"no": no, "levels": levels, "fname": fname, "fpath": fpath})
wb.close()
print(f"  Loaded {len(rows)} products")

# ============================================================
# Step 2: Build category tree and search data
# ============================================================
print("[2/6] Building category tree and search data ...")

def insert_into_tree(tree, row, depth=0):
    if depth >= len(row["levels"]):
        if "_files" not in tree:
            tree["_files"] = []
        tree["_files"].append({"no": row["no"], "name": row["fname"], "path": row["fpath"]})
        return
    key = row["levels"][depth]
    if "_children" not in tree:
        tree["_children"] = []
    found = None
    for child in tree["_children"]:
        if child.get("name") == key:
            found = child
            break
    if found is None:
        found = {"name": key}
        tree["_children"].append(found)
    insert_into_tree(found, row, depth + 1)

root = {"_children": []}
for row in rows:
    insert_into_tree(root, row, 0)

def calc_totals(node):
    total = len(node.get("_files", []))
    for child in node.get("_children", []):
        total += calc_totals(child)
    node["total"] = total
    return total

calc_totals(root)
tree_data = root["_children"]
tree_data.sort(key=lambda x: -x["total"])
for node in tree_data:
    if "_children" in node:
        node["_children"].sort(key=lambda x: -x.get("total", 0))
        for child in node["_children"]:
            if "_children" in child:
                child["_children"].sort(key=lambda x: -x.get("total", 0))
                for gc in child["_children"]:
                    if "_children" in gc:
                        gc["_children"].sort(key=lambda x: -x.get("total", 0))
                        for gg in gc["_children"]:
                            if "_children" in gg:
                                gg["_children"].sort(key=lambda x: -x.get("total", 0))

# --- Merge small top-level categories (< 50 products) into "Other" ---
OTHER_THRESHOLD = 50
large_cats = [c for c in tree_data if c["total"] >= OTHER_THRESHOLD]
small_cats = [c for c in tree_data if c["total"] < OTHER_THRESHOLD]
if small_cats:
    other_total = sum(c["total"] for c in small_cats)
    other_node = {"name": "Other", "total": other_total, "_children": small_cats}
    tree_data = large_cats + [other_node]
    tree_data.sort(key=lambda x: -x["total"])
    print(f"  Merged {len(small_cats)} small categories into 'Other' ({other_total} products)")

search_data = [
    {
        "no": r["no"],
        "fname": r["fname"],
        "fpath": r["fpath"],
        "breadcrumb": " > ".join(r["levels"]),
        "levels": r["levels"],
    }
    for r in rows
]

total_cats = len(tree_data)
print(f"  Top categories: {total_cats}, Search entries: {len(search_data)}")

# ============================================================
# Step 3: Parse all Excel files, extract images
# ============================================================
print("[3/6] Parsing all Excel files & extracting images (this may take a while) ...")

XDR_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

# --- Placeholder image detection ---
NO_IMAGE_PLACEHOLDER_COUNT = 0

def is_placeholder_image(image_path):
    """
    Detect NO IMAGE AVAILABLE placeholder images.
    These are small (110x110), mostly white (>85%), low-variance images embedded in Excel
    as placeholders for products without actual photos.
    Returns True if the image should be discarded.
    """
    global NO_IMAGE_PLACEHOLDER_COUNT
    try:
        img = Image.open(image_path)
        img.load()
        w, h = img.size
        # Only check small images (real product photos are usually larger or more detailed)
        if w > 200 or h > 200:
            return False
        gray = img.convert('L')
        hist = gray.histogram()
        total_px = sum(hist)
        if total_px == 0:
            return False
        white_pct = sum(hist[241:256]) / total_px * 100
        avg = sum(i * hist[i] for i in range(256)) / total_px
        variance = sum(hist[i] * (i - avg) ** 2 for i in range(256)) / total_px
        std_dev = math.sqrt(variance)
        # Placeholder criteria: mostly white, low variance, small dimensions
        if white_pct >= 85 and avg >= 240 and std_dev < 20:
            NO_IMAGE_PLACEHOLDER_COUNT += 1
            return True
    except Exception:
        pass
    return False

def extract_images_from_xlsx(xlsx_path, output_base_dir, rel_path_key):
    """
    Extract embedded images from the 'Products' sheet of an xlsx file.
    Returns dict mapping data_row_index -> relative_image_path.
    """
    import os, zipfile
    result = {}

    safe_name = str(hash(rel_path_key) & 0xFFFFFFFF)
    img_output_dir = os.path.join(output_base_dir, safe_name)
    os.makedirs(img_output_dir, exist_ok=True)

    try:
        zf = zipfile.ZipFile(xlsx_path, 'r')
        namelist = zf.namelist()
        media_files = [n for n in namelist if n.startswith('xl/media/')]
        if not media_files:
            zf.close()
            return result

        # ── Step A: Find which drawing file belongs to the "Products" sheet ──
        drawing_path = None
        drawing_rels_path = None
        SM_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

        wb_xml = zf.read('xl/workbook.xml')
        wb_root = ET.fromstring(wb_xml)
        sheet_rid = None
        for s in wb_root.iter('{%s}sheet' % SM_NS):
            if s.get('name') == 'Products':
                sheet_rid = s.get('{%s}id' % R_NS)
                break
        if not sheet_rid:
            if 'xl/drawings/drawing1.xml' in namelist:
                drawing_path = 'xl/drawings/drawing1.xml'
                drawing_rels_path = 'xl/drawings/_rels/drawing1.xml.rels'
        else:
            wb_rels_path = 'xl/_rels/workbook.xml.rels'
            if wb_rels_path in namelist:
                wb_rels_xml = zf.read(wb_rels_path)
                wb_rels_root = ET.fromstring(wb_rels_xml)
                sheet_file = None
                for rel in wb_rels_root.iter('{%s}Relationship' % RELS_NS):
                    if rel.get('Id') == sheet_rid:
                        sheet_file = rel.get('Target', '').lstrip('/')
                        break
                if sheet_file and sheet_file in namelist:
                    sheet_xml = zf.read(sheet_file)
                    sheet_root = ET.fromstring(sheet_xml)
                    drawing_rid = None
                    for dw in sheet_root.iter('{%s}drawing' % SM_NS):
                        drawing_rid = dw.get('{%s}id' % R_NS)
                        break
                    if drawing_rid:
                        sheet_dir = os.path.dirname(sheet_file)
                        sheet_name = os.path.basename(sheet_file)
                        sheet_rels_path = os.path.join(sheet_dir, '_rels', sheet_name + '.rels').replace('\\', '/')
                        if sheet_rels_path in namelist:
                            sheet_rels_xml = zf.read(sheet_rels_path)
                            sheet_rels_root = ET.fromstring(sheet_rels_xml)
                            for rel in sheet_rels_root.iter('{%s}Relationship' % RELS_NS):
                                if rel.get('Id') == drawing_rid:
                                    target = rel.get('Target', '')
                                    if target.startswith('/'):
                                        resolved = target.lstrip('/')
                                    else:
                                        resolved = os.path.normpath(os.path.join(sheet_dir, target)).replace('\\', '/')
                                    if resolved in namelist:
                                        drawing_path = resolved
                                        drawing_rels_path = os.path.join(os.path.dirname(resolved), '_rels', os.path.basename(resolved) + '.rels').replace('\\', '/')
                                    break

        if not drawing_path or drawing_path not in namelist:
            zf.close()
            return result

        # ── Step B: Parse drawing relationships ──
        rid_map = {}
        if drawing_rels_path and drawing_rels_path in namelist:
            rels_xml = zf.read(drawing_rels_path)
            try:
                rels_root = ET.fromstring(rels_xml)
                for rel in rels_root.iter('{%s}Relationship' % RELS_NS):
                    rid = rel.get('Id')
                    target = rel.get('Target', '')
                    rid_map[rid] = target
            except:
                pass

        # ── Step C: Parse drawing XML, extract image positions ──
        dw_xml = zf.read(drawing_path)
        root = ET.fromstring(dw_xml)

        img_counter = 0
        for anchor in root.iter('{%s}oneCellAnchor' % XDR_NS):
            row_idx = None
            blip_rid = None
            for elem in anchor.iter():
                tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag_local == 'row' and row_idx is None:
                    try:
                        row_idx = int(elem.text)
                    except (ValueError, TypeError):
                        pass
                elif tag_local == 'blip':
                    blip_rid = elem.get('{%s}embed' % R_NS)
            if row_idx is None or blip_rid is None:
                continue
            media_target = rid_map.get(blip_rid, '')
            if not media_target:
                continue
            media_target = media_target.lstrip('/')
            img_counter += 1
            ext = os.path.splitext(media_target)[1]
            out_name = f'img{img_counter}{ext}'
            out_path = os.path.join(img_output_dir, out_name)
            try:
                img_data = zf.read(media_target)
                with open(out_path, 'wb') as f:
                    f.write(img_data)
                if not is_placeholder_image(out_path):
                    result[row_idx - 1] = f"images/{safe_name}/{out_name}"
                else:
                    os.remove(out_path)  # Discard placeholder file
            except Exception as e:
                print(f"    WARNING: Could not extract image {media_target}: {e}")
        zf.close()
    except Exception as e:
        print(f"    WARNING: Could not process {xlsx_path}: {e}")
    return result

embedded_data = {}  # {rel_path: {"h": headers, "r": rows, "i": {row_idx: img_path}}}
parse_errors = 0
parse_count = 0
total_images_extracted = 0
files_with_imgs = 0

for idx, row in enumerate(rows):
    rel_path = row["fpath"]
    full_path = os.path.join(PROJECT_ROOT, rel_path.replace("/", os.sep))

    if not os.path.exists(full_path):
        parse_errors += 1
        continue

    try:
        wb = openpyxl.load_workbook(full_path, data_only=True)
        ws = wb["Products"] if "Products" in wb.sheetnames else wb.active

        # Read all cell data
        data = []
        for row_idx in range(1, ws.max_row + 1):
            row_data = []
            for col_idx in range(1, ws.max_column + 1):
                cell_value = ws.cell(row=row_idx, column=col_idx).value
                if cell_value is None:
                    row_data.append("")
                elif isinstance(cell_value, (int, float)):
                    row_data.append(cell_value)
                else:
                    row_data.append(str(cell_value))
            data.append(row_data)
        wb.close()

        if len(data) >= 1:
            js_path = rel_path.replace("\\", "/")

            # Extract images
            img_map = extract_images_from_xlsx(full_path, TEMP_IMAGES_DIR, js_path)
            if img_map:
                total_images_extracted += len(img_map)
                files_with_imgs += 1

            # ── Filter: keep only rows that have images ──
            headers = data[0]
            all_rows = data[1:]
            filtered_rows = []
            filtered_img_map = {}
            new_idx = 0
            for old_idx, r in enumerate(all_rows):
                # old_idx is 0-based in all_rows, corresponds to Excel row (old_idx+2)
                # img_map keys are 0-based data row indices (from extract_images_from_xlsx)
                if str(old_idx) in img_map or old_idx in img_map:
                    # This row has an image → keep it
                    filtered_rows.append(r)
                    # Update img_map key to new index
                    old_key = str(old_idx) if str(old_idx) in img_map else old_idx
                    filtered_img_map[str(new_idx)] = img_map[old_key]
                    new_idx += 1
                # else: skip this row (no image)

            embedded_data[js_path] = {
                "h": headers,
                "r": filtered_rows,
                "i": filtered_img_map
            }
            parse_count += 1

        # Progress indicator every 200 files
        if (idx + 1) % 200 == 0:
            print(f"  Processed {idx+1}/{len(rows)}...")

    except Exception as e:
        parse_errors += 1

print(f"  Parsed {parse_count} files, extracted {total_images_extracted} images ({files_with_imgs} files have images), {parse_errors} errors")
if NO_IMAGE_PLACEHOLDER_COUNT > 0:
    print(f"  Discarded {NO_IMAGE_PLACEHOLDER_COUNT} NO IMAGE AVAILABLE placeholders")
print(f"  Products after filtering (no-image rows removed): ", end="")
total_rows_after = sum(len(v["r"]) for v in embedded_data.values())
print(f"{total_rows_after} rows (was ~47002 before filter)")

# Recalculate tree totals from actual product row counts
print("  Recalculating tree totals from actual product data...")
product_counts = {}
for rel_path, entry in embedded_data.items():
    product_counts[rel_path] = len(entry.get("r", []))

def recalc_total_product_rows(node):
    rows = 0
    for f in node.get("_files", []):
        rows += product_counts.get(f.get("path", ""), 0)
    for child in node.get("_children", []):
        rows += recalc_total_product_rows(child)
    node["total"] = rows
    return rows

for cat in tree_data:
    recalc_total_product_rows(cat)

# Re-sort by updated totals
tree_data.sort(key=lambda x: -x["total"])
for node in tree_data:
    if "_children" in node:
        node["_children"].sort(key=lambda x: -x.get("total", 0))

# Re-apply small category merge with updated totals
OTHER_THRESHOLD = 50
large_cats = [c for c in tree_data if c["total"] >= OTHER_THRESHOLD]
small_cats = [c for c in tree_data if c["total"] < OTHER_THRESHOLD]
if small_cats:
    other_total = sum(c["total"] for c in small_cats)
    other_exists = any(c["name"] == "Other" for c in large_cats)
    if other_exists:
        for lc in large_cats:
            if lc["name"] == "Other":
                for sc in small_cats:
                    lc["_children"].append(sc)
                lc["total"] += other_total
                break
    else:
        other_node = {"name": "Other", "total": other_total, "_children": small_cats}
        large_cats.append(other_node)
    tree_data = large_cats
    tree_data.sort(key=lambda x: -x["total"])
    print(f"  Merged {len(small_cats)} small categories into 'Other' ({other_total} products)")

# ============================================================
# Step 4: Write JSON data files
# ============================================================
print("[4/6] Writing JSON data files ...")

# 4a: tree.json
tree_path = os.path.join(TEMP_DATA_DIR, "tree.json")
with open(tree_path, 'w', encoding='utf-8') as f:
    json.dump(tree_data, f, ensure_ascii=False, separators=(',', ':'))
tree_size_kb = os.path.getsize(tree_path) / 1024
print(f"  tree.json: {tree_size_kb:.1f} KB")

# 4b: search.json
search_path = os.path.join(TEMP_DATA_DIR, "search.json")
with open(search_path, 'w', encoding='utf-8') as f:
    json.dump(search_data, f, ensure_ascii=False, separators=(',', ':'))
search_size_kb = os.path.getsize(search_path) / 1024
print(f"  search.json: {search_size_kb:.1f} KB")

# 4c: products.json
products_path = os.path.join(TEMP_DATA_DIR, "products.json")
with open(products_path, 'w', encoding='utf-8') as f:
    json.dump(embedded_data, f, ensure_ascii=False, separators=(',', ':'))
products_size_mb = os.path.getsize(products_path) / 1024 / 1024
print(f"  products.json: {products_size_mb:.2f} MB")

# ============================================================
# Step 5: Build index.html (no embedded data, uses fetch)
# ============================================================
print("[5/6] Building index.html (loading data via fetch) ...")

with open(HTML_TEMPLATE, "r", encoding="utf-8") as f:
    html = f.read()

# No placeholders remain in new template — all stats computed in JS
# Keep placeholder check for backward compatibility
for ph in ["__STAT_PRODUCTS__", "__STAT_CATEGORIES__", "__TREE_DATA__", "__SEARCH_DATA__", "__EMBEDDED_DATA__"]:
    if ph in html:
        print(f"  WARNING: placeholder {ph} still in template!")
        html = html.replace(ph, "0")

with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)

html_size_kb = os.path.getsize(HTML_OUTPUT) / 1024
print(f"  Saved: {HTML_OUTPUT} ({html_size_kb:.1f} KB)")

# ============================================================
# Step 6: Atomic swap — replace old data/images with new builds
# ============================================================
print("[6/7] Atomically swapping data/ and images/ ...")

import time

def atomic_swap(temp_dir, target_dir):
    """Swap temp_dir into target_dir atomically.
    On success, old target_dir is removed. Never leaves target_dir empty."""
    backup_dir = target_dir + "_backup"
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    if os.path.exists(target_dir):
        os.rename(target_dir, backup_dir)
    try:
        os.rename(temp_dir, target_dir)
    except Exception:
        # Rollback: restore backup
        if os.path.exists(backup_dir):
            os.rename(backup_dir, target_dir)
        raise
    # Clean up backup
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    print(f"  Swapped {os.path.basename(temp_dir)} -> {os.path.basename(target_dir)}")

atomic_swap(TEMP_DATA_DIR, DATA_DIR)
atomic_swap(TEMP_IMAGES_DIR, IMAGES_DIR)

# ============================================================
# Step 7: Report total package size
# ============================================================
print("[7/7] Calculating total package size ...")

def get_dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            total += os.path.getsize(fp)
    return total

img_size_mb = get_dir_size(IMAGES_DIR) / 1024 / 1024 if os.path.exists(IMAGES_DIR) else 0
data_size_mb = get_dir_size(DATA_DIR) / 1024 / 1024 if os.path.exists(DATA_DIR) else 0
html_size_mb = html_size_kb / 1024
xlxs_total = get_dir_size(PRODUCTS_DIR) / 1024 / 1024 if os.path.exists(PRODUCTS_DIR) else 0

print(f"\nDone!")
print(f"  Products: {len(rows)}")
print(f"  Categories: {total_cats}")
print(f"  HTML: {html_size_mb:.2f} MB")
print(f"  Data JSON: {data_size_mb:.2f} MB")
print(f"  Images: {img_size_mb:.1f} MB ({total_images_extracted} images)")
print(f"  Original Excel files (not in deploy pkg): {xlxs_total:.1f} MB")
if parse_errors > 0:
    print(f"  Warning: {parse_errors} files could not be parsed.")
print(f"\nDeploy package: index.html + data/ + images/  (~{html_size_mb + data_size_mb + img_size_mb:.1f} MB total)")
