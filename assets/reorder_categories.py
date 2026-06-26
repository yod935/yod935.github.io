"""
Reorder and merge categories in tree.json:
1. Merge duplicate/near-duplicate sub-categories within each top-level
2. Reorder top-level categories logically: Plumbing → HVAC+Heating → Electrical
3. Within each category, keep sub-categories sorted by product count
"""
import json, copy, os

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
    return copy.deepcopy(node)

def merge_nodes(target, source):
    """Merge source node into target (combine _children and _files)."""
    if '_files' in source:
        if '_files' not in target:
            target['_files'] = []
        target['_files'].extend(source['_files'])
    # Deduplicate files by 'no'
    seen_nos = set()
    if '_files' in target:
        unique = []
        for f in target['_files']:
            if f['no'] not in seen_nos:
                seen_nos.add(f['no'])
                unique.append(f)
        target['_files'] = unique
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
    if '_image' not in target and '_image' in source:
        target['_image'] = source['_image']

def recalc_total(node):
    """Recalculate total by summing children's stored totals.
    Leaf nodes keep their pre-calculated total (each _file can have many product rows)."""
    if '_children' in node and node['_children']:
        total = 0
        for child in node['_children']:
            total += child.get('total', 0)
        node['total'] = total
    # Leaf: keep existing total as-is (was pre-calculated by build script)
    return node.get('total', 0)

def sort_children(node):
    if '_children' in node:
        node['_children'].sort(key=lambda x: -x.get('total', 0))
        for child in node['_children']:
            sort_children(child)

# ======================== MAIN ========================

tree = load_json(os.path.join(DATA, 'tree.json'))
print(f"Loaded tree.json with {len(tree)} top-level categories")

# Build lookup
cats = {c['name']: c for c in tree}

def get_sub(cat_name, sub_name):
    """Get a sub-category node from a top-level category."""
    cat = cats.get(cat_name)
    if not cat or '_children' not in cat:
        return None
    for s in cat['_children']:
        if s['name'] == sub_name:
            return s
    return None

def merge_sub(cat_name, from_name, into_name):
    """Merge sub-category 'from_name' into 'into_name' within 'cat_name'."""
    cat = cats.get(cat_name)
    if not cat or '_children' not in cat:
        return 0
    source = None
    target = None
    for s in cat['_children']:
        if s['name'] == from_name:
            source = s
        if s['name'] == into_name:
            target = s
    if not source or not target:
        print(f"  [SKIP] merge_sub: {cat_name}/{from_name} → {into_name} (not found)")
        return 0
    before = target.get('total', 0)
    merge_nodes(target, source)
    recalc_total(target)
    cat['_children'].remove(source)
    after = target.get('total', 0)
    print(f"  [MERGE] {cat_name}: '{from_name}' ({source.get('total',0)}) → '{into_name}' ({before}→{after})")
    return 1

# ======================== MERGES ========================
print("\n--- MERGING DUPLICATE SUBCATEGORIES ---")

# --- HVAC Parts & Controls ---
merge_sub('HVAC Parts & Controls', 'AC Registers & Grilles', 'Registers & Grilles')
merge_sub('HVAC Parts & Controls', 'HVAC Tools', 'Tools')
merge_sub('HVAC Parts & Controls', 'HVAC Zone Dampers', 'Dampers')
# Merge small hvac leaf nodes into relevant parents
# HVAC Parts (56,5) → HVAC Replacement Parts (5311,32)
merge_sub('HVAC Parts & Controls', 'HVAC Parts', 'HVAC Replacement Parts')

# --- Plumbing Fittings & Pipes ---
merge_sub('Plumbing Fittings & Pipes', 'Pipe Hangers, Clamps & Support Brackets', 'Pipe Hangers & Clamps')
merge_sub('Plumbing Fittings & Pipes', 'PEX Plumbing Supplies & Parts', 'PEX Plumbing')

# --- Plumbing Equipment ---
merge_sub('Plumbing Equipment', 'Plumbing Tools & Equipment', 'Tools')
merge_sub('Plumbing Equipment', 'Chemicals & Compounds', 'Plumbing Chemicals & Compounds')
merge_sub('Plumbing Equipment', 'Water Filtration Systems', 'Water Filters')
merge_sub('Plumbing Equipment', 'Lochinvar Indirect Water Heaters', 'Water Heaters')
# Merge Accessories into Plumbing Specialties? No, different top-level.
# Accessories has only 25 products, keep it.

