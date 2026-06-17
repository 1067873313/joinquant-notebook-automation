"""
write_cell.py — 将本地 Python 文件写入 Jupyter 单元格

解决大批量代码（几十到几百行）无法用内联数组写入的问题。
思路：读文件 → JS 模板字面量包裹 → cm.setValue()

跨平台，零个人隐私信息。
"""
import json, subprocess, sys, os, tempfile

SESSION = "joinquant"
CURL = "curl.exe" if sys.platform == "win32" else "curl"


def _temp_path():
    return os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")


def wb(code, session=SESSION):
    payload = {"action": "evaluate", "args": {"code": code}, "session": session}
    tmp = _temp_path()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    r = subprocess.run(
        [CURL, "-s", "-X", "POST",
         "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json",
         "--data-binary", "@" + tmp],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout.strip()


def escape_for_template(text):
    """
    将文本转义到 JS 模板字面量（反引号字符串）中。

    必须转义的三类字符：
    - 反斜杠 `\\`  → `\\\\` （模板字面量中 `\\` 是转义反斜杠）
    - 反引号 `` ` `` → `` \` ``（否则会关闭模板字面量）
    - `${`          → `\\${` （否则会被解释为插值语法）
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: python write_cell.py <path/to/code.py>")
        sys.exit(1)

    py_file = sys.argv[1]
    with open(py_file, "r", encoding="utf-8") as f:
        py_code = f.read()

    escaped = escape_for_template(py_code)

    js_code = f"""(function() {{
  var d = document.getElementById('research').contentDocument;
  var cm = d.querySelector('.cell.selected .CodeMirror').CodeMirror;
  cm.setValue(`{escaped}`);
  return 'ok';
}})()"""

    result = wb(js_code)
    print(result)


if __name__ == "__main__":
    main()
