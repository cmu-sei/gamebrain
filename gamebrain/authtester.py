import os
import time
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

TEST_USER_1 = "testplayer1@foundry.local"
TEST_TEAM_1 = "a538cd94ef92416bbb547ee924056edb"
TEST_USER_2 = "testplayer4@foundry.local"
TEST_TEAM_2 = "30d5396dcb324a43a85368054622d09b"
TEST_PASS = "7FB77QEc8yhDxAa!"

GAME_ID = "f63c8e41fd994e16bad08075dd2a666c"


def main():
    # SSL warnings pollute the console too much.
    warnings.filterwarnings("ignore")

    session = OAuth2Client(GB_CLIENT_ID_ADMIN, GB_CLIENT_SECRET_ADMIN, verify=False)

    session.fetch_token(TOKEN_URL)

    resp = session.put(f"{GAMEBRAIN_URL}/admin/headlessip/{TEST_TEAM_1}",
                       params={"headless_ip": "10.10.10.10"})
    print(resp.json())

    # resp = session.put(f"{GAMEBRAIN_URL}/admin/headlessip/{TEST_TEAM_2}",
    #                    params={"headless_ip": "10.10.10.11"})
    # print(resp.json())

    resp = session.post(f"{GAMEBRAIN_URL}/admin/secrets/{TEST_TEAM_1}",
                        json=["secret_1", "secret_2", "secret_3"])
    print(resp.json())

    # resp = session.post(f"{GAMEBRAIN_URL}/admin/secrets/{TEST_TEAM_2}",
    #                     json=["secret_4", "secret_5", "secret_6"])
    # print(resp.json())

    resp = session.post(f"{GAMEBRAIN_URL}/admin/media",
                        json={"video1": "example.com/video1",
                              "video2": "example.com/video2"})
    print(resp.json())

    session = OAuth2Client(GB_CLIENT_ID_PRIV, GB_CLIENT_SECRET_PRIV, verify=False)
    session.fetch_token(TOKEN_URL)

    resp = session.get(f"{GAMEBRAIN_URL}/privileged/deploy/{GAME_ID}/{TEST_TEAM_1}", timeout=60.0)
    print(resp.json())

    # resp = session.get(f"{GAMEBRAIN_URL}/privileged/deploy/{GAME_ID}/{TEST_TEAM_2}", timeout=60.0)
    # print(resp.json())

    # Give the target VM some time to come up and start the agent service.
    # time.sleep(60)

    resp = session.post(f"{GAMEBRAIN_URL}/privileged/event/{TEST_TEAM_1}",
                        params={"event_message": "Mission 2"})
    print(resp.json())

    session = OAuth2Client(GS_CLIENT_ID, GS_CLIENT_SECRET, verify=False)
    session.fetch_token(TOKEN_URL)

    # resp = session.get(f"{GAMEBRAIN_URL}/gamestate/team_data")

    # print(resp.json())


if __name__ == "__main__":
    main()
