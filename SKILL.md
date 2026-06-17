---
name: joinquant
description: |
  在聚宽(JoinQuant)量化平台的 Jupyter 研究环境中读写代码并执行。
  当用户提到"聚宽"、"JoinQuant"、"量化平台"、"策略研究"等关键词时使用。
  依赖 Kimi WebBridge 技能操控浏览器。
metadata:
  version: "3.1.0"
---

# 聚宽 JoinQuant 量化研究平台

通过 WebBridge 操控聚宽量化投研平台的 Jupyter 研究环境。

## 前置条件

- **Kimi WebBridge 浏览器扩展必须在浏览器中已安装并启用**。访问 `edge://extensions/`（Edge）或 `chrome://extensions/`（Chrome）确认。扩展装好但未启用一样连不上。
- **浏览器必须打开至少一个网页标签页**，WebBridge 扩展才会连接 daemon。光是浏览器进程开着但没有标签页是不够的。
- 用户已在浏览器登录聚宽（https://www.joinquant.com）—— **未登录会停在登录页，iframe 永远加载不出研究环境**
- Kimi WebBridge daemon 正在运行

### 启动序列（重要）

浏览器刚打开时，扩展需要几秒才能连上 daemon。立即请求会返回 `session has no tab` 或 `no extension connected`。
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
# Windows GBK 终端必须加 encoding/errors，否则中文 print 会炸
_ENV = dict(encoding="utf-8", errors="replace")

def wb_eval(code):
    payload = {"action": "evaluate", "args": {"code": code}, "session": "joinquant"}
    tmp = os.path.join(tempfile.gettempdir(), "jq_payload.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run(
        [CURL, "-s", "-X", "POST", "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json", "--data-binary", "@" + tmp],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        **_ENV)
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
    print("排查步骤：1) 浏览器标签页是否打开？ 2) 扩展是否已启用？ 3) daemon 是否在运行？")
```

#### 重启注意事项

杀掉旧 daemon 后残留的 `daemon.pid` 文件会阻止重启：
```bash
# 停止 daemon
taskkill //F //IM kimi-webbridge.exe
# 删除残留 PID 文件（关键！不然重启会报 "The file exists"）
rm "%USERPROFILE%\.kimi-webbridge\daemon.pid"
# 重新启动
"%USERPROFILE%\.kimi-webbridge\bin\kimi-webbridge.exe" run &
```

### 常见错误对照

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `no extension connected` | 浏览器扩展未连接 daemon（扩展未装/未启用/daemon 刚启动） | 先轮询等待 15 次，不行就检查浏览器扩展是否启用；某些时候 navigate 一次后会变成 `session has no tab`，说明扩展其实连上了只是 session 未建立 |
| `session "joinquant" tab was closed — navigate first` | 扩展连上了但当前 session 的标签页已失效（浏览器关闭后重开） | 先 `navigate` 重建 session |
| `session "joinquant" has no tab — navigate or find_tab first` | session 未建立或已过期 | navigate 创建新 session |
| `Cannot read properties of null (reading 'contentDocument')` | navigate 成功但 iframe 还没渲染出来 | 轮询 `document.getElementById('research')` |
| iframe URL 停在 `/user/login/...` | 用户未登录 | 提示用户先登录，登录前不要继续操作 |
| `Error: write pid: open daemon.pid: The file exists` | daemon 异常退出后 pid 文件残留 | 删除 `%USERPROFILE%\.kimi-webbridge\daemon.pid` 后重启 |
| `UnicodeEncodeError: 'gbk' codec can't encode` | Windows 终端 GBK 编码无法输出中文 | `subprocess.run` 加 `encoding='utf-8', errors='replace'` |

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

**多行代码用数组+join（仅限 1~3 行简单代码）：**

```javascript
var nl = String.fromCharCode(10);
var code = ['line 1', 'line 2', 'line 3'].join(nl);
cm.setValue(code);
```

> `String.fromCharCode(10)` 代替 `\n` 是为了避免各平台 shell 的转义差异问题。

> ⚠️ **超过 3 行代码不要用这种拼接方式**。多层 Python→JSON→JS 引号嵌套极易产生 `SyntaxError: Unexpected identifier` 或 `Invalid or unexpected token`。几十行以上的策略代码**必须用下面的 `write_cell.py` 方案**（模板字面量读取本地文件）。

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
# Windows GBK 终端必须加 encoding/errors，否则中文输出会 UnicodeEncodeError
_RUN = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            encoding="utf-8", errors="replace")
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

> **兼容性**：不使用 `capture_output`（Python 3.7+ 才有），改用 `stdout=PIPE, stderr=PIPE` 兼容 3.6。`ensure_ascii=False` 确保中文注释不被转成 `\uXXXX`。**Windows 必加 `encoding="utf-8", errors="replace"`**，否则 `print()` 输出中文时 GBK 会炸。

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

### 完整流程示例（完整策略）

