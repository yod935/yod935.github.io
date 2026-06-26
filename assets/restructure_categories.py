"""
Restructure product categories from 8 poorly-organized groups into
8 clean, logical categories. Reads tree.json and products.json,
outputs new tree.json + updates search.json.
"""
import json, copy, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
DATA = os.path.join(PROJECT, 'data')

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)

def deep_copy_node(node):
    """Deep copy a tree node."""
    return copy.deepcopy(node)

def merge_nodes(target, source):
    """Merge source node into target (combine _children and _files)."""
    # Merge _files
    if '_files' in source:
        if '_files' not in target:
            target['_files'] = []
        # Simple append — could deduplicate by 'no' but not needed
        target['_files'].extend(source['_files'])
    # Merge _children recursively
    if '_children' in source:
        if '_children' not in target:
            target['_children'] = []
        for sc in source['_children']:
            found = None
            for tc in target['_children']:
                if tc.get('name') == sc.get('name'):
                    found = tc
                    break
            if found:
                merge_nodes(found, sc)
            else:
                target['_children'].append(deep_copy_node(sc))
    # Keep _image from target if exists, or take from source
    if '_image' not in target and '_image' in source:
        target['_image'] = source['_image']

def recalc_total(node):
    """Recalculate total from children (sum their existing totals)."""
    # Start with existing total if it's a leaf (no children)
    # For parent nodes, sum children's totals
    if '_children' in node and node['_children']:
        total = 0
        for child in node['_children']:
            total += child.get('total', 0)
        node['total'] = total
    # If no children, keep existing total (from original data)
    return node.get('total', 0)

def sort_children(node):
    if '_children' in node:
        node['_children'].sort(key=lambda x: -x.get('total', 0))
        for child in node['_children']:
            sort_children(child)


# ======================== MAIN ========================

tree = load_json(os.path.join(DATA, 'tree.json'))
products = load_json(os.path.join(DATA, 'products.json'))
search = load_json(os.path.join(DATA, 'search.json'))

# Build old_by_name dict
old_by_name = {}
for cat in tree:
    old_by_name[cat['name']] = cat
    if '_children' in cat:
        for sub in cat['_children']:
            old_by_name[sub['name']] = sub

def get_subs(cat_name):
    """Get all Level-1 subcategories of a top-level category."""
    cat = old_by_name.get(cat_name)
    if not cat or '_children' not in cat:
        return {}
    return {s['name']: deep_copy_node(s) for s in cat['_children']}

def make_cat(name):
    return {'name': name, '_children': [], 'total': 0}

def add_sub(cat_dict, node):
    """Add a sub-node to a category, merging if name exists."""
    name = node['name']
    existing = None
    for c in cat_dict['_children']:
        if c['name'] == name:
            existing = c
            break
    if existing:
        merge_nodes(existing, node)
    else:
        cat_dict['_children'].append(node)

# ---- Extract all source data ----
plumb = get_subs('Plumbing Supplies')
hvac = get_subs('HVAC Supplies')
hsp = get_subs('Heating Supplies & Parts')
hs = get_subs('Heating Supplies')
elec = get_subs('Electrical Supplies')
other_cat = old_by_name.get('Other')
accessories_cat = old_by_name.get('Accessories')
wprv_cat = old_by_name.get('Water Pressure Regulating Valves')

# ---- Build 8 new categories ----

# 1. Plumbing Fittings & Pipes
cat1 = make_cat('Plumbing Fittings & Pipes')
for k in ['Pipe Fittings & Nipples', 'Pipe Hangers & Clamps',
          'Pipe Hangers, Clamps & Support Brackets', 'Pipe',
          'Firestop Products', 'Outlet Boxes', 'PEX Plumbing',
          'PEX Plumbing Supplies & Parts',
          'Plumbing Specialties', 'Plumbing Drainage']:
    if k in plumb:
        add_sub(cat1, plumb.pop(k))

# 2. Plumbing Fixtures
cat2 = make_cat('Plumbing Fixtures')
for k in ['Tub & Shower Products', 'Faucet & Sink Parts', 'Faucets', 'Sinks',
          'Toilet Parts', 'Urinals and Toilets', 'Drains', 'Flush Valves',
          'Strainers', 'Access Doors', 'Garbage Disposals']:
    if k in plumb:
        add_sub(cat2, plumb.pop(k))

# 3. Valves & Waterworks
cat3 = make_cat('Valves & Waterworks')
for k in ['Valves', 'Plumbing Valves', 'Water Works', 'Expansion Tanks']:
    if k in plumb:
        add_sub(cat3, plumb.pop(k))
# Add Water Pressure Regulating Valves as a file node
if wprv_cat:
    add_sub(cat3, deep_copy_node(wprv_cat))

# 4. Plumbing Equipment
cat4 = make_cat('Plumbing Equipment')
for k in ['Water Heaters', 'Water Heater Parts', 'Pumps',
          'Water Filters', 'Water Filtration Systems',
          'Plumbing Chemicals & Compounds', 'Chemicals & Compounds',
          'Tools', 'Plumbing Tools & Equipment',
          'Well Pressure Tanks & Parts', 'Grease Traps',
          'Macerating Toilet Systems', 'Steam Showers']:
    if k in plumb:
        add_sub(cat4, plumb.pop(k))

