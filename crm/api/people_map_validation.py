"""Pure validation shared by research output and reviewed chart saves."""
import json
from urllib.parse import urlsplit


def safe_url(value, linkedin=False):
    value = str(value or "").strip()
    if not value:
        return ""
    if not value.startswith(("https://", "http://")):
        value = "https://" + value
    p = urlsplit(value)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Use a valid public website URL")
    if linkedin and (p.hostname.lower() not in ("linkedin.com", "www.linkedin.com") or not p.path.startswith("/in/")):
        raise ValueError("Use a LinkedIn person URL beginning linkedin.com/in/")
    return value


def validate_people(value, researched=False):
    people = json.loads(value) if isinstance(value, str) else value
    if not isinstance(people, list) or len(people) > 60:
        raise ValueError("A people map must contain at most 60 people")
    result, ids = [], set()
    for index, item in enumerate(people):
        if not isinstance(item, dict):
            raise ValueError("Invalid person")
        def text(key, length=240):
            return str(item.get(key) or "").strip()[:length]
        ident = text("id", 80) or f"person-{index + 1}"
        if ident in ids or not text("name"):
            raise ValueError("Each person needs a name and a unique ID")
        ids.add(ident)
        sources = item.get("sources") or []
        if not isinstance(sources, list):
            raise ValueError("Sources must be a list")
        sources = [safe_url(s) for s in sources[:8] if s]
        if researched and not sources:
            raise ValueError("Research people must have source URLs")
        evidence = text("relationship_evidence", 1000)
        basis = text("relationship")
        # Research evidence remains a claim until a human confirms it.
        if researched:
            basis = "sourced" if basis in ("confirmed", "sourced") and evidence and sources else "unknown"
        if basis not in ("confirmed", "sourced", "inferred", "unknown"):
            basis = "unknown"
        manager = text("manager_id", 80)
        if basis == "unknown":
            manager = ""
        result.append(dict(id=ident, name=text("name"), title=text("title"),
            department=text("department") or "Unassigned", linkedin_url=safe_url(text("linkedin_url", 1000), True),
            manager_id=manager, relationship=basis, relationship_evidence=evidence,
            sources=sources, notes=text("notes", 2000), contact=text("contact")))
    by_id = {p["id"]: p for p in result}
    for p in result:
        if p["manager_id"] and p["manager_id"] not in by_id:
            raise ValueError("A manager must be another person in this map")
        seen, node = set(), p
        while node:
            if node["id"] in seen:
                raise ValueError("Reporting relationships cannot form a cycle")
            seen.add(node["id"])
            node = by_id.get(node["manager_id"])
    return result
