from m3utils.printme import *
from m3sdk import *
import pandas as pd
import os
import requests
from requests.auth import HTTPBasicAuth


####################################################################################
# Function to post to m3ter workflow
####################################################################################
def post_to_m3ter(url, payload):

    auth = HTTPBasicAuth(os.getenv('m3sh_username'), os.getenv('m3sh_password'))
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, json=payload, auth=auth, headers=headers)

    return response.status_code, response.text


####################################################################################
# This function handles authentication
####################################################################################
def m3ter_authenticate():
    printme('Warning - using environment: ' + os.getenv('ENVIRONMENT'), color='yellow', dots=True)
    auth = M3terAuth(api_key=os.getenv('apiKey'), api_secret=os.getenv('apiSecret'))
    _auth = auth.authenticate()
    client = M3terClient(org_id=os.getenv('ORGANIZATION'), token=auth.token)
    return client


####################################################################################
# Functions used to implement the business logic
####################################################################################
def get_account_plan(accountplans=None, accountId=None, planId=None):
    for accountplan in accountplans:
        if accountplan.accountId == accountId and accountplan.planId == planId:
            return accountplan.id

    return None

def build_salesforce_payload(bill=None, accountplans=None, client=None):
    """Build Salesforce payload from m3ter bill."""

    # Index overages and grants by (productId, planId, pricingId) for O(1) lookup
    overages = {
        (li['productId'], li['planId'], li['pricingId']): li
        for li in bill.lineItems if li['lineItemType'] == 'OVERAGE_USAGE'
    }

    grants = {
        (li['productId'], li['planId']): li
        for li in bill.lineItems if li['lineItemType'] == 'USAGE_CREDIT'
    }

    # Build line items from USAGE entries only
    lineitems = []
    for li in bill.lineItems:
        if li['lineItemType'] != 'USAGE' or li.get('quantity', 0) <= 0:
            continue

        key = (li['productId'], li['planId'], li['pricingId'])
        overage = overages.get(key, {})
        grant = grants.get((li['productId'], li['planId']), {})

        overage_qty = overage.get('quantity', 0)
        grant_qty = grant.get('quantity', 0)

        lineitems.append({
            'Description': li.get('description', ''),
            'accountPlanId': get_account_plan(accountplans, bill.accountId, li['planId']) or '',
            'balanceId': li.get('balanceId', ''),
            'StartDateTime': li.get('servicePeriodStartDate', ''),
            'EndDateTime': li.get('servicePeriodEndDate', ''),
            'Unit': li.get('unit', ''),
            'DebitedUnits': max(li.get('quantity', 0) - grant_qty, 0),
            'ConsumptionUnits': li.get('quantity', 0),
            'OverageUnits': overage_qty,
            'RatingDecisionDateTime': li.get('servicePeriodEndDate', ''),
            'NetUnitRate': li.get('averageUnitPrice', 0),
            'OverageQuantity': overage_qty,
            'TierQuantity': overage_qty,
            'TotalAmount': overage_qty * li.get('averageUnitPrice', 0),
            'OverageAmount': overage_qty * li.get('averageUnitPrice', 0),
            'TotalUsedQuantity': li.get('quantity', 0),
            'CurrencyIsoCode': 'USD',
        })

    return {
        'accountId': bill.accountId,
        'accountCode': bill.accountCode,
        'billDate': bill.billDate,
        'startDate': bill.startDate,
        'endDate': bill.endDate,
        'currency': bill.currency,
        'lineitems': lineitems,
    }

def handle_event(payload):
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_rows', None)

    ###################################################################################################################
    # Step 1: Authenticate to m3ter
    ###################################################################################################################
    client = m3ter_authenticate()

    ###################################################################################################################
    # Step 2: Validate we are dealing with the correct organization
    ###################################################################################################################
    org_id = payload['orgId']
    if org_id != os.getenv('ORGANIZATION'):
        printme('Organization ID does not match', color='red', dots=True)
        return
    else:
        printme('Organization ID matches', color='green', dots=True)

    ###################################################################################################################
    # Step 3: If the event is as expected, use it to generate the correct payload for m3sh workflow
    ###################################################################################################################
    event_name = payload['eventName']
    if event_name in ['billing.bill.updated', 'billing.bill.created']:
        printme('Event type is as expected: ' + payload['eventName'], color='green', dots=True)

        try:
            bill = Bill.get(client=client, id=payload['event']['new.id'])
            printme('Bill change detected for accountCode: ' + payload['event']['new.accountCode'], color='white', dots=True)

            accountplans = AccountPlan.list(client=client)

            payload = build_salesforce_payload(bill=bill, accountplans=accountplans, client=client)
            print(payload)

            url = 'https://9a3a717e-40a0-4b92-9163-70db1110f21c.webhook.m3ter.com/ddb23c5f-24c6-47ba-8b36-5b0b8a10a791'
            status, response = post_to_m3ter(url, payload)

            printme(f"Status: {status}", color='green', dots=False, time=True)

        except Exception:
            printme('Could not retrieve bill info', color='red', dots=True)
            return False

    return True
