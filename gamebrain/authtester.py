# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

import datetime
import json
import os
import pprint
import time
import warnings

from httpx import Client
from authlib.integrations.httpx_client import OAuth2Client

if os.getenv("LOCALHOST_TEST"):
    GAMEBRAIN_URL = "http://localhost:8000"
else:
    GAMEBRAIN_URL = "https://foundry.local/gamebrain"
GAMEBOARD_URL = "https://foundry.local/gameboard/api"

GB_CLIENT_ID_UNPRIV = "gb-test-client-unpriv"
GB_CLIENT_SECRET_UNPRIV = "50c6cad84df145e3bcf101df76c31fcd"
GB_CLIENT_ID_PRIV = "gb-test-client-priv"
GB_CLIENT_SECRET_PRIV = "c358f2840ee747e7b2d405225740755b"
GB_ADMIN_API_KEY = "a" * 32
GS_CLIENT_ID = "gs-test-client"
GS_CLIENT_SECRET = "ffeba3ea22a4494fa46f5c6d93811774"
TOKEN_URL = "https://foundry.local/identity/connect/token"
CA_CERT_PATH = "/usr/local/share/ca-certificates/foundry-appliance-root-ca.crt"
GAME_CLIENT_ID = "game-client"
GAME_CLIENT_SECRET = "a7f467ab5bf14e23b81c67a38fb97136"
GAMEBOARD_SCRIPT_CLIENT = "gameboard-script-test"
GAMEBOARD_SCRIPT_SECRET = "9f776c36bd2746c3946bbd4f15ac3f7a"
TOPOMOJO_API_BASE_URL = "https://foundry.local/topomojo/api"
TOPOMOJO_X_API_KEY = "hjQC_zO2tijlbjPnjIy258fW3J8E3Gc5"

TEST_USER_1 = "testplayer1@foundry.local"
TEST_USER_1_ID = "2f470899-f6f9-4041-a1f7-7b96727894df"
TEST_TEAM_1 = "97f176fa52c84b8aa048d62fdb800097"
TEST_USER_2 = "testplayer4@foundry.local"
TEST_USER_2_ID = "624ee970-33a6-48c8-850e-a51702a36887"
TEST_TEAM_2 = "3cf53975e2d94f57a06e9b058fdefbb2"
TEST_SESSION_TIME = "testplayersession@foundry.local"
TEST_SESSION_USER_ID = "44131b54-4610-4df7-aa9c-bdeba144fd45"
TEST_PASS = "TESTPASS"
TEST_WORKSPACE = "f0f9c45076d34941a32d7baa4c4b3261"
FOUNDRY_ADMIN_EMAIL = "administrator@foundry.local"
FOUNDRY_ADMIN_PASSWORD = "foundry"
TEST_SHIP_WORKSPACE = "956591cdcf5045628c98114a76111411"
TEST_CONTESTED_WORKSPACE = "426334acb1f54ed9907bf1188169265c"
TEST_UNCONTESTED_WORKSPACE = "f0f9c45076d34941a32d7baa4c4b3261"

GAME_ID = "ee7bc919d07941ccad9b80576022a8b3"


def register_gamespace(
    workspace_id: str, expiration_time: str, team_members: list[dict]
):
    """
    team_members: Each dict contains 'id' and 'approvedName' keys.
    """
    post_data = {
        "resourceId": workspace_id,
        "graderKey": "",
        "graderUrl": "",
        "variant": 0,
        "playerCount": len(team_members),
        "maxAttempts": 3,
        "maxMinutes": 20,
        "points": 100,
        "allowReset": True,
        "allowPreview": True,
        "startGamespace": True,
        "expirationTime": expiration_time,
        "players": [
            {"subjectId": player["id"], "subjectName": player["approvedName"]}
            for player in team_members
        ],
    }
    endpoint = "gamespace"

    client = Client(headers={"X-API-Key": TOPOMOJO_X_API_KEY}, verify=False)
    response = client.post(
        url=f"{TOPOMOJO_API_BASE_URL}/{endpoint}", json=post_data)

    print(f"TopoMojo Register Gamespace response: {response.status_code}")

    return response


