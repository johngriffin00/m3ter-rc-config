"""What every Salesforce-writing brick in the bill sync shares.

The m3sh sub-workflows all have the same shape: SOQL for the record by its
natural key -> HasResults? -> create (and remember it is new) | strip Status
and update. SalesforceStep gives a brick the three pieces — a query helper,
find-or-create with dry-run honoured, and the date conversion — so each brick
is only its payload and its key.

Dates: an m3ter service period ends at midnight EXCLUSIVE
(2026-11-01T00:00:00.000Z); Revenue Cloud usage records end at the last second
INCLUSIVE. m3sh did DateTime.dateSub(String.left(EndDateTime, 22) + "Z", 1,
"SECONDS") — 2026-10-31T23:59:59Z. inclusive_end() is that. SOQL date-time
literals are unquoted and carry no millis: 2026-10-14T00:00:00Z.
"""
import json

from salesforcesdk import SalesforceObject
from sync.core.context import SF_API_VERSION
from sync.core.dates import inclusive_end, sf_datetime  # noqa: F401  (re-exported for the bricks)
from sync.core.soql import clean
from sync.core.step import Step


class SalesforceStep(Step):
    sobject = None          # e.g. 'UsageSummary'
    # Sent on create, never on update. Status: m3sh's "Remove Status — we don't
    # want to reset it to New". GrantBindingTargetId: Salesforce refuses to
    # change it once set ("This field can't be edited", 403).
    CREATE_ONLY = ('Status', 'GrantBindingTargetId')

    def sf(self, ctx):
        obj = SalesforceObject(ctx.sf_auth, api_version=SF_API_VERSION)
        obj.object_name = self.sobject
        return obj

    def soql(self, ctx, soql):
        return [clean(r) for r in self.sf(ctx).query_all(soql)]

    def find_or_create(self, ctx, label, where: str, payload: dict, select=('Id',)):
        """m3sh's SOQL -> HasResults -> create | strip Status + update.

        Returns (record id, is_new, the record as found or {} if created). On
        a dry run the SOQL is real, the write is printed, and a fake id is
        returned so later bricks can chain.
        """
        found = self.soql(ctx, f"SELECT {', '.join(select)} FROM {self.sobject} WHERE {where}")
        if len(found) > 1:
            self.say(ctx, f'WARNING {len(found)} {self.sobject} records match {label}; using the first, as m3sh did')
        if found:
            record_id, is_new = self.create_or_update(ctx, label, found[0]['Id'], payload)
            return record_id, is_new, found[0]
        record_id, is_new = self.create_or_update(ctx, label, None, payload)
        return record_id, is_new, {}

    def create_or_update(self, ctx, label, existing_id, payload: dict):
        """Create when there is no record id, else update it with the CREATE_ONLY
        fields stripped. Returns (id, is_new)."""
        if existing_id:
            update = {k: v for k, v in payload.items() if k not in self.CREATE_ONLY}
            if ctx.dry_run:
                self.say(ctx, f'DRY RUN would update {self.sobject} {existing_id} for {label}: {json.dumps(update)}')
            else:
                self.sf(ctx).update(existing_id, update)
                self.say(ctx, f'updated {self.sobject} {existing_id} for {label}')
            return existing_id, False
        if ctx.dry_run:
            self.say(ctx, f'DRY RUN would create {self.sobject} for {label}: {json.dumps(payload)}')
            return f'dry-run-{self.sobject.lower()}', True
        result = self.sf(ctx).create(payload)
        self.say(ctx, f"created {self.sobject} {result['id']} for {label}")
        return result['id'], True
