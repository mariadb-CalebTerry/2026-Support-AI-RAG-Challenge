import os
import requests
import json
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
RAG_API_USER = os.getenv("RAG_API_USER", "admin")
RAG_API_PASSWORD = os.getenv("RAG_API_PASSWORD", os.getenv("DB_PASSWORD", "mariadb_rag_password_2024"))

class SharedPlatformClient:
    def __init__(self):
        self.base_url = RAG_API_URL
        self.token = self._authenticate()

    def _authenticate(self):
        """Authenticate with the RAG API and get a JWT token."""
        print(f"Authenticating with RAG API at {self.base_url}...")
        try:
            response = requests.post(
                f"{self.base_url}/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"username": RAG_API_USER, "password": RAG_API_PASSWORD}
            )
            response.raise_for_status()
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            print(f"Failed to authenticate: {e}")
            sys.exit(1)

    def _orchestrate_generation(self, query, metadata_filters=None):
        """Call the orchestration generation endpoint with the query and filters."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "metadata_filters": metadata_filters or {}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/orchestrate/generation",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Generation request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"API Response: {e.response.text}")
            return None

    def _format_and_print_response(self, response_data, persona_name):
        """Format and print the LLM response and the retrieved citations."""
        if not response_data:
            print("No response generated.")
            return

        print("\n" + "="*80)
        print(f" PERSONA: {persona_name.upper()}")
        print("="*80)
        
        print("\n🤖 AI RESPONSE:")
        print("-" * 40)
        print(response_data.get("generation", "No generation provided."))
        
        print("\n📚 CITED SOURCES / CONTEXT USED:")
        print("-" * 40)
        
        retrieved_chunks = response_data.get("retrieved_chunks", [])
        if not retrieved_chunks:
            print("No sources were retrieved to answer this query.")
        else:
            for i, chunk in enumerate(retrieved_chunks, 1):
                metadata = chunk.get("metadata", {})
                score = chunk.get("score", 0.0)
                
                print(f"\n[{i}] Source: {metadata.get('source', 'Unknown')} (Score: {score:.4f})")
                
                # Print relevant metadata dynamically
                meta_str = []
                if metadata.get("ticket_id"): meta_str.append(f"Ticket #{metadata['ticket_id']}")
                if metadata.get("ticket_type"): meta_str.append(f"Type: {metadata['ticket_type']}")
                if metadata.get("technical_area"): meta_str.append(f"Area: {metadata['technical_area']}")
                if metadata.get("status"): meta_str.append(f"Status: {metadata['status']}")
                
                if meta_str:
                    print(f"    Metadata: | {' | '.join(meta_str)} |")
                
                print(f"    Content Preview:")
                # Truncate content to 200 chars for readability
                content = chunk.get("content", "").replace('\n', ' ')
                preview = (content[:200] + '...') if len(content) > 200 else content
                print(f"    > {preview}")
                
        print("="*80 + "\n")

    # --- Persona-Specific Methods ---

    def search_support_resolutions(self, query):
        """
        Support Persona: Focuses on quick error code lookups and solved basic issues.
        """
        filters = {
            "complexity": "basic",
            "status": "solved"
        }
        print(f"\n[Support Persona] Searching for: '{query}'")
        print(f"Applying filters: {filters}")
        response = self._orchestrate_generation(query, filters)
        self._format_and_print_response(response, "Support Staff")

    def search_dpa_performance(self, query):
        """
        DPA Persona: Focuses on performance optimization techniques and benchmarks.
        """
        filters = {
            "technical_area": "performance"
        }
        print(f"\n[DPA Persona] Searching for: '{query}'")
        print(f"Applying filters: {filters}")
        response = self._orchestrate_generation(query, filters)
        self._format_and_print_response(response, "Database Performance Analyst")

    def search_ps_implementations(self, query):
        """
        PS Persona: Focuses on customer scenarios, how-to guides, and best practices.
        """
        filters = {
            "ticket_type": "howto"
        }
        print(f"\n[PS Persona] Searching for: '{query}'")
        print(f"Applying filters: {filters}")
        response = self._orchestrate_generation(query, filters)
        self._format_and_print_response(response, "Professional Services Consultant")

    def search_sre_infrastructure(self, query):
        """
        SRE Persona: Focuses on advanced outage recovery, replication, and monitoring.
        """
        filters = {
            "technical_area": "replication",
            "complexity": "advanced"
        }
        print(f"\n[SRE Persona] Searching for: '{query}'")
        print(f"Applying filters: {filters}")
        response = self._orchestrate_generation(query, filters)
        self._format_and_print_response(response, "Site Reliability Engineer")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MariaDB Shared AI RAG Platform Client")
    parser.add_argument("--query", type=str, required=True, help="The query to ask the AI RAG platform")
    parser.add_argument("--persona", type=str, choices=["support", "dpa", "ps", "sre"], required=True, 
                        help="The persona to emulate (support, dpa, ps, sre)")
    
    args = parser.parse_args()
    
    client = SharedPlatformClient()
    
    if args.persona == "support":
        client.search_support_resolutions(args.query)
    elif args.persona == "dpa":
        client.search_dpa_performance(args.query)
    elif args.persona == "ps":
        client.search_ps_implementations(args.query)
    elif args.persona == "sre":
        client.search_sre_infrastructure(args.query)
