# backend/core/db.py
from typing import Any, Dict
from backend.core.supabase_client import get_supabase
from backend.core.website import WebsiteContext

class ScopedTable:
    def __init__(self, table: str, website: WebsiteContext, privileged: bool = False):
        self.table = table
        self.website = website
        self.sb = get_supabase(privileged=privileged)

    def select(self, columns="*"):
        return self.sb.table(self.table).select(columns).eq("website_id", self.website.website_id)

    def insert(self, data: Dict[str, Any]):
        data = {**data, "website_id": self.website.website_id}
        return self.sb.table(self.table).insert(data)

    def update(self, data: Dict[str, Any]):
        return self.sb.table(self.table).update(data).eq("website_id", self.website.website_id)

    def delete(self):
        return self.sb.table(self.table).delete().eq("website_id", self.website.website_id)

def scoped_table(table: str, website: WebsiteContext, privileged: bool = False) -> ScopedTable:
    return ScopedTable(table, website, privileged)
