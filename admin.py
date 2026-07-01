#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOD Catalog Admin Panel - Local Flask Web App (v2)
================================================
本地内容管理工具。直接编辑 data/*.json（网站的真相源），改完一键发布到 GitHub Pages。

核心能力:
  - 分类结构: 改名 / 新增 / 删除 / 移动(改父级) / 合并
  - 产品表:   新建 / 改名 / 删除 / 移动到其它分类 / 合并多个表 / 拆分一个表
  - 产品:     增 / 删 / 改 / 跨表移动
  - 维护:     重算 total / 重建搜索索引 / 备份 / 发布(git push)

数据模型要点(务必牢记):
  products.json = { "<文件路径>": {"h":[表头], "r":[[行]...], "i":{"<行位置>":"图片路径"}} }
    * i 的 key 是行在 r 数组中的【位置】(0,1,2...),不是 row[0] 的显示序号!
  tree.json = [ {name,total,_children?,_files?} ]
    * _files = [{no, name, path}]  path 即 products.json 的 key
  搜索索引每个"表"一条。

节点寻址: 前端用【索引路径】数组定位树节点,例如 [0,2,1] = 第0大类>第2子类>第1子类。
"""

import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, send_file

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')

TREE_FILE = 'tree.json'
PRODUCTS_FILE = 'products.json'
SEARCH_FILE = 'search.json'

DEFAULT_HEADERS = ['#', 'Image', 'Product Name']


# ============================================================
#  JSON 读写 & 备份
# ============================================================

def read_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # 原子替换,防止写一半崩溃


def backup_data():
    """把 data/ 下三个 JSON 打个带时间戳的快照,便于回滚。"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(BASE_DIR, 'data_backup', ts)
    os.makedirs(backup_dir, exist_ok=True)
    for f in [TREE_FILE, PRODUCTS_FILE, SEARCH_FILE]:
        src = os.path.join(DATA_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, f))
    return backup_dir


# ============================================================
#  行 <-> (行,图片) 的打散/重组  —— 解决图片按位置索引的问题
# ============================================================

def explode(entry):
    """把一个表拆成 [{'row':[...], 'img':路径或None}, ...],图片按位置对齐。"""
    rows = entry.get('r', [])
    imgs = entry.get('i', {})
    out = []
    for pos, row in enumerate(rows):
        out.append({'row': list(row), 'img': imgs.get(str(pos))})
    return out


def implode(items, headers):
    """把 [{'row','img'}] 重新组装成 {h,r,i},i 按新位置重建。"""
    r = []
    i = {}
    for pos, it in enumerate(items):
        r.append(it['row'])
        if it.get('img'):
            i[str(pos)] = it['img']
    return {'h': list(headers), 'r': r, 'i': i}


def renumber(items):
    """重排每行的显示序号 row[0] = 0,1,2...(保持与位置一致,更干净)。"""
    for pos, it in enumerate(items):
        if it['row']:
            it['row'][0] = pos
    return items


# ============================================================
#  树节点寻址
# ============================================================

def get_node(tree, index_path):
    """按索引路径取节点。index_path=[] 时返回一个虚拟根(便于统一处理)。"""
    if not index_path:
        return {'_children': tree}  # 虚拟根
    node = None
    children = tree
    for idx in index_path:
        if idx < 0 or idx >= len(children):
            return None
        node = children[idx]
        children = node.get('_children', [])
    return node


def get_children_list(tree, index_path):
    """取某节点的 _children 列表引用(用于增删)。空路径=根列表。"""
    if not index_path:
        return tree
    node = get_node(tree, index_path)
    if node is None:
        return None
    if '_children' not in node:
        node['_children'] = []
    return node['_children']


def get_parent_and_index(tree, index_path):
    """返回 (父节点的children列表, 该节点在其中的下标)。"""
    if not index_path:
        return None, None
    parent_children = get_children_list(tree, index_path[:-1])
    return parent_children, index_path[-1]


def iter_all_files(node):
    """递归产出节点下所有 _files 条目。"""
    for f in node.get('_files', []):
        yield f
    for c in node.get('_children', []):
        yield from iter_all_files(c)


def recalc_totals(node, products):
    """递归重算 total = 该节点下所有表的产品行数之和。返回本节点 total。"""
    total = 0
    for f in node.get('_files', []):
        entry = products.get(f['path'])
        if entry:
            total += len(entry.get('r', []))
    for c in node.get('_children', []):
        total += recalc_totals(c, products)
    node['total'] = total
    return total


def recalc_all_totals(tree, products):
    for root in tree:
        recalc_totals(root, products)


# ============================================================
#  新路径 / 新编号生成
# ============================================================

def slugify(name):
    s = re.sub(r'[^\w\- ]', '', str(name)).strip().replace(' ', '_')
    return s[:60] or 'table'


def next_file_no(tree):
    mx = 0
    for root in tree:
        for f in iter_all_files(root):
            try:
                mx = max(mx, int(f.get('no', 0)))
            except (ValueError, TypeError):
                pass
    return mx + 1


def new_table_path(name, products):
    """为新建/拆分出的表生成唯一 key。用 _admin/ 前缀标识非源Excel派生。"""
    base = 'Organized_Products_V2/_admin/%s_%s.xlsx' % (slugify(name), uuid.uuid4().hex[:8])
    while base in products:
        base = 'Organized_Products_V2/_admin/%s_%s.xlsx' % (slugify(name), uuid.uuid4().hex[:8])
    return base


# ============================================================
#  静态文件服务
# ============================================================

@app.route('/')
def index():
    admin_html = os.path.join(BASE_DIR, 'admin.html')
    if os.path.exists(admin_html):
        return send_file(admin_html)
    return "<h1>admin.html not found</h1>", 404


@app.route('/images/<path:filepath>')
def serve_image(filepath):
    return send_from_directory(IMAGES_DIR, filepath)


@app.route('/<path:filepath>')
def serve_static(filepath):
    return send_from_directory(BASE_DIR, filepath)


# ============================================================
#  API: 分类树
# ============================================================

@app.route('/api/tree', methods=['GET'])
def get_tree():
    tree = read_json(TREE_FILE)
    if tree is None:
        return jsonify({'error': 'tree.json not found'}), 404
    return jsonify(tree)


@app.route('/api/tree', methods=['PUT'])
def save_tree():
    """整棵树覆盖保存(前端拖拽重排后可整体提交)。"""
    backup_data()
    data = request.get_json()
    products = read_json(PRODUCTS_FILE) or {}
    recalc_all_totals(data, products)
    write_json(TREE_FILE, data)
    return jsonify({'ok': True, 'message': 'Category tree saved.'})


@app.route('/api/tree/rename', methods=['POST'])
def tree_rename():
    d = request.get_json()
    tree = read_json(TREE_FILE)
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'node not found'}), 404
    backup_data()
    node['name'] = d['name']
    if '_displayName' in node:
        node['_displayName'] = d['name']
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/tree/add', methods=['POST'])
def tree_add():
    """在指定父节点下新增一个空分类。父路径为 [] 表示新增顶级大类。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    children = get_children_list(tree, d.get('parent', []))
    if children is None:
        return jsonify({'error': 'parent not found'}), 404
    backup_data()
    children.append({'name': d['name'], 'total': 0, '_children': [], '_files': []})
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/tree/delete', methods=['POST'])
def tree_delete():
    """删除一个分类节点。默认要求为空;force=True 时连同其下所有表一并删除。"""
    d = request.get_json()
    force = d.get('force', False)
    tree = read_json(TREE_FILE)
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'node not found'}), 404
    has_content = node.get('_children') or node.get('_files')
    if has_content and not force:
        return jsonify({'error': 'Category not empty. Use force to delete with contents.'}), 400
    backup_data()
    products = read_json(PRODUCTS_FILE) or {}
    if force:
        for f in list(iter_all_files(node)):
            products.pop(f['path'], None)
    parent_children, idx = get_parent_and_index(tree, d['path'])
    parent_children.pop(idx)
    recalc_all_totals(tree, products)
    write_json(PRODUCTS_FILE, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/tree/move', methods=['POST'])
def tree_move():
    """把一个分类节点移动到新的父节点下(改父级/重排)。"""
    d = request.get_json()
    src_path = d['path']
    dst_parent = d['newParent']
    tree = read_json(TREE_FILE)

    # 不能把节点移动到它自己或其子孙里
    if dst_parent[:len(src_path)] == src_path:
        return jsonify({'error': 'Cannot move a node into itself or its descendant.'}), 400

    node = get_node(tree, src_path)
    if node is None:
        return jsonify({'error': 'node not found'}), 404
    backup_data()
    # 先从原父级摘除
    src_children, src_idx = get_parent_and_index(tree, src_path)
    moved = src_children.pop(src_idx)
    # 由于删除会影响 dst_parent 的索引(若在同一父级且在其前面),重新取目标
    dst_children = get_children_list(tree, dst_parent)
    if dst_children is None:
        # 回滚
        src_children.insert(src_idx, moved)
        return jsonify({'error': 'target parent not found'}), 404
    insert_at = d.get('index')
    if insert_at is None or insert_at > len(dst_children):
        dst_children.append(moved)
    else:
        dst_children.insert(insert_at, moved)
    products = read_json(PRODUCTS_FILE) or {}
    recalc_all_totals(tree, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/tree/merge', methods=['POST'])
def tree_merge():
    """把 source 分类的所有子分类与产品表并入 target 分类,然后删除 source。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    src = get_node(tree, d['source'])
    tgt = get_node(tree, d['target'])
    if src is None or tgt is None:
        return jsonify({'error': 'node not found'}), 404
    if d['target'][:len(d['source'])] == d['source']:
        return jsonify({'error': 'Cannot merge into own descendant.'}), 400
    backup_data()
    tgt.setdefault('_files', []).extend(src.get('_files', []))
    tgt.setdefault('_children', []).extend(src.get('_children', []))
    # 删除 source
    src_children, src_idx = get_parent_and_index(tree, d['source'])
    src_children.pop(src_idx)
    products = read_json(PRODUCTS_FILE) or {}
    recalc_all_totals(tree, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


# ============================================================
#  API: 产品表 (tree 里的 _files 条目 = products.json 的一个 key)
# ============================================================

@app.route('/api/table/create', methods=['POST'])
def table_create():
    """在指定分类下新建一个空产品表。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    products = read_json(PRODUCTS_FILE) or {}
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'category not found'}), 404
    backup_data()
    name = d['name']
    path = new_table_path(name, products)
    no = next_file_no(tree)
    products[path] = {'h': list(DEFAULT_HEADERS), 'r': [], 'i': {}}
    node.setdefault('_files', []).append({'no': no, 'name': name, 'path': path})
    recalc_all_totals(tree, products)
    write_json(PRODUCTS_FILE, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True, 'path': path, 'no': no})


@app.route('/api/table/rename', methods=['POST'])
def table_rename():
    d = request.get_json()
    tree = read_json(TREE_FILE)
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'category not found'}), 404
    files = node.get('_files', [])
    fi = d['fileIndex']
    if fi < 0 or fi >= len(files):
        return jsonify({'error': 'file index out of range'}), 400
    backup_data()
    files[fi]['name'] = d['name']
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/table/delete', methods=['POST'])
def table_delete():
    d = request.get_json()
    tree = read_json(TREE_FILE)
    products = read_json(PRODUCTS_FILE) or {}
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'category not found'}), 404
    files = node.get('_files', [])
    fi = d['fileIndex']
    if fi < 0 or fi >= len(files):
        return jsonify({'error': 'file index out of range'}), 400
    backup_data()
    removed = files.pop(fi)
    products.pop(removed['path'], None)
    recalc_all_totals(tree, products)
    write_json(PRODUCTS_FILE, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/table/move', methods=['POST'])
def table_move():
    """把一个产品表从一个分类移动到另一个分类(不改数据,只改归属)。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    src = get_node(tree, d['fromPath'])
    tgt = get_node(tree, d['toPath'])
    if src is None or tgt is None:
        return jsonify({'error': 'category not found'}), 404
    files = src.get('_files', [])
    fi = d['fileIndex']
    if fi < 0 or fi >= len(files):
        return jsonify({'error': 'file index out of range'}), 400
    backup_data()
    moved = files.pop(fi)
    tgt.setdefault('_files', []).append(moved)
    products = read_json(PRODUCTS_FILE) or {}
    recalc_all_totals(tree, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True})


@app.route('/api/table/merge', methods=['POST'])
def table_merge():
    """把同一分类下的多个表合并成一个新表(或并入第一个表)。
    body: {path:[...], fileIndexes:[i,j,...], name?, keepFirst?}
    keepFirst=True 则并入第一个表并沿用其 path;否则新建表。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    products = read_json(PRODUCTS_FILE) or {}
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'category not found'}), 404
    files = node.get('_files', [])
    idxs = sorted(d['fileIndexes'])
    if len(idxs) < 2:
        return jsonify({'error': 'need at least 2 tables to merge'}), 400
    if idxs[-1] >= len(files):
        return jsonify({'error': 'file index out of range'}), 400
    backup_data()

    # 收集所有行(打散,保留图片)
    merged_items = []
    headers = DEFAULT_HEADERS
    for fi in idxs:
        entry = products.get(files[fi]['path'])
        if entry:
            headers = entry.get('h', headers)
            merged_items.extend(explode(entry))
    renumber(merged_items)

    keep_first = d.get('keepFirst', True)
    name = d.get('name') or files[idxs[0]]['name']

    if keep_first:
        target_file = files[idxs[0]]
        target_path = target_file['path']
        target_file['name'] = name
    else:
        target_path = new_table_path(name, products)

    # 删除被合并的其它表(从大到小删,避免索引错乱)
    remove_paths = []
    for fi in idxs:
        if keep_first and fi == idxs[0]:
            continue
        remove_paths.append(files[fi]['path'])
    for fi in sorted(idxs, reverse=True):
        if keep_first and fi == idxs[0]:
            continue
        files.pop(fi)
    for p in remove_paths:
        products.pop(p, None)

    products[target_path] = implode(merged_items, headers)

    if not keep_first:
        # 新建表条目放到分类下
        no = next_file_no(tree)
        node.setdefault('_files', []).append({'no': no, 'name': name, 'path': target_path})

    recalc_all_totals(tree, products)
    write_json(PRODUCTS_FILE, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True, 'path': target_path})


@app.route('/api/table/split', methods=['POST'])
def table_split():
    """把一个表按指定的行位置拆成多个新表。
    body: {path:[...], fileIndex, groups:[{name, rows:[pos,...]}, ...]}
    未被任何 group 选中的行保留在原表(若原表被清空则删除)。"""
    d = request.get_json()
    tree = read_json(TREE_FILE)
    products = read_json(PRODUCTS_FILE) or {}
    node = get_node(tree, d['path'])
    if node is None:
        return jsonify({'error': 'category not found'}), 404
    files = node.get('_files', [])
    fi = d['fileIndex']
    if fi < 0 or fi >= len(files):
        return jsonify({'error': 'file index out of range'}), 400
    src_file = files[fi]
    entry = products.get(src_file['path'])
    if not entry:
        return jsonify({'error': 'table data not found'}), 404
    backup_data()

    items = explode(entry)
    headers = entry.get('h', DEFAULT_HEADERS)
    groups = d['groups']
    assigned = set()

    new_file_entries = []
    for g in groups:
        g_items = []
        for pos in g['rows']:
            if 0 <= pos < len(items):
                g_items.append(items[pos])
                assigned.add(pos)
        if not g_items:
            continue
        g_items = renumber([dict(x) for x in g_items])
        npath = new_table_path(g['name'], products)
        products[npath] = implode(g_items, headers)
        no = next_file_no(tree) + len(new_file_entries)
        new_file_entries.append({'no': no, 'name': g['name'], 'path': npath})

    # 剩余行留在原表
    remaining = [items[p] for p in range(len(items)) if p not in assigned]
    if remaining:
        renumber(remaining)
        products[src_file['path']] = implode(remaining, headers)
        insert_pos = fi + 1
    else:
        # 原表清空 -> 删除
        products.pop(src_file['path'], None)
        files.pop(fi)
        insert_pos = fi

    for k, nf in enumerate(new_file_entries):
        files.insert(insert_pos + k, nf)

    recalc_all_totals(tree, products)
    write_json(PRODUCTS_FILE, products)
    write_json(TREE_FILE, tree)
    return jsonify({'ok': True, 'created': [f['path'] for f in new_file_entries]})


# ============================================================
#  API: 产品 (表内的行)
# ============================================================

@app.route('/api/products', methods=['GET'])
def get_products():
    """返回扁平产品列表,供 Product Manager 搜索/编辑。
    每条含 filepath + pos(行位置,即图片 key)。"""
    products = read_json(PRODUCTS_FILE)
    if products is None:
        return jsonify({'error': 'products.json not found'}), 404
    product_list = []
    for filepath, entry in products.items():
        headers = entry.get('h', [])
        imgs = entry.get('i', {})
        for pos, row in enumerate(entry.get('r', [])):
            item = {
                'filepath': filepath,
                'pos': pos,
                'num': row[0] if len(row) > 0 else pos,
                'image': imgs.get(str(pos), ''),
                'name': str(row[2]) if len(row) > 2 else '',
            }
            for ci in range(3, len(row)):
                col = headers[ci] if ci < len(headers) else ('col%d' % ci)
                item[col] = str(row[ci]) if row[ci] is not None else ''
            product_list.append(item)
    return jsonify({'products': product_list, 'total': len(product_list)})


@app.route('/api/table/rows', methods=['GET'])
def get_table_rows():
    """返回单个表的所有行(带位置和图片),供表内产品管理。"""
    filepath = request.args.get('filepath', '')
    products = read_json(PRODUCTS_FILE)
    if not products or filepath not in products:
        return jsonify({'error': 'table not found'}), 404
    entry = products[filepath]
    headers = entry.get('h', [])
    imgs = entry.get('i', {})
    rows = []
    for pos, row in enumerate(entry.get('r', [])):
        rows.append({
            'pos': pos,
            'num': row[0] if row else pos,
            'name': str(row[2]) if len(row) > 2 else '',
            'image': imgs.get(str(pos), ''),
            'cells': [str(x) if x is not None else '' for x in row],
        })
    return jsonify({'headers': headers, 'rows': rows})


@app.route('/api/product/update', methods=['POST'])
def update_product():
    """更新某表某行。body: {filepath, pos, changes:{name?,image?,<列名>:值}}"""
    d = request.get_json()
    filepath = d.get('filepath')
    pos = d.get('pos')
    changes = d.get('changes', {})
    if not filepath or pos is None:
        return jsonify({'error': 'filepath and pos required'}), 400
    products = read_json(PRODUCTS_FILE)
    if not products or filepath not in products:
        return jsonify({'error': 'table not found'}), 404
    entry = products[filepath]
    rows = entry.get('r', [])
    if pos < 0 or pos >= len(rows):
        return jsonify({'error': 'pos out of range'}), 400
    backup_data()
    row = rows[pos]
    headers = entry.get('h', [])
    if 'name' in changes and len(row) > 2:
        row[2] = changes['name']
    if 'image' in changes:
        entry.setdefault('i', {})
        if changes['image']:
            entry['i'][str(pos)] = changes['image']
        else:
            entry['i'].pop(str(pos), None)
    for col, val in changes.items():
        if col in ('name', 'image'):
            continue
        if col in headers:
            ci = headers.index(col)
            while len(row) <= ci:
                row.append('')
            row[ci] = str(val)
    write_json(PRODUCTS_FILE, products)
    return jsonify({'ok': True})


@app.route('/api/product/add', methods=['POST'])
def add_product():
    """在指定表末尾新增一行。body: {filepath, name, image?, extra:{列名:值}}"""
    d = request.get_json()
    filepath = d.get('filepath')
    name = d.get('name', '')
    image = d.get('image', '')
    extra = d.get('extra', {})
    if not filepath:
        return jsonify({'error': 'filepath required'}), 400
    if not name:
        return jsonify({'error': 'name required'}), 400
    products = read_json(PRODUCTS_FILE)
    if not products:
        return jsonify({'error': 'products.json not found'}), 404
    if filepath not in products:
        products[filepath] = {'h': list(DEFAULT_HEADERS), 'r': [], 'i': {}}
    entry = products[filepath]
    headers = entry.get('h', DEFAULT_HEADERS)
    rows = entry.get('r', [])
    pos = len(rows)
    row = [''] * len(headers)
    if len(row) > 0:
        row[0] = pos
    if len(row) > 2:
        row[2] = name
    for col, val in extra.items():
        if col in headers:
            row[headers.index(col)] = str(val)
    rows.append(row)
    if image:
        entry.setdefault('i', {})[str(pos)] = image
    backup_data()
    write_json(PRODUCTS_FILE, products)
    _sync_totals_for_file(filepath)
    return jsonify({'ok': True, 'pos': pos})


@app.route('/api/product/delete', methods=['POST'])
def delete_product():
    """删除某表某行(会重排位置和图片索引)。body: {filepath, pos}"""
    d = request.get_json()
    filepath = d.get('filepath')
    pos = d.get('pos')
    if not filepath or pos is None:
        return jsonify({'error': 'filepath and pos required'}), 400
    products = read_json(PRODUCTS_FILE)
    if not products or filepath not in products:
        return jsonify({'error': 'table not found'}), 404
    entry = products[filepath]
    items = explode(entry)
    if pos < 0 or pos >= len(items):
        return jsonify({'error': 'pos out of range'}), 400
    backup_data()
    items.pop(pos)
    renumber(items)
    products[filepath] = implode(items, entry.get('h', DEFAULT_HEADERS))
    write_json(PRODUCTS_FILE, products)
    _sync_totals_for_file(filepath)
    return jsonify({'ok': True})


@app.route('/api/product/move', methods=['POST'])
def move_product():
    """把某行从一个表移动到另一个表。body: {fromFile, pos, toFile}"""
    d = request.get_json()
    from_file = d.get('fromFile')
    to_file = d.get('toFile')
    pos = d.get('pos')
    if not from_file or not to_file or pos is None:
        return jsonify({'error': 'fromFile, toFile, pos required'}), 400
    if from_file == to_file:
        return jsonify({'error': 'source and target are the same table'}), 400
    products = read_json(PRODUCTS_FILE)
    if not products or from_file not in products or to_file not in products:
        return jsonify({'error': 'table not found'}), 404
    backup_data()
    src_items = explode(products[from_file])
    if pos < 0 or pos >= len(src_items):
        return jsonify({'error': 'pos out of range'}), 400
    moved = src_items.pop(pos)
    renumber(src_items)
    products[from_file] = implode(src_items, products[from_file].get('h', DEFAULT_HEADERS))

    dst_items = explode(products[to_file])
    dst_items.append(moved)
    renumber(dst_items)
    products[to_file] = implode(dst_items, products[to_file].get('h', DEFAULT_HEADERS))

    write_json(PRODUCTS_FILE, products)
    # 两个表所属分类的 total 都变了,整体重算最稳
    _recalc_and_save_tree()
    return jsonify({'ok': True})


def _sync_totals_for_file(filepath):
    """某表行数变化后,重算整棵树 total 并保存(简单稳妥)。"""
    _recalc_and_save_tree()


def _recalc_and_save_tree():
    tree = read_json(TREE_FILE)
    products = read_json(PRODUCTS_FILE) or {}
    if tree:
        recalc_all_totals(tree, products)
        write_json(TREE_FILE, tree)


# ============================================================
#  API: 搜索索引重建
# ============================================================

@app.route('/api/search/rebuild', methods=['POST'])
def rebuild_search():
    """从 tree.json 重建 search.json(每个产品表一条)。"""
    tree = read_json(TREE_FILE)
    if not tree:
        return jsonify({'error': 'tree.json missing'}), 400
    index = []

    def walk(node, levels):
        name = node.get('_displayName') or node.get('name', '')
        cur_levels = levels + [name]
        for f in node.get('_files', []):
            index.append({
                'no': f.get('no', ''),
                'fname': f.get('name', ''),
                'fpath': f.get('path', ''),
                'breadcrumb': ' > '.join(cur_levels + [f.get('name', '')]),
                'levels': cur_levels + [f.get('name', '')],
            })
        for c in node.get('_children', []):
            walk(c, cur_levels)

    for root in tree:
        walk(root, [])
    # 重排 no 使其连续唯一
    for i, item in enumerate(index, start=1):
        item['no'] = i
    write_json(SEARCH_FILE, index)
    return jsonify({'ok': True, 'total': len(index)})


# ============================================================
#  API: 图片
# ============================================================

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    target_dir = request.form.get('dir', 'custom')
    dir_path = os.path.join(IMAGES_DIR, target_dir)
    os.makedirs(dir_path, exist_ok=True)
    # 防止文件名冲突
    fname = file.filename
    dest = os.path.join(dir_path, fname)
    stem, ext = os.path.splitext(fname)
    n = 1
    while os.path.exists(dest):
        fname = '%s_%d%s' % (stem, n, ext)
        dest = os.path.join(dir_path, fname)
        n += 1
    file.save(dest)
    return jsonify({'ok': True, 'path': 'images/%s/%s' % (target_dir, fname)})


# ============================================================
#  API: 备份 / 发布
# ============================================================

@app.route('/api/backup', methods=['POST'])
def create_backup():
    try:
        path = backup_data()
        return jsonify({'ok': True, 'path': os.path.relpath(path, BASE_DIR)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _git(args, timeout=60):
    return subprocess.run(['git'] + args, cwd=BASE_DIR,
                          capture_output=True, text=True, timeout=timeout)


@app.route('/api/git/status', methods=['GET'])
def git_status():
    try:
        r = _git(['status', '--short'])
        files = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return jsonify({'ok': True, 'changes': files, 'clean': len(files) == 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/publish', methods=['POST'])
def publish():
    """重建搜索 -> git add/commit/push。"""
    data = request.get_json() or {}
    message = data.get('message') or ('Update from admin panel %s'
                                      % datetime.now().strftime('%Y-%m-%d %H:%M'))
    # 发布前重建搜索索引,保证一致
    rebuild_search()
    try:
        _git(['add', '-A'])
        commit = _git(['commit', '-m', message])
        combined = commit.stdout + commit.stderr
        if commit.returncode != 0 and 'nothing to commit' not in combined:
            return jsonify({'error': 'Commit failed: %s' % combined}), 500
        push = _git(['push', 'origin', 'main'], timeout=120)
        if push.returncode != 0:
            if 'Everything up-to-date' in (push.stdout + push.stderr):
                return jsonify({'ok': True, 'message': 'Already up-to-date.'})
            return jsonify({'error': 'Push failed: %s' % (push.stdout + push.stderr)}), 500
        return jsonify({'ok': True, 'message': 'Published to GitHub successfully!'})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Git operation timed out. Check your network/auth.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('=' * 60)
    print('  YOD Catalog Admin Panel  (v2)')
    print('  http://localhost:8888')
    print('=' * 60)
    app.run(host='127.0.0.1', port=8888, debug=False)
