"""
N8N service for managing n8n workflows asynchronously.
Handles workflow creation, updates, activation, and execution tracking.
"""

import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dbmodels.features_models import Schedule
from app.dbmodels.n8n_models import (
    N8NExecutionStatus,
    N8NWorkflow,
    N8NWorkflowExecution,
    N8NWorkflowStatus,
)
from app.utils.cache import cached_n8n_workflows, get_cache


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


class N8NService:
    """
    Async N8N API Client Service
    Handles workflow creation, updates, and management with database integration
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        timeout: float = 30.0,
    ):
        self.api_key = api_key if api_key else settings.N8N_API_KEY
        self.base_url = base_url if base_url else settings.N8N_BASE_URL
        self.timeout = timeout if timeout else settings.N8N_TIMEOUT
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
            "settings": {
                "executionOrder": "v1",
                "timezone": schedule_payload.get("timezone", "UTC"),
            },
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
                                    "rightValue": schedule_payload.get(
                                        "startDate", "2024-01-01"
                                    ),
                                    "operator": {
                                        "type": "dateTime",
                                        "operation": "afterOrEquals",
                                        "singleValue": schedule_payload.get(
                                            "startDate", "2024-01-01"
                                        ),
                                    },
                                },
                                {
                                    "id": str(uuid.uuid4()),
                                    "leftValue": "={{ $now.toFormat('yyyy-MM-dd') }}",
                                    "rightValue": schedule_payload.get(
                                        "endDate", "2030-12-31"
                                    ),
                                    "operator": {
                                        "type": "dateTime",
                                        "operation": "beforeOrEquals",
                                        "singleValue": schedule_payload.get(
                                            "endDate", "2030-12-31"
                                        ),
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
                        "url": f"=https://lenna-humic-nontransgressively.ngrok-free.dev/internal/dashboards/{dashboard_id}?user_id={user_id}",
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
                        "url": f"=https://lenna-humic-nontransgressively.ngrok-free.dev/internal/dashboards/{dashboard_id}/content",
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
        }

        return workflow

    async def get_workflow_by_tag(
        self, user_id: str, dashboard_id: str
    ) -> Optional[dict]:
        """Find existing workflow for a user's dashboard"""
        tag_name = f"user_{user_id}_dashboard_{dashboard_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

    async def create_and_assign_tag(
        self, workflow_id: str, user_id: str, dashboard_id: str
    ) -> bool:
        """Create and assign a tag to a workflow"""
        tag_name = f"user_{user_id}_dashboard_{dashboard_id}"

        tag_data = {"name": tag_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # First check if tag already exists
            tags_response = await client.get(
                f"{self.base_url}/tags", headers=self.headers
            )

            tag_id = None
            if tags_response.status_code == 200:
                existing_tags = tags_response.json().get("data", [])
                existing_tag = next(
                    (tag for tag in existing_tags if tag.get("name") == tag_name), None
                )
                if existing_tag:
                    tag_id = existing_tag.get("id")

            # Create tag if it doesn't exist
            if not tag_id:
                response = await client.post(
                    f"{self.base_url}/tags", json=tag_data, headers=self.headers
                )
                if response.status_code in [200, 201]:
                    tag_id = response.json().get("id")
                else:
                    return False

            # Assign tag to workflow using PUT endpoint (as per n8n API)
            assign_response = await client.put(
                f"{self.base_url}/workflows/{workflow_id}/tags",
                json=[{"id": tag_id}],
                headers=self.headers,
            )
            return assign_response.status_code in [200, 201]

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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/workflows", json=workflow_data, headers=self.headers
            )

            if response.status_code in [200, 201]:
                result = response.json()

                # Add tags
                await self.create_and_assign_tag(
                    result.get("id"), user_id, dashboard_id
                )

                return result
            else:
                return None

    async def update_workflow(
        self, workflow_id: str, workflow_data: dict
    ) -> Optional[dict]:
        """Update existing workflow using PUT endpoint"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                f"{self.base_url}/workflows/{workflow_id}",
                json=workflow_data,
                headers=self.headers,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

    async def activate_workflow(self, workflow_id: str, active: bool = True) -> bool:
        """Activate or deactivate workflow"""
        endpoint = "activate" if active else "deactivate"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/workflows/{workflow_id}/{endpoint}",
                headers=self.headers,
            )

            return response.status_code == 200

    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate workflow"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/workflows/{workflow_id}/deactivate",
                headers=self.headers,
            )

            return response.status_code == 200

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow from n8n"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/workflows/{workflow_id}",
                headers=self.headers,
            )

            return response.status_code == 200

    async def create_or_update_workflow(
        self,
        db_session: AsyncSession,
        schedule: Schedule,
        user_info: dict,
        workspace_id: str,
        project_id: str,
    ) -> Optional[N8NWorkflow]:
        """
        Create or update n8n workflow for a schedule
        This is the main method called when schedules are created/updated
        """
        user_id = user_info["user_id"]
        dashboard_id = str(schedule.dashboard_id)

        # Check if workflow already exists in database
        existing_workflow = await self.get_workflow_by_schedule(
            db_session, schedule.schedule_id
        )

        # Build schedule payload for workflow
        schedule_payload = {
            "hour": schedule.hour,
            "minute": schedule.minute,
            "period": schedule.period.value,
            "frequency": schedule.frequency.value.lower()
            if schedule.frequency
            else "daily",
            "daysOfWeek": schedule.days_of_week or [],
            "dayOfMonth": schedule.day_of_month or 1,
            "startDate": schedule.start_date.strftime("%Y-%m-%d"),
            "endDate": schedule.end_date.strftime("%Y-%m-%d")
            if schedule.end_date
            else "2030-12-31",
            "timezone": schedule.timezone,
        }

        workflow_name = f"Dashboard {dashboard_id} - Schedule {schedule.schedule_id}"
        tag_name = f"user_{user_id}_dashboard_{dashboard_id}"

        if existing_workflow:
            # Update existing workflow
            workflow_data = self.build_workflow(
                workflow_name,
                user_id,
                dashboard_id,
                workspace_id,
                project_id,
                schedule_payload,
            )

            # Update workflow in n8n
            n8n_result = await self.update_workflow(
                existing_workflow.n8n_workflow_id, workflow_data
            )

            if n8n_result:
                # Update database record
                existing_workflow.workflow_data = workflow_data
                existing_workflow.updated_at = datetime.now()
                db_session.add(existing_workflow)
                await db_session.commit()

                # Activate/deactivate based on schedule status
                if schedule.is_active:
                    await self.activate_workflow(
                        existing_workflow.n8n_workflow_id, True
                    )
                    existing_workflow.status = N8NWorkflowStatus.ACTIVE
                    existing_workflow.last_activated_at = datetime.now()
                else:
                    await self.activate_workflow(
                        existing_workflow.n8n_workflow_id, False
                    )
                    existing_workflow.status = N8NWorkflowStatus.INACTIVE
                    existing_workflow.last_deactivated_at = datetime.now()

                db_session.add(existing_workflow)
                await db_session.commit()

                # Invalidate cache for this workflow and dashboard using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:n8n",
                    f"entity:workflow:{schedule.schedule_id}",
                    f"entity:dashboard:{schedule.dashboard_id}",
                    f"collection:n8n:dashboard:{schedule.dashboard_id}",
                    f"collection:n8n:user:{user_id}",
                )

                return existing_workflow
        else:
            # Create new workflow
            n8n_result = await self.create_workflow(
                workflow_name,
                user_id,
                dashboard_id,
                workspace_id,
                project_id,
                schedule_payload,
            )

            if n8n_result:
                # Create database record
                workflow = N8NWorkflow(
                    dashboard_id=schedule.dashboard_id,
                    schedule_id=schedule.schedule_id,
                    n8n_workflow_id=n8n_result.get("id"),
                    n8n_tag_name=tag_name,
                    workflow_name=workflow_name,
                    workflow_data=self.build_workflow(
                        workflow_name,
                        user_id,
                        dashboard_id,
                        workspace_id,
                        project_id,
                        schedule_payload,
                    ),
                    status=N8NWorkflowStatus.ACTIVE
                    if schedule.is_active
                    else N8NWorkflowStatus.INACTIVE,
                    last_activated_at=datetime.now() if schedule.is_active else None,
                )

                db_session.add(workflow)
                await db_session.commit()

                # Activate if schedule is active
                if schedule.is_active:
                    await self.activate_workflow(workflow.n8n_workflow_id, True)

                return workflow

        return None

    @cached_n8n_workflows(ttl=30)
    async def get_workflow_by_schedule(
        self, db_session: AsyncSession, schedule_id: uuid.UUID
    ) -> Optional[N8NWorkflow]:
        """Get workflow by schedule ID"""
        result = await db_session.execute(
            select(N8NWorkflow).where(N8NWorkflow.schedule_id == schedule_id)
        )
        return result.scalar_one_or_none()

    @cached_n8n_workflows(ttl=30)
    async def get_workflows_by_dashboard(
        self, db_session: AsyncSession, dashboard_id: uuid.UUID
    ) -> List[N8NWorkflow]:
        """Get all workflows for a dashboard"""
        result = await db_session.execute(
            select(N8NWorkflow).where(N8NWorkflow.dashboard_id == dashboard_id)
        )
        return list(result.scalars().all())

    @cached_n8n_workflows(ttl=30)
    async def get_workflows_by_user(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> List[N8NWorkflow]:
        """Get all workflows for a user (based on tag pattern)"""
        result = await db_session.execute(
            select(N8NWorkflow).where(
                N8NWorkflow.n8n_tag_name.like(f"user_{user_id}_%")
            )
        )
        return list(result.scalars().all())

    async def update_workflow_status(
        self,
        db_session: AsyncSession,
        workflow_id: uuid.UUID,
        status: N8NWorkflowStatus,
    ) -> bool:
        """Update workflow status"""
        await db_session.execute(
            update(N8NWorkflow)
            .where(N8NWorkflow.workflow_id == workflow_id)
            .values(status=status, updated_at=datetime.now())
        )
        await db_session.commit()

        # Invalidate cache for this workflow
        workflow = await self.get_workflow_by_schedule(db_session, workflow_id)
        if workflow:
            cache_manager = await get_cache()
            await cache_manager.delete_multi_level_by_tags(
                f"resource:n8n",
                f"entity:workflow:{workflow_id}",
                f"entity:dashboard:{workflow.dashboard_id}",
                f"collection:n8n:dashboard:{workflow.dashboard_id}",
                f"collection:n8n:user",
            )

        return True

    async def delete_workflow_by_schedule(
        self, db_session: AsyncSession, schedule_id: uuid.UUID
    ) -> bool:
        """Delete workflow by schedule ID"""
        workflow = await self.get_workflow_by_schedule(db_session, schedule_id)
        if workflow:
            # Delete from n8n
            success = await self.delete_workflow(workflow.n8n_workflow_id)
            if success:
                # Delete from database
                await db_session.delete(workflow)
                await db_session.commit()
                # Invalidate cache for this schedule using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:n8n",
                    f"entity:workflow:{schedule_id}",
                    f"entity:dashboard:{workflow.dashboard_id}",
                    f"collection:n8n:dashboard:{workflow.dashboard_id}",
                    f"collection:n8n:user",
                )

                return True
        return False

    async def create_execution_record(
        self,
        db_session: AsyncSession,
        workflow_id: uuid.UUID,
        execution_status: N8NExecutionStatus,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        success_count: Optional[int] = None,
        error_count: Optional[int] = None,
        execution_logs: Optional[dict] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
        n8n_execution_id: Optional[str] = None,
    ) -> N8NWorkflowExecution:
        """Create execution record for workflow run"""
        execution = N8NWorkflowExecution(
            workflow_id=workflow_id,
            execution_status=execution_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            success_count=success_count,
            error_count=error_count,
            execution_logs=execution_logs,
            error_message=error_message,
            stack_trace=stack_trace,
            n8n_execution_id=n8n_execution_id,
        )

        db_session.add(execution)
        await db_session.commit()

        # Invalidate execution cache for this workflow using tags
        cache_manager = await get_cache()
        await cache_manager.delete_multi_level_by_tags(
            f"resource:n8n",
            f"entity:workflow:{workflow_id}",
            f"collection:n8n:executions:{workflow_id}",
        )

        return execution

    @cached_n8n_workflows(
        ttl=10
    )  # Shorter TTL for execution history as it changes frequently
    async def get_executions_by_workflow(
        self, db_session: AsyncSession, workflow_id: uuid.UUID, limit: int = 50
    ) -> List[N8NWorkflowExecution]:
        """Get execution history for a workflow"""
        result = await db_session.execute(
            select(N8NWorkflowExecution)
            .where(N8NWorkflowExecution.workflow_id == workflow_id)
            .order_by(N8NWorkflowExecution.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @cached_n8n_workflows(ttl=15)  # Shorter TTL for external API calls
    async def async_wrapper(self, *args, **kwargs) -> dict:
        """
        Async wrapper for n8n workflows API that accepts *args and **kwargs
        Provides flexible parameter handling for n8n API calls
        """
        try:
            # Extract method and endpoint from kwargs or first arg
            method = kwargs.pop("method", "GET").upper()
            endpoint = kwargs.pop("endpoint", "/workflows")

            # Build URL
            url = f"{self.base_url}{endpoint}"

            # Prepare request parameters
            params = {}
            headers = self.headers.copy()

            # Handle different HTTP methods
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    # Add query parameters from kwargs
                    params.update(kwargs)
                    response = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    # Use kwargs as request body
                    response = await client.post(url, json=kwargs, headers=headers)
                elif method == "PUT":
                    response = await client.put(url, json=kwargs, headers=headers)
                elif method == "PATCH":
                    response = await client.patch(url, json=kwargs, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

            # Handle response
            if response.status_code in [200, 201]:
                return response.json()
            else:
                return {
                    "error": f"API call failed with status {response.status_code}",
                    "status_code": response.status_code,
                    "response_text": response.text,
                }

        except Exception as e:
            return {
                "error": f"API wrapper error: {str(e)}",
                "exception_type": type(e).__name__,
            }

    async def get_all_workflows(self) -> List[dict]:
        """Get all workflows from n8n"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/workflows", headers=self.headers
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                return []
