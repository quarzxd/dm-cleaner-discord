import requests
import time
import json
import websocket
import threading
import os
from datetime import datetime, timezone
from pystyle import Colors, Colorate, Center

ascii_text = r"""
   ___  __  ___  _______   _______   _  _________ 
  / _ \/  |/  / / ___/ /  / __/ _ | / |/ / __/ _ \
 / // / /|_/ / / /__/ /__/ _// __ |/    / _// , _/
/____/_/  /_/  \___/____/___/_/ |_/_/|_/___/_/|_| 
"""

def get_token_from_file():
    try:
        with open("token.txt", "r") as file:
            return file.read().strip()  
    except FileNotFoundError:
        print("Token.txt not found.")
        return None

TOKEN = get_token_from_file()  
if not TOKEN:
    print("Token retrieval failed. Please make sure you have placed the token.txt file correctly..")
    exit()

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0",
}

os.system('cls')

def get_user_info():
    r = requests.get("https://discord.com/api/v9/users/@me", headers=HEADERS)
    if r.status_code == 200:
        user_data = r.json()
        return f"{user_data['username']}#{user_data['discriminator']}"
    return "Unknown User"

user_tag = get_user_info()
print(Center.XCenter(f"Selfbot is now running as `{user_tag}`"))
print(Colorate.Horizontal(Colors.red_to_white, Center.XCenter(ascii_text)))
print()

RUNNING = True
DELETE_DELAY = 1.5
STOP_DELETION = {}
USER_ID = None
ACTIVE_DELETIONS = {}

def get_user_id():
    global USER_ID
    if USER_ID:
        return USER_ID
    
    r = requests.get("https://discord.com/api/v9/users/@me", headers=HEADERS)
    if r.status_code == 200:
        USER_ID = r.json()["id"]
        return USER_ID
    else:
        print("User ID could not be obtained.")
        return None

def get_dm_channels():
    r = requests.get("https://discord.com/api/v9/users/@me/channels", headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    else:
        print(f"Failed to get DM channels: {r.status_code}")
        return []

def count_messages(channel_id):
    last_message_id = None
    count = 0
    
    while True:
        try:
            params = {'before': last_message_id} if last_message_id else {}
            r = requests.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=100", 
                headers=HEADERS,
                params=params
            )
            
            if r.status_code != 200:
                break

            messages = r.json()
            if not messages:
                break
            
            user_id = get_user_id()
            for msg in messages:
                if user_id and msg["author"]["id"] == user_id:
                    count += 1

            last_message_id = messages[-1]["id"]
            
        except:
            break
    
    return count

def backup_messages(channel_id):
    last_message_id = None
    messages_data = []
    
    while True:
        try:
            params = {'before': last_message_id} if last_message_id else {}
            r = requests.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=100", 
                headers=HEADERS,
                params=params
            )
            
            if r.status_code != 200:
                break

            messages = r.json()
            if not messages:
                break
            
            for msg in messages:
                timestamp = msg["timestamp"][:19].replace("T", " ")
                username = msg["author"]["username"]
                display_name = msg["author"].get("display_name")
                
                if display_name and display_name != username:
                    author_name = f"{display_name} - {username}"
                else:
                    author_name = username
                    
                messages_data.append({
                    "author": author_name,
                    "content": msg["content"],
                    "timestamp": timestamp
                })

            last_message_id = messages[-1]["id"]
            
        except:
            break
    
    messages_data.reverse()
    
    filename = f"backup_{channel_id}_{int(time.time())}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"=== DISCORD BACKUP - Channel {channel_id} ===\n")
        f.write(f"Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Messages: {len(messages_data)}\n")
        f.write("=" * 50 + "\n\n")
        
        for msg in messages_data:
            f.write(f"[{msg['timestamp']}] {msg['author']}: {msg['content']}\n")
    
    return filename, len(messages_data)

