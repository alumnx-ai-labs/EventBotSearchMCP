"""
EventBot MCP Server
-------------------
Single tool: search_attendees(question, limit)

Accepts any natural-language question about event attendees and returns
matching profiles from the AlumnxAI Labs EventBot database.

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
        "Use search_attendees to answer any question about registered candidates — "
        "who they are, what they do, which organisation they belong to, and more. "
        "Pass the user's question (or the key part of it) directly as the query."
    ),
)

mcp.settings.host = "0.0.0.0"
mcp.settings.port = int(os.environ.get("PORT", 8000))

# Disable DNS rebinding protection so the server is reachable from external
# hosts (Render domain, claude.ai, etc.) not just localhost
mcp.settings.transport_security.enable_dns_rebinding_protection = False


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
    return "\n".join(lines)


@mcp.tool()
async def search_attendees(question: str, limit: int = 50) -> str:
    """
    Answer any question about registered event attendees.

    Pass the user's question as-is. The backend uses semantic search with
    LLM query expansion, so it understands natural language — ask about
    names, roles, industries, locations, skills, organisations, or anything else.

    To get ALL attendees, pass question="list all attendees" and limit=50.

    Args:
        question : Any natural-language question or keyword about candidates.
        limit    : Maximum number of results (1–50, default 50).
    """
    limit = max(1, min(limit, 50))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": question, "limit": limit},
        )
        resp.raise_for_status()

    data = resp.json()
    attendees = data.get("results", [])

    if not attendees:
        return f"No attendees found for: '{question}'"

    expanded = data.get("expanded_query") or question
    header = (
        f"Query   : {question}\n"
        f"Expanded: {expanded}\n"
        f"Results : {len(attendees)}\n"
        f"{'=' * 50}"
    )

    blocks = [header]
    for idx, a in enumerate(attendees, 1):
        blocks.append(f"\n#{idx}  (ID: {a['id']})\n{_format_attendee(a)}")
        blocks.append("-" * 50)

    return "\n".join(blocks)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
