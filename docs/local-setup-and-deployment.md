\# PAMI Local Setup and Deployment Notes



This document explains how to run the PAMI project on a new computer and what must be configured before merging or deploying the Slack service.



\## 1. Prerequisites



Install the following tools before running the project:



\- Git

\- Python 3.11 or newer

\- Node.js and npm

\- MongoDB, either:

&#x20; - local MongoDB installed on the computer, or

&#x20; - a valid MongoDB Atlas connection string

\- Access to the GitHub repository

\- Access to the Slack App credentials, if running the Slack service



\## 2. Clone the Repository



```bash

git clone https://github.com/OrKeren8/pami.git

cd pami

```



If working on the deployment preparation branch:



```bash

git checkout prepare-slack-deployment

```



\## 3. Frontend Setup



Go to the frontend folder:



```bash

cd frontend

```



Install dependencies:



```bash

npm install

```



Create a local environment file:



```bash

copy .env.example .env.local

```



The local file should contain:



```env

REACT\_APP\_PROJECTS\_API\_BASE\_URL=http://127.0.0.1:8000

REACT\_APP\_SLACK\_API\_BASE\_URL=http://127.0.0.1:8001

```



Run the frontend:



```bash

npm start

```



The frontend should usually open at:



```text

http://localhost:3000

```



\## 4. Projects Service Setup



Open a new terminal from the repository root:



```bash

cd projects\_service

```



Create a virtual environment:



```bash

python -m venv venv

```



Activate it on Windows:



```bash

venv\\Scripts\\activate

```



Install the service:



```bash

python -m pip install --upgrade pip

python -m pip install -e .

```



Run the Projects service:



```bash

uvicorn projects\_service.main:app --reload --port 8000

```



Check that it works:



```bash

curl -i http://127.0.0.1:8000/health

curl -i http://127.0.0.1:8000/projects/

```



Expected results:



\- `/health` should return `200 OK`

\- `/projects/` should return a JSON list, for example `\[]`



\## 5. Slack Service Setup



Open a new terminal from the repository root:



```bash

cd slack\_service

```



Create a virtual environment:



```bash

python -m venv venv

```



Activate it on Windows:



```bash

venv\\Scripts\\activate

```



Install the service:



```bash

python -m pip install --upgrade pip

python -m pip install -e .

```



Create a local `.env` file inside `slack\_service`.



Required values:



```env

SLACK\_BOT\_TOKEN=<your-slack-bot-token>

SLACK\_SIGNING\_SECRET=<your-slack-signing-secret>

MONGODB\_URL=<your-mongodb-url>

```



Do not commit this `.env` file.



Run the Slack service locally:



```bash

uvicorn slack\_service.main:app --reload --port 8001

```



Check that the Slack service responds:



```bash

curl -i http://127.0.0.1:8001/slack/list-channels

```



\## 6. Running the Full Local System



Use three terminals.



\### Terminal 1 - Projects service



```bash

cd projects\_service

venv\\Scripts\\activate

uvicorn projects\_service.main:app --reload --port 8000

```



\### Terminal 2 - Slack service



```bash

cd slack\_service

venv\\Scripts\\activate

uvicorn slack\_service.main:app --reload --port 8001

```



\### Terminal 3 - Frontend



```bash

cd frontend

npm start

```



Then open:



```text

http://localhost:3000

```



\## 7. Important Environment Files



These files should exist only locally and must not be committed:



```text

frontend/.env.local

slack\_service/.env

backend/slack-test/.env

```



The repository includes safe example files such as:



```text

frontend/.env.example

slack\_service/.env.example

```



Example files may contain placeholders only. Real secrets must never be committed.



\## 8. GitHub Secret Required Before Merge or Deployment



Before merging or deploying the Slack service, a GitHub repository secret must be configured.



Secret name:



```text

MONGODB\_URL

```



Secret value:



```text

mongodb+srv://<username>:<password>@<cluster-url>/<database-name>?appName=<app-name>

```



For this project, the GitHub Actions workflow expects this value:



```yaml

${{ secrets.MONGODB\_URL }}

```



This means the real MongoDB connection string must be stored in GitHub Secrets, not directly in the workflow file.



To add the secret in GitHub:



1\. Open the repository on GitHub.

2\. Go to `Settings`.

3\. Go to `Secrets and variables`.

4\. Go to `Actions`.

5\. Open the `Secrets` tab.

6\. Click `New repository secret`.

7\. Set the name to:



```text

MONGODB\_URL

```



8\. Set the value to the full MongoDB connection string.

9\. Click `Add secret`.



The deployment workflow will not work correctly unless this secret exists.



\## 9. Security Note



A MongoDB connection string must never be hardcoded in:



\- GitHub Actions workflow files

\- source code

\- README files

\- committed `.env` files



If a real MongoDB password was ever committed or shared, the MongoDB Atlas password should be rotated and the new connection string should be saved again as the `MONGODB\_URL` GitHub Secret.



\## 10. Basic Validation Before Commit



Before committing changes, run:



```bash

git status --short

```



Check for secrets:



```bash

git grep -n -E "xoxb-|xoxp-|xapp-|SLACK\_BOT\_TOKEN=.+|SLACK\_SIGNING\_SECRET=.+|mongodb\\+srv://|client\_secret|api\_key" -- .

```



Build the frontend:



```bash

cd frontend

npm run build

```



The build should complete successfully. Warnings may exist, but there should be no build errors.



\## 11. Current Deployment Preparation Notes



The current deployment preparation branch is:



```text

prepare-slack-deployment

```



The relevant prepared changes include:



\- Frontend API configuration was split into separate clients:

&#x20; - Projects API

&#x20; - Slack API

\- `frontend/.env.example` was added for local setup.

\- `HomePage.js` now uses the correct API client for each backend service.

\- Slack channel creation now handles the case where a channel already exists.

\- `projects\_service` startup was fixed by registering the required routers.

\- `projects\_service` MongoDB initialization was fixed to include the database name.

\- The Slack deployment workflow no longer stores the MongoDB connection string directly.

\- The workflow now uses:



```yaml

${{ secrets.MONGODB\_URL }}

```



Before merging this branch or deploying it, make sure the `MONGODB\_URL` repository secret exists in GitHub.

