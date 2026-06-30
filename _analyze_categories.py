"""
Analyze each of 16 display categories and list product sub-categories + sample products with images.
Mirrors the buildDisplayCategories() JS logic.
"""
import json

with open('D:/SupplyHouseFetch/YOD_Catalog_Website/data/tree.json', 'r', encoding='utf-8') as f:
    tree = json.load(f)

with open('D:/SupplyHouseFetch/YOD_Catalog_Website/data/products.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

# ─── Build name→node lookup ───────────────────────────────────────────────────
def build_lookup(nodes, result=None):
    if result is None:
        result = {}
    for n in nodes:
        result[n['name']] = n
        build_lookup(n.get('_children', []), result)
    return result

node_map = build_lookup(tree)

def get_node(name):
    return node_map.get(name)

# ─── Collect all product names+paths from a given parent node + child filter ─
def collect_children(parent_name, child_names):
    parent = get_node(parent_name)
    if not parent:
        return []
    results = []
    for c in parent.get('_children', []):
        if c['name'] in child_names:
            results.append(c)
    return results

def collect_all_except(parent_name, exclude_names):
    parent = get_node(parent_name)
    if not parent:
        return []
    return [c for c in parent.get('_children', []) if c['name'] not in exclude_names]

def gather_files(node):
    """Recursively gather all _files from a node subtree."""
    files = list(node.get('_files', []))
    for c in node.get('_children', []):
        files.extend(gather_files(c))
    return files

def get_representative_products(nodes, max_per_subcat=5):
    """For each sub-category node, return sample products that have images."""
    rep = []
    for node in nodes:
        files = gather_files(node)
        subcat_prods = []
        for f in files:
            path = f['path']
            pdata = products.get(path, {})
            rows = pdata.get('r', [])
            imgs = pdata.get('i', {})
            for row in rows[:20]:  # check first 20 rows per file
                idx = row[0]
                name = row[2] if len(row) > 2 else ''
                has_img = str(idx) in imgs
                if has_img and name:
                    subcat_prods.append({
                        'subcat': node['name'],
                        'name': name,
                        'img': imgs[str(idx)],
                        'path': path,
                        'row_idx': idx
                    })
                    if len(subcat_prods) >= max_per_subcat:
                        break
            if subcat_prods:
                break  # got enough from this sub-cat
        rep.extend(subcat_prods[:3])
    return rep

# ─── Mirror buildDisplayCategories() ─────────────────────────────────────────
CATEGORIES = [
    # (display_name, [(parent_name, [child_names])])
    ("Valves & Fittings", [
        ("Plumbing Fittings & Pipes", ["Pipe Fittings & Nipples","MegaPress Fittings","Push-to-Connect Fittings","Copper Fittings","CPVC Fittings","PVC Fittings","Compression Fittings","Brass Fittings","Cast Iron Fittings","Specialty Fittings","Gas Connectors","Dielectric Unions","Pipe Nipples","Couplings"]),
        ("Plumbing Equipment",        ["Backflow Preventers","Ball Valves","Gate Valves","Globe Valves","Check Valves","Relief Valves","PRV","Angle Valves","Valves"]),
    ]),
    ("Pipes & PEX", [
        ("Plumbing Fittings & Pipes", ["PEX","Copper Pipe","Plastic Pipe","Black Pipe","Galvanized Pipe","CPVC Pipe","PVC Pipe","Stainless Steel Pipe","Flexible Pipe"]),
    ]),
    ("AC Installation Parts & Line Sets", [
        ("HVAC Parts & Controls", ["Air Conditioning Installation Parts"]),
        ("HVAC Equipment & Systems", ["Line Sets"]),
    ]),
    ("AC Equipment", [
        ("HVAC Equipment & Systems", ["Mini Split Air Conditioners","PTAC Air Conditioners","Compressors","HVAC Equipment"]),
    ]),
    ("HVAC Replacement Parts", [
        ("HVAC Parts & Controls", ["HVAC Replacement Parts","Motors & Accessories","HVAC Controls","Capacitors","System Protectors"]),
        ("HVAC Equipment & Systems", ["Motors & Accessories","HVAC and Refrigeration Valves"]),
    ]),
    ("Condensate & Refrigeration", [
        ("HVAC Equipment & Systems", ["Condensate Removal Pumps"]),
        ("HVAC Parts & Controls",    ["Refrigeration Supplies","Refrigeration Controls","Dryer Parts","Electric Heat Coil Restring Kits","Refrigerator Parts","Swamp Cooler and Ice Maker Pumps"]),
    ]),
    ("Ventilation & Air Distribution", [
        ("HVAC Equipment & Systems", ["Ventilation Fans","Range Hoods"]),
        ("HVAC Parts & Controls",    ["Dampers","Registers & Grilles","Flex Duct"]),
    ]),
    ("Indoor Air Quality", [
        ("HVAC Equipment & Systems", ["Air Cleaners","Heat & Energy Recovery Ventilators","Dehumidifiers","Humidifiers"]),
        ("HVAC Parts & Controls",    ["Replacement Filters","Temperature Controllers","Hand Dryers"]),
    ]),
    ("Boilers & Heating Parts", [
        ("Heating Supplies",         ["Boilers","Boiler Parts","Circulator Pumps","Expansion Tanks","Air Eliminators","Aquastats & Wells","Low Water Cutoffs","Flow Switches","Magnetic Boiler Filters","Switching Relays","Temperature & Pressure Gauges","Water Feeders","Boiler Trim Kits","Tankless Coils"]),
        ("Plumbing Equipment",       ["Water Heater Parts"]),
    ]),
    ("Radiant & Hydronic Heating", [
        ("Heating Supplies",         ["