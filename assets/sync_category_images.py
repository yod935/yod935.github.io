"""
同步分类图片到项目文件夹，并在 tree.json 中添加 _image 字段。
- 复制顶部背景图到 images/hero-bg.jpg
- 复制所有分类/子分类图片到 images/categories/
- 匹配图片到 tree 节点，写入 _image 字段
- 没有匹配图片的节点，从产品数据中取第一张图
"""
import json, os, shutil, re

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = r"D:\SupplyHouseFetch\YOD图片资源"
SRC_CAT_DIR = os.path.join(SRC_DIR, "分类image")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
IMG_DIR = os.path.join(PROJECT_DIR, "images")
CAT_IMG_DIR = os.path.join(IMG_DIR, "categories")

# 1. 复制背景图
hero_src = os.path.join(SRC_DIR, "YOD 网站底图.jpg")
hero_dst = os.path.join(IMG_DIR, "hero-bg.jpg")
if os.path.exists(hero_src):
    shutil.copy2(hero_src, hero_dst)
    print(f"[OK] Hero background: {hero_dst}")
else:
    print(f"[!!] Hero background not found: {hero_src}")

# 2. 复制顶级分类图片
os.makedirs(CAT_IMG_DIR, exist_ok=True)
top_files = [f for f in os.listdir(SRC_CAT_DIR)
             if os.path.isfile(os.path.join(SRC_CAT_DIR, f))]
print(f"\nTop-level category images: {len(top_files)} files")

for fname in top_files:
    src = os.path.join(SRC_CAT_DIR, fname)
    # normalize extension to lowercase
    name, ext = os.path.splitext(fname)
    ext_lower = ext.lower()
    dst = os.path.join(CAT_IMG_DIR, name + ext_lower)
    shutil.copy2(src, dst)
    print(f"  -> {name + ext_lower}")

# 3. 复制子分类图片，保持父分类目录结构
sub_dirs = [d for d in os.listdir(SRC_CAT_DIR)
            if os.path.isdir(os.path.join(SRC_CAT_DIR, d))]
print(f"\nSub-category folders: {len(sub_dirs)}")
for sd in sub_dirs:
    # 去掉前缀 "01_" 等，得到纯分类名
    clean_name = re.sub(r'^\d+_', '', sd).strip()
    dst_sub = os.path.join(CAT_IMG_DIR, clean_name)
    os.makedirs(dst_sub, exist_ok=True)
    src_sub = os.path.join(SRC_CAT_DIR, sd)
    count = 0
    for fname in os.listdir(src_sub):
        if not os.path.isfile(os.path.join(src_sub, fname)):
            continue
        # normalize extension
        name, ext = os.path.splitext(fname)
        ext_lower = ext.lower()
        dst = os.path.join(dst_sub, name + ext_lower)
        shutil.copy2(os.path.join(src_sub, fname), dst)
        count += 1
    print(f"  {clean_name}: {count} images")

# 4. 加载 tree.json 和 products.json
with open(os.path.join(DATA_DIR, "tree.json"), "r", encoding="utf-8") as f:
    tree = json.load(f)

with open(os.path.join(DATA_DIR, "products.json"), "r", encoding="utf-8") as f:
    products = json.load(f)

# 5. 匹配顶级分类图片
top_cat_imgs = {}  # normalized_name -> relative_path
for fname in os.listdir(CAT_IMG_DIR):
    fp = os.path.join(CAT_IMG_DIR, fname)
    if os.path.isfile(fp):
        name = os.path.splitext(fname)[0]
        # normalize for matching
    norm = name.strip().lower().replace('&amp;', '&')
    # normalize spaces around & (both "A & B" and "A&B" should match)
    norm = re.sub(r'\s*&\s*', '&', norm)
    top_cat_imgs[norm] = f"images/categories/{fname}"

print(f"\nTop image map: {list(top_cat_imgs.keys())}")

