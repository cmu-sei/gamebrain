import os
import pprint
import warnings

from httpx import Client
from authlib.integrations.httpx_client import OAuth2Client

if os.getenv("LOCALHOST_TEST"):
    GAMEBRAIN_URL = "http://localhost:8000"
else:
    GAMEBRAIN_URL = "https://foundry.local/gamebrain"
GAMEBOARD_URL = "https://foundry.local/gameboard/api"

GB_CLIENT_ID_UNPRIV = "gb-test-client-unpriv"
GB_CLIENT_SECRET_UNPRIV = "46ec755e2bab4070a9634214620389b5"
GB_CLIENT_ID_PRIV = "gb-test-client-priv"
GB_CLIENT_SECRET_PRIV = "cbcf8df872684a82b370f461513ad0b3"
GB_ADMIN_API_KEY = "a" * 32
GS_CLIENT_ID = "gs-test-client"
GS_CLIENT_SECRET = "43bcc0072ab54a349368b20f1c31b0cd"
TOKEN_URL = "https://foundry.local/identity/connect/token"
CA_CERT_PATH = "/usr/local/share/ca-certificates/foundry-appliance-root-ca.crt"
GAME_CLIENT_ID = "game-client"
GAME_CLIENT_SECRET = "a78ea5460fdd4293abe5c8e09f5bba57"
GAMEBOARD_SCRIPT_CLIENT = "gameboard-script-test"
GAMEBOARD_SCRIPT_SECRET = "0887738d326547ae92f06f04b4d434e2"

TEST_USER_1 = "testplayer1@foundry.local"
TEST_USER_1_ID = "0ee37ac5-7a64-4dca-9049-8a64f370d241"
TEST_TEAM_1 = "a538cd94ef92416bbb547ee924056edb"
TEST_USER_2 = "testplayer4@foundry.local"
TEST_TEAM_2 = "30d5396dcb324a43a85368054622d09b"
TEST_SESSION_TIME = "testplayersession@foundry.local"
TEST_SESSION_USER_ID = "dd716a9d-8b22-465b-8fbb-1bfa45a404c2"
TEST_PASS = "7FB77QEc8yhDxAa!"
FOUNDRY_ADMIN_EMAIL = "administrator@foundry.local"
FOUNDRY_ADMIN_PASSWORD = "foundry"

GAME_ID = "f63c8e41fd994e16bad08075dd2a666c"


