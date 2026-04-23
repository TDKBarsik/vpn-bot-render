import os
import requests
import socket
import time
import re
import json

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not set!")

MAX_LATENCY = 2.0
API = f"https://api.telegram.org/bot{TOKEN}"
PORTS = {'vless': 443, 'vmess': 443, 'trojan': 443, 'ss': 8388, 'ssr': 8388, 'hysteria2': 443, 'hysteria': 443, 'tuic': 443}

def api(method, **kwargs):
    return requests.post(f"{API}/{method}", timeout=30, **kwargs).json()

def send_message(chat_id, text):
    api("sendMessage", json={"chat_id": chat_id, "text": text})

def send_file(chat_id, path, caption=""):
    with open(path, 'rb') as f:
        api("sendDocument", files={"document": f}, data={"chat_id": chat_id, "caption": caption})

def get_host_port(line):
    line = line.strip()
    if not line or line.startswith('#') or not re.match(r'^\w+://', line):
        return None, None
    p = re.match(r'^(\w+)://', line).group(1).lower()
    if p == 'vmess':
        try:
            import base64
            b = line[8:].split('#')[0]
            pad = 4 - len(b) % 4
            if pad != 4: b += '=' * pad
            c = json.loads(base64.b64decode(b).decode())
            return c.get('add'), int(c.get('port', 443))
        except: pass
    for pat in [r'@\[?([\w\.\-]+)\]?:(\d+)', r'@([\w\.\-]+):(\d+)']:
        m = re.search(pat, line)
        if m: return m.group(1), int(m.group(2))
    m = re.search(r'@([\w\.\-]+)(?:/|\?|#|$)', line)
    if m and p in PORTS: return m.group(1), PORTS[p]
    return None, None

def check(host, port):
    try:
        ip = socket.gethostbyname(host)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        t = time.time()
        r = s.connect_ex((ip, port))
        l = time.time() - t
        s.close()
        return l if r == 0 and l <= MAX_LATENCY else None
    except: return None

def clean(content):
    lines = content.strip().split('\n')
    res, ok, bad, tot = [], 0, 0, 0
    for line in lines:
        orig, l = line, line.strip()
        if not l or l.startswith('#') or not re.match(r'^\w+://', l):
            res.append(orig)
            continue
        tot += 1
        h, p = get_host_port(l)
        if h and p:
            if check(h, p):
                res.append(orig); ok += 1
            else: bad += 1
        else: res.append(orig)
    return '\n'.join(res), ok, bad, tot

def process(msg):
    cid = msg['chat']['id']
    txt = msg.get('text', '').strip()
    if txt == '/start':
        send_message(cid, "👋 Привет! Отправь ссылку на VPN-подписку.")
    elif txt.startswith('http'):
        send_message(cid, "⏳ Скачиваю...")
        try:
            r = requests.get(txt, timeout=15, headers={'User-Agent': 'Bot'})
            r.raise_for_status()
            send_message(cid, "🔍 Проверяю...")
            c, ok, bad, tot = clean(r.text)
            s = f"📊 Всего: {tot}\n✅ Рабочих: {ok}\n❌ Удалено: {bad}"
            if ok == 0:
                send_message(cid, s + "\n\nНет рабочих серверов.")
                return
            fn = f"/tmp/vpn_{int(time.time())}.txt"
            with open(fn, 'w') as f: f.write(c)
            send_file(cid, fn, s)
        except Exception as e:
            send_message(cid, f"❌ Ошибка: {str(e)[:200]}")
    else:
        send_message(cid, "❌ Отправь ссылку.")

print("Бот запущен...")
off = 0
while True:
    try:
        r = requests.get(f"{API}/getUpdates?offset={off}&timeout=30", timeout=35).json()
        if r.get('ok'):
            for u in r.get('result', []):
                off = u['update_id'] + 1
                if 'message' in u: process(u['message'])
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
