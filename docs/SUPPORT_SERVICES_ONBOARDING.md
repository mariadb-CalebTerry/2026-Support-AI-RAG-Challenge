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
.\src\start_tunnels.ps1
```

_(Note: On Windows, you may need to run this in a PowerShell instance run as Administrator, depending on your local execution policies)._

Once running, the following services are available to you:

- **RAG REST API**: `http://localhost:8000` (Swagger UI at `/docs`)
- **MCP Server**: `http://localhost:8002`

---

## 3. Test the RAG API Connection

Before configuring MCP, verify that the RAG API is accessible and functioning properly:

1. **Test API Health**:
   Open your browser or use curl to check the API status:

   ```bash
   curl http://localhost:8000/health
   ```

   You should see a healthy response indicating the service is running.

2. **Generate Authentication Token**:
   Create a token for MCP authentication:

   ```bash
   curl -X POST http://localhost:8000/token \
     -H "Content-Type: application/json" \
     -d '{"username": "admin@example.com", "password": "admin123"}'
   ```

   Save the returned token for the next step.

---

## 4. Connect your IDE via MCP

The Model Context Protocol (MCP) allows your local AI coding assistant (like Windsurf) to natively understand and query the MariaDB vector database.

**Important**: Ensure the RAG API is running and accessible before proceeding with MCP configuration.

To connect your IDE to the MariaDB Support AI RAG system:

1. **Configure MCP**:
   Add an SSE (Server-Sent Events) connection to `http://localhost:8002/mcp` in your IDE's MCP configuration.

   _Example for Windsurf (`~/.codeium/windsurf/mcp_config.json`):_

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
   Use the token generated in the previous step. If your IDE requires headers in the `mcp_config.json`, add an `Authorization: Bearer <TOKEN>` header. Otherwise, you can ask your AI assistant to authenticate itself using the `http://localhost:8000/token` endpoint.

3. **Verify the Connection**:
   In your IDE chat panel, ask the AI:

   > "What tools are available from the `rag-mcp` server?"

   If connected properly, it will list tools like `mcp9_rag_generation`, `mcp9_search_vector_store`, and `mcp9_execute_sql`.

---

## 5. Querying the Support Data

The environment has already been pre-loaded with **1000 high-value Zendesk tickets** (including attachments) and their associated **Organizations** and **Users**.

You can now use your IDE's AI assistant to debug customer issues using historical data.

**Example Prompts to try in your IDE:**

- _"Search the vector database for troubleshooting steps regarding Galera cluster node evictions."_
- _"Based on previous tickets from Amdocs, what specific configuration flags do they typically use for MaxScale?"_
- _"Query the RAG pipeline for the most common solutions to 'Error 1040: Too many connections'."_

The AI will intelligently search the MariaDB native vector storage, read the attached `my.cnf` files or error logs from past tickets, and synthesize an accurate answer.

---

## Modifying the Environment (Advanced)

If you are a developer looking to extend the RAG pipeline, check out the `src/ingest_zendesk.py` script. It handles the idempotent extraction of Zendesk data, markdown summarization, and direct streaming to the RAG API for Docling-Ray vector embedding.
