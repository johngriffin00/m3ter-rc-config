"""Step 2 — the m3ter Account for the Salesforce Account on the order.

The m3sh "Order: Account creation" sub-workflow, brick for brick:

    ExternalMappingExists(Salesforce/Account/<sf AccountId>)?
      yes -> GetM3terEntity(Account, mapping.m3terId)            # reuse
      no  -> ReadSalesforceObject(Account)                       # (already in the snapshot)
             ApplyTransformation(sfAccount -> m3Account)         # build_payload() below
             CreateM3terEntity(Account)
             CreateExternalMapping(Account <-> sf AccountId)

Why an ExternalMapping and not just the code? The code IS the Salesforce Id
(John's choice, the Entrust convention) so you could find the account by code
— but the mapping is what m3ter's own Salesforce connector, m3sh and the
console "external ids" view all read, and it works the same for objects whose
code is NOT the Salesforce Id (plans, account plans). One mechanism everywhere.

What goes into the m3ter Account:
    code          Salesforce Account Id  (unique, 18 chars, no whitespace — m3ter is happy)
    name          Salesforce Account Name
    emailAddress  first Contact's Email — m3ter requires one; a Salesforce Account has none
    currency      the unit the negotiated rates are expressed in (RateUnitOfMeasure.UnitCode)
    address       Billing address, field by field
    customFields  the Salesforce Id and Name again, for anyone looking at the account in
                  the m3ter console (custom fields show; the external mapping is a tab away)
"""
from m3sdk import Account, ExternalMapping

from sync.core.step import Step

EXTERNAL_SYSTEM = 'Salesforce'     # the m3sh workflows use exactly this spelling
PLACEHOLDER_EMAIL = 'no-contact@{code}.invalid'


class EnsureAccount(Step):
    name = 'account'

    def run(self, ctx):
        sf_account = ctx.snapshot['account']
        sf_id = sf_account['Id']

        # 1. Look before you create.
        mappings = ExternalMapping.find(ctx.m3, EXTERNAL_SYSTEM, 'Account', sf_id)
        if mappings:
            account = Account.get(ctx.m3, mappings[0].m3terId)
            self.say(ctx, f'found via external mapping: {account.name} ({account.id})')
            ctx.state['account'] = account
            return account

        # 1b. No mapping, but an account with this code may still exist (created by
        #     hand, or a previous run that died between create and mapping). Adopt it
        #     and add the missing mapping rather than failing on a duplicate code.
        account = next((a for a in Account.list(ctx.m3) if a.code == sf_id), None)
        if account:
            self.say(ctx, f'found by code without a mapping: {account.name} ({account.id}) — adding mapping')
        else:
            account = self.create_or_pretend(ctx, Account, **self.build_payload(ctx))

        self.create_or_pretend(ctx, ExternalMapping,
                               externalSystem=EXTERNAL_SYSTEM, externalTable='Account', externalId=sf_id,
                               m3terEntity='Account', m3terId=account.id)
        ctx.state['account'] = account
        return account

    @staticmethod
    def build_payload(ctx) -> dict:
        """The m3sh ApplyTransformation: Salesforce Account -> m3ter Account payload."""
        sf = ctx.snapshot['account']
        contacts = ctx.snapshot.get('contacts', [])
        email = next((c['Email'] for c in contacts if c.get('Email')), None)
        if not email:
            email = PLACEHOLDER_EMAIL.format(code=sf['Id'].lower())
            ctx.say(f'account: WARNING no contact email on {sf["Name"]}; using {email}')

        rates = ctx.snapshot.get('order_item_rates', [])
        currency = next((r['RateUnitOfMeasure']['UnitCode'] for r in rates
                         if r.get('RateUnitOfMeasure')), None)

        address = {
            'addressLine1': sf.get('BillingStreet'),
            'locality': sf.get('BillingCity'),
            'region': sf.get('BillingState'),
            'postCode': sf.get('BillingPostalCode'),
            'country': sf.get('BillingCountry'),
        }
        address = {k: v for k, v in address.items() if v}

        payload = {
            'code': sf['Id'],
            'name': sf['Name'],
            'emailAddress': email,
            'customFields': {'sfAccountId': sf['Id'], 'sfAccountName': sf['Name']},
        }
        if currency:
            payload['currency'] = currency
        if address:
            payload['address'] = address
        return payload
