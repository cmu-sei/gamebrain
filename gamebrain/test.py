import gbsettings

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import yaml


def main():
    settings = gbsettings.load_settings("./settings.yaml")

    identity = settings.settings.identity
    token_url = f'{identity.base_url}{identity.token_endpoint}'

    client = BackendApplicationClient(client_id=identity.client_id)
    session = OAuth2Session(client=client)
    token = session.fetch_token(token_url=token_url, client_id=identity.client_id, client_secret=identity.client_secret, verify=settings.settings.ca_cert_path)

    print(token)

    r = session.get("https://foundry.local/topomojo/api/gamespaces")
    print(r.status_code)


if __name__ == "__main__":
    main()
