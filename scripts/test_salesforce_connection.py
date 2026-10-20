import os
from salesforcesdk import *
import requests

def get_objects(auth):
    # List all available objects
    url = f"{auth.instance_url}/services/data/v59.0/sobjects"
    response = requests.get(url, headers=auth.get_headers())
    objects = response.json()

    # Search for anything with "usage" in the name
    for obj in objects['sobjects']:
        if 'usage' in obj['name'].lower():
            print(obj['name'])


def main():
    salesforce = SalesforceAuth(client_id=os.getenv("SF_CONSUMER_KEY"),
                          client_secret=os.getenv("SF_CONSUMER_SECRET"),
                          token_url=os.getenv("SF_INSTANCE_URL")).authenticate()

    accounts = Account(auth=salesforce)
    print(accounts.get_all(limit=10))

    # Examine usage objects
    #get_objects(auth=salesforce)

    print('\nTrying to get UsageSummaries ...')

    # Simple query to test
    url = f"{salesforce.instance_url}/services/data/v60.0/sobjects"
    response = requests.get(url, headers=salesforce.get_headers())
    objects = response.json()

    for obj in objects['sobjects']:
        name_lower = obj['name'].lower()
        if 'usage' in name_lower or 'summary' in name_lower or 'entitlement' in name_lower:
            print(f"{obj['name']} - queryable: {obj['queryable']}")
    #usagesummaries = UsageSummary(auth=salesforce)
    #print(usagesummaries.get_all(limit=50))





if __name__ == "__main__":
    main()

