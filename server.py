"""
EventBot MCP Server
-------------------
Exposes two tools to Claude (or any MCP client):

  list_all_attendees()          – returns every registered attendee
  get_attendee_details(query)   – semantic search for a specific person / role / org

Backend API: http://13.126.130.56:8003
Transport  : Streamable HTTP  →  connect claude.ai to  http://<host>:8000/mcp
"""

from mcp.server.fastmcp import FastMCP
import httpx

BASE_URL = "http://13.126.130.56:8003"

mcp = FastMCP(
    name="EventBot Attendees",
    instructions=(
        "You have access to the AlumnxAI Labs event attendee database. "
        "Use list_all_attendees to show everyone, and get_attendee_details "
        "to look up a specific person by name, role, or organisation."
    ),
)

# Bind to all interfaces so the server is reachable externally
mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8000


# ── helpers ──────────────────────────────────────────────────────────────────

def _format_attendee(a: dict, show_score: bool = False) -> str:
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
    if show_score:
        lines.append(f"Match Score : {a['score']:.2f}")
    return "\n".join(lines)


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_all_attendees() -> str:
    """
    Return the full list of every registered event attendee.

    Includes name, role, organisation, experience level, bio, and
    LinkedIn/website URL for each person.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": "business professional event attendee", "limit": 50},
        )
        resp.raise_for_status()

    data = resp.json()
    attendees = data.get("results", [])
    total = data.get("total", len(attendees))

    if not attendees:
        return "No attendees found in the database."

    blocks = [f"Registered attendees: {total}\n{'=' * 50}"]
    for idx, a in enumerate(attendees, 1):
        blocks.append(f"\n#{idx}  (ID: {a['id']})\n{_format_attendee(a)}")
        blocks.append("-" * 50)

    return "\n".join(blocks)


@mcp.tool()
async def get_attendee_details(query: str, limit: int = 5) -> str:
    """
    Search for a specific attendee and return their full profile.

    Uses semantic search so natural-language queries work well.

    Args:
        query : Name, role, organisation, skill, or any keyword —
                e.g. "Vijender", "dentist", "cloud services", "IIT Bombay"
        limit : Max number of results to return (default 5, max 50)
    """
    limit = max(1, min(limit, 50))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()

    data = resp.json()
    attendees = data.get("results", [])

    if not attendees:
        return f"No attendees found matching: '{query}'"

    blocks = [
        f"Found {len(attendees)} result(s) for '{query}'\n"
        f"(expanded query: {data.get('expanded_query', query)})\n"
        f"{'=' * 50}"
    ]
    for idx, a in enumerate(attendees, 1):
        blocks.append(f"\n#{idx}  (ID: {a['id']})\n{_format_attendee(a, show_score=True)}")
        blocks.append("-" * 50)

    return "\n".join(blocks)


# ── entry-point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Streamable HTTP transport – required for claude.ai custom connectors.
    # Connect claude.ai to: http://<this-machine-ip>:8000/mcp
    mcp.run(transport="streamable-http")