# 6. 匹配子分类图片
def build_sub_img_map(parent_clean_name):
    """返回 {normalized_name: relative_path} 的映射"""
    sub_dir = os.path.join(CAT_IMG_DIR, parent_clean_name)
    if not os.path.isdir(sub_dir):
        return {}
    imap = {}
    for fname in os.listdir(sub_dir):
        fp = os.path.join(sub_dir, fname)
        if os.path.isfile(fp):
            # 文件名如 "01_Pipe Fittings & Nipples.jpg"
            name = os.path.splitext(fname)[0]
            # 去掉前缀数字
            clean = re.sub(r'^\d+_', '', name).strip()
            norm = clean.lower().replace('&amp;', '&')
            # normalize spaces around &
            norm = re.sub(r'\s*&\s*', '&', norm)
            rel = f"images/categories/{parent_clean_name}/{fname}"
            imap[norm] = rel
    return imap

# 7. 为节点查找产品图（递归搜索所有子节点）
def get_product_image_from_node(node):
    """从节点的 _files 列表及所有子节点中找第一张产品图片"""
    # 先检查当前节点的 _files
    files = node.get("_files", [])
    for f in files:
        path = f.get("path", "")
        if path in products:
            pdata = products[path]
            img_map = pdata.get("i", {})
            if img_map:
                first_key = sorted(img_map.keys(), key=lambda x: int(x))[0]
                return img_map[first_key]
    # 递归搜索子节点
    for child in node.get("_children", []):
        img = get_product_image_from_node(child)
        if img:
            return img
    return None

# 8. 递归给所有节点加 _image（先清除旧的，再重新匹配）
def clear_images(nodes):
    """清除所有节点的 _image 字段"""
    for node in nodes:
        node.pop("_image", None)
        if "_children" in node:
            clear_images(node["_children"])

clear_images(tree)

def add_images_to_nodes(nodes, parent_clean_name=None):
    """递归处理节点，添加 _image 字段"""
    # 先构建此级别的子分类图片映射
    sub_imgs = {}
    if parent_clean_name:
        sub_imgs = build_sub_img_map(parent_clean_name)

    for node in nodes:
        name = node.get("name", "").strip()
        norm = name.lower().replace('&amp;', '&')
        # normalize spaces around &
        norm = re.sub(r'\s*&\s*', '&', norm)

        # 优先匹配用户提供的图片
        matched_img = None
        if parent_clean_name and sub_imgs:
            # 在子分类目录中匹配
            matched_img = sub_imgs.get(norm)
        elif not parent_clean_name:
            # 顶级分类匹配
            matched_img = top_cat_imgs.get(norm)

        if matched_img:
            node["_image"] = matched_img
        else:
            # 没有匹配的图片，尝试用产品图
            prod_img = get_product_image_from_node(node)
            if prod_img:
                node["_image"] = prod_img

        # 递归处理子节点，传当前节点的净化名作为父目录
        if "_children" in node:
            clean_parent_name = name  # 直接用原始名
            add_images_to_nodes(node["_children"], clean_parent_name)

# 执行匹配
add_images_to_nodes(tree, parent_clean_name=None)

# 9. 统计结果
def count_with_images(nodes, level=0):
    total = 0
    with_img = 0
    for node in nodes:
        total += 1
        if node.get("_image"):
            with_img += 1
        if "_children" in node:
            t, w = count_with_images(node["_children"], level+1)
            total += t
            with_img += w
    return total, with_img

total_nodes, with_img = count_with_images(tree)
print(f"\n=== 匹配结果 ===")
print(f"总节点数: {total_nodes}")
print(f"有图片的节点: {with_img}")
print(f"无图片的节点: {total_nodes - with_img}")

# 10. 保存更新后的 tree.json
with open(os.path.join(DATA_DIR, "tree.json"), "w", encoding="utf-8") as f:
    json.dump(tree, f, ensure_ascii=False, separators=(",", ":"))

print(f"\n[OK] tree.json 已更新，所有节点添加 _image 字段")
print(f"[OK] 图片已全部复制到项目文件夹内")

# 11. 展示一些样例
print(f"\n顶级分类图片:")
for cat in tree:
    img = cat.get("_image", "NONE")
    print(f"  {cat['name']} -> {img}")
