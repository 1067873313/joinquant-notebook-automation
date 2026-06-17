---
name: joinquant
description: |
  在聚宽(JoinQuant)量化平台的 Jupyter 研究环境中读写代码并执行。
  当用户提到"聚宽"、"JoinQuant"、"量化平台"、"策略研究"等关键词时使用。
  依赖 Kimi WebBridge 技能操控浏览器。
metadata:
  version: "3.0.0"
---

# 聚宽 JoinQuant 量化研究平台

通过 WebBridge 操控聚宽量化投研平台的 Jupyter 研究环境。

## 前置条件

- **浏览器必须打开至少一个网页标签页**，WebBridge 扩展才会连接。光是浏览器开着但没页面是不够的。
- 用户已在浏览器登录聚宽（https://www.joinquant.com）—— **未登录会停在登录页，iframe 永远加载不出研究环境**
- Kimi WebBridge daemon 正在运行

### 启动序列（重要）

浏览器刚打开时，扩展需要几秒才能连上 daemon。立即请求会返回 `no extension connected`。
可以用 `start https://...`（Windows）或 `open`（macOS）自动打开浏览器到聚宽：

```bash
# Windows
start https://www.joinquant.com
# macOS
open https://www.joinquant.com
# Linux
xdg-open https://www.joinquant.com
```

然后**轮询等待连接**（不要单次检查就放弃）：

```python
import time, subprocess, json, os, tempfile

CURL = "curl.exe" if os.name == "nt" else "curl"

def wb_eval(code):
    payload = {"action": "evaluate", "args": {"code": code}, "session": "joinquant"}
    tmp = os.path.join(tempfile.gettempdir(), "jq_payload.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run(
        [CURL, "-s", "-X", "POST", "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json", "--data-binary", "@" + tmp],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return json.loads(r.stdout.strip())

# 轮询：扩展启动需要时间
for attempt in range(15):
    res = wb_eval("document.title")
    if res.get("ok"):
        print("connected:", res["data"]["value"])
        break
    time.sleep(2)
else:
    print("扩展未连接，请用户检查浏览器")
```

### 常见错误对照

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `no extension connected` | 浏览器没开 / 扩展刚启动还没连上 | 轮询等待，或让用户打开浏览器 |
| `session "joinquant" tab was closed — navigate first` | 浏览器被关闭后重开，旧 session 的标签页已失效 | 先 `navigate` 重建 session |
| `Cannot read properties of null (reading 'contentDocument')` | navigate 成功但 iframe 还没渲染出来 | 轮询 `document.getElementById('research')` |
| iframe URL 停在 `/user/login/...` | 用户未登录 | 提示用户先登录，登录前不要继续操作 |

## 工作流程

### 1. 打开研究平台

```json
{"action":"navigate","args":{"url":"https://www.joinquant.com/research"},"session":"joinquant"}
```

如果跳转到登录页，告诉用户需要登录。聚宽页面使用**同源 iframe** (`id="research"`) 加载 Jupyter 环境，所有操作需通过 iframe 访问：

```javascript
var d = document.getElementById('research').contentDocument;
```

> ⚠️ **iframe 是异步加载的**：`navigate` 返回 `success:true` 不代表 iframe 已经渲染完成。立即访问 `contentDocument` 会得到 `null`。必须轮询等待：

```python
# navigate 之后轮询 iframe 加载
for attempt in range(15):
    js = ("(function(){"
          "var f=document.getElementById('research');"
          "if(!f)return 'NO_ELEMENT';"
          "var d=f.contentDocument;"
          "if(!d)return 'NO_DOC';"
          "return 'OK:'+d.location.href;"
          "})()")
    res = wb_eval(js)
    val = res.get("data", {}).get("value", "")
    if "OK:" in str(val):
        print("iframe ready:", val)
        break
    time.sleep(2)
```

