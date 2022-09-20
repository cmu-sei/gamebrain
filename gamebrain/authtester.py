import os
import pprint
import warnings

from authlib.integrations.httpx_client import OAuth2Client

if os.getenv("LOCALHOST_TEST"):
    GAMEBRAIN_URL = "https://localhost:8000"
else:
    GAMEBRAIN_URL = "https://foundry.local/gamebrain"

GB_CLIENT_ID_UNPRIV = "gb-test-client-unpriv"
GB_CLIENT_SECRET_UNPRIV = "46ec755e2bab4070a9634214620389b5"
GB_CLIENT_ID_PRIV = "gb-test-client-priv"
GB_CLIENT_SECRET_PRIV = "cbcf8df872684a82b370f461513ad0b3"
GB_CLIENT_ID_ADMIN = "gb-test-client-admin"
GB_CLIENT_SECRET_ADMIN = "accbc5dfa5a84aa9a9ce8ff26902a349"
GS_CLIENT_ID = "gs-test-client"
GS_CLIENT_SECRET = "43bcc0072ab54a349368b20f1c31b0cd"
TOKEN_URL = "https://foundry.local/identity/connect/token"
CA_CERT_PATH = "/usr/local/share/ca-certificates/foundry-appliance-root-ca.crt"
GAME_CLIENT_ID = "game-client"
GAME_CLIENT_SECRET = "a78ea5460fdd4293abe5c8e09f5bba57"

TEST_USER_1 = "testplayer1@foundry.local"
TEST_USER_1_ID = "0ee37ac5-7a64-4dca-9049-8a64f370d241"
TEST_TEAM_1 = "a538cd94ef92416bbb547ee924056edb"
TEST_USER_2 = "testplayer4@foundry.local"
TEST_TEAM_2 = "30d5396dcb324a43a85368054622d09b"
TEST_PASS = "7FB77QEc8yhDxAa!"

GAME_ID = "f63c8e41fd994e16bad08075dd2a666c"


def main():
    # SSL warnings pollute the console too much.
    warnings.filterwarnings("ignore")

    admin_session = OAuth2Client(GB_CLIENT_ID_ADMIN, GB_CLIENT_SECRET_ADMIN, verify=False)
    admin_session.fetch_token(TOKEN_URL)

    gamestate_session = OAuth2Client(GS_CLIENT_ID, GS_CLIENT_SECRET, verify=False)
    gamestate_session.fetch_token(TOKEN_URL)

    priv_session = OAuth2Client(GB_CLIENT_ID_PRIV, GB_CLIENT_SECRET_PRIV, verify=False)
    priv_session.fetch_token(TOKEN_URL)

    user_session = OAuth2Client(GAME_CLIENT_ID, GAME_CLIENT_SECRET, verify=False)
    user_session.fetch_token(TOKEN_URL, username=TEST_USER_1, password=TEST_PASS)

    print("Getting Team 1 headless client assignment:")
    resp = admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_1}",
    )
    print(resp.json())

    print("Getting Team 2 headless client assignment:")
    resp = admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_2}",
    )
    print(resp.json())

    resp = admin_session.get(
        f"{GAMEBRAIN_URL}/admin/deploy/{GAME_ID}/{TEST_TEAM_1}", timeout=60.0
    )
    print(resp.json())

    resp = admin_session.post(
        f"{GAMEBRAIN_URL}/admin/secrets/{TEST_TEAM_1}",
        json=["secret_1", "secret_2", "secret_3"],
    )
    print(resp.json())

    resp = admin_session.post(
        f"{GAMEBRAIN_URL}/admin/media",
        json={"video1": "example.com/video1", "video2": "example.com/video2"},
    )
    print(resp.json())

    user_token = user_session.token["access_token"]

    print("Testing get_team endpoint")
    json_data = {"user_token": user_token}
    print(json_data)
    request = priv_session.post(
        f"{GAMEBRAIN_URL}/privileged/get_team",
        json=json_data,
    )
    print(resp.json())

    resp = priv_session.post(
        f"{GAMEBRAIN_URL}/privileged/event/{TEST_TEAM_1}",
        params={"event_message": "Mission 2"},
    )
    print(resp.json())

    print("Getting initial GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData")
    # pprint.pprint(resp.json())

    print("Getting GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/team1")
    # pprint.pprint(resp.json())

    print("Unlocking location 0 (expect alreadyunlocked)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/LocationUnlock/000000/team1")
    # pprint.pprint(resp.json())

    print("Unlocking location 1 (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/LocationUnlock/111111/team1")
    # pprint.pprint(resp.json())

    print("Invalid unlock (expect invalid)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/LocationUnlock/123456/team1")
    # pprint.pprint(resp.json())

    print("Jump to current location (expect failure")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/Jump/location1/team1")
    # pprint.pprint(resp.json())

    print("Jump to invalid location (expect failure")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/Jump/invalid/team1")
    # pprint.pprint(resp.json())

    print("Jump to locked location (expect failure")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/Jump/location3/team1")
    # pprint.pprint(resp.json())

    print("Jump to unlocked location (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/Jump/location2/team1")
    # pprint.pprint(resp.json())

    print("Scan new location (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/ScanLocation/team1")
    # pprint.pprint(resp.json())

    print("Changing power mode (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/PowerMode/explorationMode/team1")
    # pprint.pprint(resp.json())

    print("Marking comm event complete (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/CommEventCompleted/team1")
    # pprint.pprint(resp.json())

    print("Getting GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/team1")
    # pprint.pprint(resp.json())

    resp = admin_session.get(
        f"{GAMEBRAIN_URL}/admin/undeploy/{GAME_ID}/{TEST_TEAM_1}", timeout=60.0
    )
    print(resp.json())


if __name__ == "__main__":
    main()
