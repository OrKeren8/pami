import os
import requests
from requests.auth import HTTPBasicAuth
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JiraClient:
    def __init__(self, base_url, username, api_token):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, api_token)
        self.api_url = f"{self.base_url}/rest/api/3"

    def create_issue(
        self,
        project_key,
        issue_type,
        summary,
        description=None,
        assignee=None,
        priority=None,
        due_date=None,
        labels=None,
    ):
        """
        Create a new issue in Jira.

        :param project_key: The key of the project (e.g., 'PROJ')
        :param issue_type: The type of issue (e.g., 'Task', 'Bug')
        :param summary: The summary/title of the issue
        :param description: The description of the issue
        :param assignee: The account ID of the assignee
        :param priority: The priority (e.g., 'High', 'Medium')
        :param due_date: The due date in YYYY-MM-DD format
        :param labels: List of labels
        :return: The created issue key or None if failed
        """
        url = f"{self.api_url}/issue"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
            }
        }
        if description:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"text": description, "type": "text"}],
                    }
                ],
            }
        if assignee:
            payload["fields"]["assignee"] = {"accountId": assignee}
        if priority:
            payload["fields"]["priority"] = {"name": priority}
        if due_date:
            payload["fields"]["duedate"] = due_date
        if labels:
            payload["fields"]["labels"] = labels

        try:
            response = requests.post(url, json=payload, auth=self.auth, timeout=10)
            if response.status_code == 201:
                issue_key = response.json().get("key")
                logger.info(f"Issue created: {issue_key}")
                return issue_key
            else:
                logger.error(
                    f"Failed to create issue: {response.status_code} - {response.text}"
                )
                return None
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def get_issue(self, issue_key):
        """
        Get details of an issue.

        :param issue_key: The key of the issue (e.g., 'PROJ-123')
        :return: Issue data or None
        """
        url = f"{self.api_url}/issue/{issue_key}"
        try:
            response = requests.get(url, auth=self.auth, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Failed to get issue: {response.status_code} - {response.text}"
                )
                return None
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def update_issue(self, issue_key, fields):
        """
        Update an issue.

        :param issue_key: The key of the issue
        :param fields: Dict of fields to update
        :return: True if successful
        """
        url = f"{self.api_url}/issue/{issue_key}"
        payload = {"fields": fields}
        try:
            response = requests.put(url, json=payload, auth=self.auth, timeout=10)
            if response.status_code == 204:
                logger.info(f"Issue updated: {issue_key}")
                return True
            else:
                logger.error(
                    f"Failed to update issue: {response.status_code} - {response.text}"
                )
                return False
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return False

    def search_issues(self, jql, max_results=50):
        """
        Search for issues using JQL.

        :param jql: JQL query string
        :param max_results: Maximum number of results
        :return: List of issues
        """
        url = f"{self.api_url}/search/jql"
        params = {"jql": jql, "maxResults": max_results}
        try:
            response = requests.get(url, params=params, auth=self.auth, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("issues", [])
            else:
                logger.error(
                    f"Failed to search issues: {response.status_code} - {response.text}"
                )
                return []
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return []

    def fetch_projects(self):
        """
        Fetch all projects accessible to the user.

        :return: List of project dicts or empty list if failed
        """
        url = f"{self.api_url}/project"
        try:
            response = requests.get(url, auth=self.auth, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Failed to fetch projects: {response.status_code} - {response.text}"
                )
                return []
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return []

    def get_project_issues(self, project_key, status=None):
        """
        Get all issues for a project.

        :param project_key: The project key
        :param status: Filter by status (optional)
        :return: List of issues
        """
        jql = f"project = {project_key}"
        if status:
            jql += f" AND status = '{status}'"
        return self.search_issues(jql)


# Example usage
if __name__ == "__main__":
    # Load from environment variables
    jira_url = os.getenv("JIRA_BASE_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_token]):
        print(
            "Please set JIRA_BASE_URL, JIRA_USERNAME, and JIRA_API_TOKEN environment variables."
        )
        exit(1)

    client = JiraClient(jira_url, jira_username, jira_token)

    # Fetch and display projects
    projects = client.fetch_projects()
    if not projects:
        print("No projects found or failed to fetch projects.")
        exit(1)

    print("Available projects:")
    for i, project in enumerate(projects):
        print(f"{i + 1}. {project['name']} (Key: {project['key']})")

    # Let user choose a project
    while True:
        try:
            choice = int(input("Choose a project by number: ")) - 1
            if 0 <= choice < len(projects):
                selected_project = projects[choice]
                project_key = selected_project["key"]
                print(
                    f"Selected project: {selected_project['name']} (Key: {project_key})"
                )
                break
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")

    # Ask user for task details
    title = input("Enter task title: ").strip()
    if not title:
        title = "Untitled Task"
    description = input("Enter task description (optional): ").strip()

    issue_key = client.create_issue(
        project_key,
        "Task",
        title,
        description,
        None,
        "High",
        "2026-03-15",
        ["pami", "integration"],
    )
    if issue_key:
        print(f"Task synced to Jira: {issue_key}")

        # Example: Get project issues
        issues = client.get_project_issues(project_key)
        print(f"Total issues in {selected_project['name']} project: {len(issues)}")