> 如果 iframe URL 停在 `/user/login/...`，说明用户没登录，**停止操作并提示用户登录**。

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
// 先点击单元格的 input_area 选中它
d.querySelector('.cell .input_area').click();
// 再点"运行"按钮（用 title 属性匹配，比 data-jupyter-action 更可靠）
var btns = d.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
  if (btns[i].getAttribute('title') === '运行') {
    btns[i].click();
    break;
  }
}
```

> ⚠️ 注意：在嵌套 JSON 的 JS 字符串中，`data-jupyter-action` 属性值里的引号容易丢失，导致选择器失效。**优先用按钮的 `title` 属性匹配**。

聚宽 Jupyter 工具栏按钮映射（按 HTML 中的出现顺序）：

| 索引 | title | 操作 |
|------|-------|------|
| 0 | —（汉堡菜单） | 菜单 |
| 1 | 保存并创建检查点 | 保存 |
| 2 | 在下方插入单元格 | 插入 |
| 3 | 剪切选择的单元格 | 剪切 |
| 4 | 复制选择的单元格 | 复制 |
| 5 | 粘贴到下方 | 粘贴 |
| 6 | 上移选中单元格 | 上移 |
| 7 | 下移选中单元格 | 下移 |
| 8 | **运行** | **运行单元格** |
| 9 | 中断内核 | 中断 |
| 10 | 重启内核(显示确认对话框) | 重启 |
| 11 | 重启内核,然后重新运行整个代码(显示确认对话框) | 重启并全跑 |

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

检查单元格执行状态：`d.querySelector('.cell .input_prompt').textContent`

| 状态 | 含义 |
|------|------|
| `In [ ]:` | 未执行 |
| `In [*]:` | 正在执行中 |
| `In [N]:` | 已执行完成（N为执行序号） |

### 6. 插入/删除单元格

**插入新单元格**（自动选中新单元格）：

```javascript
var ins = d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]');
ins.click();
```

**删除当前选中单元格**：

```javascript
var cut = d.querySelector('[data-jupyter-action="jupyter-notebook:cut-cell"]');
cut.click();
```

### 7. 内核管理

**中断内核**（当单元格卡住 `In [*]` 时）：

```javascript
var btns = d.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
  if (btns[i].getAttribute('title') === '中断内核') {
    btns[i].click();
    break;
  }
}
```

**重启内核**：

```javascript
var btns = d.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
  if (btns[i].getAttribute('title') === '重启内核(显示确认对话框)') {
    btns[i].click();
    break;
  }
}
```

---

## 推荐工作流（跨平台通用）

**永远优先使用这个方案。** 它用 Python 构建 JSON 请求体并通过临时文件发送，零 shell 转义问题，在 Windows / macOS / Linux / WSL 上行为完全一致。

### 核心模式

```python
import json, os, subprocess, sys, tempfile

CURL = "curl.exe" if sys.platform == "win32" else "curl"

# 兼容 Python 3.6：不用 capture_output, text 参数
_RUN = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
try:
    _RUN["text"] = True           # Python 3.7+
except TypeError:
    _RUN["universal_newlines"] = True  # Python 3.6

def wb(code):
    """向 WebBridge 发送 evaluate 请求，返回 Python dict"""
    payload = {
        "action": "evaluate",
        "args": {"code": code},
        "session": "joinquant",
    }
    tmp = os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)  # False = 中文不转义
    r = subprocess.run(
        [CURL, "-s", "-X", "POST",
         "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json",
         "--data-binary", "@" + tmp],
        **_RUN,
    )
    return json.loads(r.stdout.strip())
```

> **兼容性**：不使用 `capture_output`（Python 3.7+ 才有），改用 `stdout=PIPE, stderr=PIPE` 兼容 3.6。`ensure_ascii=False` 确保中文注释不被转成 `\uXXXX`。

### 长 JS 代码用函数包装

超过一行的 JS 代码包裹 IIFE，避免跨调用声明冲突：

```python
js = '''(function(){
  var d = document.getElementById("research").contentDocument;
  // ...任何代码...
  return result;
})()'''
```

---

## 🔥 大批量代码写入（几十到几百行）

文档之前的版本只给了一行一行 `['code1', 'code2'].join(nl)` 的方式，这对几行代码还行，但几十上百行的策略代码要写成数组就太痛苦了。

**正确做法：把 Python 代码写在本地文件里，通过辅助脚本写入 Jupyter 单元格。**

### 辅助脚本：write_cell.py

```python
"""将本地 Python 文件写入 Jupyter 单元格"""
import json, os, subprocess, sys, tempfile

