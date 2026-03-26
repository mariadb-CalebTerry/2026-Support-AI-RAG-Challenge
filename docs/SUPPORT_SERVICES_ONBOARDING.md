# MariaDB Support AI RAG Workspace

Welcome to the MariaDB Support AI RAG Challenge environment! This repository sets up a state-of-the-art Retrieval-Augmented Generation (RAG) platform tailored for the MariaDB Support & Services organization. 

It provides an isolated GCP VM running MariaDB AI RAG 1.1 (Beta) that contains semantic embeddings of real Zendesk support tickets, organizations, and user data. This empowers support engineers, DPAs, and SREs to query deep technical context quickly and efficiently.

## Prerequisites

Before starting, ensure you have the following installed on your local workstation:
1. [Google Cloud CLI (gcloud)](https://cloud.google.com/sdk/docs/install)
2. A modern IDE with an MCP client (e.g., Codeium Windsurf, Cursor, VSCode with MCP extensions).

---

## 1. Authenticate to Google Cloud

The environment lives in a shared GCP project. To access the underlying VM and establish secure tunnels, you first need to authenticate via the gcloud CLI.

Open your terminal or PowerShell and run:

```bash
gcloud auth login
```

Follow the browser prompt to log in with your MariaDB corporate credentials.

Make sure your active project is set to the correct GCP project hosting the RAG environment:
```bash
# If you know the specific project ID, set it here:
gcloud config set project [YOUR_PROJECT_ID]
```

---

## 2. Start the IAP Tunnels

For security, the GCP VM does not have public IP access. Instead, we use Google's Identity-Aware Proxy (IAP) to tunnel local traffic directly to the containerized services on the VM.

We have a provided PowerShell script that automates the creation of these tunnels. This forwards the remote RAG API and the MCP Server directly to your `localhost`.

Run the following command from the root of this repository:

```powershell
# Starts background tunnels for ports 8000 (RAG API) and 8002 (MCP Server)
.\pipeline\start_tunnels.ps1
```

*(Note: On Windows, you may need to run this in a PowerShell instance run as Administrator, depending on your local execution policies).*

Once running, the following services are available to you:
- **RAG REST API**: `http://localhost:8000` (Swagger UI at `/docs`)
- **MCP Server**: `http://localhost:8002`

---

## 3. Connect your IDE via MCP

The Model Context Protocol (MCP) allows your local AI coding assistant (like Windsurf) to natively understand and query the MariaDB vector database.

To connect your IDE to the MariaDB Support AI RAG system:

1. **Configure MCP**:
   Add an SSE (Server-Sent Events) connection to `http://localhost:8002/mcp` in your IDE's MCP configuration. 

   *Example for Windsurf (`~/.codeium/windsurf/mcp_config.json`):*
   ```json
   {
     "mcpServers": {
       "rag-mcp": {
         "url": "http://localhost:8002/mcp"
       }
     }
   }
   ```

2. **Authenticate the Server**:
   Depending on your IDE's implementation, you may need to pass an authentication token. You can generate a token by making a POST request to `http://localhost:8000/token` with the credentials:
   - **Username**: `admin@example.com`
   - **Password**: `admin123`

   *(If your IDE requires headers in the `mcp_config.json`, add an `Authorization: Bearer <TOKEN>` header. Otherwise, you can ask your AI assistant to authenticate itself using the `http://localhost:8000/token` endpoint).*

3. **Verify the Connection**:
   In your IDE chat panel, ask the AI:
   > "What tools are available from the `rag-mcp` server?"
   
   If connected properly, it will list tools like `mcp9_rag_generation`, `mcp9_search_vector_store`, and `mcp9_execute_sql`.

---

## 4. Querying the Support Data

The environment has already been pre-loaded with **1000 high-value Zendesk tickets** (including attachments) and their associated **Organizations** and **Users**.

You can now use your IDE's AI assistant to debug customer issues using historical data. 

**Example Prompts to try in your IDE:**
- *"Search the vector database for troubleshooting steps regarding Galera cluster node evictions."*
- *"Based on previous tickets from Amdocs, what specific configuration flags do they typically use for MaxScale?"*
- *"Query the RAG pipeline for the most common solutions to 'Error 1040: Too many connections'."*

The AI will intelligently search the MariaDB native vector storage, read the attached `my.cnf` files or error logs from past tickets, and synthesize an accurate answer.

---

## Modifying the Environment (Advanced)

If you are a developer looking to extend the RAG pipeline, check out the `pipeline/ingest_zendesk.py` script. It handles the idempotent extraction of Zendesk data, markdown summarization, and direct streaming to the RAG API for Docling-Ray vector embedding.
