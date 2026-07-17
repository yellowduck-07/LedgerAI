# deploy-starter

Minimal FastAPI deployment boilerplate. One service serves both the static frontend and API from the same origin—no CORS required.

## Local setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 2. Install requirements

```bash
pip install -r requirements.txt
```

### 3. Start the server

```bash
uvicorn app.main:app --reload
```

The app runs at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### 4. Test locally

- **Homepage:** open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) — you should see “Deployment starter is live” and a green “Backend connected” status.
- **Health API:** open [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) — response should be `{"status":"ok"}`.

## Deploy to Render

### 1. Push to GitHub

Create a new repository, then push this project:

```bash
git init
git add .
git commit -m "Initial deploy-starter boilerplate"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

### 2. Deploy with the Blueprint

1. In the [Render Dashboard](https://dashboard.render.com/), click **New → Blueprint**.
2. Connect your GitHub repository.
3. Render reads `render.yaml` and creates the web service automatically.

### 3. Replace the placeholder service name

Before or after the first deploy, edit `render.yaml` and change `replace-with-your-service-name` to a name you want for your Render service (for example, `my-app-starter`).

Render will rebuild and redeploy on each commit when `autoDeploy` is enabled.