# Anything left in plumb
for k, v in plumb.items():
    add_sub(cat4, v)
    print(f"  [WARN] Unclassified Plumbing: {k} ({v.get('total',0)})")

# 5. Heating Supplies (merged)
cat5 = make_cat('Heating Supplies')
# Add all subcategories from both heating categories
for sub_dict in [hsp, hs]:
    for k, v in sub_dict.items():
        add_sub(cat5, deep_copy_node(v))

# 6. HVAC Equipment & Systems
cat6 = make_cat('HVAC Equipment & Systems')
for k in ['Mini Split Air Conditioners', 'Mini-Split Air Conditioners',
          'Ductless Mini-Split Air Conditioners', 'PTAC Air Conditioners',
          'Compressors', 'Motors & Accessories', 'Ventilation Fans',
          'Dehumidifiers', 'Humidifiers', 'Air Cleaners',
          'Heat & Energy Recovery Ventilators', 'Range Hoods',
          'HVAC Equipment', 'Condensate Removal Pumps',
          'Line Sets', 'HVAC and Refrigeration Valves']:
    if k in hvac:
        add_sub(cat6, hvac.pop(k))

# 7. HVAC Parts & Controls
cat7 = make_cat('HVAC Parts & Controls')
for k in ['HVAC Replacement Parts', 'Dampers', 'HVAC Zone Dampers',
          'Registers & Grilles', 'AC Registers & Grilles',
          'HVAC Controls', 'Tools', 'HVAC Tools',
          'Flex Duct', 'Capacitors', 'System Protectors',
          'Refrigeration Supplies', 'Refrigeration Controls',
          'Chemicals & Cleaners', 'Replacement Filters',
          'Air Conditioning Installation Parts',
          'Temperature Controllers', 'HVAC Parts']:
    if k in hvac:
        add_sub(cat7, hvac.pop(k))

# Remaining HVAC
for k, v in hvac.items():
    add_sub(cat7, v)
    print(f"  [WARN] Unclassified HVAC: {k} ({v.get('total',0)})")

# 8. Electrical Supplies (unchanged)
cat8 = make_cat('Electrical Supplies')
for k, v in elec.items():
    add_sub(cat8, deep_copy_node(v))

# ---- Handle Other and Accessories ----
# Other: Lochinvar Water Heaters → Plumbing Equipment
# Other: Fluorescent Lamps, Halogen Lamps → Electrical Supplies
# Other: Aprilaire ERV → HVAC Equipment
# Other: Sloan Flushometers → Plumbing Fixtures
# Other: Bundle Ties → Electrical Supplies
if other_cat and '_children' in other_cat:
    for oc in other_cat['_children']:
        name = oc['name']
        if 'Lochinvar' in name or 'Water Heater' in name:
            add_sub(cat4, deep_copy_node(oc))
            print(f"  Other → Plumbing Equipment: {name}")
        elif 'Fluorescent' in name or 'Halogen' in name or 'Lamp' in name:
            add_sub(cat8, deep_copy_node(oc))
            print(f"  Other → Electrical Supplies: {name}")
        elif 'Aprilaire' in name or 'ERV' in name or 'Ventilator' in name:
            add_sub(cat6, deep_copy_node(oc))
            print(f"  Other → HVAC Equipment: {name}")
        elif 'Sloan' in name or 'Flushometer' in name:
            add_sub(cat2, deep_copy_node(oc))
            print(f"  Other → Plumbing Fixtures: {name}")
        elif 'Bundle Tie' in name:
            add_sub(cat8, deep_copy_node(oc))
            print(f"  Other → Electrical Supplies: {name}")
        else:
            add_sub(cat4, deep_copy_node(oc))
            print(f"  Other → Plumbing Equipment (default): {name}")

# Accessories → whatever seems appropriate, put in Plumbing Equipment as default
if accessories_cat:
    add_sub(cat4, deep_copy_node(accessories_cat))
    print(f"  Accessories → Plumbing Equipment")

# ---- Recalculate totals and sort ----
new_tree = [cat1, cat2, cat3, cat4, cat5, cat6, cat7, cat8]
for cat in new_tree:
    recalc_total(cat)
    if '_children' in cat:
        for sub in cat['_children']:
            recalc_total(sub)
            sort_children(sub)
        cat['_children'].sort(key=lambda x: -x.get('total', 0))
    sort_children(cat)

new_tree.sort(key=lambda x: -x.get('total', 0))

# ---- Print summary ----
print("\n===== NEW CATEGORY STRUCTURE =====")
for i, cat in enumerate(new_tree):
    sub_count = len(cat.get('_children', []))
    print(f"{i+1}. {cat['name']}: {cat['total']:,} products, {sub_count} subcategories")
    for sub in cat.get('_children', []):
        sub_sub = len(sub.get('_children', []))
        print(f"   └ {sub['name']} ({sub['total']:,}){' [leaf]' if sub_sub==0 else f' [{sub_sub} sub]'}")

# ---- Write output ----
save_json(new_tree, os.path.join(DATA, 'tree.json'))
print(f"\n[OK] Saved {len(new_tree)} categories to tree.json")

# ---- Verify JSON is valid ----
tree_check = load_json(os.path.join(DATA, 'tree.json'))
print(f"[OK] Verified: tree.json has {len(tree_check)} top-level categories")
total_prod = sum(c['total'] for c in tree_check)
print(f"[OK] Total products across all categories: {total_prod:,}")
