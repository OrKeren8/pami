#!/usr/bin/env python3
"""
Basic validation script for AI Conversation Service
Tests the code structure and basic functionality without external dependencies
"""

import sys
import os
import ast
import importlib.util


def validate_syntax():
    """Validate Python syntax of all source files"""
    print("🔍 Validating Python syntax...")

    source_files = [
        "src/ai_conversation_service/main.py",
        "src/ai_conversation_service/core/config.py",
        "src/ai_conversation_service/services/ai_conversation_service/service.py",
        "src/ai_conversation_service/api/v1/ai_conversations.py",
        "tests/test_ai_conversation_service.py",
        "tests/test_ai_conversation_integration.py",
    ]

    all_valid = True
    for file_path in source_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            ast.parse(source_code)
            print(f"  ✓ {file_path}")
        except SyntaxError as e:
            print(f"  ✗ {file_path}: {e}")
            all_valid = False
        except FileNotFoundError:
            print(f"  ✗ {file_path}: File not found")
            all_valid = False

    return all_valid


def validate_code_structure():
    """Validate that the code structure and basic logic is sound"""
    print("\n🔍 Validating code structure...")

    try:
        # Check that key classes and functions are defined
        with open(
            "src/ai_conversation_service/services/ai_conversation_service/service.py",
            "r",
        ) as f:
            service_code = f.read()

        # Check for key class definitions and imports
        checks = [
            (
                "from ai_conversation_service.models.ai_conversation import Conversation",
                "Conversation model imported",
            ),
            ("class AIConversationService:", "AIConversationService class defined"),
            ("async def create_conversation", "create_conversation method defined"),
            ("async def send_message", "send_message method defined"),
            ("async def get_conversation", "get_conversation method defined"),
        ]

        for check, description in checks:
            if check in service_code:
                print(f"  ✓ {description}")
            else:
                print(f"  ✗ {description}")
                return False

        # Check API endpoints
        with open("src/ai_conversation_service/api/v1/ai_conversations.py", "r") as f:
            api_code = f.read()

        api_checks = [
            (
                '@router.post("/", response_model=ConversationResponse)',
                "Create conversation endpoint",
            ),
            ('@router.post("/{conversation_id}/messages")', "Send message endpoint"),
            (
                '@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)',
                "Get conversation endpoint",
            ),
        ]

        for check, description in api_checks:
            if check in api_code:
                print(f"  ✓ {description}")
            else:
                print(f"  ✗ {description}")
                return False

        # Check main app
        with open("src/ai_conversation_service/main.py", "r") as f:
            main_code = f.read()

        if "app = FastAPI(" in main_code and "ai_conversation_service" in main_code:
            print("  ✓ FastAPI app properly configured")
        else:
            print("  ✗ FastAPI app configuration issue")
            return False

        return True

    except Exception as e:
        print(f"  ✗ Code structure validation failed: {e}")
        return False


def validate_project_structure():
    """Validate that the project structure is correct"""
    print("\n🔍 Validating project structure...")

    required_files = [
        "pyproject.toml",
        "pytest.ini",
        "Dockerfile",
        "README.md",
        ".env.example",
        ".gitignore",
    ]

    required_dirs = [
        "src/ai_conversation_service",
        "src/ai_conversation_service/core",
        "src/ai_conversation_service/services/ai_conversation_service",
        "src/ai_conversation_service/api/v1",
        "tests",
    ]

    all_present = True

    for file_path in required_files:
        if os.path.isfile(file_path):
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - missing")
            all_present = False

    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ✗ {dir_path}/ - missing")
            all_present = False

    return all_present


def main():
    """Run all validations"""
    print("🚀 AI Conversation Service Validation")
    print("=" * 50)

    results = []

    # Change to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    results.append(("Project Structure", validate_project_structure()))
    results.append(("Python Syntax", validate_syntax()))
    results.append(("Code Structure", validate_code_structure()))

    print("\n" + "=" * 50)
    print("📊 VALIDATION RESULTS:")

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("The AI Conversation Service is structurally sound.")
        print("Note: Full functionality testing requires installing dependencies with:")
        print("  uv sync")
        print("  uv run pytest")
    else:
        print("⚠️  Some validations failed. Please check the errors above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
