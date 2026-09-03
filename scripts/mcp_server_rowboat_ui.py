"""
rowboat-ui — stdio MCP server: chat with the Rowboat space INSIDE the VibeMind
Multiverse Electron app via Chrome DevTools Protocol (CDP), no sign-in needed.

WHY CDP (not OS mouse/keyboard): the Rowboat chat is an embedded BrowserView in
the "VibeMind - Multiverse" Electron window (launched with --remote-debugging-port
9223). CDP lets us set the <textarea> value React-compatibly and submit precisely,
without risking typing into the wrong OS window and without the "Sign in to
Rowboat" banner blocking anything (the chat field works unauthenticated —
verified 2026-06-08). Mirrors the vibemind-notify CDP:9223 pattern.

Tool:
  rowboat_chat_send(message, timeout_s=60, settle_s=2.5)
    -> activates the Chat tab, types `message`, submits, waits until the chat
       region text stops changing (streaming done) or timeout, returns the new
       assistant reply text.

Target page is matched by URL substring '/spaces/rowboat/' (robust against the
Rowboat/Roarboot title ambiguity).

Env: ROWBOAT_UI_CDP_PORT (default 9223).

Usage:  python mcp_server_rowboat_ui.py
"""

import asyncio
import json
import os
import sys
import time
import urllib.request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

try:
    import websocket  # websocket-client
except ImportError:
    print("websocket-client not installed (pip install websocket-client)", file=sys.stderr)
    sys.exit(1)

SERVER_NAME = "rowboat-ui"
CDP_PORT = int(os.environ.get("ROWBOAT_UI_CDP_PORT", "9223"))
CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"
TARGET_URL_MARKER = "/spaces/rowboat/"


# ── minimal CDP client (one Runtime.evaluate at a time) ──────────────────────

class _CDP:
    def __init__(self, ws_url: str, timeout: float = 20.0):
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self._id = 0

    def evaluate(self, expression: str):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({
            "id": mid, "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
        }))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    raise RuntimeError(str(res["exceptionDetails"])[:300])
                return res.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def _find_rowboat_ws() -> str:
    data = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/list", timeout=5).read())
    # URL-match is robust against the Rowboat/Roarboot title ambiguity.
    for t in data:
        if t.get("type") == "page" and TARGET_URL_MARKER in (t.get("url") or ""):
            return t["webSocketDebuggerUrl"]
    raise RuntimeError(
        f"Rowboat page not found via CDP :{CDP_PORT} (marker '{TARGET_URL_MARKER}'). "
        f"Is the VibeMind Multiverse app open on the Rowboat space?"
    )


# JS: activate Chat tab + return whether the textarea is usable.
_JS_PREPARE = r"""
(() => {
  const btns=[...document.querySelectorAll('button,[role="tab"],a')];
  const chat=btns.find(b=>/^\s*chat\s*$/i.test((b.textContent||'').trim()));
  if(chat) chat.click();
  const ta=document.querySelector('textarea');
  if(!ta) return {ok:false, reason:'no textarea'};
  if(ta.disabled||ta.readOnly) return {ok:false, reason:'textarea disabled/readonly'};
  return {ok:true};
})()
"""

# JS: read the chat region text (textarea's high ancestor innerText) — used to
# snapshot before send and to poll for streaming-settle.
_JS_REGION = r"""
(() => {
  const ta=document.querySelector('textarea'); if(!ta) return null;
  let n=ta; for(let i=0;i<10 && n.parentElement;i++) n=n.parentElement;
  return (n.innerText||'').replace(/\s+/g,' ');
})()
"""

# JS: read the chat MESSAGES as structured {role, text}. Rowboat marks each
# message bubble with class `is-user` / `is-assistant` (verified 2026-06-08) —
# a reliable semantic marker, no guessing. Returns the last `limit` messages.
def _js_read(limit: int) -> str:
    return r"""
(() => {
  const bubbles=[...document.querySelectorAll('.is-user, .is-assistant')];
  if(!bubbles.length) return {ok:false, reason:'no message bubbles (chat tab open?)', count:0};
  const msgs=bubbles.map(b=>({
    role: b.classList.contains('is-user') ? 'user' : 'assistant',
    text: (b.innerText||'').replace(/[ \t]+/g,' ').trim(),
  })).filter(m=>m.text);
  const lim=""" + str(int(limit)) + r""";
  return {ok:true, count:msgs.length, messages: lim>0 ? msgs.slice(-lim) : msgs};
})()
"""