def main():
    # SSL warnings pollute the console too much.
    warnings.filterwarnings("ignore")

    missing_api_key_session = Client(verify=False)
    invalid_api_key_session = Client(
        headers={"X-API-Key": "x" * 32}, verify=False)
    gamebrain_admin_session = Client(
        headers={"X-API-Key": GB_ADMIN_API_KEY}, verify=False
    )

    gamestate_session = OAuth2Client(
        GS_CLIENT_ID, GS_CLIENT_SECRET, verify=False)
    gamestate_session.fetch_token(TOKEN_URL)

    gamebrain_priv_session = OAuth2Client(
        GB_CLIENT_ID_PRIV, GB_CLIENT_SECRET_PRIV, verify=False
    )
    gamebrain_priv_session.fetch_token(TOKEN_URL)

    user_session = OAuth2Client(
        GAME_CLIENT_ID, GAME_CLIENT_SECRET, verify=False)
    user_session.fetch_token(
        TOKEN_URL, username=TEST_USER_1, password=TEST_PASS)

    session_time_test_admin = OAuth2Client(
        GAMEBOARD_SCRIPT_CLIENT, GAMEBOARD_SCRIPT_SECRET, verify=False
    )
    session_time_test_admin.fetch_token(
        TOKEN_URL, username=FOUNDRY_ADMIN_EMAIL, password=FOUNDRY_ADMIN_PASSWORD
    )

    gs_expiration_time = datetime.datetime.now() + datetime.timedelta(minutes=20)

    ship_gamespace_team_1 = register_gamespace(
        TEST_SHIP_WORKSPACE,
        gs_expiration_time.isoformat(),
        [{"id": TEST_TEAM_1, "approvedName": "Test Player 1"}],
    ).json()
    print(ship_gamespace_team_1)

    uncon_gamespace_team_1 = register_gamespace(
        TEST_UNCONTESTED_WORKSPACE,
        gs_expiration_time.isoformat(),
        [{"id": TEST_TEAM_1, "approvedName": "Test Player 1"}],
    ).json()
    print(uncon_gamespace_team_1)

    ship_gamespace_team_2 = register_gamespace(
        TEST_SHIP_WORKSPACE,
        gs_expiration_time.isoformat(),
        [{"id": TEST_USER_1_ID, "approvedName": "Test Player 2"}],
    ).json()
    print(ship_gamespace_team_2)

    uncon_gamespace_team_2 = register_gamespace(
        TEST_UNCONTESTED_WORKSPACE,
        gs_expiration_time.isoformat(),
        [{"id": TEST_USER_2_ID, "approvedName": "Test Player 2"}],
    ).json()
    print(uncon_gamespace_team_2)

    # workspace_id: str, expiration_time: str, team_members: List[Dict], total_points: int
    deploy_data = {
        "game_id": GAME_ID,
        "teams": {
            TEST_TEAM_1: {
                "team_name": "Test Team 1",
                "gamespaces": [
                    ship_gamespace_team_1["id"],
                    uncon_gamespace_team_1["id"],
                ],
            },
            TEST_TEAM_2: {
                "team_name": "Test Team 2",
                "gamespaces": [
                    ship_gamespace_team_2["id"],
                    uncon_gamespace_team_2["id"],
                ],
            },
        },
    }

    print("Deploying shared game.")
    resp = gamebrain_admin_session.post(
        url=f"{GAMEBRAIN_URL}/admin/deploy", json=deploy_data
    )
    deployment = resp.json()
    print(deployment)

    user_token = user_session.token["access_token"]

    print("Testing get_team endpoint")
    json_data = {
        "user_token": user_token,
        "server_container_hostname": f"server-{deployment[TEST_TEAM_1][-1]}",
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
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/000000/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Unlocking location 1 (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/111111/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Invalid unlock (expect invalid)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/LocationUnlock/123456/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Jump to current location (expect failure")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/Jump/location1/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Jump to invalid location (expect failure")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/Jump/invalid/{TEST_TEAM_1}")
    # pprint.pprint(resp.json())

    print("Jump to locked location (expect failure")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/Jump/location3/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Jump to unlocked location (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/Jump/cantina/{TEST_TEAM_1}")
    pprint.pprint(resp.json())

    print("Getting GameData again")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/{TEST_TEAM_1}")
    pprint.pprint(resp.json())

    print("Scan new location (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/ScanLocation/{TEST_TEAM_1}")
    # pprint.pprint(resp.json())

    print("Changing power mode (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/PowerMode/explorationMode/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Marking comm event complete (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/CommEventCompleted/{TEST_TEAM_1}"
    )
    # pprint.pprint(resp.json())

    print("Extend the antenna (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/ExtendAntenna/{TEST_TEAM_1}"
    )

    print("Retract the antenna (expect success)")
    resp = gamestate_session.get(
        f"{GAMEBRAIN_URL}/GameData/RetractAntenna/{TEST_TEAM_1}"
    )

    print("Getting GameData")
    resp = gamestate_session.get(f"{GAMEBRAIN_URL}/GameData/{TEST_TEAM_1}")
    # pprint.pprint(resp.json())
    game_data = resp.json()
    current_status = game_data.get("currentStatus")
    print(json.dumps(current_status, indent=2))

    time.sleep(10.0)

    resp = gamebrain_admin_session.post(f"{GAMEBRAIN_URL}/admin/undeploy")
    print(resp.json())

    # Testing out grabbing the session remaining time for the Gamebrain deploy endpoint.

    # First, clear out the test user's session to make sure the state is fresh.
    resp = session_time_test_admin.get(
        f"{GAMEBOARD_URL}/players", params={"gid": GAME_ID, "WantsGame": True}
    )
    data = resp.json()
    print(f"Players GET response: {data}")
    if resp.status_code not in range(200, 300):
        print(
            f"Player call failed with status code {resp.status_code} and data: {data}"
        )
        return
    for session in data:
        print(session)
        if session["userId"] == TEST_SESSION_USER_ID:
            player_id = session["id"]
            resp = session_time_test_admin.delete(
                f"{GAMEBOARD_URL}/player/{player_id}/session"
            )
            if resp.status_code not in range(200, 300):
                print(
                    f"Player delete failed with status code {resp.status_code} "
                    f"and data: {data}"
                )
            else:
                print(f"Deleted player {player_id}")

    # Then create a new session.
    resp = session_time_test_admin.post(
        f"{GAMEBOARD_URL}/player",
        json={"gameId": GAME_ID, "userId": TEST_SESSION_USER_ID},
    )
    data = resp.json()
    print(f"Player POST response: {data}")
    player_id = data["id"]
    print(f"Created player {player_id}")

    # Then start the created session.
    resp = session_time_test_admin.put(
        f"{GAMEBOARD_URL}/player/{player_id}/start")
    print(f"player/start status: {resp.status_code}")
    data = resp.json()
    expiration = data["sessionEnd"]
    team_id = data["teamId"]
    print(f"Session expiration time: {expiration}")

    while True:
        time.sleep(10.0)
        resp = gamestate_session.get(
            f"{GAMEBRAIN_URL}/gamestate/team_active/{team_id}")
        result = resp.json()
        print(f"Checked if team {team_id} is active: {result}")
        if not result:
            break


if __name__ == "__main__":
    main()
