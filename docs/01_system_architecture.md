# Definition
This file has the following software pieces:

```mermaid
graph TD
    %% Definición del usuario y entorno externo
    User((User))
    TG[Telegram]

    %% Entorno del Servidor
    subgraph VPS [VPS]
    DB[(Conversations)]
    Streamlit[Streamlit Dashboard]
    Bot[Telegram Bot]
    Kissy[KissyEngine]
        subgraph Docker [Docker Containers]
            Ninja[Invoice Ninja]
        end 
    end
    Brain[Inference Node]

    %% Flujo de interacciones del usuario
    User -->|Quick interactions / Receive notifications| TG
    User --> |Quick Verifications|Streamlit
    User --> |Complex operations / Generate reports|Ninja

    %% Conexiones internas del sistema
    Bot --> |delegates messages| Kissy
    Kissy <--> |HTTP REST (ollama API)| Brain
    Kissy <--> |Store conversations| DB
    TG <-->|Webhook| Bot
    Ninja <--> |Trigger Operations| Kissy
    Ninja <--> |Relevant Information| Streamlit
```

## Component Description

### 1. Telegram Bot
*   **Purpose:** Thin UI layer for quick operations and system notifications. All logic is delegated to KissyEngine.
*   **Technology Stack:** Python (using `python-telegram-bot`)
*   **Responsibilities:**
    *   Receive messages from the user and forward them to KissyEngine.
    *   Notify user directly on its telephone.
    *   Render replies and confirmations from KissyEngine.

### 2. Invoice Ninja (Docker App)
*   **Purpose:** Invoicing software with robust database.
*   **Technology Stack:** Docker (separate container).
*   **Auth Model:**
    *   System-to-system (KissyEngine, Streamlit): **API token**.
    *   User-facing: **Google OAuth2**.
*   **Responsibilities:**
    *   Expose REST API endpoints for KissyEngine and Streamlit.
    *   Generate financial reports.
    *   Keep track of clients, debts and finances.

### 3. Conversations database (DB)
*   **Purpose:** Store conversation history to maintain context across user interactions with the Telegram Bot.
*   **Technology Stack:** SQLite3.
*   **Responsibilities:**
    *   Persist all conversation messages per chat.
    *   Allow KissyEngine to query active conversations and retrieve full history for context window.

### 4. Streamlit Dashboard
*   **Purpose:** Provide an administrative interface to monitor projects, track time, and manage tasks.
*   **Technology Stack:** Python with Streamlit.
*   **Responsibilities:**
    *   Connect to the Invoice Ninja to fetch and display operational metrics.
    *   Render a **Kanban board** of tasks for active projects.
    *   Provide a **time logging** interface to track effort per project and display accumulated hours.

### 5. Inference Node
*   **Purpose:** Extracts structured data from natural language.
*   **Technology Stack:** Ollama (gemma2:4b) running on an external machine.
*   **Protocol:** HTTP REST — KissyEngine calls the Ollama API at `http://<inference-node>:11434/api/generate`.
*   **Responsibilities:**
    *   Identify operations from a single message.
    *   Extract parameters from unstructured conversations coming from the user.

### 6. Kissy Engine
*   **Purpose:** Central integration layer — owns the Telegram Bot instance, the Ollama client, and the Invoice Ninja client.
*   **Technology Stack:** Python (single in-process class).
*   **Process Model:** Runs in the same process as the Telegram Bot and the SQLite DB. Not a separate service.
*   **Responsibilities:**
    *   Own the Telegram Bot `Application` instance.
    *   Maintain an Ollama client (HTTP REST to Inference Node).
    *   Maintain an Invoice Ninja client (API token auth).
    *   Manage conversation persistence (SQLite read/write).
    *   Verify all components are working (health checks).
    *   Define the scope of operations doable via the Telegram Bot.
    *   Route incoming messages through the Inference Node to extract intent and parameters.
    *   Execute operations against Invoice Ninja's REST API based on extracted intent.

## Communication Protocols

| From | To | Protocol | Auth |
|---|---|---|---|
| Telegram Bot | KissyEngine | In-process (Python) | — |
| KissyEngine | Ollama | HTTP REST (`:11434/api/generate`) | None (internal network) |
| KissyEngine | Invoice Ninja | HTTP REST | API token |
| Streamlit | Invoice Ninja | HTTP REST | API token |
| Telegram | Telegram Bot | Webhook | Secret token (optional) |