def main():
    # SSL warnings pollute the console too much.
    warnings.filterwarnings("ignore")

    missing_api_key_session = Client(verify=False)
    invalid_api_key_session = Client(headers={"X-API-Key": "x" * 32}, verify=False)
    gamebrain_admin_session = Client(
        headers={"X-API-Key": GB_ADMIN_API_KEY}, verify=False
    )

    gamestate_session = OAuth2Client(GS_CLIENT_ID, GS_CLIENT_SECRET, verify=False)
    gamestate_session.fetch_token(TOKEN_URL)

    gamebrain_priv_session = OAuth2Client(
        GB_CLIENT_ID_PRIV, GB_CLIENT_SECRET_PRIV, verify=False
    )
    gamebrain_priv_session.fetch_token(TOKEN_URL)

    user_session = OAuth2Client(GAME_CLIENT_ID, GAME_CLIENT_SECRET, verify=False)
    user_session.fetch_token(TOKEN_URL, username=TEST_USER_1, password=TEST_PASS)

    session_time_test_admin = OAuth2Client(
        GAMEBOARD_SCRIPT_CLIENT, GAMEBOARD_SCRIPT_SECRET, verify=False
    )
    session_time_test_admin.fetch_token(
        TOKEN_URL, username=FOUNDRY_ADMIN_EMAIL, password=FOUNDRY_ADMIN_PASSWORD
    )

    print("Testing invalid API key:")
    resp = missing_api_key_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_1}",
    )
    team_1_headless_assignment = resp.json()
    print(team_1_headless_assignment)

    print("Testing invalid API key:")
    resp = invalid_api_key_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_1}",
    )
    team_1_headless_assignment = resp.json()
    print(team_1_headless_assignment)

    print("Getting Team 1 headless client assignment:")
    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_1}",
    )
    team_1_headless_assignment = resp.json()
    print(team_1_headless_assignment)

    print("Deploying for Team 1")
    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/deploy/{GAME_ID}/{TEST_TEAM_1}", timeout=60.0
    )
    print(resp.json())

    print("Getting Team 2 headless client assignment:")
    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{TEST_TEAM_2}",
    )
    print(resp.json())

    print("Testing headless client pool expended (response should be null or None):")
    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client/{'a'*32}",
    )
    print(resp.json())

    resp = gamebrain_admin_session.post(
        f"{GAMEBRAIN_URL}/admin/secrets/{TEST_TEAM_1}",
        json=["secret_1", "secret_2", "secret_3"],
    )
    print(resp.json())

    resp = gamebrain_admin_session.post(
        f"{GAMEBRAIN_URL}/admin/media",
        json={"video1": "example.com/video1", "video2": "example.com/video2"},
    )
    print(resp.json())

    user_token = user_session.token["access_token"]

    print("Testing get_team endpoint")
    json_data = {
        "user_token": user_token,
        "server_container_hostname": f"server-{team_1_headless_assignment[-1]}",
    }
    print(json_data)
    resp = gamestate_session.post(
        f"{GAMEBRAIN_URL}/privileged/get_team",
        json=json_data,
    )
    print(resp.json())

    print(
        "Testing that get_team rejects users attempting to connect through an unauthorized server."
    )
    json_data = {
        "user_token": user_token,
        "server_container_hostname": f"server-3",
    }
    print(json_data)
    resp = gamestate_session.post(
        f"{GAMEBRAIN_URL}/privileged/get_team",
        json=json_data,
    )
    print(resp.json())

    # Revisit this later. Needs to be tested, but it's not really testable right now.
    # resp = gamebrain_priv_session.post(
    #     f"{GAMEBRAIN_URL}/privileged/event/{TEST_TEAM_1}",
    #     params={"event_message": "Mission 2"},
    # )
    # print(resp.json())

    print("Getting initial GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData")
    # pprint.pprint(resp.json())

    print("Getting GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/{TEST_TEAM_1}")
    pprint.pprint(resp.json())

    print("Unlocking location 0 (expect alreadyunlocked)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/000000/team1"
    )
    # pprint.pprint(resp.json())

    print("Unlocking location 1 (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/111111/team1"
    )
    # pprint.pprint(resp.json())

    print("Invalid unlock (expect invalid)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/123456/team1"
    )
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
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/PowerMode/explorationMode/team1"
    )
    # pprint.pprint(resp.json())

    print("Marking comm event complete (expect success)")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/CommEventCompleted/team1")
    # pprint.pprint(resp.json())

    print("Getting GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/team1")
    # pprint.pprint(resp.json())

    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/undeploy/{TEST_TEAM_1}", timeout=60.0
    )
    print(resp.json())

    # Testing out grabbing the session remaining time for the Gamebrain deploy endpoint.

    # First, clear out the test user's session to make sure the state is fresh.
    resp = session_time_test_admin.get(
        f"{GAMEBOARD_URL}/players", params={"gid": GAME_ID, "WantsGame": True}
    )
    data = resp.json()
    if resp.status_code not in range(200, 300):
        print(
            f"Player call failed with status code {resp.status_code} and data: {data}"
        )
        return
    for session in data:
        print(session)
        if session["userId"] == TEST_SESSION_USER_ID:
            player_id = session["id"]
            session_time_test_admin.delete(f"{GAMEBOARD_URL}/player/{player_id}")
            print(f"Deleted player {player_id}")

    # Then create a new session.
    resp = session_time_test_admin.post(
        f"{GAMEBOARD_URL}/player",
        json={"gameId": GAME_ID, "userId": TEST_SESSION_USER_ID},
    )
    data = resp.json()
    player_id = data["id"]
    print(f"Created player {player_id}")

    # Then start the created session.
    resp = session_time_test_admin.put(
        f"{GAMEBOARD_URL}/player/start", json={"id": player_id}
    )
    print(f"player/start status: {resp.status_code}")
    data = resp.json()
    expiration = data["sessionEnd"]
    team_id = data["teamId"]
    print(f"Session expiration time: {expiration}")

    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/deploy/{GAME_ID}/{team_id}", timeout=60.0
    )
    print(resp.json())

    # Clean up.
    session_time_test_admin.delete(f"{GAMEBOARD_URL}/player/{player_id}")
    print(f"Deleted player {player_id}")

    print("Unassigning Team 2 headless client:")
    resp = gamebrain_admin_session.get(
        f"{GAMEBRAIN_URL}/admin/headless_client_unassign/{TEST_TEAM_2}",
    )
    print(resp.json())


if __name__ == "__main__":
    main()
