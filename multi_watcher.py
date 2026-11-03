import os
import json
from curl_cffi import requests
from bs4 import BeautifulSoup

# 監視するターゲットのリスト
TARGETS = [
    {
        "name": "Ikebe-Gakki (Tak Matsumoto DC)",
        "url": "https://www.ikebe-gakki.com/Form/Product/ProductDetail.aspx?shop=0&pid=870613&bid=ec",
        "sold_out_keywords": ["SOLD OUT", "受付終了", "在庫なし"]
    },
    {
        "name": "Kurosawa Gakki (Tak Matsumoto DC)",
        "url": "https://www.kurosawagakki.com/gibson/tak_matsumoto_dc_std_tp/",
        "sold_out_keywords": ["SOLD OUT", "売約済", "在庫なし", "HOLD"]
    }
]

STATE_FILE = "multi_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send_discord_notification(webhook_url, message):
    payload = {"content": message}
    requests.post(webhook_url, json=payload)

def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    state = load_state()
    session = requests.Session()

    for target in TARGETS:
        name = target["name"]
        url = target["url"]
        keywords = target["sold_out_keywords"]

        target_state = state.get(url, {})
        was_in_stock = target_state.get("in_stock", False)
        was_error = target_state.get("has_error", False)

        current_in_stock = was_in_stock
        current_error = False
        error_message = ""

        try:
            response = session.get(url, impersonate="chrome", timeout=15)
            if response.status_code != 200:
                current_error = True
                error_message = f"HTTP Status Code: {response.status_code}"
            else:
                soup = BeautifulSoup(response.text, 'html.parser')
                page_text = soup.get_text()

                is_sold_out = any(kw in page_text for kw in keywords)
                current_in_stock = not is_sold_out

                print(f"[{name}] In Stock: {current_in_stock}")

                if current_in_stock and not was_in_stock:
                    msg = f"🚨 **【在庫復活！】** `{name}` のカートがオープンした可能性があります！\n🔗 {url}"
                    send_discord_notification(webhook_url, msg)
                    print(f"[{name}] Stock notification sent!")

        except Exception as e:
            current_error = True
            error_message = str(e)
            print(f"[{name}] Error: {e}")

        if current_error and not was_error:
            err_msg = f"⚠️ **【監視エラー】** `{name}` にアクセスできませんでした。\n🔗 {url}\n📝 理由: `{error_message}`"
            send_discord_notification(webhook_url, err_msg)
            print(f"[{name}] Error notification sent!")
        elif not current_error and was_error:
            rec_msg = f"✅ **【監視復旧】** `{name}` へのアクセスが復旧しました。"
            send_discord_notification(webhook_url, rec_msg)
            print(f"[{name}] Recovery notification sent!")

        if url not in state:
            state[url] = {}
        state[url]["in_stock"] = current_in_stock
        state[url]["has_error"] = current_error

    save_state(state)

if __name__ == "__main__":
    main()
