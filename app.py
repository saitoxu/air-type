from flask import Flask, request, render_template_string, send_file
import pyautogui
import pyperclip
import socket
import io
import time
import mss
from PIL import Image

app = Flask(__name__)
pyautogui.PAUSE = 0.02

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>air-type</title>
    <style>
        html, body { height: 100%; margin: 0; overscroll-behavior: none; }
        body { font-family: -apple-system, sans-serif; display: flex; flex-direction: column;
               padding: 0; box-sizing: border-box; gap: 4px;
               padding-bottom: env(safe-area-inset-bottom); }
        #preview-wrap { flex: 1; min-height: 120px; overflow: auto;
                        background: #000; -webkit-overflow-scrolling: touch; }
        #preview { display: block; width: 100%; max-width: none; }
        #zoom-indicator { position: fixed; top: 8px; right: 8px; padding: 4px 10px;
                          background: rgba(0,0,0,0.55); color: #fff; font-size: 12px;
                          border-radius: 12px; pointer-events: none; z-index: 100; }
        .row { display: flex; gap: 4px; padding: 0 4px; }
        .row > * { flex: 1; }
        button { height: 36px; font-size: 14px; touch-action: manipulation; padding: 0; }
        textarea { display: block; width: 100%; height: 40px; font-size: 16px; box-sizing: border-box;
                   resize: none; border: none; border-top: 1px solid #ddd; padding: 8px; }
        #status { position: fixed; top: 8px; left: 8px; max-width: calc(100% - 80px);
                  padding: 4px 10px; background: rgba(0,0,0,0.55); color: #fff; font-size: 12px;
                  border-radius: 12px; pointer-events: none; z-index: 100;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #status:empty { display: none; }
    </style>
</head>
<body>
    <div id="preview-wrap"><img id="preview" alt="Mac画面プレビュー"></div>
    <div id="zoom-indicator">100%</div>
    <textarea id="input" placeholder="ここに入力（⌫はキーボードから）" autofocus></textarea>
    <div class="row">
        <button onclick="setZoom(zoom / 1.25)">−</button>
        <button onclick="setZoom(zoom * 1.25)">＋</button>
        <button onclick="sendEnter()">↵</button>
        <button onclick="clearBuffer()">クリア</button>
    </div>
    <div id="status"></div>

    <script>
        const input = document.getElementById('input');
        const status = document.getElementById('status');
        const preview = document.getElementById('preview');
        let isComposing = false;
        let lastValue = '';
        let zoom = 1;
        let queue = Promise.resolve();

        function setZoom(z) {
            zoom = Math.max(0.5, Math.min(z, 5));
            preview.style.width = (zoom * 100) + '%';
            document.getElementById('zoom-indicator').textContent = Math.round(zoom * 100) + '%';
        }

        function enqueue(fn) {
            queue = queue.then(fn).catch(e => { status.textContent = '送信失敗: ' + e.message; });
            return queue;
        }

        function postSend(text) {
            return enqueue(async () => {
                const res = await fetch('/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text})
                });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                status.textContent = '送信: ' + JSON.stringify(text);
            });
        }

        function postBackspace(count) {
            return enqueue(async () => {
                const res = await fetch('/backspace', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({count})
                });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                status.textContent = '⌫ × ' + count;
            });
        }

        function syncDelta() {
            const cur = input.value;
            if (cur === lastValue) return;
            if (cur.length > lastValue.length && cur.startsWith(lastValue)) {
                postSend(cur.slice(lastValue.length));
            } else if (cur.length < lastValue.length && lastValue.startsWith(cur)) {
                postBackspace(lastValue.length - cur.length);
            } else {
                if (lastValue.length > 0) postBackspace(lastValue.length);
                if (cur.length > 0) postSend(cur);
            }
            lastValue = cur;
        }

        input.addEventListener('compositionstart', () => { isComposing = true; });
        input.addEventListener('compositionend', () => {
            isComposing = false;
            setTimeout(syncDelta, 0);
        });
        input.addEventListener('input', () => {
            if (isComposing) return;
            syncDelta();
        });

        async function sendEnter() {
            enqueue(async () => {
                const res = await fetch('/enter', {method: 'POST'});
                if (!res.ok) throw new Error('HTTP ' + res.status);
                status.textContent = 'Enter送信';
            });
        }

        function clearBuffer() {
            input.value = '';
            lastValue = '';
            status.textContent = 'バッファをクリア';
        }

        let touchStartX = 0;
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        }, {passive: true});
        document.addEventListener('touchmove', (e) => {
            const x = e.touches[0].clientX;
            const w = window.innerWidth;
            if ((touchStartX < 20 && x > touchStartX + 5) ||
                (touchStartX > w - 20 && x < touchStartX - 5)) {
                e.preventDefault();
            }
        }, {passive: false});

        function refreshPreview() {
            const next = new Image();
            next.onload = () => { preview.src = next.src; };
            next.src = '/screenshot?t=' + Date.now();
        }
        setInterval(refreshPreview, 1000);
        refreshPreview();
    </script>
</body>
</html>
"""


_warmed_up = False


def paste_text(text: str) -> None:
    global _warmed_up
    if not _warmed_up:
        pyautogui.keyDown('command')
        time.sleep(0.05)
        pyautogui.keyUp('command')
        time.sleep(0.05)
        _warmed_up = True
    pyperclip.copy(text)
    pyautogui.keyDown('command')
    time.sleep(0.03)
    pyautogui.press('v')
    time.sleep(0.03)
    pyautogui.keyUp('command')


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/send', methods=['POST'])
def send():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    if text:
        paste_text(text)
    return {'status': 'ok'}


@app.route('/backspace', methods=['POST'])
def backspace():
    data = request.get_json(silent=True) or {}
    count = max(1, int(data.get('count', 1)))
    pyautogui.press('backspace', presses=count, interval=0.01)
    return {'status': 'ok'}


@app.route('/enter', methods=['POST'])
def enter():
    pyautogui.press('enter')
    return {'status': 'ok'}


@app.route('/screenshot')
def screenshot():
    import os
    with mss.MSS() as sct:
        shot = sct.grab(sct.monitors[1])
        img = Image.frombytes('RGB', shot.size, shot.rgb)
    target_w = int(os.environ.get('SCREENSHOT_WIDTH', '1800'))
    quality = int(os.environ.get('SCREENSHOT_QUALITY', '70'))
    if img.width > target_w:
        ratio = target_w / img.width
        img = img.resize((target_w, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg')


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', '5050'))
    ip = get_local_ip()
    print(f"iPhoneからブラウザでアクセス: http://{ip}:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=True)
