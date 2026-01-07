"""
Features API Test File
Tests shares, schedules, and integrations operations
"""

import asyncio
import uuid

import httpx

BASE_URL = "http://localhost:8021"
AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZTBjYmE4Ni0xMTBhLTRkNDUtYTIwNS0xODI5NjM4ODBkNzUiLCJleHAiOjE3OTc2NTkzNTB9.2xvermcsNaRFqJQEJDTEcyg6_b18WcpZaU0UEkK49nQ"
DASHBOARD_ID = "YOUR_DASHBOARD_ID_HERE"


class FeaturesTester:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    async def create_shares(self, dashboard_id: str):
        """Create multiple shares"""
        payload = {
            "dashboard_id": dashboard_id,
            "share_info": [
                {
                    "entity_type": "user",
                    "entity_id": str(uuid.uuid4()),
                    "permission": "read",
                },
                {
                    "entity_type": "team",
                    "entity_id": str(uuid.uuid4()),
                    "permission": "write",
                },
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/shares", json=payload, headers=self.headers
            )
            response.raise_for_status()
            result = response.json()
            print("Multiple shares created")
            return result

    async def create_single_share(self, dashboard_id: str):
        """Create single share"""
        payload = {
            "dashboard_id": dashboard_id,
            "share_info": {
                "entity_type": "group",
                "entity_id": str(uuid.uuid4()),
                "permission": "read",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/shares", json=payload, headers=self.headers
            )
            response.raise_for_status()
            result = response.json()
            print("Single share created")
            return result

    async def update_share_permission(self, share_id: str):
        """Update share permission to write"""
        payload = {"permission": "write"}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/features/shares/{share_id}/permission",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            print(f"Share permission updated: {share_id}")
            return response.json()

    async def delete_share(self, share_id: str):
        """Delete share"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/features/shares/{share_id}", headers=self.headers
            )
            response.raise_for_status()
            print(f"Share deleted: {share_id}")
            return response.json()

    async def create_schedules(self, dashboard_id: str):
        """Create multiple schedules"""
        payload = {
            "dashboard_id": dashboard_id,
            "schedule_info": [
                {
                    "scheduleType": "scheduled",
                    "frequency": "daily",
                    "startDate": "2024-01-01T10:00:00Z",
                    "endDate": "2024-12-31T10:00:00Z",
                    "hour": 10,
                    "minute": 30,
                    "period": "AM",
                    "timeZone": "UTC",
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/schedules",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()
            print("Multiple schedules created")
            return result

    async def create_single_schedule(self, dashboard_id: str):
        """Create single schedule"""
        payload = {
            "dashboard_id": dashboard_id,
            "schedule_info": {
                "scheduleType": "scheduled",
                "frequency": "weekly",
                "startDate": "2024-01-01T14:00:00Z",
                "endDate": "2024-12-31T14:00:00Z",
                "hour": 14,
                "minute": 0,
                "period": "PM",
                "daysOfWeek": ["Mon", "Wed", "Fri"],
                "timeZone": "UTC",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/schedules",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()
            print("Single schedule created")
            return result

    async def update_schedule_status(self, schedule_id: str):
        """Update schedule status"""
        payload = {"is_active": False}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/features/schedules/{schedule_id}/status",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            print(f"Schedule status updated: {schedule_id}")
            return response.json()

    async def delete_schedule(self, schedule_id: str):
        """Delete schedule"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/features/schedules/{schedule_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            print(f"Schedule deleted: {schedule_id}")
            return response.json()

    async def create_integrations(self, dashboard_id: str):
        """Create multiple integrations"""
        payload = {"dashboard_id": dashboard_id, "integration_type": ["webhook", "api"]}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/integrations",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()
            print("Multiple integrations created")
            return result

    async def create_single_integration(self, dashboard_id: str):
        """Create single integration"""
        payload = {"dashboard_id": dashboard_id, "integration_type": "email"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/features/integrations",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()
            print("Single integration created")
            return result

    async def update_integration_config(self, integration_id: str):
        """Update integration config"""
        payload = {"config": {"email": "test@example.com"}}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/features/integrations/{integration_id}/config",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            print(f"Integration config updated: {integration_id}")
            return response.json()

    async def delete_integration(self, integration_id: str):
        """Delete integration"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/features/integrations/{integration_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            print(f"Integration deleted: {integration_id}")
            return response.json()

    async def run_tests(self, dashboard_id: str):
        """Run all features tests"""
        print("Starting Features Tests")

        try:
            # Share tests
            print("\n1. Testing Shares:")
            await self.create_shares(dashboard_id)

            single_share = await self.create_single_share(dashboard_id)
            if isinstance(single_share, dict) and "share_id" in single_share:
                share_id = single_share["share_id"]
                await self.update_share_permission(share_id)
                await self.delete_share(share_id)

            # Schedule tests
            print("\n2. Testing Schedules:")
            await self.create_schedules(dashboard_id)

            single_schedule = await self.create_single_schedule(dashboard_id)
            if isinstance(single_schedule, dict) and "schedule_id" in single_schedule:
                schedule_id = single_schedule["schedule_id"]
                await self.update_schedule_status(schedule_id)
                await self.delete_schedule(schedule_id)

            # Integration tests
            print("\n3. Testing Integrations:")
            await self.create_integrations(dashboard_id)

            single_integration = await self.create_single_integration(dashboard_id)
            if (
                isinstance(single_integration, dict)
                and "integration_id" in single_integration
            ):
                integration_id = single_integration["integration_id"]
                await self.update_integration_config(integration_id)
                await self.delete_integration(integration_id)

            print("\nAll features tests completed successfully!")

        except Exception as e:
            print(f"Test failed: {e}")


async def main():
    if AUTH_TOKEN == "YOUR_AUTH_TOKEN_HERE":
        print("Set AUTH_TOKEN variable")
        return

    if DASHBOARD_ID == "YOUR_DASHBOARD_ID_HERE":
        print("Set DASHBOARD_ID variable")
        return

    tester = FeaturesTester(BASE_URL, AUTH_TOKEN)
    await tester.run_tests(DASHBOARD_ID)


if __name__ == "__main__":
    asyncio.run(main())
