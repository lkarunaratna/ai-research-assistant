# How to Run the AI Research Assistant Application

This guide will walk you through setting up and running both the backend (FastAPI) and frontend (React.js) components of the AI Research Assistant.

## Prerequisites

*   Python 3.8+
*   Node.js and npm (or yarn)
*   An OpenAI API Key

## Setup Steps

### 1. OpenAI API Key

Ensure you have your OpenAI API Key set as an environment variable or in a `.env` file in the **project root directory** (i.e., `ai-research-assistant/`).

Create a file named `.env` in the project root with the following content:

```
OPENAI_API_KEY="your_openai_api_key_here"
```

Replace `"your_openai_api_key_here"` with your actual OpenAI API Key.

### 2. Backend Setup (FastAPI)

Navigate to the project root directory:

```bash
cd C:\Projects\AI\ai-research-assistant
```

Install the backend Python dependencies:

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

Start the FastAPI backend server:

```bash
uvicorn backend.app:app --reload --port 8001
```

The backend server should now be running and accessible at `http://localhost:8001`. You can test it by visiting `http://localhost:8001/docs` in your browser.

### 3. Frontend Setup (React.js)

Open a **new terminal window** and navigate to the `frontend` directory:

```bash
cd C:\Projects\AI\ai-research-assistant\frontend
```

Install the frontend Node.js dependencies:

```bash
npm install
# or
yarn install
```

Start the React development server:

```bash
npm run dev
# or
yarn dev
```

**Note:** The `npm run dev` command in `frontend/package.json` has been updated to use `npx vite` to make the execution more robust.

The React application should open in your default web browser, usually at `http://localhost:5173` (or another available port).

## Using the Application

Once both the backend and frontend servers are running:

1.  Open your web browser and navigate to the frontend URL (e.g., `http://localhost:5173`).
2.  Enter your research topic in the input field.
3.  Click the "Start Research" button.
4.  Observe the streaming output as the AI Research Assistant gathers and processes information.

---

## Troubleshooting

*   **FastAPI Backend Not Accessible (e.g., `http://localhost:8001/docs` not loading):**
    *   **Port Conflict:** Another application might be using port `8001`. Try running the backend on a different port (e.g., `uvicorn backend.app:app --reload --port 8002`). If you change the backend port, remember to update the URL in `frontend/src/App.jsx` as well.
    *   **Firewall/Antivirus:** Temporarily disable any firewall or antivirus software that might be blocking network connections to `localhost:8001`.
    *   **Backend Logs:** Check the `uvicorn` terminal for any errors or warnings during startup.
*   **Frontend Errors (`vite` not recognized, import errors, empty page, etc.):**
    *   **`'vite' is not recognized`**: Ensure you are in the `frontend` directory and have run `npm install`. If issues persist, try a clean reinstall:
        ```bash
        cd frontend
        npm cache clean --force
        rm -rf node_modules
        rm package-lock.json # or yarn.lock
        npm install
        npm run dev
        ```
    *   **Empty Page / Import Errors for React**: Ensure `frontend/index.html` has `<div id="root"></div>` and `<script type="module" src="/src/main.jsx"></script>`. Also, make sure `frontend/src/main.jsx` correctly imports and renders `<App />`. Run `npm install` again after any `package.json` changes.
    *   **Syntax Errors in `App.jsx`**: Ensure `frontend/src/App.jsx` does not have any unterminated string literals or regex. If an error persists, delete the `.vite` cache directory (`rm -rf .vite`) and restart `npm run dev`.
*   **CORS Errors**: Ensure your FastAPI backend is running and `allow_origins=["*"]` is correctly set in `backend/app.py` for development.
*   **Button Remains Disabled / No Streaming Output**:
    *   **Backend Logs:** Check the `uvicorn` terminal for `DEBUG` messages from `backend/app.py` and `src/agent.py` to confirm the backend is processing the request and generating events.
    *   **Frontend Console (F12):** Check for `EventSource` errors or messages indicating the stream is not correctly handled. Ensure the frontend is calling `http://localhost:8001/api/v1/research` (GET request).
