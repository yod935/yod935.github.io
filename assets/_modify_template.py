#!/usr/bin/env python3
"""
Modify Product_Catalog.template.html:
1. Replace __STAT_PRODUCTS__ and __STAT_CATEGORIES__ with "..."
2. Remove __TREE_DATA__, __SEARCH_DATA__, __EMBEDDED_DATA__ placeholders
3. Add fetch() logic to load JSON data
4. Convert the self-executing function to initApp()
5. Add Promise.all fetch at the end of <script>
"""
import re

import os
FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Product_Catalog.template.html')

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace stats placeholders (already done via Edit, but ensure)
content = content.replace('__STAT_PRODUCTS__', '…')
content = content.replace('__STAT_CATEGORIES__', '…')

# 2. Remove data placeholders and replace with fetch logic
#    Find: var TREE_DATA = __TREE_DATA__;
#           var SEARCH_DATA = __SEARCH_DATA__;
#           var EMBEDDED_DATA = __EMBEDDED_DATA__;
#    Replace with: var TREE_DATA = null; ...
old_data = """var TREE_DATA = __TREE_DATA__;
var SEARCH_DATA = __SEARCH_DATA__;
// Embedded Excel data: { "path/to/file.xlsx": { "h": [headers], "r": [[row1], [row2], ...] } }
var EMBEDDED_DATA = __EMBEDDED_DATA__;"""

new_data = """var TREE_DATA = null;
var SEARCH_DATA = null;
var EMBEDDED_DATA = null;"""

if old_data in content:
    content = content.replace(old_data, new_data)
    print("[OK] Replaced data placeholders")
else:
    # Already replaced or different format
    print("[SKIP] Data placeholders not found (may already be replaced)")

# 3. Replace the self-executing init block
#    Find: (function(){ ... })();
#    But only the one right after =utils=== comment
old_init = """// ===== INIT =====
(function(){
    var h=''; for(var i=0;i<TREE_DATA.length;i++) h+=nodeHTML(TREE_DATA[i],0,'');
    document.getElementById('tc').innerHTML=h;
    setTimeout(function(){var rs=document.querySelectorAll('#tc > .tree-node > .tree-row');for(var i=0;i<rs.length;i++)tgl(rs[i]);},60);
})();"""

new_init = """// ===== INIT =====
function initApp() {
    if (!TREE_DATA || !SEARCH_DATA) { console.error('Data not loaded'); return; }
    var h=''; for(var i=0;i<TREE_DATA.length;i++) h+=nodeHTML(TREE_DATA[i],0,'');
    document.getElementById('tc').innerHTML=h;
    setTimeout(function(){var rs=document.querySelectorAll('#tc > .tree-node > .tree-row');for(var i=0;i<rs.length;i++)tgl(rs[i]);},60);

    // Update stats
    document.getElementById('sp').textContent = SEARCH_DATA.length;
    document.getElementById('sc').textContent = TREE_DATA.length;

    // Build search index
    buildSearchIndex();
}"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("[OK] Replaced init function with initApp()")
else:
    print("[SKIP] Init block not found at expected location")

# 4. Add fetch() logic before </script>
#    Insert before the closing </script>
fetch_block = """
// ===== LOAD DATA (fetch JSON files) =====
Promise.all([
  fetch('data/tree.json').then(function(r){return r.json();}),
  fetch('data/search.json').then(function(r){return r.json();}),
  fetch('data/products.json').then(function(r){return r.json();})
]).then(function(results){
  TREE_DATA = results[0];
  SEARCH_DATA = results[1];
  EMBEDDED_DATA = results[2];
  initApp();
}).catch(function(err){
  document.getElementById('mc').innerHTML='<div class="er"><h3>Loading Error</h3><p>Could not load data files. Make sure data/ folder exists.</p></div>';
  console.error('Data load error:', err);
});
"""

# Insert before </script>
if '</script>' in content:
    content = content.replace('</script>', fetch_block + '</script>', 1)
    print("[OK] Added fetch() logic before </script>")
else:
    print("[ERROR] </script> not found!")

# 5. Add buildSearchIndex() function definition
#    The original code built SEARCH_ALL globally; we need to wrap it in a function
#    Find: var SEARCH_ALL = [];
#    Replace with: function buildSearchIndex() { ... }
old_search = """// Build a flat list of searchable items including categories
var SEARCH_ALL = [];

// Add all leaf products
for(var si=0;si<SEARCH_DATA.length;si++){
    var item = SEARCH_DATA[si];
    SEARCH_ALL.push({
        type:'product',
        no:item.no,
        fname:item.fname,
        fpath:item.fpath,
        breadcrumb:item.breadcrumb,
        levels:item.levels
    });
}

// Add category nodes (from tree)
function addCatNodes(nodes, parentPath){
    if(!nodes) return;
    for(var ni=0;ni<nodes.length;ni++){
        var node = nodes[ni];
        var catPath = parentPath ? parentPath+' > '+node.name : node.name;
        SEARCH_ALL.push({
            type:'category',
            name:node.name,
            path:catPath,
            total:node.total||0
        });
        if(node._children) addCatNodes(node._children, catPath);
    }
}
addCatNodes(TREE_DATA, '');"""

new_search = """// Build a flat list of searchable items including categories
var SEARCH_ALL = [];
function buildSearchIndex() {
    SEARCH_ALL = [];
    // Add all leaf products
    for(var si=0;si<SEARCH_DATA.length;si++){
        var item = SEARCH_DATA[si];
        SEARCH_ALL.push({
            type:'product',
            no:item.no,
            fname:item.fname,
            fpath:item.fpath,
            breadcrumb:item.breadcrumb,
            levels:item.levels
        });
    }

    // Add category nodes (from tree)
    function addCatNodes(nodes, parentPath){
        if(!nodes) return;
        for(var ni=0;ni<nodes.length;ni++){
            var node = nodes[ni];
            var catPath = parentPath ? parentPath+' > '+node.name : node.name;
            SEARCH_ALL.push({
                type:'category',
                name:node.name,
                path:catPath,
                total:node.total||0
            });
            if(node._children) addCatNodes(node._children, catPath);
        }
    }
    addCatNodes(TREE_DATA, '');
}"""

if old_search in content:
    content = content.replace(old_search, new_search)
    print("[OK] Wrapped search index build in buildSearchIndex()")
else:
    print("[SKIP] Search building block not found at expected location")
    # Try to find it with regex (flexible whitespace)
    pattern = r'// Build a flat list of searchable items including categories\s*var SEARCH_ALL = \[\];'
    if re.search(pattern, content):
        print("[INFO] Found with regex, but exact match failed")

# Write back
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone! Template modified successfully.")
print("Stats: __STAT_PRODUCTS__ count:", content.count('__STAT_PRODUCTS__'))
print("Stats: __STAT_CATEGORIES__ count:", content.count('__STAT_CATEGORIES__'))
print("Stats: __TREE_DATA__ count:", content.count('__TREE_DATA__'))
print("Stats: __SEARCH_DATA__ count:", content.count('__SEARCH_DATA__'))
print("Stats: __EMBEDDED_DATA__ count:", content.count('__EMBEDDED_DATA__'))
