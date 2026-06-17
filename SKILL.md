---
name: joinquant
description: |
  在聚宽(JoinQuant)量化平台的 Jupyter 研究环境中读写代码并执行。
  当用户提到"聚宽"、"JoinQuant"、"量化平台"、"策略研究"等关键词时使用。
  依赖 Kimi WebBridge 技能操控浏览器。
metadata:
  version: "2.0.0"
---

# 聚宽 JoinQuant 量化研究平台

通过 WebBridge 操控聚宽量化投研平台的 Jupyter 研究环境。

## 前置条件

- 用户已在浏览器登录聚宽（https://www.joinquant.com）
- Kimi WebBridge daemon 正在运行

## 工作流程

### 1. 打开研究平台

```json
{"action":"navigate","args":{"url":"https://www.joinquant.com/research"},"session":"joinquant"}
```

如果跳转到登录页，告诉用户需要登录。聚宽页面使用**同源 iframe** (`id="research"`) 加载 Jupyter 环境，所有操作需通过 iframe 访问：

```javascript
var d = document.getElementById('research').contentDocument;
// 或
var w = document.getElementById('research').contentWindow;
var d = w.document;
```

### 2. 创建新 Notebook

用聚宽 Jupyter API 创建：

```javascript
// 先获取 XSRF token
var d = document.getElementById('research').contentDocument;
var xsrf = d.cookie.match(/_xsrf=([^;]+)/)[1];

// 创建 notebook
var r = await fetch('/user/USER_ID/api/contents', {
  method: 'POST',
  headers: {'Content-Type':'application/json','X-Xsrftoken':xsrf},
  body: JSON.stringify({type:'notebook'})
});
var j = await r.json();  // j.path = "Untitled.ipynb"

// 导航 iframe 到 notebook
var f = document.getElementById('research');
f.src = 'https://www.joinquant.com/user/USER_ID/notebooks/' + j.path;
```

用户 ID 可以从 iframe URL 中提取：`/user/{USER_ID}/tree`

### 3. 向当前单元格写代码

```javascript
var cm = d.querySelector('.CodeMirror').CodeMirror;
cm.setValue('print("hello")');
```

**多行代码用数组+join：**

```javascript
var nl = String.fromCharCode(10);
var code = ['line 1', 'line 2', 'line 3'].join(nl);
cm.setValue(code);
```

> `String.fromCharCode(10)` 代替 `\n` 是为了避免各平台 shell 的转义差异问题。

### 4. 执行单元格

```javascript
// 先点击单元格选中它
d.querySelector('.cell').click();
// 再点"运行"按钮
d.querySelector('[data-jupyter-action="jupyter-notebook:run-cell-and-select-next"]').click();
```

> 必须先点 cell 再点 Run，否则 notebook 不知道执行哪个单元格。

### 5. 读取输出

```javascript
d.querySelector('.output_text')?.textContent
// 或读取所有单元格的输出：
var cells = d.querySelectorAll('.cell');
cells.forEach(function(c, i) {
  var out = c.querySelector('.output_text');
  if (out) console.log('cell', i, ':', out.textContent.trim());
});
```

### 6. 插入新单元格并写代码

```javascript
var ins = d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]');

// 选中第一个单元格
d.querySelectorAll('.cell')[0].click();

// 写第一个单元格
var cm = d.querySelector('.cell.selected .CodeMirror').CodeMirror;
cm.setValue('code 1');

// 插入新单元格（自动选中新单元格）
ins.click();

// 写第二个单元格
cm = d.querySelector('.cell.selected .CodeMirror').CodeMirror;
cm.setValue('code 2');

// 以此类推...
```

---

## 推荐工作流（跨平台通用）

**永远优先使用这个方案。** 它用 Python 构建 JSON 请求体并通过临时文件发送，零 shell 转义问题，在 Windows / macOS / Linux / WSL 上行为完全一致。

### 核心模式

```python
import json, subprocess

def wb(code):
    """向 WebBridge 发送 evaluate 请求并返回响应"""
    payload = {
        'action': 'evaluate',
        'args': {'code': code},
        'session': 'joinquant'  # 每次调用使用同一个 session
    }
    # 写临时文件 → curl --data-binary @file
    with open('/tmp/jq-req.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=True)
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'http://127.0.0.1:10086/command',
        '-H', 'Content-Type: application/json',
        '--data-binary', '@/tmp/jq-req.json'
    ], capture_output=True, text=True)
    return r.stdout.strip()
```

> **Windows 注意**：路径用 `C:\Users\xxx\AppData\Local\Temp\jq-req.json`；curl 可能叫 `curl.exe`。
> **WSL 注意**：`/tmp/jq-req.json` 在 WSL 文件系统中，与 Windows 不共享。但 WSL 的 `curl`（非 `curl.exe`）可以直接访问 `127.0.0.1:10086`，所以用 `/tmp/` 路径完全没有问题。
> **macOS/Linux**：同上，直接用 `/tmp/`。

### 长 JS 代码用函数包装

超过一行的 JS 代码包裹 IIFE，避免跨调用声明冲突：

```python
# ✅ 正确：用 IIFE 避免 const/let 重复声明
js = '''(function(){
  var d = document.getElementById("research").contentDocument;
  // ...任何代码...
  return result;
})()'''
```

### 完整流程示例（3 个单元格）

