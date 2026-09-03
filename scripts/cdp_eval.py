"""Minimal CDP eval — run JS in the running Electron renderer and print result.
Usage: python cdp_eval.py "<js expression>"
Finds the Multiverse page on CDP :9223 automatically.
"""
import json
import sys
import urllib.request

try:
    from websocket import create_connection  # websocket-client
except ImportError:
    print("NEED: pip install websocket-client", file=sys.stderr)
    sys.exit(2)


def find_ws():
    data = json.loads(urllib.request.urlopen("http://127.0.0.1:9223/json", timeout=4).read())
    for p in data:
        if "Multiverse" in p.get("title", "") and p.get("webSocketDebuggerUrl"):
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("Multiverse page not found on :9223")


def main():
    expr = sys.argv[1] if len(sys.argv) > 1 else "1+1"
    ws = create_connection(find_ws(), timeout=8,
                           suppress_origin=True)
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
    }))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            res = msg.get("result", {})
            if "exceptionDetails" in res:
                print("JS-ERROR:", json.dumps(res["exceptionDetails"], indent=2))
            else:
                val = res.get("result", {}).get("value")
                print(json.dumps(val, indent=2, ensure_ascii=False) if not isinstance(val, str) else val)
            break
    ws.close()


if __name__ == "__main__":
    main()
