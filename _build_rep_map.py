"""
Build comprehensive catRepImageMap for ALL category levels - V2 (improved).
For every node that has _children, find a representative product image.
Improved strategy:
  1. Gather more products per file (5 instead of 3)
  2. Better keyword extraction (don't strip everything to nothing)
  3. When keyword match fails, use any product from the subtree as fallback
"""
import json, re, os

BASE = 'D:/SupplyHouseFetch/YOD_Catalog_Website'

print("Loading data...")
with open(f'{BASE}/data/tree.json', 'r', encoding='utf-8') as f:
    tree = json.load(f)
with open(f'{BASE}/data/products.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

# ─── Gather products from subtree ──────────────────────────────────────
def gather_products(node, max_per_file=5):
    """Collect {name, img} from products in node's subtree."""
    results = []
    for f in node.get('_files', []):
        pdata = products.get(f['path'], {})
        imgs = pdata.get('i', {})
        rows = pdata.get('r', [])
        count = 0
        for row in rows:
            idx = str(row[0]) if row else ''
            pname = row[2] if len(row) > 2 else ''
            if idx in imgs and pname:
                results.append({'name': pname, 'img': imgs[idx]})
                count += 1
                if count >= max_per_file:
                    break
    for c in node.get('_children', []):
        results.extend(gather_products(c, max_per_file))
    return results

def find_any_image(node):
    """DFS to find any product image in subtree."""
    for f in node.get('_files', []):
        pdata = products.get(f['path'], {})
        imgs = pdata.get('i', {})
        if imgs:
            return list(imgs.values())[0]
    for c in node.get('_children', []):
        r = find_any_image(c)
        if r:
            return r
    return None

# ─── Keyword extraction ────────────────────────────────────────────────
# Suffix words that indicate category grouping, not the product itself
SUFFIX_WORDS = {
    'fittings', 'supplies', 'equipment', 'systems', 'parts', 'products',
    'accessories', 'components', 'materials', 'fixtures', 'controls',
    'tools', 'chemicals', 'cleaners', 'kits', 'specialties', 'instruments',
    'devices', 'units', 'elements', 'items', 'solutions', 'connections',
    'assemblies', 'packages',
}

SINGULAR_MAP = {
    'fittings': 'fitting', 'supplies': 'supply', 'parts': 'part',
    'systems': 'system', 'controls': 'control', 'valves': 'valve',
    'tools': 'tool', 'kits': 'kit', 'products': 'product',
    'accessories': 'accessory', 'components': 'component',
    'fixtures': 'fixture', 'cleaners': 'cleaner', 'chemicals': 'chemical',
    'specialties': 'specialty', 'instruments': 'instrument',
    'devices': 'device', 'units': 'unit', 'elements': 'element',
    'items': 'item', 'adapters': 'adapter', 'connectors': 'connector',
    'drains': 'drain', 'pumps': 'pump', 'motors': 'motor',
    'capacitors': 'capacitor', 'sensors': 'sensor', 'fans': 'fan',
    'filters': 'filter', 'grilles': 'grille', 'registers': 'register',
    'dampers': 'damper', 'sleeves': 'sleeve',
    'couplings': 'coupling', 'nipples': 'nipple', 'elbows': 'elbow',
    'tees': 'tee', 'unions': 'union', 'caps': 'cap', 'plugs': 'plug',
    'bushings': 'bushing', 'flanges': 'flange', 'reducers': 'reducer',
    'wyes': 'wye', 'heaters': 'heater', 'boilers': 'boiler',
    'switches': 'switch', 'controllers': 'controller',
    'ignitors': 'igniter', 'burners': 'burner', 'regulators': 'regulator',
    'thermostats': 'thermostat', 'compressors': 'compressor',
    'condensers': 'condenser', 'housings': 'housing', 'panels': 'panel',
    'breakers': 'breaker', 'enclosures': 'enclosure', 'starters': 'starter',
    'brackets': 'bracket', 'evaporators': 'evaporator',
    'dehumidifiers': 'dehumidifier', 'humidifiers': 'humidifier',
    'ventilators': 'ventilator', 'eliminators': 'eliminator',
    'registers': 'register', 'routers': 'router', 'splitters': 'splitter',
    'transmitters': 'transmitter', 'receivers': 'receiver',
    'indicators': 'indicator', 'detectors': 'detector',
    'generators': 'generator', 'transformers': 'transformer',
    'cleaners': 'cleaner', 'covers': 'cover', 'mounters': 'mounter',
    'washers': 'washer', 'wrenches': 'wrench', 'cutters': 'cutter',
    'cables': 'cable', 'wires': 'wire', 'cords': 'cord', 'strips': 'strip',
    'gaskets': 'gasket', 'seals': 'seal', 'o-rings': 'o-ring',
    'springs': 'spring', 'bearings': 'bearing', 'belts': 'belt',
    'coils': 'coil', 'cores': 'core', 'inserts': 'insert',
    'gauges': 'gauge', 'meters': 'meter', 'timers': 'timer',
    'relays': 'relay', 'contactors': 'contactor',
    'protectors': 'protector', 'isolators': 'isolator',
    'actuators': 'actuator', 'operators': 'operator',
    'seats': 'seat', 'stems': 'stem', 'disks': 'disk',
    'handles': 'handle', 'knobs': 'knob', 'levers': 'lever',
    'tanks': 'tank', 'vessels': 'vessel', 'cylinders': 'cylinder',
    'sprinklers': 'sprinkler', 'extinguishers': 'extinguisher',
    'hydrants': 'hydrant', 'strainers': 'strainer',
    'traps': 'trap', 'vents': 'vent', 'outlets': 'outlet',
    'supports': 'support', 'hangers': 'hanger', 'clamps': 'clamp',
    'anchors': 'anchor', 'brackets': 'bracket', 'saddles': 'saddle',
    'risers': 'riser', 'manifolds': 'manifold',
    'pumps': 'pump', 'motors': 'motor',
}

def extract_keywords(cat_name):
    """Build keyword strategies from most specific to least, NEVER empty."""
    name = cat_name.strip()
    strategies = []
    
    # Split into words, handle "&" as separator
    raw_words = []
    for part in name.replace('&', ' and ').split():
        w = part.strip().rstrip(',')
        if w and w.lower() not in ('and',):
            raw_words.append(w)
    
    # Strategy 1: Singularize the last word, keep everything else
    if raw_words:
        last_lower = raw_words[-1].lower()
        singular = SINGULAR_MAP.get(last_lower)
        if singular:
            s = ' '.join(raw_words[:-1]) + ' ' + singular
            s = s.strip()
            if s and s != name:
                strategies.append(s)
    
    # Strategy 2: Remove only the LAST suffix word(s)
    meaningful = []
    for w in raw_words:
        if w.lower() not in SUFFIX_WORDS:
            meaningful.append(w)
    if meaningful and len(meaningful) < len(raw_words):
        core = ' '.join(meaningful)
        if core and core not in strategies:
            strategies.append(core)
    
    # Strategy 3: Try to singularize meaningful last word
    if meaningful:
        last_lower = meaningful[-1].lower()
        singular = SINGULAR_MAP.get(last_lower)
        if singular:
            s = ' '.join(meaningful[:-1]) + ' ' + singular
            s = s.strip()
            if s and s not in strategies:
                strategies.append(s)
    
    # Strategy 4: Full name always
    if name not in strategies:
        strategies.append(name)
    
    return strategies

def normalize(s):
    """Tolerant normalization for matching."""
    s = s.lower()
    # Remove punctuation, special chars, keep alphanumeric and spaces
    s = re.sub(r'[\/\-–—,\.\(\)\[\]\{\}"\']+', ' ', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # For matching: remove spaces too
    s_nospace = re.sub(r'\s+', '', s)
    return s_nospace

def find_rep_image(node):
    """Find representative product image for a category node using keyword matching.
    Falls back to any image in the subtree on keyword miss."""
    all_prods = gather_products(node)
    if not all_prods:
        return find_any_image(node)
    
    keywords_list = extract_keywords(node['name'])
    
    best_img = None
    best_score = -1
    
    for kw in keywords_list:
        kw_norm = normalize(kw)
        if not kw_norm or len(kw_norm) < 3:
            continue
        for pi, prod in enumerate(all_prods):
            prod_norm = normalize(prod['name'])
            if kw_norm in prod_norm:
                # Score: higher = better match
                # - shorter product name (more specific)
                # - earlier position in list
                # - keyword at start of name
                score = 2000 - len(prod_norm) - pi * 2
                if prod_norm.startswith(kw_norm):
                    score += 1000
                if score > best_score:
                    best_score = score
                    best_img = prod['img']
    
    if best_img:
        return best_img
    
    # No keyword match: use first product in subtree
    return all_prods[0]['img'] if all_prods else find_any_image(node)

# ─── Build map ─────────────────────────────────────────────────────────
def build_map(nodes, result_map=None):
    if result_map is None:
        result_map = {}
    for n in nodes:
        if n.get('_children'):
            name = n['name']
            if name not in result_map:
                img = find_rep_image(n)
                if img:
                    result_map[name] = img
            build_map(n['_children'], result_map)
    return result_map

print("Building representative image map for all sub-categories...")
rep_map = build_map(tree)
print(f"Total entries: {len(rep_map)}")

# ─── Generate JS output ─────────────────────────────────────────────────
lines = ['var catRepImageMap = {']
for name, img in sorted(rep_map.items()):
    lines.append(f"  {json.dumps(name)}: {json.dumps(img)},")
lines.append('};')
output_js = '\n'.join(lines)

out_js = 'D:/SupplyHouseFetch/PythonFetch/_catRepImageMap.js'
with open(out_js, 'w', encoding='utf-8') as f:
    f.write(output_js)
print(f"JS written to {out_js}")

# ─── Verification summary ──────────────────────────────────────────────
# Build name lookup for product matching
def build_lookup(nodes, res=None):
    if res is None:
        res = {}
    for n in nodes:
        res[n['name']] = n
        build_lookup(n.get('_children', []), res)
    return res

node_lookup = build_lookup(tree)

summary = []
summary.append("# catRepImageMap V2 - Verification Summary\n")
summary.append(f"Generated {len(rep_map)} category image mappings\n\n")

matched_count = 0
fallback_count = 0

for name, img in sorted(rep_map.items()):
    node = node_lookup.get(name)
    if not node:
        continue
    # Gather products to find which one matches the selected image
    prods = gather_products(node, max_per_file=5)
    matched_name = ''
    for p in prods:
        if p['img'] == img:
            matched_name = p['name']
            break
    
    keywords_tried = ' → '.join(extract_keywords(name))
    
    summary.append(f"## {name}")
    summary.append(f"  Image: `{img}`")
    if matched_name:
        summary.append(f"  ✅ Product: **{matched_name}**")
        matched_count += 1
    else:
        summary.append(f"  ⚠️  Fallback (first product in subtree)")
        fallback_count += 1
    summary.append(f"  Keywords: {keywords_tried}")
    summary.append('')

summary.insert(3, f"**Matched: {matched_count} | Fallback: {fallback_count}**\n")
summary.insert(3, '')

out_md = 'D:/SupplyHouseFetch/PythonFetch/_catRepImageMap_verify.md'
with open(out_md, 'w', encoding='utf-8') as f:
    f.write('\n'.join(summary))
print(f"Verification: {out_md}")

print(f"\nDone! Matched: {matched_count}, Fallback: {fallback_count}")
