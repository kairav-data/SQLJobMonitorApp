import json
import os
import uuid

DB_FILE = "servers_db.json"
USERS_DB_FILE = "users_db.json"

def _init_default_users():
    if not os.path.exists(USERS_DB_FILE):
        default_users = [
            {"username": "admin", "password": "admin123", "role": "admin"},
            {"username": "user", "password": "user123", "role": "viewer"}
        ]
        with open(USERS_DB_FILE, "w") as f:
            json.dump(default_users, f, indent=4)

def authenticate(username, password):
    _init_default_users()
    try:
        with open(USERS_DB_FILE, "r") as f:
            users = json.load(f)
        for u in users:
            if u["username"] == username and u["password"] == password:
                return True, u["role"]
    except Exception:
        pass
    return False, None

def load_servers():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_servers(servers):
    with open(DB_FILE, "w") as f:
        json.dump(servers, f, indent=4)

def add_server(server_data):
    servers = load_servers()
    server_data["id"] = str(uuid.uuid4())
    servers.append(server_data)
    save_servers(servers)
    return servers

def delete_server(server_id):
    servers = load_servers()
    servers = [s for s in servers if s.get("id") != server_id]
    save_servers(servers)
    return servers
