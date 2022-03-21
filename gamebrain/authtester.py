from oauthlib.oauth2 import LegacyApplicationClient
import requests
from requests_oauthlib import OAuth2Session


CLIENT_ID = "gb-test-client"
CLIENT_SECRET = "cbcf8df872684a82b370f461513ad0b3"
TOKEN_URL = "https://foundry.local/identity/connect/token"
CA_CERT_PATH = "/usr/local/share/ca-certificates/foundry-appliance-root-ca.crt"

TEST_USER = "testplayer1@foundry.local"
TEST_PASS = "7FB77QEc8yhDxAa!"


def main():
    session = OAuth2Session(client=LegacyApplicationClient(client_id=CLIENT_ID))

    session.fetch_token(token_url=TOKEN_URL,
                        username=TEST_USER,
                        password=TEST_PASS,
                        client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        verify=CA_CERT_PATH)

    session.get("https://localhost:8000/authtest", verify=False)



if __name__ == "__main__":
    main()
