import json

with open('D:/SupplyHouseFetch/YOD_Catalog_Website/data/tree.json', 'r', encoding='utf-8') as f:
    tree = json.load(f)
with open('D:/SupplyHouseFetch/YOD_Catalog_Website/data/products.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

def build_lookup(nodes, result=None):
    if result is None: result = {}
    for n in nodes:
        result[n['name']] = n
        build_lookup(n.get('_children', []), result)
    return result
node_map = build_lookup(tree)

def get_children(parent_name, child_names):
    p = node_map.get(parent_name)
    if not p: return []
    return [c for c in p.get('_children', []) if c['name'] in child_names]

def get_all_except(parent_name, exclude):
    p = node_map.get(parent_name)
    if not p: return []
    return [c for c in p.get('_children', []) if c['name'] not in exclude]

def find_img(node):
    for f in node.get('_files', []):
        pd = products.get(f['path'], {})
        imgs = pd.get('i', {})
        if imgs:
            return list(imgs.values())[0]
    for c in node.get('_children', []):
        r = find_img(c)
        if r: return r
    return None

def find_first_img(nodes):
    for n in nodes:
        r = find_img(n)
        if r: return r
    return None

PE = "Plumbing Equipment"
PF = "Plumbing Fittings & Pipes"
FIX = "Plumbing Fixtures"
HE = "HVAC Equipment & Systems"
HP = "HVAC Parts & Controls"
HTG = "Heating Supplies"
EL = "Electrical Supplies"

cats = [
    ("Valves & Fittings", get_children(PF,["Pipe Fittings & Nipples","MegaPress Fittings","Push-to-Connect Fittings","Copper Fittings","CPVC Fittings","PVC Fittings","Compression Fittings","Brass Fittings","Cast Iron Fittings","Specialty Fittings","Gas Connectors","Dielectric Unions","Pipe Nipples","Couplings"]) + get_children(PE,["Backflow Preventers","Ball Valves","Gate Valves","Globe Valves","Check Valves","Relief Valves","Angle Valves","Valves"])),
    ("Pipes & PEX", get_children(PF,["PEX","Copper Pipe","Plastic Pipe","Black Pipe","Galvanized Pipe","CPVC Pipe","PVC Pipe","Stainless Steel Pipe","Flexible Pipe"])),
    ("AC Installation Parts & Line Sets", get_children(HP,["Air Conditioning Installation Parts"]) + get_children(HE,["Line Sets"])),
    ("AC Equipment", get_children(HE,["Mini Split Air Conditioners","PTAC Air Conditioners","Compressors","HVAC Equipment"])),
    ("HVAC Replacement Parts", get_children(HP,["HVAC Replacement Parts","Motors & Accessories","HVAC Controls","Capacitors","System Protectors"]) + get_children(HE,["Motors & Accessories","HVAC and Refrigeration Valves"])),
    ("Condensate & Refrigeration", get_children(HE,["Condensate Removal Pumps"]) + get_children(HP,["Refrigeration Supplies","Refrigeration Controls","Dryer Parts","Electric Heat Coil Restring Kits","Refrigerator Parts","Swamp Cooler and Ice Maker Pumps"])),
    ("Ventilation & Air Distribution", get_children(HE,["Ventilation Fans","Range Hoods"]) + get_children(HP,["Dampers","Registers & Grilles","Flex Duct"])),
    ("Indoor Air Quality", get_children(HE,["Air Cleaners","Heat & Energy Recovery Ventilators","Dehumidifiers","Humidifiers"]) + get_children(HP,["Replacement Filters","Temperature Controllers","Hand Dryers"])),
    ("Boilers & Heating Parts", get_children(HTG,["Boilers","Boiler Parts","Circulator Pumps","Expansion Tanks","Air Eliminators","Aquastats & Wells","Low Water Cutoffs","Flow Switches","Magnetic Boiler Filters","Switching Relays","Temperature & Pressure Gauges","Water Feeders","Boiler Trim Kits","Tankless Coils"]) + get_children(PE,["Water Heater Parts"])),
    ("Radiant & Hydronic Heating", get_children(HTG,["Radiant Heat","Baseboard Heaters","KickSpace Heaters","Unit Heaters","Radiator Valves","Roof & Gutter De-Icing Cables"])),
    ("Gas & Burner Systems", get_children(HTG,["Gas Valves & Controls","Ignitors & Burners","Maxitrol Gas Regulators","Underground Gas Products","Heating Specialties"])),
    ("Heat Pumps & Thermostats", get_children(HTG,["Heat Pumps","Thermostats","Tekmar Controls"])),
    ("Drains & Sewer", get_children(PF,["Plumbing Drainage"]) + get_children(FIX,["Drains","Access Doors"]) + get_children(PE,["Grease Traps"])),
    ("Pumps & Water Treatment", get_children(PE,["Pumps","Water Filters","Well Pressure Tanks & Parts","Fire Sprinklers","Macerating Toilet Systems"])),
    ("Electrical Supplies", get_all_except(EL,["Electrical Tools & Instruments"])),
    ("Other", get_children(PE,["Tools","Water Heaters","Accessories","Steam Showers","Plumbing Chemicals & Compounds"]) + get_children(FIX,["Tub & Shower Products","Toilet Parts","Sinks","Garbage Disposals","Urinals and Toilets","Sloan Sensor Operated Optima SMOOTH Flushometers"]) + get_children(HP,["Tools","Chemicals & Cleaners"
