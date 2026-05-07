"""Flask app: serves the iPhone UI and forwards input/clicks to Mac."""

from __future__ import annotations

import os
import socket

from flask import Flask, Response, jsonify, render_template, request

import mac_io

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/send', methods=['POST'])
def send():
    data = request.get_json(silent=True) or {}
    mac_io.paste_text(data.get('text', ''))
    return {'status': 'ok'}


@app.route('/backspace', methods=['POST'])
def backspace():
    data = request.get_json(silent=True) or {}
    mac_io.press_backspace(int(data.get('count', 1)))
    return {'status': 'ok'}


@app.route('/enter', methods=['POST'])
def enter():
    mac_io.press_enter()
    return {'status': 'ok'}


@app.route('/click', methods=['POST'])
def click():
    data = request.get_json(silent=True) or {}
    mac_io.click_at(int(data['x']), int(data['y']))
    return {'status': 'ok'}


@app.route('/size')
def size():
    w, h = mac_io.screen_size()
    return jsonify(width=w, height=h)


@app.route('/focus')
def focus():
    pos = mac_io.caret_position()
    if pos is None:
        return jsonify(x=None, y=None)
    return jsonify(x=pos[0], y=pos[1])


@app.route('/screenshot')
def screenshot():
    width = int(os.environ.get('SCREENSHOT_WIDTH', '1800'))
    quality = int(os.environ.get('SCREENSHOT_QUALITY', '70'))
    return Response(mac_io.grab_screenshot_jpeg(width, quality), mimetype='image/jpeg')


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5050'))
    print(f'iPhoneからブラウザでアクセス: http://{get_local_ip()}:{port}')
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=True)