CURL = "curl.exe" if sys.platform == "win32" else "curl"
_RUN = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
try:
    _RUN["text"] = True
except TypeError:
    _RUN["universal_newlines"] = True

def wb(code, session="joinquant"):
    payload = {"action": "evaluate", "args": {"code": code}, "session": session}
    tmp = os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run(
        [CURL, "-s", "-X", "POST",
         "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json",
         "--data-binary", "@" + tmp],
        **_RUN,
    )
    return json.loads(r.stdout.strip())

def escape_for_template(text):
    """转义 JS 模板字面量中的特殊字符"""
    text = text.replace("\\", "\\\\")
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    return text

# 确保有单元格被选中
wb("(function(){"
   "var d=document.getElementById('research').contentDocument;"
   "var sel=d.querySelector('.cell.selected');"
   "if(sel)return'ok';"
   "d.querySelectorAll('.cell')[0].click();"
   "return'auto';"
   "})()")

with open(sys.argv[1], "r", encoding="utf-8") as f:
    py_code = f.read()

escaped = escape_for_template(py_code)
js_code = ("(function(){"
           "var d=document.getElementById('research').contentDocument;"
           "var cm=d.querySelector('.cell.selected .CodeMirror').CodeMirror;"
           "cm.setValue(`" + escaped + "`);"
           "return'ok';"
           "})()")
print(wb(js_code))
```

**使用方式：**

```bash
# 1. 先把 Python 代码写到本地文件（如 strategy.py）
# 2. 在 Notebook 中插入一个新单元格并确保它被选中
# 3. 运行脚本写入
python write_cell.py strategy.py
```

### 完整流程示例（4 个单元格的大策略）

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

def wb_js(code):
    """发送 JS IIFE 到 WebBridge"""
    return wb(f'''(function(){{{code}}})()''')

# d = iframe document 的快捷引用
D = 'var d=document.getElementById("research").contentDocument;'

# ==== 写 Cell 0 ====
# 用 write_cell.py 方式：把 strategy.py 内容写入单元格
# 先选中一个空单元格，然后：
# subprocess.run(['python', 'write_cell.py', 'strategy.py'])

# ==== 写完后依次执行 ====
# 获取所有单元格，按索引选中并点击运行
for i in range(4):
    js = D + f'''
        var cells = d.querySelectorAll('.cell');
        cells[{i}].querySelector('.input_area').click();
        var btns = d.querySelectorAll('button');
        for (var j = 0; j < btns.length; j++) {{
            if (btns[j].getAttribute('title') === '运行') {{
                btns[j].click();
                break;
            }}
        }}
    '''
    wb_js(js)
    time.sleep(5)  # 等待执行

# ==== 读取输出 ====
js = D + '''
    var cells = d.querySelectorAll('.cell');
    var out = [];
    for (var i = 0; i < cells.length; i++) {
        var t = cells[i].querySelector('.output_text');
        out.push('Cell ' + i + ': ' + (t ? t.textContent.trim() : '(no output)'));
    }
    return out.join(String.fromCharCode(10));
'''
print(wb_js(js))
```

