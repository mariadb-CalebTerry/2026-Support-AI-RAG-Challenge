import os
import json
import asyncio
import argparse
import sys
import httpx
from typing import Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv

# Load configuration from src/config.env
load_dotenv("src/config.env")

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_pass(label: str, detail: str = ""):
    print(f"  {GREEN}PASS{RESET} {label}" + (f" - {detail}" if detail else ""))


def print_fail(label: str, detail: str = ""):
    print(f"  {RED}FAIL{RESET} {label}" + (f" - {detail}" if detail else ""))


def print_section(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")


def print_tool(name: str, desc: str):
    print(f"    - {BOLD}{name}{RESET}: {desc[:80]}")


async def get_auth_token(rag_api_url: str, username: str, password: str) -> str:
    """Authenticate against the RAG API /token endpoint to get a JWT."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{rag_api_url}/token",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


class MCPTester:
    def __init__(self, auth_token: str, base_url: str = "http://127.0.0.1:8002/mcp"):
        self.auth_token = auth_token
        self.base_url = base_url
        self.passed = 0
        self.failed = 0

    def _record(self, success: bool, label: str, detail: str = ""):
        if success:
            self.passed += 1
            print_pass(label, detail)
        else:
            self.failed += 1
            print_fail(label, detail)

    async def _call_tool(self, session: ClientSession, name: str, args: dict) -> tuple:
        """Call a tool and return (success, response_text)."""
        try:
            result = await session.call_tool(name, arguments=args)
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                if "Unauthorized" in text or "Error" in text.split("\n")[0]:
                    return False, text
                return True, text
            return True, "(empty response)"
        except Exception as e:
            return False, str(e)

    def _print_full_response(self, label: str, text: str):
        """Print a tool response with full pretty-printed JSON."""
        try:
            data = json.loads(text)
            formatted = json.dumps(data, indent=2, default=str)
        except (json.JSONDecodeError, TypeError):
            formatted = text
        print(f"  {CYAN}{label} response:{RESET}")
        for line in formatted.split("\n"):
            print(f"    {line}")

    async def run_tests(self):
        print(f"\n{BOLD}MariaDB AI RAG - MCP Server Test Suite{RESET}")
        print(f"Server URL: {self.base_url}")
        print(f"Auth token: {self.auth_token[:30]}...{self.auth_token[-10:]}")

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        try:
            async with streamablehttp_client(
                url=self.base_url, headers=headers, timeout=30
            ) as (read, write, _get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # ---- 1. Connection & Tool Discovery ----
                    print_section("1. Connection & Tool Discovery")

                    tools = await session.list_tools()
                    tool_names = [t.name for t in tools.tools]
                    self._record(
                        len(tool_names) > 0,
                        "list_tools",
                        f"{len(tool_names)} tools found",
                    )
                    for tool in tools.tools:
                        print_tool(tool.name, tool.description or "")

                    # ---- 2. Health Check ----
                    print_section("2. Health Check")

                    ok, text = await self._call_tool(session, "health_check", {})
                    self._record(ok, "health_check")
                    self._print_full_response("health_check", text)

                    # ---- 3. Database Tools ----
                    print_section("3. Database Tools")

                    ok, text = await self._call_tool(session, "list_databases", {})
                    self._record(ok, "list_databases")
                    self._print_full_response("list_databases", text)

                    if "list_tables" in tool_names:
                        ok, text = await self._call_tool(
                            session,
                            "list_tables",
                            {"database_name": "support_ai_rag_db"},
                        )
                        self._record(ok, "list_tables", _summarize(text))

                    schema_tool = next(
                        (t for t in ["get_table_schema", "describe_table"] if t in tool_names),
                        None,
                    )
                    if schema_tool:
                        ok, text = await self._call_tool(
                            session,
                            schema_tool,
                            {
                                "database_name": "support_ai_rag_db",
                                "table_name": "documents",
                            },
                        )
                        self._record(ok, f"{schema_tool} (documents)", _summarize(text))

                    if "execute_sql" in tool_names:
                        ok, text = await self._call_tool(
                            session,
                            "execute_sql",
                            {
                                "database_name": "support_ai_rag_db",
                                "sql_query": "SELECT COUNT(*) AS total_documents FROM documents",
                            },
                        )
                        self._record(ok, "execute_sql (COUNT)", _summarize(text))

                    # ---- 4. Vector Tools ----
                    print_section("4. Vector Tools")

                    if "list_vector_stores" in tool_names:
                        ok, text = await self._call_tool(
                            session,
                            "list_vector_stores",
                            {"database_name": "support_ai_rag_db"},
                        )
                        self._record(ok, "list_vector_stores")
                        self._print_full_response("list_vector_stores", text)

                    search_tool = next(
                        (t for t in ["search_vector_store", "vector_search"] if t in tool_names),
                        None,
                    )
                    if search_tool:
                        ok, text = await self._call_tool(
                            session,
                            search_tool,
                            {
                                "database_name": "support_ai_rag_db",
                                "vector_store_name": "vdb_tbl",
                                "query": "MariaDB replication lag troubleshooting",
                                "top_k": 3,
                            },
                        )
                        self._record(ok, search_tool, _summarize(text, max_len=120))

                    # ---- 5. RAG Tools ----
                    print_section("5. RAG Tools")

                    if "rag_generation" in tool_names:
                        ok, text = await self._call_tool(
                            session,
                            "rag_generation",
                            {
                                "query": "What are common causes of Galera cluster node evictions?",
                                "top_k": 3,
                            },
                        )
                        self._record(ok, "rag_generation")
                        self._print_full_response("rag_generation", text)

                    # ---- 6. Server Info ----
                    print_section("6. Server Info")

                    if "get_server_status" in tool_names:
                        ok, text = await self._call_tool(
                            session, "get_server_status", {}
                        )
                        self._record(ok, "get_server_status")
                        self._print_full_response("get_server_status", text)

        except Exception as e:
            print(f"\n{RED}Connection Error: {e}{RESET}")
            import traceback

            traceback.print_exc()
            self.failed += 1

        # ---- Summary ----
        print_section("Summary")
        total = self.passed + self.failed
        print(
            f"  Total: {total}  |  {GREEN}Passed: {self.passed}{RESET}  |  {RED}Failed: {self.failed}{RESET}"
        )
        if self.failed == 0:
            print(f"\n  {GREEN}{BOLD}All tests passed!{RESET}")
        else:
            print(f"\n  {YELLOW}{BOLD}Some tests failed. Check output above.{RESET}")
        return self.failed == 0


def _summarize(text: str, max_len: int = 80) -> str:
    """Return a compact one-line summary of a response."""
    try:
        data = json.loads(text)
        return json.dumps(data, default=str)[:max_len]
    except (json.JSONDecodeError, TypeError):
        one_line = text.replace("\n", " ").strip()
        return one_line[:max_len] + ("..." if len(one_line) > max_len else "")


async def main():
    parser = argparse.ArgumentParser(description="Test MariaDB AI RAG MCP Tools")
    parser.add_argument(
        "--token", help="Provide a pre-generated auth token (skips auto-login)"
    )
    parser.add_argument(
        "--url", default="http://127.0.0.1:8002/mcp", help="MCP server URL"
    )
    parser.add_argument(
        "--rag-url", default=None, help="RAG API URL for token generation"
    )
    parser.add_argument("--username", default=None, help="Override RAG API username")
    parser.add_argument("--password", default=None, help="Override RAG API password")
    args = parser.parse_args()

    rag_api_url = args.rag_url or os.getenv("RAG_API_URL", "http://localhost:8000")
    username = args.username or os.getenv("RAG_API_USER")
    password = args.password or os.getenv("RAG_API_PASSWORD")

    # Step 1: Obtain auth token
    if args.token:
        token = args.token
        print(f"Using provided token.")
    else:
        if not username or not password:
            print(
                f"{RED}Error: No credentials. Set RAG_API_USER/RAG_API_PASSWORD in config.env or use --token.{RESET}"
            )
            sys.exit(1)
        print(f"Authenticating as {username} against {rag_api_url}...")
        try:
            token = await get_auth_token(rag_api_url, username, password)
            print(f"{GREEN}Token acquired successfully.{RESET}")
        except httpx.HTTPStatusError as e:
            print(f"{RED}Auth failed ({e.response.status_code}): {e.response.text}{RESET}")
            sys.exit(1)
        except Exception as e:
            print(f"{RED}Auth failed: {e}{RESET}")
            print(
                f"{YELLOW}Hint: Is the RAG API running at {rag_api_url}? Try: curl {rag_api_url}/health{RESET}"
            )
            sys.exit(1)

    # Step 2: Run MCP tests
    tester = MCPTester(auth_token=token, base_url=args.url)
    success = await tester.run_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
