"""
jq_helper.py — WebBridge 核心通信库

跨平台（Windows/macOS/Linux），零个人隐私信息。
自动检测操作系统选择 curl 命令和临时文件路径。
"""
import json, subprocess, sys, os, tempfile

SESSION = "joinquant"
CURL = "curl.exe" if sys.platform == "win32" else "curl"


def _temp_path():
    """返回跨平台的临时 JSON 文件路径"""
    return os.path.join(tempfile.gettempdir(), "jq_webbridge_payload.json")


def wb(code, session=SESSION):
    """向 WebBridge 发送 evaluate 请求并返回响应 JSON"""
    payload = {
        "action": "evaluate",
        "args": {"code": code},
        "session": session,
    }
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


def wb_nav(url, session=SESSION):
    """导航到指定 URL"""
    payload = {
        "action": "navigate",
        "args": {"url": url},
        "session": session,
    }
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


def js(code):
    """用 IIFE 包裹 JS 代码，避免跨调用声明冲突"""
    indent = "  " if "\n" in code else ""
    return f"(function(){{\n{indent}{code}\n}})()"


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "js":
        print(wb(js(sys.argv[2])))
    elif len(sys.argv) > 2 and sys.argv[1] == "raw":
        print(wb(sys.argv[2]))
    else:
        print("Usage: python jq_helper.py <js|raw> <code>")