def delete_messages(channel_id, limit=None, search_term=None, before_date=None, files_only=False):
    global STOP_DELETION, ACTIVE_DELETIONS
    task_id = f"{channel_id}_{int(time.time())}"
    ACTIVE_DELETIONS[task_id] = {'count': 0, 'status': 'running', 'channel': channel_id}
    STOP_DELETION[task_id] = False
    last_message_id = None
    deleted_count = 0
    
    while True:
        if STOP_DELETION.get(task_id, False):
            print("Deletion stopped by user.")
            STOP_DELETION.pop(task_id, None)
            ACTIVE_DELETIONS.pop(task_id, None)
            break
            
        try:
            params = {'before': last_message_id} if last_message_id else {}
            r = requests.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=100", 
                headers=HEADERS,
                params=params
            )
            
            if r.status_code != 200:
                print(f"Messages could not be received: {r.status_code}")
                if r.status_code == 429:
                    retry_after = r.headers.get('Retry-After', 5)
                    print(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(int(retry_after))
                    continue
                break

            messages = r.json()
            if not messages:  
                print(f"Deleted {deleted_count} messages total.")
                ACTIVE_DELETIONS.pop(task_id, None)
                STOP_DELETION.pop(task_id, None)
                break
            
            user_id = get_user_id()
            for msg in messages:
                if STOP_DELETION.get(task_id, False):
                    break
                    
                if user_id and msg["author"]["id"] == user_id:
                    # Apply filters
                    if search_term and search_term.lower() not in msg["content"].lower():
                        continue
                    if before_date:
                        msg_time = datetime.fromisoformat(msg["timestamp"].replace('Z', '+00:00'))
                        if msg_time >= before_date:
                            continue
                    if files_only and not msg.get("attachments"):
                        continue
                    if limit and deleted_count >= limit:
                        break

                    
                    message_content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
                    delete_url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg['id']}"
                    del_r = requests.delete(delete_url, headers=HEADERS)
                    
                    if del_r.status_code in [200, 204]:
                        print(f"[+] Deleted: {message_content}")
                        deleted_count += 1
                        ACTIVE_DELETIONS[task_id]['count'] = deleted_count
                        if deleted_count % 10 == 0:
                            print(f"[PROGRESS] {deleted_count} messages deleted so far...")
                    elif del_r.status_code == 429:
                        retry_after = int(del_r.headers.get('Retry-After', 5))
                        print(f"[⏳] Rate limited. Waiting {retry_after}s...")
                        time.sleep(retry_after)
                    elif del_r.status_code == 403:
                        print(f"[x] No permission: {msg['id']} (too old or protected)")
                    elif del_r.status_code == 404:
                        print(f"[!] Message not found: {msg['id']}")
                    else:
                        print(f"[x] Failed {msg['id']}: HTTP {del_r.status_code}")
                    
                    time.sleep(DELETE_DELAY)

            last_message_id = messages[-1]["id"]
            
        except Exception as e:
            print(f"Error in delete_messages: {e}")
            ACTIVE_DELETIONS.pop(task_id, None)
            STOP_DELETION.pop(task_id, None)
            time.sleep(1)

def show_help():
    help_text = """
**Available Commands:** 
[developed by @quarzxd](https://discord.gg/tarafsizrc)
`.clear` - Delete all your messages in this DM
`.help` - Show this help message
`.delay <seconds>` - Set custom delay between message deletions
`.delete <channel_id>` - Delete your messages from specific channel
`.count <channel_id>` - Count your messages in channel
`.stop` - Stop current deletion process
`.backup [channel_id]` - Backup messages
`.status` - Show active deletion processes
`.speed` - Show current deletion speed
`.recent <number> [channel_id]` - Delete last N messages
`.search <term> [channel_id]` - Delete messages containing term
`.before <YYYY-MM-DD> [channel_id]` - Delete messages before date
`.files [channel_id]` - Delete only messages with attachments

**Usage:**
Just type any command in a DM channel and the bot will respond!
"""
    return help_text



