import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx


def schedule_to_cron(schedule_payload: dict) -> str:
    """
    Convert schedule payload to cron expression
    Cron format: minute hour day month day-of-week
    """
    hour = int(schedule_payload["hour"])
    minute = int(schedule_payload["minute"])
    period = schedule_payload["period"]
    frequency = schedule_payload["frequency"].lower()

    # Convert 12-hour to 24-hour
    if period == "PM" and hour != 12:
        hour += 12
    elif period == "AM" and hour == 12:
        hour = 0

    # Day mapping for cron (0=Sunday, 1=Monday, ...)
    day_map = {
        "Sun": "0",
        "Mon": "1",
        "Tue": "2",
        "Wed": "3",
        "Thu": "4",
        "Fri": "5",
        "Sat": "6",
    }

    if frequency == "daily":
        return f"{minute} {hour} * * *"

    elif frequency == "weekly":
        days = schedule_payload.get("daysOfWeek", ["Mon"])
        cron_days = ",".join([day_map[day] for day in days])
        return f"{minute} {hour} * * {cron_days}"

    elif frequency == "biweekly":
        days = schedule_payload.get("daysOfWeek", ["Mon"])
        cron_days = ",".join([day_map[day] for day in days])
        # Every 2 weeks - using day-of-week with weeks
        return f"{minute} {hour} * * {cron_days}/2"

    elif frequency == "fortnightly":
        days = schedule_payload.get("daysOfWeek", ["Mon"])
        cron_days = ",".join([day_map[day] for day in days])
        # Every 2 weeks - same as biweekly
        return f"{minute} {hour} * * {cron_days}/2"

    elif frequency == "monthly":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        return f"{minute} {hour} {day_of_month} * *"

    elif frequency == "bimonthly":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        # Every 2 months
        return f"{minute} {hour} {day_of_month} */2 *"

    elif frequency == "quarterly":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        months = schedule_payload.get("monthsOfYear", [1, 4, 7, 10])
        cron_months = ",".join([str(m) for m in months])
        return f"{minute} {hour} {day_of_month} {cron_months} *"

    elif frequency == "semiannual":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        # Every 6 months
        return f"{minute} {hour} {day_of_month} */6 *"

    elif frequency == "biannual":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        # Twice a year - equivalent to semiannual
        return f"{minute} {hour} {day_of_month} */6 *"

    elif frequency == "annual":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        month_of_year = schedule_payload.get("monthOfYear", 1)
        return f"{minute} {hour} {day_of_month} {month_of_year} *"

    elif frequency == "yearly":
        day_of_month = schedule_payload.get("dayOfMonth", 1)
        month_of_year = schedule_payload.get("monthOfYear", 1)
        return f"{minute} {hour} {day_of_month} {month_of_year} *"

    else:
        raise ValueError(f"Unsupported frequency: {frequency}")


