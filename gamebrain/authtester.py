from oauthlib.oauth2 import BackendApplicationClient, LegacyApplicationClient
from requests_oauthlib import OAuth2Session

GB_CLIENT_ID_UNPRIV = "gb-test-client-unpriv"
GB_CLIENT_SECRET_UNPRIV = "46ec755e2bab4070a9634214620389b5"
GB_CLIENT_ID_PRIV = "gb-test-client-priv"
GB_CLIENT_SECRET_PRIV = "cbcf8df872684a82b370f461513ad0b3"
GS_CLIENT_ID = "gs-test-client"
GS_CLIENT_SECRET = "43bcc0072ab54a349368b20f1c31b0cd"
TOKEN_URL = "https://foundry.local/identity/connect/token"
CA_CERT_PATH = "/usr/local/share/ca-certificates/foundry-appliance-root-ca.crt"

TEST_USER_1 = "testplayer1@foundry.local"
TEST_USER_2 = "testplayer4@foundry.local"
TEST_PASS = "7FB77QEc8yhDxAa!"

GAME_ID = "f63c8e41fd994e16bad08075dd2a666c"


def main():
    session = OAuth2Session(client=LegacyApplicationClient(client_id=GB_CLIENT_ID_UNPRIV))

    session.fetch_token(token_url=TOKEN_URL,
                        username=TEST_USER_1,
                        password=TEST_PASS,
                        client_id=GB_CLIENT_ID_UNPRIV,
                        client_secret=GB_CLIENT_SECRET_UNPRIV,
                        verify=CA_CERT_PATH)

    resp = session.get(f"https://localhost:8000/gamebrain/deploy/{GAME_ID}", verify=False)

    print(resp.json())

    session = OAuth2Session(client=LegacyApplicationClient(client_id=GB_CLIENT_ID_UNPRIV))

    session.fetch_token(token_url=TOKEN_URL,
                        username=TEST_USER_2,
                        password=TEST_PASS,
                        client_id=GB_CLIENT_ID_UNPRIV,
                        client_secret=GB_CLIENT_SECRET_UNPRIV,
                        verify=CA_CERT_PATH)

    resp = session.get(f"https://localhost:8000/gamebrain/deploy/{GAME_ID}", verify=False)

    print(resp.json())

    session = OAuth2Session(client=BackendApplicationClient(client_id=GB_CLIENT_ID_PRIV))

    session.fetch_token(token_url=TOKEN_URL,
                        client_id=GB_CLIENT_ID_PRIV,
                        client_secret=GB_CLIENT_SECRET_PRIV,
                        verify=CA_CERT_PATH)

    vm_id = next(iter(resp.json()["vms"]))

    resp = session.put(f"https://localhost:8000/gamebrain/changenet/{vm_id}", verify=False,
                       params={"new_net": "bridge-net"})
    print(resp.json())

    session = OAuth2Session(client=BackendApplicationClient(client_id=GS_CLIENT_ID))

    session.fetch_token(token_url=TOKEN_URL,
                        client_id=GS_CLIENT_ID,
                        client_secret=GS_CLIENT_SECRET,
                        verify=CA_CERT_PATH)

    resp = session.get(f"https://localhost:8000/gamestate/team_data", verify=False)

    print(resp.json())


if __name__ == "__main__":
    main()
