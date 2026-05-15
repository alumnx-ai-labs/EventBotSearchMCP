"""
EventBot MCP Server
-------------------
Tools exposed to Claude:

  search_attendees   – semantic search with optional experience/org filters
  add_attendee       – index a new or updated attendee
  remove_attendee    – remove an attendee from the index
  health_check       – verify the search service is up

Backend API: http://13.126.130.56:8003
Transport  : Streamable HTTP  →  connect claude.ai to  http://<host>:<port>/mcp
"""

import os
from mcp.server.fastmcp import FastMCP
import httpx

BASE_URL = "http://13.126.130.56:8003"

mcp = FastMCP(
    name="EventBot Attendees",
    instructions=(
        "You have access to the AlumnxAI Labs event attendee database. "
        "Use search_attendees to answer any question about registered candidates. "
        "You can filter by experience level (junior/mid/senior/expert) or organisation. "
        "Use add_attendee to register a new candidate, remove_attendee to delete one, "
        "and health_check to verify the service is running."
    ),
)

mcp.settings.host = "0.0.0.0"
mcp.settings.port = int(os.environ.get("PORT", 8000))
mcp.settings.transport_security.enable_dns_rebinding_protection = False


# ── helpers ───────────────────────────────────────────────────────────────────

def _score_label(score: float) -> str:
    if score >= 0.75:
        return "Strong match"
    if score >= 0.50:
        return "Good match"
    if score >= 0.25:
        return "Partial match"
    return "Weak match"


def _format_attendee(a: dict) -> str:
    lines = [
        f"Name        : {a['full_name']}",
        f"Role        : {a['role']}",
        f"Organisation: {a['organization']}",
    ]
    if a.get("experience_level"):
        lines.append(f"Experience  : {a['experience_level']}")
    if a.get("detailed_profile"):
        lines.append(f"Profile     : {a['detailed_profile']}")
    if a.get("linkedin_url"):
        lines.append(f"LinkedIn/URL: {a['linkedin_url']}")
    if "score" in a:
        label = _score_label(a["score"])
        lines.append(f"Match       : {label} ({a['score']:.2f})")
    return "\n".join(lines)


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_attendees(
    question: str,
    experience_level: str = "",
    organization: str = "",
    limit: int = 10,
) -> str:
    """
    Search for event attendees using a natural language question.

    The backend uses semantic search with LLM query expansion, so any phrasing works.
    Optionally filter by experience level or organisation.

    Args:
        question         : Any question or keyword — name, role, skill, industry, location, etc.
        experience_level : Filter by seniority — junior | mid | senior | expert (leave blank for all)
        organization     : Filter by exact organisation name (leave blank for all)
        limit            : Number of results to return (1–50, default 10)
    """
    limit = max(1, min(limit, 50))

    params: dict = {"q": question, "limit": limit}
    if experience_level:
        params["experience_level"] = experience_level
    if organization:
        params["organization"] = organization

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/search", params=params)
        resp.raise_for_status()

    data = resp.json()
    attendees = data.get("results", [])

    if not attendees:
        return f"No attendees found for: '{question}'"

    expanded = data.get("expanded_query") or question
    header_lines = [
        f"Query    : {question}",
        f"Expanded : {expanded}",
        f"Results  : {len(attendees)}",
    ]
    if experience_level:
        header_lines.append(f"Filter   : experience = {experience_level}")
    if organization:
        header_lines.append(f"Filter   : organisation = {organization}")
    header_lines.append("=" * 50)

    blocks = ["\n".join(header_lines)]
    for idx, a in enumerate(attendees, 1):
        blocks.append(f"\n#{idx}  (ID: {a['id']})\n{_format_attendee(a)}")
        blocks.append("-" * 50)

    return "\n".join(blocks)


@mcp.tool()
async def add_attendee(
    id: str,
    full_name: str,
    email: str,
    organization: str,
    role: str,
    phone: str = "",
    experience_level: str = "",
    detailed_profile: str = "",
    linkedin_url: str = "",
) -> str:
    """
    Add a new attendee to the search index, or update an existing one.

    Safe to call multiple times for the same ID — it will update in place.

    Args:
        id               : Unique attendee ID from your main backend
        full_name        : Full name
        email            : Email address
        organization     : Company or institution
        role             : Job title / role
        phone            : Phone number (optional)
        experience_level : junior | mid | senior | expert (optional)
        detailed_profile : Free-text bio — the main search signal, highly recommended
        linkedin_url     : LinkedIn or website URL (optional)
    """
    payload: dict = {
        "id": id,
        "full_name": full_name,
        "email": email,
        "organization": organization,
        "role": role,
    }
    if phone:
        payload["phone"] = phone
    if experience_level:
        payload["experience_level"] = experience_level
    if detailed_profile:
        payload["detailed_profile"] = detailed_profile
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BASE_URL}/attendees", json=payload)
        resp.raise_for_status()

    return f"Attendee '{full_name}' (ID: {id}) indexed successfully."


@mcp.tool()
async def remove_attendee(attendee_id: str) -> str:
    """
    Remove an attendee from the search index.

    Call this when an attendee cancels their registration.

    Args:
        attendee_id : The ID used when the attendee was indexed
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(f"{BASE_URL}/attendees/{attendee_id}")
        resp.raise_for_status()

    return f"Attendee ID '{attendee_id}' removed from the index."


@mcp.tool()
async def health_check() -> str:
    """
    Check if the EventBot search service is up and running.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/health")
        resp.raise_for_status()

    data = resp.json()
    return f"Service is UP — status: {data.get('status')}, version: {data.get('version')}"


# ── entry-point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