# --- Heating Supplies ---
merge_sub('Heating Supplies', 'Air Eliminator Valves', 'Air Eliminators')
merge_sub('Heating Supplies', 'Boiler Circulating Pumps', 'Circulator Pumps')
merge_sub('Heating Supplies', 'Radiant Floor Heating Supplies', 'Radiant Heat')

# --- HVAC Equipment & Systems ---
merge_sub('HVAC Equipment & Systems', 'Mini-Split Air Conditioners', 'Mini Split Air Conditioners')
merge_sub('HVAC Equipment & Systems', 'Ductless Mini-Split Air Conditioners', 'Mini Split Air Conditioners')
merge_sub('HVAC Equipment & Systems', 'Aprilaire Energy Recovery Ventilators', 'Heat & Energy Recovery Ventilators')

# --- Valves & Waterworks ---
merge_sub('Valves & Waterworks', 'Plumbing Valves', 'Valves')
# Also merge Water Pressure Regulating Valves (30) into Valves (985)
merge_sub('Valves & Waterworks', 'Water Pressure Regulating Valves', 'Valves')

# --- Electrical Supplies ---
merge_sub('Electrical Supplies', 'Bundle Ties', 'Cable Accessories')
merge_sub('Electrical Supplies', 'Tap Connectors', 'Plugs & Connectors')
merge_sub('Electrical Supplies', 'Alligator Clips', 'Electrical Tools & Instruments')
merge_sub('Electrical Supplies', 'Fluorescent Lamps', 'Lighting')
merge_sub('Electrical Supplies', 'Halogen Lamps', 'Lighting')

# ======================== RECALC & SORT ========================
print("\n--- RECALCULATING TOTALS ---")
for cat in tree:
    recalc_total(cat)
    sort_children(cat)
    print(f"  {cat['name']}: {cat['total']:,} products, {len(cat.get('_children',[]))} subcats")

# ======================== REORDER ========================
# Logical order: Plumbing group → HVAC+Heating group → Electrical
desired_order = [
    'Plumbing Fittings & Pipes',      # 1. Most fundamental (pipes, fittings)
    'Plumbing Fixtures',              # 2. End-user fixtures
    'Plumbing Equipment',             # 3. Equipment (water heaters, pumps)
    'Valves & Waterworks',            # 4. Control & distribution
    'HVAC Equipment & Systems',       # 5. HVAC main units
    'HVAC Parts & Controls',          # 6. HVAC replacement parts
    'Heating Supplies',               # 7. Heating systems
    'Electrical Supplies',            # 8. Electrical
]

reordered = []
for name in desired_order:
    found = None
    for cat in tree:
        if cat['name'] == name:
            found = cat
            break
    if found:
        reordered.append(found)
    else:
        print(f"  [WARN] Category not found: {name}")

# Safety: append any categories not in desired_order
for cat in tree:
    if cat not in reordered:
        print(f"  [WARN] Unexpected category added at end: {cat['name']}")
        reordered.append(cat)

# ======================== PRINT SUMMARY ========================
print("\n===== NEW CATEGORY ORDER =====")
for i, cat in enumerate(reordered):
    sub_count = len(cat.get('_children', []))
    print(f"{i+1}. {cat['name']}: {cat['total']:,} products, {sub_count} subcategories")
    for sub in cat.get('_children', []):
        sub_sub = len(sub.get('_children', []))
        marker = f' [{sub_sub} sub]' if sub_sub > 0 else ' [leaf]'
        print(f"   {sub['name']} ({sub['total']:,}){marker}")

# ======================== WRITE OUTPUT ========================
save_json(reordered, os.path.join(DATA, 'tree.json'))
print(f"\n[OK] Saved reordered tree.json ({len(reordered)} categories)")

# Verify
check = load_json(os.path.join(DATA, 'tree.json'))
total = sum(c['total'] for c in check)
print(f"[OK] Verified: {len(check)} categories, {total:,} total products")