```python
import json, subprocess, time, os, tempfile

CURL = "curl.exe" if os.name == "nt" else "curl"

# Python 3.6+ 兼容写法 + Windows GBK 终端保护
_RUN = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "timeout": 30,
        "encoding": "utf-8", "errors": "replace"}
try: _RUN["text"] = True
except TypeError: _RUN["universal_newlines"] = True

def wb(code, session="joinquant"):
    payload = {"action": "evaluate", "args": {"code": code}, "session": session}
    tmp = os.path.join(tempfile.gettempdir(), "jq.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run([CURL, "-s", "-X", "POST",
        "http://127.0.0.1:10086/command",
        "-H", "Content-Type: application/json",
        "--data-binary", "@" + tmp], **_RUN)
    return json.loads(r.stdout.strip())

def js(code):
    """IIFE 包裹 JS 代码"""
    if "\n" in code:
        return "(function(){\n  " + code.replace("\n", "\n  ") + "\n})()"
    return "(function(){" + code + "})()"

D = 'var d=document.getElementById("research").contentDocument;'

# 1. 用 write_cell.py 写策略代码（推荐）
# subprocess.run([sys.executable, "write_cell.py", "ma_strategy.py"])

# 2. 执行当前选中单元格（按 title="运行"）
run = D + (''
    'var cells=d.querySelectorAll(\".cell\");'
    'cells[0].querySelector(\".input_area\").click();'
    'var btns=d.querySelectorAll(\"button\");'
    'for(var i=0;i<btns.length;i++){'
    'if(btns[i].getAttribute(\"title\")===\"\\u8fd0\\u884c\"){btns[i].click();break;}'
    '}'
)
wb(js(run))

# 3. 轮询等待执行完成
for _ in range(15):
    state = wb(js(D + "return d.querySelectorAll('.cell')[0].querySelector('.input_prompt').textContent;"))
    val = state.get("data", {}).get("value", "")
    if "In [*]" not in str(val) and "In [ ]" not in str(val):
        print("done:", val)
        break
    time.sleep(2)

# 4. 读取输出
output = wb(js(D + ''
    'var cells=d.querySelectorAll(\".cell\");'
    'var out=[];'
    'for(var i=0;i<cells.length;i++){'
    'var t=cells[i].querySelector(\".output_text\");'
    'out.push(\"Cell \"+i+\": \"+(t?t.textContent.trim():\"(empty)\"));'
    '}'
    'return out.join(String.fromCharCode(10));'
))
print(output.get("data", {}).get("value", ""))
```

> **关于引号**：JS 字符串里用 `\"` 转义双引号，因为外面 Python 字符串也是双引号。中文 `\u8fd0\u884c` = "运行"。

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

- **浏览器扩展必须安装并启用**。Kimi WebBridge 浏览器扩展是操控浏览器的前提，只开 daemon 不够。访问 `edge://extensions/` 或 `chrome://extensions/` 确认。
- **浏览器必须打开一个网页**，光浏览器进程开启但没标签页，扩展不连接。
- **每次操作前检查连接**：用轮询而非单次 curl，扩展启动有数秒延迟。遇到 `session tab closed` 或 `session has no tab` 错误先 navigate。
- **区分两个错误**：`no extension connected` = 扩展根本没连上 daemon；`session has no tab` = 扩展连上了但 session 未建立。后者 navigate 即可修复，前者要检查扩展状态。
- **Windows GBK 终端问题**：所有 `subprocess.run` 必须加 `encoding="utf-8", errors="replace"`，否则 `print()` 中文/emoji 会 `UnicodeEncodeError`。如果怀疑输出编码问题，用写文件代替 print：
  ```python
  with open("output.txt", "w", encoding="utf-8") as f:
      f.write(val)
  ```
- **daemon.pid 残留**：kill daemon 后必须删除 `%USERPROFILE%\.kimi-webbridge\daemon.pid`，否则重启报 `The file exists`。
- **关闭浏览器不会关闭运行中的 Notebook 内核**——它们持续占用聚宽的内存和 CPU。每次进入研究平台先通过 API 清理旧内核（见第 7 节）。
- 每次访问聚宽 iframe，都从 `document.getElementById('research').contentDocument` 开始。
- 写代码必须用 `cm.setValue()`（经典 Jupyter 的 CodeMirror API），不是 `fill` 工具。
- 执行前必须 `.click()` 选中单元格；优先点 `.input_area` 而不是 `.cell` 更可靠。
- `data-jupyter-action` 是标准选择器，但在 JSON 嵌套字符串中属性值引号容易丢失。**在 Python 调用的场景下，用 `button.title === '运行'` 更可靠。**
- 如果弹出新标签页（popup），WebBridge 无法控制——改用 API 创建 notebook + iframe 导航。
- `String.fromCharCode(10)` + 数组拼接仅适合 1~3 行代码。**超过 3 行必须用 `write_cell.py`（JS 模板字面量读取本地文件），否则引号嵌套必然翻车。**
- 截图路径在 Windows 下是 `C:\Users\...`，WSL 下映射为 `/mnt/c/Users/...`。
- **聚宽环境网络受限**：研究环境的容器可能无法访问外网 API（如 Binance、CoinGecko）。如果要获取外部数据，最好在**本地**先下载好，再写入到 notebook 中。
- **curl 依赖**：`jq_helper.py` 和 `write_cell.py` 依赖系统自带 curl。Windows 10+ 自带了 `curl.exe`，但某些精简版或旧系统可能没有，可用 `where curl`（Windows）或 `which curl`（macOS/Linux）检查。

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
