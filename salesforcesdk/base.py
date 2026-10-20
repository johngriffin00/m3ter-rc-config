import requests


class SalesforceObject:
    object_name = None  # Override in subclasses
    api_version = 'v60.0'

    def __init__(self, auth, api_version=None):
        self.auth = auth
        # Revenue Cloud Usage Management objects (TransactionUsageEntitlement,
        # OrderItemRateCardEntry, ...) only exist from the mid-60s API versions,
        # so callers can pin a newer version than the SDK default.
        if api_version:
            self.api_version = api_version
        self.base_url = f"{auth.instance_url}/services/data/{self.api_version}"

    def query(self, soql):
        """Run a SOQL query (first page only — see query_all)"""
        url = f"{self.base_url}/query"
        params = {'q': soql}
        response = requests.get(url, headers=self.auth.get_headers(), params=params)
        return response.json()

    def query_all(self, soql):
        """Run a SOQL query and return every record, following nextRecordsUrl.

        Salesforce pages query results (2,000 records by default). The first page
        carries `done: false` and a `nextRecordsUrl` when there are more; this
        keeps fetching until `done` is true. Errors come back as a list, not a
        dict, so they are raised rather than silently returned.
        """
        url = f"{self.base_url}/query"
        response = requests.get(url, headers=self.auth.get_headers(), params={'q': soql})
        data = response.json()
        if isinstance(data, list):  # Salesforce error shape: [{"message": ..., "errorCode": ...}]
            raise RuntimeError(f"SOQL failed ({response.status_code}): {data}\n  {soql}")
        records = list(data.get('records', []))
        while not data.get('done', True):
            response = requests.get(f"{self.auth.instance_url}{data['nextRecordsUrl']}",
                                    headers=self.auth.get_headers())
            data = response.json()
            records.extend(data.get('records', []))
        return records

    def get(self, record_id):
        """Get a single record by ID"""
        url = f"{self.base_url}/sobjects/{self.object_name}/{record_id}"
        response = requests.get(url, headers=self.auth.get_headers())
        return response.json()

    def get_all(self, fields=None, limit=None):
        """Get all records, optionally specifying fields and limit"""
        fields_str = ', '.join(fields) if fields else 'Id, Name'
        soql = f"SELECT {fields_str} FROM {self.object_name}"
        if limit:
            soql += f" LIMIT {limit}"
        return self.query(soql)

    def create(self, data):
        """Create a new record; returns {'id': ..., 'success': True, ...}.

        Salesforce answers 201 with the new Id, or 400 with a LIST of errors
        ([{"message": ..., "errorCode": ..., "fields": [...]}]); the latter is
        raised so a caller never mistakes it for a record.
        """
        url = f"{self.base_url}/sobjects/{self.object_name}"
        headers = {**self.auth.get_headers(), 'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 201:
            raise RuntimeError(f"create {self.object_name} failed ({response.status_code}): {response.text}\n  {data}")
        return response.json()

    def update(self, record_id, data):
        """Update an existing record (PATCH); returns True, or raises with Salesforce's errors."""
        url = f"{self.base_url}/sobjects/{self.object_name}/{record_id}"
        headers = {**self.auth.get_headers(), 'Content-Type': 'application/json'}
        response = requests.patch(url, headers=headers, json=data)
        if response.status_code != 204:
            raise RuntimeError(f"update {self.object_name} {record_id} failed ({response.status_code}): {response.text}\n  {data}")
        return True

    def delete(self, record_id):
        """Delete a record"""
        url = f"{self.base_url}/sobjects/{self.object_name}/{record_id}"
        response = requests.delete(url, headers=self.auth.get_headers())
        return response.status_code == 204

    def describe(self):
        """Get object metadata/schema"""
        url = f"{self.base_url}/sobjects/{self.object_name}/describe"
        response = requests.get(url, headers=self.auth.get_headers())
        return response.json()
