# Antigrav P1 - LangGraph Router

An intelligent query router application using LangGraph, FastAPI, and React. This system automatically directs user queries to the most appropriate processing agent:
- **RAG Agent**: For answering questions based on uploaded documents (PDF, DOCX).
- **Text2SQL Agent**: For querying structured data from a PostgreSQL database.
- **Hybrid**: For complex queries requiring both sources.

## Features

- 🧠 **Smart Routing**: Uses an LLM to classify and route queries.
- 📚 **RAG Support**: Upload and query PDF/DOCX documents using ChromaDB vectors.
- 🗄️ **Text2SQL**: Natural language interface for your SQL database.
- 🚀 **Modern Stack**: FastAPI backend with a React (Vite) frontend.

## Prerequisites

- **Python** 3.10 or higher
- **Node.js** 18 or higher (for UI)
- **PostgreSQL** database
- **Groq API Key** (for LLM inference)

## Setup Instructions

### 1. Backend Setup

1.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**:
    Copy the example environment file and fill in your details:
    ```bash
    cp .env.example .env
    ```
    
    Update `.env` with your configuration:
    - `GROQ_API_KEY`: Your Groq API key.
    - `DB_CONNECTION_STRING`: PostgreSQL connection string (e.g., `postgresql://user:pass@localhost:5432/dbname`).
    - `CHROMA_DB_DIR`: Path for vector store persistence.

4.  **Run the Server**:
    ```bash
    python main.py
    ```
    The API will be available at `http://localhost:8000`.
    - API Documentation: `http://localhost:8000/docs`

### 2. Frontend Setup

1.  **Navigate to the UI directory**:
    ```bash
    cd ui
    ```

2.  **Install dependencies**:
    ```bash
    npm install
    ```

3.  **Start the Development Server**:
    ```bash
    npm run dev
    ```
    The application will open at `http://localhost:5173` (or the port shown in your terminal).

## Usage Guide

### Uploading Documents (RAG)
You can upload PDF or DOCX files via the UI or the API directly:
- **Endpoint**: `POST /upload`
- **Supported Formats**: `.pdf`, `.docx`
- These documents will be indexed and made available for QA immediately.

### Querying Data
Simply type your question in the main search bar. The router will decide the best way to answer:
- *"Summarize the uploaded contract"* -> **RAG Agent**
- *"How many users signed up last week?"* -> **Text2SQL Agent**

## Project Structure

- `main.py`: FastAPI entry point and API routes.
- `graph.py`: LangGraph definition (nodes, edges, workflow).
- `agents/`: Implementation of RAG, Text2SQL, and Router agents.
- `ui/`: React frontend application.
- `requirements.txt`: Python dependencies.
