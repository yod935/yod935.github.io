# Product Catalog

前端产品目录网页，适用于 GitHub Pages 部署。

## 项目结构

```
.
├── index.html          # 主页面（入口）
├── data/
│   ├── tree.json      # 分类目录树
│   ├── search.json    # 搜索索引
│   └── products.json # 产品数据（已过滤无图产品）
├── images/           # 产品图片（~400 MB，43144 张）
├── assets/
│   ├── build_catalog_v2.py  # 构建脚本
│   └── ...
├── start.bat         # Windows 本地预览启动脚本
└── start.sh          # Mac/Linux 本地预览启动脚本
```

## 本地预览

**Windows:**
双击 `start.bat`，脚本会启动 HTTP 服务器并自动打开浏览器。

**Mac / Linux:**
在终端运行：
```bash
chmod +x start.sh
./start.sh
```

## 部署到 GitHub Pages

1. 创建 GitHub 仓库
2. 只推送以下文件和目录（参考 `.gitignore`）：
   - `index.html`
   - `data/`
   - `images/`
   - `README.md`
   - `.gitignore`
3. 在仓库设置中启用 GitHub Pages（分支选择 `main` 或 `gh-pages`）
4. 访问 `https://<username>.github.io/<repo-name>/` 查看

⚠️ **注意**：
- `images/` 目录约 400 MB，确保仓库总大小不超过 GitHub 的 1 GB 限制
- 如需减小仓库大小，可将图片上传到图床（如 Cloudinary、Imgur），然后修改 `images/` 路径

## 构建（重新生成数据）

如果需要重新从 Excel 源文件构建：

```bash
cd assets
python -B build_catalog_v2.py
```

⚠️ 需要 `Organized_Products_V2/` 目录（Excel 源文件，不纳入版本控制）

## 技术栈

- 纯前端（HTML + CSS + Vanilla JavaScript）
- 数据通过 `fetch()` 加载 JSON 文件
- 无后端依赖，可部署到任何静态文件服务器
- SheetJS（xlsx.js）用于备用 Excel 文件解析

## 特性

- ✅ 响应式设计，支持桌面和移动端
- ✅ 分类目录树浏览
- ✅ 实时搜索（支持产品名、编号、分类名）
- ✅ 产品图片展示
- ✅ 无图产品自动过滤
- ✅ 可下载原始 Excel 文件（需提供 Excel 源文件）
