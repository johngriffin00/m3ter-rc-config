from m3utils.printme import *
from m3sdk import *
from google.test_google_email import get_gmail_service, create_message, send_email
import os
import json
import time
import pandas as pd
from tabulate import tabulate
from dotenv import load_dotenv
import os
import requests
from requests.auth import HTTPBasicAuth


####################################################################################
# This function allows you to send an email when an event is triggered
####################################################################################

def email(subject=None, body=None):
    # Authenticate and construct the Gmail service.
    service = get_gmail_service()

    # Define the email parameters.
    sender = "john@m3ter.com"  # Your Gmail address
    recipient = ["john@m3ter.com, john@dinerbytes.com"]  # Recipient's email address
    subject = subject
    body = body

    # Create and send the email.
    message = create_message(sender, recipient, subject, body)
    send_email(service, 'me', message)


####################################################################################
# These are the functions that interact with m3sh workflow
####################################################################################
def post_to_m3ter(url, payload):
    auth = HTTPBasicAuth('test', 'test')
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, json=payload, auth=auth, headers=headers)

    return response.status_code, response.text


####################################################################################
# These are the functions we use to run billing jobs
####################################################################################

def load_config(filename):
    with open(filename) as jsonFile:
        jsonObject = json.load(jsonFile)
        jsonFile.close()

    return jsonObject


def run_config(cfg, client):
    # Loop over products and create
    if "BillJobs" in cfg:
        for _billjob in cfg['BillJobs']:
            payload = BillJob.replace_codes(client, **_billjob)
            print('Creating billjob: ', payload)
            billjob = BillJob.create(client=client, **payload)
            print('Created billjob: ', billjob.id)
            # Sleep in between
            #time.sleep(5)


####################################################################################
# This function handles authentication
####################################################################################

def m3ter_authenticate():
    printme('Warning - using environment: ' + os.getenv('ENVIRONMENT'), color='yellow', dots=True)

    if os.getenv('ENVIRONMENT') == 'gamma':
        auth = M3terAuthGamma(api_key=os.getenv('apiKey'), api_secret=os.getenv('apiSecret'))
    else:
        auth = M3terAuth(api_key=os.getenv('apiKey'), api_secret=os.getenv('apiSecret'))

    _auth = auth.authenticate()

    if os.getenv('ENVIRONMENT') == 'gamma':
        client = M3terClientGamma(org_id=os.getenv('ORGANIZATION'), token=auth.token)
    else:
        client = M3terClient(org_id=os.getenv('ORGANIZATION'), token=auth.token)

    return client


####################################################################################
# Functions used to implement the business logic
####################################################################################
def get_pricings(client=None, lineitem=None, plans=None, pricings=None):
    token_rate = 0
    usd_rate = 0

    # Use the lineitem pricingId to get the start date
    for pricing in pricings:
        if pricing.id == lineitem['pricingId']:
            pricing_start_date = pricing.startDate
            break

    # Get the plan name
    for plan in plans:
        if plan.id == lineitem['planId']:
            plan_code = plan.code
            break

    if 'tok' in plan_code:
        new_plan_code = plan_code.replace('tok', 'usd')
    elif 'usd' in plan_code:
        new_plan_code = plan_code.replace('usd', 'tok')

    # Get the planId for the new plan code
    for plan in plans:
        if plan.code == new_plan_code:
            new_plan_id = plan.id
            break

    if lineitem['currency'] == 'TOK':
        for band in lineitem['usagePerPricingBand']:
            token_rate = band['unitPrice']

        # Now get the USD rate from pricings
        for pricing in pricings:
            if pricing.planId == new_plan_id and pricing.startDate == pricing_start_date:
                for band in pricing.pricingBands:
                    usd_rate = band['unitPrice']
                break

    elif lineitem['currency'] == 'USD':
        for band in lineitem['usagePerPricingBand']:
            usd_rate = band['unitPrice']

        # Now get the TOK rate from pricings
        for pricing in pricings:
            if pricing.planId == new_plan_id and pricing.startDate == pricing_start_date:
                for band in pricing.pricingBands:
                    token_rate = band['unitPrice']
                break

    return token_rate, usd_rate


