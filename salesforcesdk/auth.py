"""Two ways to authenticate to Salesforce.

SalesforceAuth     connected-app client-credentials flow (needs a client id/secret
                   in the environment). What the m3ter -> Salesforce webhook
                   handlers use. Right for an unattended process such as a Flask app.

SalesforceCliAuth  reuse the local `sf` CLI session for an org alias. No secrets in
                   the repo or the env; the CLI holds the OAuth session and refreshes
                   it. Right for a script run from a terminal that is already logged
                   in (`sf org login web --alias m3ter`). Same trick revenue-cloud-config
                   uses.

Both expose the same three things the SDK needs: access_token, instance_url and
get_headers(), so a SalesforceObject does not care which one it was given.
"""
import json
import shutil
import subprocess

import requests


class SalesforceAuth:
    def __init__(self, client_id, client_secret, token_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url

        self.access_token = None
        self.instance_url = None

    def authenticate(self):
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(self.token_url, data=payload, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.text}")

        data = response.json()
        self.access_token = data['access_token']
        self.instance_url = data['instance_url']

        return self

    def get_headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}


class SalesforceCliAuth:
    """Get a session token for an org alias from the `sf` CLI.

    Two subprocess calls (sf >= 2.136 redacts the token from `org display`, so
    the token comes from the dedicated `org auth show-access-token` command):
        sf org auth show-access-token --target-org <alias> --json   -> accessToken
        sf org display               --target-org <alias> --json   -> instanceUrl
    """
    REDACTED = '[REDACTED]'

    def __init__(self, alias='m3ter'):
        self.alias = alias
        self.access_token = None
        self.instance_url = None
        self.username = None

    def _run_sf(self, *args):
        if shutil.which('sf') is None:
            raise RuntimeError('The Salesforce CLI (`sf`) is not on the PATH of this shell.')
        try:
            result = subprocess.run(
                ['sf', *args, '--target-org', self.alias, '--json'],
                check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"`sf {' '.join(args)} --target-org {self.alias}` failed. "
                f"Logged in?  sf org login web --alias {self.alias}\n{e.stderr}") from e
        return json.loads(result.stdout).get('result', {})

    def authenticate(self):
        token = self._run_sf('org', 'auth', 'show-access-token').get('accessToken') or ''
        if not token or token.startswith(self.REDACTED):
            raise RuntimeError(f'No usable access token for org alias {self.alias!r}; '
                               f'try: sf org login web --alias {self.alias}')
        display = self._run_sf('org', 'display')
        if not display.get('instanceUrl'):
            raise RuntimeError(f'`sf org display` returned no instanceUrl for {self.alias!r}')

        self.access_token = token
        self.instance_url = display['instanceUrl']
        self.username = display.get('username')
        return self

    def get_headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}
