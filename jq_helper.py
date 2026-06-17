"""
jq_helper.py -- WebBridge 通信库

跨平台（Windows / macOS / Linux），兼容 Python 3.6+。
自动检测操作系统选择 curl 命令和临时文件路径。
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

# Python 3.6 没有 capture_output，统一用手动 PIPE
_RUN_KWARGS = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "timeout": 30}
try:
    # Python 3.7+ 可以加 text=True
    _RUN_KWARGS["text"] = True
except TypeError:
    # Python 3.6 用 universal_newlines
    _RUN_KWARGS["universal_newlines"] = True


def _temp_path():
    """返回跨平台临时 JSON 文件路径"""
    return os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")


def _send(payload, session=SESSION):
    """发送 JSON payload 到 WebBridge，返回解析后的 dict"""
    payload["session"] = session
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


def wb(code, session=SESSION):
    """evaluate JS 代码，返回 Python dict"""
    return _send({
        "action": "evaluate",
        "args": {"code": code},
    }, session)


def wb_nav(url, session=SESSION):
    """导航到指定 URL"""
    return _send({
        "action": "navigate",
        "args": {"url": url},
    }, session)


def js(code):
    """用 IIFE 包裹 JS 代码，避免跨调用声明冲突"""
    if "\n" in code:
        return "(function(){\n  " + code.replace("\n", "\n  ") + "\n})()"
    return "(function(){" + code + "})()"


# ---- CLI 用法 ----
if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("js", "raw"):
        mode, code = sys.argv[1], sys.argv[2]
        if mode == "js":
            code = js(code)
        print(wb(code))
    else:
        print("Usage: python jq_helper.py <js|raw> <code>")
