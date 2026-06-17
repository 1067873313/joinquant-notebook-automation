"""
write_cell.py -- 将本地 Python 文件写入 Jupyter 单元格

解决大批量代码无法用内联数组写入的问题。
思路：读文件 -> JS 模板字面量包裹 -> cm.setValue()

兼容 Python 3.6+，跨平台，零隐私信息。

使用前提：Notebook 中必须有一个单元格处于选中状态。
"""
import json
import os
import subprocess
import sys
import tempfile

SESSION = "joinquant"

# ---- 平台自适应 ----
if sys.platform == "win32":
    CURL = "curl.exe"
else:
    CURL = "curl"

_RUN_KWARGS = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "timeout": 30}
try:
    _RUN_KWARGS["text"] = True
except TypeError:
    _RUN_KWARGS["universal_newlines"] = True


def _temp_path():
    return os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")


def wb(code, session=SESSION):
    """发送 evaluate 请求，返回 Python dict"""
    payload = {"action": "evaluate", "args": {"code": code}, "session": session}
    tmp = _temp_path()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run(
        [CURL, "-s", "-X", "POST",
         "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json",
         "--data-binary", "@" + tmp],
        **_RUN_KWARGS,
    )
    return json.loads(r.stdout.strip())


def escape_for_template(text):
    """
    将文本转义为 JS 模板字面量安全内容。

    必须处理的三类字符：
      - 反斜杠          -> 加倍  （模板字面量中 \\ 是转义反斜杠）
      - 反引号 (backtick) -> 转义  （否则会关闭模板字面量）
      - ${               -> 转义$ （否则被当成插值语法）
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    return text


def ensure_cell_selected():
    """确保有一个单元格被选中，没有则点击第一个"""
    result = wb(
        "(function(){"
        "var d=document.getElementById('research').contentDocument;"
        "if(!d)return 'NO_IFRAME';"
        "var sel=d.querySelector('.cell.selected');"
        "if(sel)return 'SELECTED';"
        "var first=d.querySelectorAll('.cell')[0];"
        "if(first){first.querySelector('.input_area').click();return 'AUTO_SELECTED';}"
        "return 'NO_CELLS';"
        "})()"
    )
    value = result.get("data", {}).get("value", "")
    if "NO_IFRAME" in str(value):
        sys.exit("ERROR: 无法访问聚宽 iframe，请确认已在研究平台页面。")
    if "NO_CELLS" in str(value):
        sys.exit("ERROR: Notebook 中没有单元格，请先插入一个。")
    return value


def main():
    if len(sys.argv) < 2:
        print("Usage: python write_cell.py <path/to/code.py>")
        sys.exit(1)

    py_file = sys.argv[1]
    if not os.path.isfile(py_file):
        sys.exit(f"ERROR: 文件不存在: {py_file}")

    with open(py_file, "r", encoding="utf-8") as f:
        py_code = f.read()

    if not py_code.strip():
        sys.exit("ERROR: 文件为空。")

    # 确保有单元格选中
    sel_state = ensure_cell_selected()
    print(f"Cell: {sel_state}")

    # 写入代码
    escaped = escape_for_template(py_code)
    js_code = (
        "(function(){"
        "var d=document.getElementById('research').contentDocument;"
        "var cm=d.querySelector('.cell.selected .CodeMirror').CodeMirror;"
        "cm.setValue(`" + escaped + "`);"
        "return 'ok';"
        "})()"
    )

    result = wb(js_code)
    ok = result.get("ok")
    if ok:
        print("Write: OK  (" + str(len(py_code)) + " chars)")
    else:
        print("Write: FAILED -", result.get("error", {}).get("message", str(result)))


if __name__ == "__main__":
    main()
