# YOD Product Catalog

> One-Stop Supplier For HVAC & Plumbing Service Contractors

---

## Version History

### v1.4 — 2026-06-27
- Hero 标题更新为 "One-Stop Supplier For HVAC & Plumbing Service Contractors"
- Hero 统计：14 Yrs · Rapid R&D（3-Day Drawings, 7-Day Samples）
- About 年份更新为 Since 2012 / 14 Years Experience
- 联系方式更新：WhatsApp +86 136-5678-9307 · sales@yodcompany.com
- 密码面板重设计：SVG 图标 + 多层阴影 + 克制风格
- 安全检测动画改为 Dashboard 手动触发
- start.bat 加入端口占用自动清理

### v1.3 — 2026-06-26
- Export Full Catalog 功能（导出合并后的完整产品 JSON）
- GitHub Publish 面板（通过 API 直接写回仓库）
- 操作日志系统（Activity Log，最多 500 条）
- 密码 SHA-256 哈希存储，Web Crypto API 异步验证
- 新建产品功能（Custom Products 带黄色标签）

### v1.2 — 2026-06-25
- 管理员面板：Dashboard 统计 / Product Manager CRUD / 显示隐藏切换
- 首页跳转逻辑修复、搜索框失焦修复、按钮样式修复
- 进入管理员系统入口：页面底部「·」→ 密码验证

### v1.1 — 2026-06-24
- 优化构建脚本，按分类规模排序，全局唯一序号 0001-1795
- 分离卖家版 / 买家版目录

### v1.0 — 2026-06-23
- 初始发布：1,892 个源 Excel → 预编译为 JSON + 图片
- 8 大分类 · 40,000+ 产品 · 41,229 张图片
- 纯静态前端：分类树浏览、实时搜索、响应式设计

---

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