def get_account_plan(accountplans=None, accountId=None, planId=None):
    for accountplan in accountplans:
        if accountplan.accountId == accountId and accountplan.planId == planId:
            return accountplan.id

    return None


def apply_grants(billStartDate='', balances=None, productId=None, unit=None, quantity=0):
    grant_quantity = 0
    for balance in balances:
        if 'productIds' in balance and len(balance['productIds']) > 0:
            if productId in balance['productIds']:
                if balance['startDate'][:10] <= billStartDate <= balance['endDate'][:10]:
                    if unit == 'GB':
                        if balance['currency'] == 'GBs':
                            # We have found a matching grant
                            grant_quantity = balance['totalCreditAmount']
                    elif unit == 'Hours':
                        if balance['currency'] == 'Hrs':
                            # We have found a matching grant
                            grant_quantity = balance['totalCreditAmount']

    return max(quantity - grant_quantity, 0)


def apply_commitments(billStartDate='', balances=None, productId=None, quantity=0, tok_rate=0, usd_rate=0):
    for balance in balances:
        if 'productIds' in balance and len(balance['productIds']) > 0:
            if productId in balance['productIds']:
                if balance['startDate'][:10] <= billStartDate <= balance['endDate'][:10]:
                    # Valid balance found
                    if 'remainingAmount' not in balance:
                        balance['remainingAmount'] = balance['totalCreditAmount']

                    # Calculate commitment quantity
                    if balance['currency'] == 'TOK':
                        commitment_quantity = balance['remainingAmount'] / tok_rate if tok_rate > 0 else 0
                    elif balance['currency'] == 'USD':
                        commitment_quantity = balance['remainingAmount'] / usd_rate if usd_rate > 0 else 0
                    else:
                        commitment_quantity = 0

                    # Apply the balance (THIS MUST BE INSIDE THE IF BLOCKS)
                    if commitment_quantity >= quantity:
                        rate = tok_rate if balance['currency'] == 'TOK' else usd_rate
                        balance['remainingAmount'] -= quantity * rate
                        return 0, balances
                    else:
                        quantity -= commitment_quantity
                        balance['remainingAmount'] = 0

    return quantity, balances


####################################################################################
# This is the event handler
####################################################################################