def process_command(command, channel_id, msg_id):
    global DELETE_DELAY
    print(f"Processing command: {command} in channel {channel_id}")
    
    if command.lower() == ".clear":
        print(f"[CLEAR] Clear command detected in DM channel {channel_id}")
        print("[DELETE] Starting message deletion...")
        threading.Thread(target=lambda: delete_messages(channel_id), daemon=True).start()
        return True
        
    elif command.lower() == ".help":
        help_msg = show_help()
        requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            headers=HEADERS,
            json={"content": help_msg}
        )
        print("[INFO] Help message sent.")
        return True
        

    elif command.lower().startswith(".delay "):
        try:
            delay_value = float(command.split(" ", 1)[1])
            if 0.1 <= delay_value <= 30:
                DELETE_DELAY = delay_value
                speed_desc = "Very Fast" if delay_value < 1 else "Fast" if delay_value < 2 else "Normal" if delay_value < 5 else "Slow"
                requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"⚙️ Delay set to {delay_value}s ({speed_desc})"})
                print(f"[CONFIG] Delay updated to {delay_value}s")
            else:
                requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Delay must be between 0.1 and 30 seconds"})
        except ValueError:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "❌ Invalid delay format!"})
        except:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Usage: .delay <seconds> (0.1-30)"})
        return True
        
    elif command.lower() == ".status":
        if ACTIVE_DELETIONS:
            status_lines = []
            for task_id, info in ACTIVE_DELETIONS.items():
                elapsed = int(time.time()) - int(task_id.split('_')[-1])
                rate = info['count'] / max(elapsed, 1)
                status_lines.append(f"Channel {info['channel']}: {info['count']} deleted ({rate:.1f}/s)")
            status_msg = "🔄 Active deletions:\n" + "\n".join(status_lines)
        else:
            status_msg = "✅ No active deletions"
        requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": status_msg})
        return True
        
    elif command.lower() == ".speed":
        speed_desc = "Very Fast" if DELETE_DELAY < 1 else "Fast" if DELETE_DELAY < 2 else "Normal" if DELETE_DELAY < 5 else "Slow"
        msgs_per_min = int(60 / DELETE_DELAY)
        requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"⚡ Speed: {DELETE_DELAY}s delay ({speed_desc}) - ~{msgs_per_min} msgs/min"})
        return True
        
    elif command.lower().startswith(".recent "):
        try:
            parts = command.split(" ")
            limit = int(parts[1])
            if limit > 1000:
                requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "⚠️ Limit too high! Maximum 1000 messages."})
                return True
            target_channel = parts[2] if len(parts) > 2 else channel_id
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"🗑️ Deleting last {limit} messages in channel {target_channel}..."})
            threading.Thread(target=lambda: delete_messages(target_channel, limit=limit), daemon=True).start()
        except ValueError:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "❌ Invalid number format!"})
        except:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Usage: .recent <number> [channel_id]"})
        return True
        
    elif command.lower().startswith(".search "):
        try:
            parts = command.split(" ", 2)
            if len(parts) == 3:  # .search term channel_id
                term, target_channel = parts[1], parts[2]
            else:  # .search term
                term, target_channel = parts[1], channel_id
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"🔍 Deleting messages containing '{term}' in channel {target_channel}..."})
            threading.Thread(target=lambda: delete_messages(target_channel, search_term=term), daemon=True).start()
        except:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Usage: .search <term> [channel_id]"})
        return True
        
    elif command.lower().startswith(".before "):
        try:
            parts = command.split(" ")
            date_str = parts[1]
            target_channel = parts[2] if len(parts) > 2 else channel_id
            before_date = datetime.fromisoformat(date_str + "T00:00:00+00:00")
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"📅 Deleting messages before {date_str} in channel {target_channel}..."})
            threading.Thread(target=lambda: delete_messages(target_channel, before_date=before_date), daemon=True).start()
        except:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Usage: .before YYYY-MM-DD [channel_id]"})
        return True
        
    elif command.lower().startswith(".files"):
        try:
            parts = command.split(" ")
            target_channel = parts[1] if len(parts) > 1 else channel_id
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"📎 Deleting messages with files in channel {target_channel}..."})
            threading.Thread(target=lambda: delete_messages(target_channel, files_only=True), daemon=True).start()
        except:
            requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "Usage: .files [channel_id]"})
        return True
        
    elif command.lower().startswith(".delete "):
        try:
            target_channel_id = command.split(" ", 1)[1].strip()
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": f"Anlaşıldı {target_channel_id}."}
            )
            print(f"[DELETE] Starting deletion in channel {target_channel_id}")
            
            threading.Thread(target=lambda: delete_messages(target_channel_id), daemon=True).start()
            
        except:
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": "Usage: .delete <channel_id>"}
            )
        return True
        
    elif command.lower().startswith(".count "):
        try:
            target_channel_id = command.split(" ", 1)[1].strip()
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": "🔢 Counting messages..."}
            )
            
            def count_task():
                try:
                    count = count_messages(target_channel_id)
                    requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"You have {count} messages in channel {target_channel_id}"})
                except:
                    requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "❌ Count failed"})
            threading.Thread(target=count_task, daemon=True).start()
            
        except:
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": "Usage: .count <channel_id>"}
            )
        return True
        
    elif command.lower() == ".stop":
        for task_id in list(STOP_DELETION.keys()):
            STOP_DELETION[task_id] = True
        requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "🛑 Stopping all deletion processes..."})
        return True
        
    elif command.lower().startswith(".backup"):
        try:
            if len(command.split()) > 1:
                target_channel_id = command.split(" ", 1)[1].strip()
            else:
                target_channel_id = channel_id
                
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": "📦 Creating backup..."}
            )
            
            def backup_task():
                try:
                    filename, msg_count = backup_messages(target_channel_id)
                    requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": f"✅ Backup saved: {filename} ({msg_count} messages)"})
                except:
                    requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=HEADERS, json={"content": "❌ Backup failed"})
            threading.Thread(target=backup_task, daemon=True).start()
            
        except:
            requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=HEADERS,
                json={"content": "Usage: .backup [channel_id] (optional)"}
            )
        return True
        

        
    return False