def _js_send(message: str) -> str:
    val = json.dumps(message)
    return r"""
(() => {
  const ta=document.querySelector('textarea'); if(!ta) return 'no-textarea';
  ta.focus();
  const proto=window.HTMLTextAreaElement.prototype;
  const setter=Object.getOwnPropertyDescriptor(proto,'value').set;
  setter.call(ta, """ + val + r""");
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
  const ev=(t)=>new KeyboardEvent(t,{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});
  ta.dispatchEvent(ev('keydown')); ta.dispatchEvent(ev('keypress')); ta.dispatchEvent(ev('keyup'));
  return 'sent';
})()
"""


def _send_and_wait(message: str, timeout_s: float, settle_s: float) -> dict:
    ws_url = _find_rowboat_ws()
    cdp = _CDP(ws_url)
    try:
        prep = cdp.evaluate(_JS_PREPARE)
        if not isinstance(prep, dict) or not prep.get("ok"):
            return {"success": False, "error": f"chat field not usable: {prep}"}
        time.sleep(0.4)
        before = cdp.evaluate(_JS_REGION) or ""
        send_res = cdp.evaluate(_js_send(message))
        if send_res != "sent":
            return {"success": False, "error": f"send failed: {send_res}"}

        # Poll the region text until it stays stable for `settle_s` (streaming
        # done) or `timeout_s` elapses. Stability — not DOM-class guessing — is
        # the robust "answer finished" signal.
        deadline = time.time() + timeout_s
        last = ""
        stable_since = None
        while time.time() < deadline:
            time.sleep(0.6)
            cur = cdp.evaluate(_JS_REGION) or ""
            if cur != before and cur == last:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= settle_s:
                    break
            else:
                stable_since = None
            last = cur

        after = cdp.evaluate(_JS_REGION) or ""
        # The assistant reply = the suffix of `after` not present in `before`.
        reply = after
        if before and after.startswith(before[: max(0, len(before) - 60)]):
            reply = after[len(before):].strip()
        # Fallback: trim to text after the last occurrence of the sent message.
        idx = reply.rfind(message)
        if idx != -1:
            reply = reply[idx + len(message):].strip()
        timed_out = time.time() >= deadline and stable_since is None
        return {
            "success": True,
            "sent": message,
            "reply": reply[:4000] if reply else "(no new text detected)",
            "timed_out": timed_out,
        }
    finally:
        cdp.close()


def _read_messages(limit: int, activate_chat: bool) -> dict:
    ws_url = _find_rowboat_ws()
    cdp = _CDP(ws_url)
    try:
        if activate_chat:
            # The message bubbles only exist when the Chat tab is active (the
            # Knowledge tab replaces them). Activate, but don't fail if absent.
            cdp.evaluate(_JS_PREPARE)
            time.sleep(0.4)
        res = cdp.evaluate(_js_read(limit))
        if not isinstance(res, dict) or not res.get("ok"):
            return {"success": False, "error": (res or {}).get("reason", "read failed"),
                    "messages": []}
        return {"success": True, "count": res.get("count", 0),
                "messages": res.get("messages", [])}
    finally:
        cdp.close()


# ── MCP wiring ───────────────────────────────────────────────────────────────

server = Server(SERVER_NAME)

TOOLS = [
    Tool(
        name="rowboat_chat_send",
        description=(
            "Send a message to the Rowboat chat inside the VibeMind Multiverse "
            "app (via CDP, no sign-in needed) and return the assistant's reply. "
            "Activates the Chat tab, types the message, submits, and waits until "
            "the streamed answer settles (or timeout). Use for talking to the "
            "Rowboat knowledge assistant through its GUI."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to send."},
                "timeout_s": {"type": "number", "default": 60,
                              "description": "Max seconds to wait for the reply."},
                "settle_s": {"type": "number", "default": 2.5,
                             "description": "Seconds the text must stay unchanged to count as 'done'."},
            },
            "required": ["message"],
        },
    ),
    Tool(
        name="rowboat_chat_read",
        description=(
            "Read the last messages from the Rowboat chat inside the VibeMind "
            "Multiverse app (via CDP, read-only — sends nothing). Returns a list "
            "of {role: 'user'|'assistant', text}. Use to inspect the conversation "
            "or to poll for a reply after rowboat_chat_send."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10,
                          "description": "How many of the most recent messages to return (0 = all)."},
                "activate_chat": {"type": "boolean", "default": True,
                                  "description": "Click the Chat tab first (message bubbles only exist when it's active)."},
            },
        },
    ),
]


@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    a = arguments or {}
    try:
        if name == "rowboat_chat_send":
            msg = (a.get("message") or "").strip()
            if not msg:
                result = {"success": False, "error": "message is required"}
            else:
                result = await asyncio.to_thread(
                    _send_and_wait, msg,
                    float(a.get("timeout_s", 60)),
                    float(a.get("settle_s", 2.5)),
                )
        elif name == "rowboat_chat_read":
            result = await asyncio.to_thread(
                _read_messages,
                int(a.get("limit", 10)),
                bool(a.get("activate_chat", True)),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
