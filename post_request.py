import requests
import os
from dotenv import load_dotenv

load_dotenv()

emoex_email = os.environ["EMOEX_EMAIL"]
emoex_password = os.environ["EMOEX_PASSWORD"]
product_id = os.environ["EMOEX_PRODUCT_ID"]
firebase_api_key = os.environ["FIREBASE_API_KEY"]

# Sign in to Firebase to get an ID token
firebase_auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
auth_payload = {
    "email": emoex_email,
    "password": emoex_password,
    "returnSecureToken": True
}
auth_response = requests.post(firebase_auth_url, json=auth_payload)
auth_response.raise_for_status()
auth_data = auth_response.json()
id_token = auth_data["idToken"]

# Use the ID token to request the room token
room_token_url = "https://api.emoexai.com/realtime/roomToken"
headers = {"Authorization": f"Bearer {id_token}"}
room_payload = {"productId": product_id}
room_response = requests.post(room_token_url, headers=headers, data=room_payload)
room_response.raise_for_status()
print("------------room data------------------")
print(room_response.json())
print("--------------------------------------")

# ...check the validity of the room token...
import datetime
import base64
import json

id_token = auth_data["idToken"]

# 1) From Firebase response (expiresIn is seconds as string)
expires_in = int(auth_data.get("expiresIn", "3600"))
expiry_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
print("Firebase idToken expires in (seconds):", expires_in)
print("Approx expiry (UTC):", expiry_dt.isoformat() + "Z")

print("---------- create agent token ----------")
# 1. get user token (creates the room)
# user_resp = requests.post(room_token_url, headers=headers, data={"productId": product_id})
user_data = room_response.json()["data"]
room_name = user_data["roomName"]
print("Using room:", room_name)

# 2. get agent token for the same room as the user
payload_agent = {"productId": product_id}#, "roomName": room_name}

agent_resp = requests.post(room_token_url,
                          headers=headers,
                          data=payload_agent)

print("------------agent data------------------")
print(agent_resp.json())
agent_data = agent_resp.json()["data"]



# ----------  show / save tokens  ----------
print("\n-----  USER  -----")
print("userToken :", user_data["userToken"])
print("roomName  :", user_data["roomName"])
print("wsUrl     :", user_data["wsUrl"])

print("\n-----  AGENT  -----")
print("agentToken:", agent_data["userToken"])   # same field name
print("roomName  :", agent_data["roomName"])
print("wsUrl     :", agent_data["wsUrl"])

# optional: write to .env.agent so your agent script can load it
# with open(".env.agent", "w") as f:
#     f.write(f"LIVEKIT_URL={agent_data['wsUrl']}\n"
#             f"AGENT_TOKEN={agent_data['userToken']}\n"
#             f"ROOM_NAME={agent_data['roomName']}\n")
# print("\n Saved to .env.agent")

# 2) Decode JWT exp claim without verification (UTC timestamp)
def jwt_expiry(ts_jwt: str):
    try:
        payload_b64 = ts_jwt.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        exp = payload.get("exp")
        return datetime.datetime.utcfromtimestamp(exp) if exp else None
    except Exception:
        return None

jwt_exp = jwt_expiry(id_token)
print("JWT exp claim (UTC):", jwt_exp)
# ...existing code...