def on_message(ws, message):
    global RUNNING
    try:
        data = json.loads(message)
        
        if data.get('t') == 'MESSAGE_CREATE':
            msg_data = data['d']
            author_id = msg_data['author']['id']
            content = msg_data.get('content', '').strip()
            channel_id = msg_data['channel_id']
            message_id = msg_data['id']
            
            user_id = get_user_id()
            if user_id and author_id == user_id:
                content_lower = content.lower()
                commands = ['.clear', '.help', '.stop', '.backup', '.status', '.speed', '.files']
                prefixes = ['.delay ', '.delete ', '.count ', '.backup ', '.recent ', '.search ', '.before ']
                if content_lower in commands or any(content_lower.startswith(p) for p in prefixes):
                    print(f"INSTANT COMMAND: {content}")
                    
                    if process_command(content_lower, channel_id, message_id):
                        try:
                            requests.delete(
                                f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}",
                                headers=HEADERS
                            )
                        except:
                            pass
                            
    except Exception as e:
        print(f"WebSocket message error: {e}")

def on_open(ws):
    identify = {
        "op": 2,
        "d": {
            "token": TOKEN,
            "properties": {
                "$os": "windows",
                "$browser": "chrome",
                "$device": "pc"
            }
        }
    }
    ws.send(json.dumps(identify))

def start_websocket():
    ws = websocket.WebSocketApp(
        "wss://gateway.discord.gg/?v=9&encoding=json",
        on_message=on_message,
        on_open=on_open
    )
    ws.run_forever()

def monitor_dm_channels():
    global RUNNING
    print("[INFO] Send .clear in a DM to delete your messages instantly")
    print("[INFO] Send .delete <channel_id> to delete from specific channel")
    print("[INFO] Send .help for available commands")
    
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()
    
    try:
        while RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Stopping bot...")
        RUNNING = False
    
    print("[EXIT] Script stopped.")

if __name__ == "__main__":
    monitor_dm_channels()