class N8N:
    """
    N8N API Client Class
    Handles workflow creation, updates, and management
    """

    def __init__(
        self, api_key: str, base_url: str = "http://172.191.171.71:5678/api/v1"
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

    def build_workflow(
        self,
        workflow_name: str,
        user_id: str,
        dashboard_id: str,
        workspace_id: str,
        project_id: str,
        schedule_payload: dict,
    ) -> dict:
        """
        Build complete n8n workflow JSON with all nodes including IF date check
        """

        # Generate cron expression
        cron_expr = schedule_to_cron(schedule_payload)

        # Generate UUIDs for all nodes
        schedule_id = str(uuid.uuid4())
        date_check_id = str(uuid.uuid4())
        config_id = str(uuid.uuid4())
        get_dashboard_id = str(uuid.uuid4())
        prepare_render_id = str(uuid.uuid4())
        edit_fields_id = str(uuid.uuid4())
        render_dashboard_id = str(uuid.uuid4())
        edit_fields1_id = str(uuid.uuid4())
        update_dashboard_id = str(uuid.uuid4())

        workflow = {
            "name": workflow_name,
            "nodes": [
                # 1. Schedule Trigger - Fires based on cron schedule
                {
                    "parameters": {
                        "rule": {
                            "interval": [
                                {"field": "cronExpression", "expression": cron_expr}
                            ]
                        }
                    },
                    "id": schedule_id,
                    "name": "Schedule Trigger",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "typeVersion": 1.2,
                    "position": [240, 304],
                },
                # 2. Check Date Range - IF node to validate start/end dates (FIXED)
                {
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                            },
                            "conditions": [
                                {
                                    "id": str(uuid.uuid4()),
                                    "leftValue": "={{ $now.toFormat('yyyy-MM-dd') }}",
                                    "rightValue": schedule_payload["startDate"],
                                    "operator": {
                                        "type": "dateTime",
                                        "operation": "afterOrEquals",
                                        "singleValue": schedule_payload["startDate"],
                                    },
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "leftValue": "={{ $now.toFormat('yyyy-MM-dd') }}",
                                    "rightValue": schedule_payload["endDate"],
                                    "operator": {
                                        "type": "dateTime",
                                        "operation": "beforeOrEquals",
                                        "singleValue": schedule_payload["endDate"],
                                    },
                                },
                            ],
                            "combinator": "and",
                        }
                    },
                    "id": date_check_id,
                    "name": "Check Date Range",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [400, 304],
                },
                # 3. Config - Store configuration variables
                {
                    "parameters": {
                        "assignments": {
                            "assignments": [
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "user_id",
                                    "value": user_id,
                                    "type": "string",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "dashboard_id",
                                    "value": dashboard_id,
                                    "type": "string",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "workspace_id",
                                    "value": workspace_id,
                                    "type": "string",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "project_id",
                                    "value": project_id,
                                    "type": "string",
                                },
                            ]
                        },
                        "options": {},
                    },
                    "id": config_id,
                    "name": "Config",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [620, 304],
                },
                # 4. Get Dashboard - Fetch dashboard data
                {
                    "parameters": {
                        "url": "=https://lenna-humic-nontransgressively.ngrok-free.dev/internal/dashboards/{{ $json.dashboard_id }}?user_id={{ $json.user_id }}",
                        "options": {},
                    },
                    "id": get_dashboard_id,
                    "name": "Get Dashboard",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [840, 304],
                },
                # 5. Prepare Render Request - Extract and prepare data
                {
                    "parameters": {
                        "assignments": {
                            "assignments": [
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "workflow_id",
                                    "value": "={{ $now.toISO() }}-{{ $('Config').item.json.dashboard_id }}",
                                    "type": "string",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "dashboard_name",
                                    "value": "={{ $json.name || 'Dashboard' }}",
                                    "type": "string",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "widgets",
                                    "value": "={{ $json.content }}",
                                    "type": "array",
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "dashboard_id",
                                    "value": "={{ $('Config').item.json.dashboard_id }}",
                                    "type": "string",
                                },
                            ]
                        },
                        "options": {},
                    },
                    "id": prepare_render_id,
                    "name": "Prepare Render Request",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [1060, 304],
                },
                # 6. Edit Fields - Transform data to Payload format (Complex transformation)
                {
                    "parameters": {
                        "mode": "raw",
                        "jsonOutput": '={\n  "Payload": {{\n    (function () {\n      return {\n        workflow_id: $json.dashboard_id,\n        project_id: $(\'Config\').item.json.project_id,\n        state: $json.widgets?.status ?? "draft",\n        current_step: 0,\n\n        workflow_metadata: {\n          dashboard_template: "",\n          dashboard_layout: "",\n          refresh_rate: 0,\n          report_title: $json.dashboard_name,\n          report_description: "",\n          report_sections: [],\n          writer_actor: "",\n          business_goal: {},\n          custom_config: {}\n        },\n\n        thread_components: ($json.widgets || []).map((c, index) => ({\n          id: c.widget_id,\n          component_type: "question",\n          sequence_order: index,\n          question: c.question ?? "",\n          description: c.description ?? "",\n          overview: c.overview ?? {},\n          chart_config: c.chart ?? {},\n          table_config: c.table ?? {},\n          sql_query: c.sql_query ?? "",\n          executive_summary: c.overview?.summary ?? "",\n          data_overview: {},\n          visualization_data: {},\n          sample_data: c.chart?.data_sample ?? {},\n          thread_metadata: c.metadata ?? {},\n          chart_schema: c.chart?.chart_schema ?? {},\n          reasoning: c.chart?.reasoning ?? "",\n          data_count: c.chart?.data_count ?? 0,\n          validation_results: c.chart?.execution_info ?? {},\n          alert_config: {},\n          alert_status: "",\n          last_triggered: "",\n          trigger_count: 0,\n          configuration: c.configuration ?? {},\n          is_configured: c.is_configured ?? false,\n          created_at: new Date().toISOString(),\n          updated_at: new Date().toISOString()\n        })),\n\n        natural_language_query: "",\n        additional_context: {},\n        time_filters: {},\n        render_options: {},\n        error_message: "",\n        created_at: new Date().toISOString(),\n        updated_at: new Date().toISOString(),\n        completed_at: ""\n      };\n    })()\n  }}\n}\n',
                        "options": {},
                    },
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [1188, 112],
                    "id": edit_fields_id,
                    "name": "Edit Fields",
                },
                # 7. Render Dashboard - Send to render API
                {
                    "parameters": {
                        "method": "POST",
                        "url": "http://100.26.125.159:8025/dashboard/render-from-workflow",
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": "={{ $json.Payload }}",
                        "options": {
                            "response": {"response": {"responseFormat": "json"}}
                        },
                    },
                    "id": render_dashboard_id,
                    "name": "Render Dashboard",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [1268, 304],
                    "alwaysOutputData": True,
                },
                # 8. Edit Fields1 - Extract rendered components
                {
                    "parameters": {
                        "assignments": {
                            "assignments": [
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "content",
                                    "value": "={{$json.dashboard_data.content.components}}",
                                    "type": "array",
                                }
                            ]
                        },
                        "options": {},
                    },
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [1396, 112],
                    "id": edit_fields1_id,
                    "name": "Edit Fields1",
                },
                # 9. Update Dashboard - Save rendered content back
                {
                    "parameters": {
                        "method": "PATCH",
                        "url": "=https://lenna-humic-nontransgressively.ngrok-free.dev/internal/dashboards/{{ $('Config').item.json.dashboard_id }}/content",
                        "sendQuery": True,
                        "queryParameters": {
                            "parameters": [
                                {
                                    "name": "user_id",
                                    "value": "={{ $('Config').item.json.user_id }}",
                                }
                            ]
                        },
                        "sendBody": True,
                        "contentType": "raw",
                        "body": "={{ $json.content }}",
                        "options": {},
                    },
                    "id": update_dashboard_id,
                    "name": "Update Dashboard",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [1492, 304],
                },
            ],
            "connections": {
                "Schedule Trigger": {
                    "main": [[{"node": "Check Date Range", "type": "main", "index": 0}]]
                },
                "Check Date Range": {
                    "main": [
                        [{"node": "Config", "type": "main", "index": 0}],
                        [],  # FALSE branch - stops execution
                    ]
                },
                "Config": {
                    "main": [[{"node": "Get Dashboard", "type": "main", "index": 0}]]
                },
                "Get Dashboard": {
                    "main": [
                        [{"node": "Prepare Render Request", "type": "main", "index": 0}]
                    ]
                },
                "Prepare Render Request": {
                    "main": [[{"node": "Edit Fields", "type": "main", "index": 0}]]
                },
                "Render Dashboard": {
                    "main": [[{"node": "Edit Fields1", "type": "main", "index": 0}]]
                },
                "Edit Fields": {
                    "main": [[{"node": "Render Dashboard", "type": "main", "index": 0}]]
                },
                "Edit Fields1": {
                    "main": [[{"node": "Update Dashboard", "type": "main", "index": 0}]]
                },
            },
            "settings": {"executionOrder": "v1"},
        }

        return workflow

    async def get_workflow_by_tag(
        self, user_id: str, dashboard_id: str
    ) -> Optional[dict]:
        """Find existing workflow for a user's dashboard"""
        tag_name = f"user_{user_id}_dashboard_{dashboard_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/workflows", headers=self.headers
            )

            if response.status_code == 200:
                workflows = response.json().get("data", [])
                # Filter by tag
                for workflow in workflows:
                    tags = workflow.get("tags", [])
                    if any(tag.get("name") == tag_name for tag in tags):
                        return workflow
            return None

    async def create_workflow(
        self,
        workflow_name: str,
        user_id: str,
        dashboard_id: str,
        workspace_id: str,
        project_id: str,
        schedule_payload: dict,
    ) -> Optional[dict]:
        """Create new workflow in n8n"""
        workflow_data = self.build_workflow(
            workflow_name,
            user_id,
            dashboard_id,
            workspace_id,
            project_id,
            schedule_payload,
        )

        print("Creating workflow...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/workflows", json=workflow_data, headers=self.headers
            )

            print(f"Response status: {response.status_code}")

            if response.status_code in [200, 201]:
                result = response.json()
                print(f"Workflow created! ID: {result.get('id')}")

                # Add tags
                await self.create_and_assign_tag(
                    result.get("id"), user_id, dashboard_id
                )

                return result
            else:
                print(f"Failed: {response.status_code}")
                print(f"Error: {response.text}")
                return None

    async def update_workflow(
        self, workflow_id: str, workflow_data: dict
    ) -> Optional[dict]:
        """Update existing workflow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                f"{self.base_url}/workflows/{workflow_id}",
                json=workflow_data,
                headers=self.headers,
            )

            if response.status_code == 200:
                print(f"Workflow {workflow_id} updated")
                return response.json()
            else:
                print(f"Update failed: {response.status_code} - {response.text}")
                return None

    async def activate_workflow(self, workflow_id: str, active: bool = True) -> bool:
        """Activate or deactivate workflow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                f"{self.base_url}/workflows/{workflow_id}",
                json={"active": active},
                headers=self.headers,
            )

            if response.status_code == 200:
                status = "activated" if active else "deactivated"
                print(f"Workflow {workflow_id} {status}")
                return True
            return False

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self.base_url}/workflows/{workflow_id}", headers=self.headers
            )

            return response.status_code == 200

    async def create_or_update_workflow(
        self,
        workflow_name: str,
        user_id: str,
        dashboard_id: str,
        workspace_id: str,
        project_id: str,
        schedule_payload: dict,
    ) -> Optional[dict]:
        """
        Main entry point: Create new or update existing workflow
        """
        # Check if workflow exists
        existing = await self.get_workflow_by_tag(user_id, dashboard_id)

        # Build workflow data
        workflow_data = self.build_workflow(
            workflow_name,
            user_id,
            dashboard_id,
            workspace_id,
            project_id,
            schedule_payload,
        )

        if existing:
            print(f"Updating existing workflow: {existing['id']}")
            result = await self.update_workflow(existing["id"], workflow_data)

            # Activate/deactivate based on dates
            should_activate = self.should_workflow_be_active(schedule_payload)
            await self.activate_workflow(existing["id"], should_activate)

            return result
        else:
            print("Creating new workflow")
            result = await self.create_workflow(
                workflow_name,
                user_id,
                dashboard_id,
                workspace_id,
                project_id,
                schedule_payload,
            )

            if result:
                should_activate = self.should_workflow_be_active(schedule_payload)
                await self.activate_workflow(result["id"], should_activate)

            return result

    def should_workflow_be_active(self, schedule_payload: dict) -> bool:
        """Check if workflow should be active based on dates"""
        today = datetime.now().date()
        start_date = datetime.strptime(schedule_payload["startDate"], "%Y-%m-%d").date()
        end_date = datetime.strptime(schedule_payload["endDate"], "%Y-%m-%d").date()

        return start_date <= today <= end_date

    async def create_and_assign_tag(
        self, workflow_id: str, user_id: str, dashboard_id: str
    ):
        """Create and assign tag to workflow"""
        tag_name = f"user_{user_id}_dashboard_{dashboard_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create tag
            create_response = await client.post(
                f"{self.base_url}/tags",
                json={"name": tag_name},
                headers=self.headers,
            )

            if create_response.status_code == 201:
                tag_id = create_response.json().get("id")
                print(f"Tag created: {tag_id}")
            elif create_response.status_code == 409:
                # Tag exists, get it
                get_tags_response = await client.get(
                    f"{self.base_url}/tags", headers=self.headers
                )
                if get_tags_response.status_code == 200:
                    tags = get_tags_response.json().get("data", [])
                    existing_tag = next(
                        (tag for tag in tags if tag.get("name") == tag_name), None
                    )
                    if existing_tag:
                        tag_id = existing_tag.get("id")
                        print(f"Using existing tag: {tag_id}")
                    else:
                        print("Failed to find existing tag")
                        return
                else:
                    print(f"Failed to get tags: {get_tags_response.text}")
                    return
            else:
                print(f"Failed to create tag: {create_response.text}")
                return

            # Assign tag
            tag_data = [{"id": tag_id}]
            assign_response = await client.put(
                f"{self.base_url}/workflows/{workflow_id}/tags",
                json=tag_data,
                headers=self.headers,
            )

            if assign_response.status_code == 200:
                print(f"Tag assigned to workflow {workflow_id}")
            else:
                print(f"Failed to assign tag: {assign_response.text}")

    async def get_all_workflows(self) -> list:
        """Get all workflows from n8n"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/workflows", headers=self.headers
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            return []


# ============================================================================
# USAGE EXAMPLES
# ============================================================================


async def main():
    """Example usage"""

    # Initialize N8N client
    api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlYjZmN2I4MC0xOTQ1LTQzNjEtODQ0MS0xYTkzMzAxNDA5MmEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY1Mjc3NjI1LCJleHAiOjE3Njc4NDg0MDB9.b5GNKkLuYSw-gz09EfJF9Tvlkd_usC3CvIrCBady18Q"
    n8n = N8N(api_key=api_key)

    # Example 1: Create/Update workflow
    schedule_payload = {
        "scheduleType": "scheduled",
        "frequency": "Weekly",
        "startDate": "2025-12-11",
        "endDate": "2026-01-11",
        "hour": "9",
        "minute": "30",
        "period": "AM",
        "daysOfWeek": ["Mon", "Wed", "Fri"],
        "timeZone": "UTC",
    }

    result = await n8n.create_or_update_workflow(
        workflow_name="Dashboard Scheduler",
        user_id="1e0cba86-110a-4d45-a205-182963880d75",
        dashboard_id="2cc8644c-e6ed-4c63-9502-2ec08e88f9f0",
        workspace_id="055d8308-1534-424a-8b41-7b6901c38c75",
        project_id="cornerstone_learning",
        schedule_payload=schedule_payload,
    )

    if result:
        print("\n=== Workflow Created/Updated Successfully! ===")
        print(f"Workflow ID: {result.get('id')}")
        print(f"Workflow Name: {result.get('name')}")
        print(f"Cron Expression: {schedule_to_cron(schedule_payload)}")
        print(f"\nSchedule Details:")
        print(f"  Frequency: {schedule_payload['frequency']}")
        print(
            f"  Time: {schedule_payload['hour']}:{schedule_payload['minute']} {schedule_payload['period']}"
        )
        if schedule_payload["frequency"] == "Weekly":
            print(f"  Days: {', '.join(schedule_payload['daysOfWeek'])}")
        print(f"  Start Date: {schedule_payload['startDate']}")
        print(f"  End Date: {schedule_payload['endDate']}")
        print(f"  Timezone: {schedule_payload['timeZone']}")
        print("\nWorkflow Steps:")
        print("  1. Schedule Trigger → Fires based on cron")
        print("  2. Check Date Range → Validates start/end dates")
        print("  3. Config → Sets configuration variables")
        print("  4. Get Dashboard → Fetches dashboard data")
        print("  5. Prepare Render Request → Extracts widgets")
        print("  6. Edit Fields → Transforms to Payload format")
        print("  7. Render Dashboard → Sends to render API")
        print("  8. Edit Fields1 → Extracts rendered components")
        print("  9. Update Dashboard → Saves back to dashboard")
        print("\n✓ Check your n8n instance to verify the workflow!")
    else:
        print("\n=== Failed to create/update workflow ===")

    # Example 2: Different schedule types
    print("\n" + "=" * 60)


def test_all_frequencies():
    """Test function to demonstrate all frequencies work correctly."""
    test_payload = {"hour": "9", "minute": "30", "period": "AM", "timeZone": "UTC"}

    frequencies = [
        "daily",
        "weekly",
        "biweekly",
        "fortnightly",
        "monthly",
        "bimonthly",
        "quarterly",
        "semiannual",
        "biannual",
        "annual",
        "yearly",
    ]

    print("\n=== Testing All Frequency Types ===\n")

    for freq in frequencies:
        test_payload["frequency"] = freq

        # Add required fields based on frequency
        if freq == "weekly":
            test_payload["daysOfWeek"] = ["Mon"]
        elif freq in [
            "monthly",
            "bimonthly",
            "quarterly",
            "semiannual",
            "biannual",
            "annual",
            "yearly",
        ]:
            test_payload["dayOfMonth"] = 1
        if freq in ["quarterly"]:
            test_payload["monthsOfYear"] = [1, 4, 7, 10]
        elif freq in ["annual", "yearly"]:
            test_payload["monthOfYear"] = 1

        try:
            cron_expr = schedule_to_cron(test_payload)
            print(f"✓ {freq:12} → {cron_expr}")
        except Exception as e:
            print(f"✗ {freq:12} → ERROR: {e}")

    print("\n=== Frequency Test Complete ===\n")


if __name__ == "__main__":
    # Run the frequency tests
    test_all_frequencies()
    print("Additional Schedule Examples:")
    print("=" * 60 + "\n")

    # Daily schedule
    daily_schedule = {
        "scheduleType": "scheduled",
        "frequency": "Daily",
        "startDate": "2025-12-15",
        "endDate": "2026-01-15",
        "hour": "9",
        "minute": "0",
        "period": "AM",
        "timeZone": "UTC",
    }
    print(f"Daily: {schedule_to_cron(daily_schedule)}")

    # Weekly schedule
    weekly_schedule = {
        "scheduleType": "scheduled",
        "frequency": "Weekly",
        "startDate": "2025-12-15",
        "endDate": "2026-01-15",
        "hour": "2",
        "minute": "30",
        "period": "PM",
        "daysOfWeek": ["Mon", "Wed", "Fri"],
        "timeZone": "UTC",
    }
    print(f"Weekly (Mon/Wed/Fri): {schedule_to_cron(weekly_schedule)}")

    # Monthly schedule
    monthly_schedule = {
        "scheduleType": "scheduled",
        "frequency": "Monthly",
        "startDate": "2025-12-15",
        "endDate": "2026-12-15",
        "hour": "10",
        "minute": "0",
        "period": "AM",
        "dayOfMonth": 15,
        "timeZone": "UTC",
    }
    print(f"Monthly (15th): {schedule_to_cron(monthly_schedule)}")

    # Quarterly schedule
    quarterly_schedule = {
        "scheduleType": "scheduled",
        "frequency": "Quarterly",
        "startDate": "2025-12-15",
        "endDate": "2026-12-15",
        "hour": "8",
        "minute": "0",
        "period": "AM",
        "dayOfMonth": 1,
        "monthsOfYear": [1, 4, 7, 10],
        "timeZone": "UTC",
    }
    print(f"Quarterly (Jan/Apr/Jul/Oct 1st): {schedule_to_cron(quarterly_schedule)}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