```python
import json, subprocess, time

def wb(code):
    payload = {'action': 'evaluate', 'args': {'code': code}, 'session': 'joinquant-demo'}
    with open('/tmp/jq.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=True)
    r = subprocess.run(['curl', '-s', '-X', 'POST',
        'http://127.0.0.1:10086/command',
        '-H', 'Content-Type: application/json',
        '--data-binary', '@/tmp/jq.json'], capture_output=True, text=True)
    return r.stdout.strip()

d = 'document.getElementById("research").contentDocument'

# Step 1: 写 3 个单元格（选中 → 写 → insert → 写 → insert → 写）
# 先写 cell 0
js1 = f'''(function(){{
  var d = {d};
  var cm = d.querySelector('.CodeMirror').CodeMirror;
  var nl = String.fromCharCode(10);
  cm.setValue(['# Cell 1','print("hello")'].join(nl));
  return 'ok';
}})()'''
wb(js1)

# 插入 cell 1 并写代码
js2 = f'''(function(){{
  var d = {d};
  d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]').click();
  var cm = d.querySelector('.cell.selected .CodeMirror').CodeMirror;
  var nl = String.fromCharCode(10);
  cm.setValue(['# Cell 2','print("world")'].join(nl));
  return 'ok';
}})()'''
wb(js2)

# 插入 cell 2 并写代码
js3 = f'''(function(){{
  var d = {d};
  d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]').click();
  var cm = d.querySelector('.cell.selected .CodeMirror').CodeMirror;
  var nl = String.fromCharCode(10);
  cm.setValue(['# Cell 3','print("!")'].join(nl));
  return 'ok';
}})()'''
wb(js3)

# Step 2: 从 cell 0 开始依次运行
for i in range(3):
    js = f'''(function(){{
      var d = {d};
      d.querySelectorAll('.cell')[{i}].click();
      d.querySelector('[data-jupyter-action="jupyter-notebook:run-cell-and-select-next"]').click();
      return 'ok';
    }})()'''
    wb(js)
    time.sleep(3)  # 等待 kernel 执行

# Step 3: 读取所有输出
js = f'''(function(){{
  var d = {d};
  var cells = d.querySelectorAll('.cell');
  var out = [];
  for (var i = 0; i < cells.length; i++) {{
    var t = cells[i].querySelector('.output_text');
    out.push('Cell ' + i + ': ' + (t ? t.textContent.trim() : '(no output)'));
  }}
  return out.join(String.fromCharCode(10));
}})()'''
print(wb(js))
```

> 为什么 Python 代码里用 `{d}` 而不是 `{d}` 的 f-string 拼接？因为 JS 本身也有 `{}` 语法，需要用 `{{` 和 `}}` 来双层转义，让 Python 输出字面花括号。

---

## WebBridge 调用备忘

### 基础命令格式

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  --data-binary @/path/to/request.json
```

### 常用操作速查

| 操作 | evaluate 脚本片段 |
|------|-------------------|
| 获取 iframe document | `document.getElementById('research').contentDocument` |
| 写代码到选中单元格 | `d.querySelector('.cell.selected .CodeMirror').CodeMirror.setValue(code)` |
| 运行选中单元格 | `d.querySelector('[data-jupyter-action="jupyter-notebook:run-cell-and-select-next"]').click()` |
| 插入下方单元格 | `d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]').click()` |
| 读取文本输出 | `d.querySelector('.output_text')?.textContent` |
| 检查是否有图表 | `d.querySelector('.output_png') !== null` |
| 截图 | `{"action":"screenshot","args":{}}` — 得到图片路径后用 Read 工具查看 |

### 截图

```python
payload = {'action': 'screenshot', 'args': {'format': 'jpeg', 'quality': 85}, 'session': 'joinquant-demo'}
# 返回 {path: "C:\\Users\\..."} — WSL 下映射为 /mnt/c/Users/...
```

---

## 注意事项

- 每次访问聚宽 iframe，都从 `document.getElementById('research').contentDocument` 开始
- 写代码必须用 `cm.setValue()`（经典 Jupyter 的 CodeMirror API），不是 `fill` 工具
- 执行前必须 `.click()` 选中单元格
- `data-jupyter-action` 属性比 CSS class 更可靠作为选择器
- 如果弹出新标签页（popup），WebBridge 无法控制——改用 API 创建 notebook + iframe 导航
- `String.fromCharCode(10)` 是避免各平台 shell 转义问题的关键技巧
- 截图路径在 Windows 下是 `C:\Users\...`，WSL 下映射为 `/mnt/c/Users/...`

## 与本地 JupyterLab 的区别

| | 聚宽（经典 Jupyter） | 本地 JupyterLab |
|--|---------------------|----------------|
| 访问方式 | iframe `#research` | 直接页面 |
| 写代码 | `cm.setValue()` | `cm.innerText` + InputEvent |
| 执行 | 点"运行"按钮（标准 `<button>`） | CDP Shift+Enter（jp-button 不吃合成事件） |
| 读输出 | `.output_text` | `.jp-OutputArea-output` |
| 难度 | ★☆☆ 简单 | ★★★ 有坑 |

---

## 附录：关于 bash 内联 JSON（不推荐）

> 以下方案**仅适用于** macOS/Linux 原生终端 + 极简单的单行代码。遇到 f-string、花括号、多层嵌套引号时立即切换到上面的 Python 方案。

### 为什么容易炸

```bash
# 这种写法对以下情况都会炸：
# 1. Python f-string 里的花括号 { } → bash 视为 $变量
# 2. 代码里有 $(...)     → bash 执行子命令
# 3. 单引号不足以包裹     → 因为 JSON 键本身必须用双引号
# 4. 多行代码          → 每层嵌套反斜杠数量指数增长
```

### WSL 额外注意

WSL 下不要用 `curl.exe`（不存在），用原生 `curl`：
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  -d '{ "action": "snapshot", "args": {}, "session": "demo" }'
```
短 JSON 可以直接 `-d '...'`（单引号包裹），但一旦代码里出现单引号就断裂。