def on_bill_change(client=None, event=None):
    printme('Bill change detected for accountCode: ' + event['event']['new.accountCode'], color='white', dots=True)

    ###################################################################################################################
    # Step 1: Authenticate to m3ter
    ###################################################################################################################
    client = m3ter_authenticate()

    ###################################################################################################################
    # Step 2: Validate the bill details
    ###################################################################################################################
    printme('Validating bill info', color='white', dots=True)

    valid_bill = False
    try:
        bill = Bill.get(client=client, id=event['event']['new.id'])
        print('Current version is: ', bill.version)
        valid_bill = True
    except:
        printme('Could not retrieve bill info', color='red', dots=True)
        return False

    ###################################################################################################################
    # Step 3: Loop through the line items and calculate the correct consumed and overage units
    ###################################################################################################################
    _balance_list = []
    _balance = dict()
    printme('Retrieving balance data', color='white', dots=True, time=True)
    balances = Balance.list(client=client)
    for balance in balances:
        if balance.accountId == bill.accountId:
            #_balance['id'] = balance.id
            _balance['code'] = balance.code
            _balance['description'] = balance.description
            _balance['startDate'] = balance.startDate
            _balance['endDate'] = balance.endDate
            _balance['currency'] = balance.currency
            if hasattr(balance, 'productIds'):
                _balance['productIds'] = balance.productIds
            else:
                _balance['productIds'] = []
            summary = TransactionSummary.list(client=client, balanceId=balance.id)
            _balance['totalCreditAmount'] = summary['totalCreditAmount']
            _balance['totalDebitAmount'] = summary['totalDebitAmount']
            _balance['initialCreditAmount'] = summary['initialCreditAmount']
            _balance['balanceConsumed'] = summary['balanceConsumed']
            _balance_list.append(_balance.copy())

    _balances = _balance_list.copy()
    printme('Processing line items', color='white', dots=True, time=True)

    # Retrieve the config data so that we can get pricings
    plantemplates = PlanTemplate.list(client=client)
    plans = Plan.list(client=client)
    accountplans = AccountPlan.list(client=client)
    pricings = Pricing.list(client=client)

    for lineitem in bill.lineItems:
        if lineitem['lineItemType'] == 'USAGE':
            # Retrieve TOK and USD pricings for this product
            tok_rate, usd_rate = get_pricings(client=client, lineitem=lineitem, plans=plans, pricings=pricings)

            # Get the accountPlanId from the lineitem
            lineitem['accountPlanId'] = get_account_plan(accountplans=accountplans, accountId=bill.accountId, planId=lineitem['planId'])

            # Adjust quantity for any grants that exist for this product - grants impact quantity only
            # This should automatically work for quantity commmitments also
            #printme('Apply grants', color='white', dots=True, time=True)
            post_grant_quantity = apply_grants(billStartDate=bill.startDate, balances=_balances, productId = lineitem['productId'], unit=lineitem['unit'], quantity=lineitem['quantity'])
            if lineitem['currency'] == 'TOK':
                post_grant_amount = post_grant_quantity * tok_rate
            elif lineitem['currency'] == 'USD':
                post_grant_amount = post_grant_quantity * usd_rate

            # Adjust quantity for any Token commitments that exist for this product
            #printme('Apply commitments', color='white', dots=True, time=True)
            post_commitment_quantity, _balances = apply_commitments(billStartDate=bill.startDate, balances=_balances, productId = lineitem['productId'], quantity=post_grant_quantity, tok_rate=tok_rate, usd_rate=usd_rate)
            if lineitem['currency'] == 'TOK':
                post_commitment_amount = post_commitment_quantity * tok_rate
            elif lineitem['currency'] == 'USD':
                post_commitment_amount = post_commitment_quantity * usd_rate

            # Set final values
            final_quantity = post_commitment_quantity
            final_tok_amount = post_commitment_quantity * tok_rate
            final_usd_amount = post_commitment_quantity * usd_rate

            lineitem['tokenRate'] = tok_rate
            lineitem['usdRate'] = usd_rate
            lineitem['postGrantQuantity'] = post_grant_quantity
            lineitem['postGrantSubtotal'] = post_grant_amount
            lineitem['postCommitQuantity'] = post_commitment_quantity
            lineitem['postCommitSubtotal'] = post_commitment_amount
            lineitem['finalQuantity'] = final_quantity
            lineitem['finalTokAmount'] = final_tok_amount
            lineitem['finalUsdAmount'] = final_usd_amount

    ###################################################################################################################
    # Step 4: Output the usage data nicely to the screen
    ###################################################################################################################
    usage_list = []
    usage = dict()
    for lineitem in bill.lineItems:
        if lineitem['lineItemType'] == 'USAGE':
            usage['description'] = lineitem['description']
            usage['unit'] = lineitem['unit']
            usage['quantity'] = lineitem['quantity']
            usage['subtotal'] = lineitem['subtotal']
            usage['currency'] = lineitem['currency']
            usage['tokenRate'] = lineitem.get('tokenRate', '')
            usage['usdRate'] = lineitem.get('usdRate', '')
            usage['postGrantQuantity'] = lineitem.get('postGrantQuantity', '')
            usage['postGrantSubtotal'] = lineitem.get('postGrantSubtotal', '')
            usage['postCommitQuantity'] = lineitem.get('postCommitQuantity', '')
            usage['postCommitSubtotal'] = lineitem.get('postCommitSubtotal', '')
            usage['finalQuantity'] = lineitem.get('finalQuantity', '')
            usage['finalTokAmount'] = lineitem.get('finalTokAmount', '')
            usage['finalUsdAmount'] = lineitem.get('finalUsdAmount', '')
            usage_list.append(usage.copy())

    usage_df = pd.DataFrame(usage_list)
    # sort the dataframe by description
    usage_df = usage_df.sort_values(by=['description'])
    printme('\nUsage Line Items:', color='cyan', dots=True, time=True)
    print(tabulate(usage_df, headers='keys', tablefmt='psql'))

    ###################################################################################################################
    # Step 5: Output the balance data nicely to the screen
    ###################################################################################################################
    balance_df = pd.DataFrame(_balance_list)
    balance_df = balance_df.drop(columns=['productIds'])
    # sort the dataframe by description
    balance_df = balance_df.sort_values(by=['startDate'])
    printme('\nBalance details:', color='cyan', dots=True, time=True)
    print(tabulate(balance_df, headers='keys', tablefmt='psql'))

    ###################################################################################################################
    # Step 6: Call the workflow that sync's to m3ter with the above payload
    ###################################################################################################################
    # Usage
    url = 'https://e1edd915-262d-4014-8e4b-07ec6919dd47.webhook.m3ter.com/fc08ab42-6ad1-47bf-833a-2e6462860311'
    printme('Build payload for m3ter workflow', color='white', dots=True, time=True)
    payload = dict()
    payload['accountId'] = bill.accountId
    payload['accountCode'] = bill.accountCode
    payload['billDate'] = bill.billDate
    payload['startDate'] = bill.startDate
    payload['endDate'] = bill.endDate
    payload['currency'] = bill.currency
    payload['lineitems'] = []
    for lineitem in bill.lineItems:
        if lineitem['lineItemType'] == 'USAGE':
            item = dict()
            item['Description'] = lineitem['description']
            item['accountPlanId'] = lineitem['accountPlanId']
            item['StartDateTime'] = lineitem['servicePeriodStartDate']
            item['EndDateTime'] = lineitem['servicePeriodEndDate']
            item['Unit'] = lineitem['unit']
            item['DebitedUnits'] = max(lineitem['quantity'] - lineitem['finalQuantity'], 0)
            item['ConsumptionUnits'] = lineitem['quantity']
            item['OverageUnits'] = lineitem['finalQuantity']
            item['RatingDecisionDateTime'] = lineitem['servicePeriodEndDate']
            if lineitem['currency'] == 'TOK':
                item['NetUnitRate'] = lineitem['tokenRate']
            else:
                item['NetUnitRate'] = lineitem['usdRate']
            item['OverageQuantity'] = lineitem['finalQuantity']
            item['TierQuantity'] = lineitem['finalQuantity']
            if lineitem['currency'] == 'TOK':
                item['TotalAmount'] = lineitem['finalTokAmount']
            else:
                item['TotalAmount'] = lineitem['finalUsdAmount']
            item['OverageAmount'] = lineitem['finalUsdAmount']
            item['TotalUsedQuantity'] = lineitem['quantity']
            item['CurrencyIsoCode'] = 'USD'
            payload['lineitems'].append(item.copy())

    status, response = post_to_m3ter(url, payload)
    printme('Invoking m3ter workflow to sync to Salesforce', color='white', dots=True, time=True)
    printme(f"Status: {status}", color='green', dots=False, time=True)

    ###################################################################################################################
    # Step 6: Re-calc the bill again if supposed to run in Continuous Mode
    ###################################################################################################################
    #run_config(bill_jobs, client)

    return True


def handle_event(payload):
    client = m3ter_authenticate()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_rows', None)

    # First validate that payload is based on the correct Organization
    org_id = payload['orgId']
    if org_id != os.getenv('ORGANIZATION'):
        printme('Organization ID does not match', color='red', dots=True)
        return
    else:
        printme('Organization ID matches', color='green', dots=True)


    # Next we need to make sure the event type is one we are interested in
    event_name = payload['eventName']
    if event_name in ['billing.bill.updated', 'billing.bill.created']:
        printme('Event type is as expected: ' + payload['eventName'], color='green', dots=True)
        result = on_bill_change(client, payload)
    else:
        printme('Event type is not as expected: ' + payload['eventName'], color='red', dots=True)
        return False

    return True
