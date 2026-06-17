# JoinQuant Notebook Automation

通过 Kimi WebBridge 自动化操控聚宽（JoinQuant）量化研究平台的 Jupyter Notebook 环境。

## 📋 简介

本项目提供了一套完整的工具链，让 AI 可以像人一样操作聚宽研究平台：

- **打开浏览器 → 登录聚宽 → 创建 Notebook → 写代码 → 执行 → 读结果**
- 支持复杂的多单元格策略代码写入
- 跨平台（Windows / macOS / Linux / WSL）

## 🚀 快速开始

### 前置条件

1. 安装 [Kimi WebBridge](https://www.joinquant.com) 浏览器扩展
2. 启动 WebBridge daemon（监听 `127.0.0.1:10086`）
3. 浏览器打开至少一个网页标签页
4. 在浏览器中登录 [聚宽](https://www.joinquant.com)

### 连接检查

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  -d '{"action":"evaluate","args":{"code":"document.title"},"session":"joinquant"}'
```

返回 `{"ok":true,...}` 表示连接成功。

## 📦 工具脚本

| 脚本 | 用途 |
|------|------|
| `jq_helper.py` | WebBridge 核心通信库，封装了 `evaluate` / `navigate` 等操作 |
| `write_cell.py` | 将本地 Python 文件写入 Jupyter 单元格，解决大批量代码写入问题 |

### jq_helper.py

```python
from jq_helper import wb, wb_nav, js

# 执行 JavaScript
result = wb('document.title')

# 导航到 URL
wb_nav('https://www.joinquant.com/research')

# 包装 IIFE
code = js('''
  var d = document.getElementById("research").contentDocument;
  return d.title;
''')
```

### write_cell.py

将本地文件写入当前选中的单元格，避免 bash 内联 JSON 的转义噩梦：

```bash
# 1. 在 Notebook 中插入一个新单元格
# 2. 确保它被选中
# 3. 写入代码
python write_cell.py my_strategy.py
```

## 📘 Skill 文档

完整的聚宽操控指南见 [SKILL.md](./SKILL.md)，包含：

- Notebook 创建 / 写入 / 执行 / 读取全流程
- 按钮映射表（解决 `data-jupyter-action` 选择器失效问题）
- 内核中断与重启
- 大批量代码写入方案
- 常见问题与注意事项

## ⚠️ 已知限制

- **网络限制**：聚宽研究环境的容器可能无法访问外网 API（如 Binance、CoinGecko）。建议在本地先下载外部数据，再写入 Notebook。
- **弹窗限制**：WebBridge 无法控制弹出新标签页，需改用 API 创建 Notebook + iframe 导航。
- **浏览器要求**：浏览器必须保持打开状态且至少有一个网页标签页，WebBridge 扩展才能维持连接。

## 🔧 技术栈

- **Kimi WebBridge** — 浏览器自动化桥接
- **Classic Jupyter** — 聚宽使用的经典 Jupyter（非 JupyterLab）
- **CodeMirror** — 经典 Jupyter 的代码编辑器
- **Python 3.6** — 聚宽研究环境的 Python 版本
