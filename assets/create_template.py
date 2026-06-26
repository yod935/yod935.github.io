"""
从当前已填充数据的 Product_Catalog.html 创建模板文件
把数据部分（TREE_DATA, SEARCH_DATA, EMBEDDED_DATA）恢复为占位符
"""
import re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_FILE = os.path.join(ROOT, 'Product_Catalog.html')
TEMPLATE_FILE = os.path.join(ROOT, 'Product_Catalog.template.html')

with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

print(f"读取 HTML: {len(html)} 字符")

# 1. 替换 var TREE_DATA = [...] 为 var TREE_DATA = __TREE_DATA__;
# 找到 TREE_DATA 的起始和结束位置
tree_pattern = r'var TREE_DATA = \[.*?\];\n'
html, count = re.subn(tree_pattern, 'var TREE_DATA = __TREE_DATA__;\n', html, count=1, flags=re.DOTALL)
print(f"  替换 TREE_DATA: {count} 处")

# 2. 替换 var SEARCH_DATA = [...] 为 var SEARCH_DATA = __SEARCH_DATA__;
search_pattern = r'var SEARCH_DATA = \[.*?\];\n'
html, count = re.subn(search_pattern, 'var SEARCH_DATA = __SEARCH_DATA__;\n', html, count=1, flags=re.DOTALL)
print(f"  替换 SEARCH_DATA: {count} 处")

# 3. 替换 var EMBEDDED_DATA = {...} 为 var EMBEDDED_DATA = __EMBEDDED_DATA__;
# EMBEDDED_DATA 是大对象，需要找到匹配的结尾
# 使用更简单的方法：找到 "var EMBEDDED_DATA = " 和接下来的 "};"
emb_start = html.find('var EMBEDDED_DATA = ')
if emb_start >= 0:
    # 找到后面的 "};" (数据结尾)
    emb_data_start = emb_start + len('var EMBEDDED_DATA = ')
    # 使用括号匹配来找到正确的结束位置
    # 因为 JSON 对象有用 {} 包裹
    brace_count = 0
    pos = emb_data_start
    in_string = False
    escape_next = False
    
    for i in range(emb_data_start, len(html)):
        ch = html[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
        elif not in_string:
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    # 找到了匹配的结束位置
                    emb_end = i + 1  # 包含 }
                    # 检查后面是否有 ;
                    semi = ''
                    if emb_end < len(html) and html[emb_end] == ';':
                        semi = ';'
                        emb_end += 1
                    
                    # 替换
                    html = html[:emb_start] + 'var EMBEDDED_DATA = __EMBEDDED_DATA__;' + html[emb_end:]
                    print(f"  替换 EMBEDDED_DATA: 1 处")
                    break

# 4. 替换统计数字为占位符
html = html.replace('__STAT_PRODUCTS__', '__STAT_PRODUCTS__')  # 确保存在
html = html.replace('__STAT_CATEGORIES__', '__STAT_CATEGORIES__')  # 确保存在

# 实际上统计数字是在 HTML 中的，需要找到并替换
# 查找类似 <span id="pc">1782</span> 的内容
html = re.sub(r'<span id="pc">\d+</span>', '<span id="pc">__STAT_PRODUCTS__</span>', html)
html = re.sub(r'<span id="cc">\d+</span>', '<span id="cc">__STAT_CATEGORIES__</span>', html)

# 保存模板
with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n模板已保存: {TEMPLATE_FILE}")
print(f"模板大小: {len(html)} 字符 ({len(html)/1024:.1f} KB)")