> **关于 f-string 双层花括号**：`{D}` 是 Python f-string 变量替换，而 `{{` / `}}` 输出字面花括号给 JS 用。

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
| 运行选中单元格 | `var b=d.querySelectorAll('button');for(var i=0;i<b.length;i++){if(b[i].title==='运行'){b[i].click();break;}}` |
| 插入下方单元格 | `d.querySelector('[data-jupyter-action="jupyter-notebook:insert-cell-below"]').click()` |
| 删除选中单元格 | `d.querySelector('[data-jupyter-action="jupyter-notebook:cut-cell"]').click()` |
| 中断内核 | `var b=d.querySelectorAll('button');for(var i=0;i<b.length;i++){if(b[i].title==='中断内核'){b[i].click();break;}}` |
| 读取文本输出 | `d.querySelector('.output_text')?.textContent` |
| 检查执行状态 | `d.querySelector('.input_prompt').textContent`（`In [ ]`=未执行，`In [*]`=执行中，`In [N]`=已完成） |
| 检查是否有图表 | `d.querySelector('.output_png') !== null` |
| 截图 | `{"action":"screenshot","args":{}}` — 得到图片路径后用 Read 工具查看 |

### 截图

```python
payload = {'action': 'screenshot', 'args': {'format': 'jpeg', 'quality': 85}, 'session': 'joinquant-demo'}
# 返回 {path: "C:\\Users\\..."} — WSL 下映射为 /mnt/c/Users/...
```

---

## 注意事项

- **浏览器必须打开一个网页**，光浏览器开启但没页面，扩展不连接。
- 每次访问聚宽 iframe，都从 `document.getElementById('research').contentDocument` 开始。
- 写代码必须用 `cm.setValue()`（经典 Jupyter 的 CodeMirror API），不是 `fill` 工具。
- 执行前必须 `.click()` 选中单元格；优先点 `.input_area` 而不是 `.cell` 更可靠。
- `data-jupyter-action` 是标准选择器，但在 JSON 嵌套字符串中属性值引号容易丢失。**在 Python 调用的场景下，用 `button.title === '运行'` 更可靠。**
- 如果弹出新标签页（popup），WebBridge 无法控制——改用 API 创建 notebook + iframe 导航。
- `String.fromCharCode(10)` 是避免各平台 shell 转义问题的关键技巧。
- 截图路径在 Windows 下是 `C:\Users\...`，WSL 下映射为 `/mnt/c/Users/...`。
- **聚宽环境网络受限**：研究环境的容器可能无法访问外网 API（如 Binance、CoinGecko）。如果要获取外部数据，最好在**本地**先下载好，再写入到 notebook 中。
- **大规模代码**（几十行以上）不要用 `['line1', 'line2'].join(nl)` 的方式，改用 `write_cell.py` 辅助脚本从本地文件读取。

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

### 转义参考表（如果非要用 bash 内联的话）

| 你要写的内容 | 在 bash `-d "..."` 中写 | 原因 |
|-------------|------------------------|------|
| JSON 键/值的 `"` | `\"` | bash 双引号内 `\"` → `"` |
| Python 字符串的 `"` | `\\\"` | bash → `\"` → JSON → `"` |
| JavaScript 的 `'` | `'` | 直接写，bash 双引号不处理单引号 |
| 代码中的换行 `\n` | `String.fromCharCode(10)` | 避免 4 层反斜杠转义 |

### bash 内联完整示例（写+执行一步到位）

```bash
curl.exe -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"evaluate\",\"args\":{\"code\":\"(function(){
    var w=document.getElementById('research').contentWindow;
    var d=w.document;
    var cm=d.querySelector('.CodeMirror').CodeMirror;
    var nl=String.fromCharCode(10);
    cm.setValue(['# demo','print(\\\"hello\\\")'].join(nl));
    d.querySelector('.cell').click();
    var b=d.querySelectorAll('button');
    for(var i=0;i<b.length;i++){if(b[i].title==='\u8fd0\u884c'){b[i].click();break;}}
    return 'ok';
  })()\"},\"session\":\"joinquant\"}"
```

> **Windows 用户注意**：上面用的是 `curl.exe`。WSL 用户改为 `curl`（不带 `.exe`）。

### WSL 额外注意

WSL 下不要用 `curl.exe`（不存在），用原生 `curl`：
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  -d '{ "action": "snapshot", "args": {}, "session": "demo" }'
```
短 JSON 可以直接 `-d '...'`（单引号包裹），但一旦代码里出现单引号就断裂。
