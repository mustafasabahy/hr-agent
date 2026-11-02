"""Deterministic schema/dispatch checks, not claims about real model judgment."""

import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from pydantic import ValidationError
from database import connect, initialize
from operation_schemas import build_schema
from services.common import (
    ACTOR,
    OPERATIONS,
    SCHEMAS,
    METADATA,
    execute,
    operation_details,
)
from tools.company_tools import COMPANY_TOOLS, describe_operation, dispatch

SAMPLES = {
    "employee_id": "E001",
    "employee_ids": ["E001", "E004"],
    "target_employee_id": "E002",
    "assignee_id": "E001",
    "start_date": "2030-01-07",
    "end_date": "2030-01-08",
    "new_start_date": "2030-02-04",
    "new_end_date": "2030-02-05",
    "date": "2026-10-30",
    "shift_date": "2030-01-07",
    "due_date": "2030-01-07",
    "month": "2026-09",
    "date_range": "2026-10-01/2026-10-02",
    "period": "2026-10-01/2026-10-02",
    "corrected_time": "08:55",
    "year": 2026,
    "request_id": 1,
    "ticket_id": 1,
    "task_id": 1,
    "quantity": 3,
    "amount": 1500.0,
    "hours": 2.0,
    "decision": "approve",
    "status": "in_progress",
    "field": "preferred_name",
    "value": "Ahmed Demo",
    "name": "Ahmed",
    "department_id": "ENG",
    "target_department": "Finance",
    "project_id": "ALPHA",
    "item_id": "LAPTOP",
    "item_name": "laptops",
    "asset_id": "ASSET-1",
    "course_id": "PYTHON",
    "order_id": "ORD-1",
    "invoice_id": "INV-100",
    "vendor_id": "V001",
    "invoice_number": "100",
    "policy_type": "annual",
    "document_type": "employment_verification",
    "category": "travel",
    "receipt_reference": "DEMO-RECEIPT",
    "issue_description": "Fictional laptop issue",
    "description": "Fictional work purchase",
    "reason": "Fictional escalation reason",
    "new_address": "Fictional street 10",
    "software_name": "Microsoft Office",
    "device_type": "mouse",
    "title": "Prepare report",
    "query": "remote work",
}


class ToolContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"COMPANY_DB_PATH": str(Path(self.temp.name) / "contracts.db")}
        )
        self.env.start()
        initialize()
        self.token = ACTOR.set("ahmed")

    def tearDown(self):
        ACTOR.reset(self.token)
        self.env.stop()
        self.temp.cleanup()

    def snapshot(self):
        c = connect()
        try:
            return "\n".join(c.iterdump())
        finally:
            c.close()

    def arguments(self, name):
        return {key: SAMPLES[key] for key in SCHEMAS[name].model_fields}

    def test_metadata_and_all_sixty_discoverable(self):
        self.assertEqual(len(COMPANY_TOOLS), 11)
        names = [t.name for t in COMPANY_TOOLS]
        self.assertEqual(len(set(names)), 11)
        self.assertEqual(len(SCHEMAS), 60)
        for tool in COMPANY_TOOLS:
            with self.subTest(tool=tool.name):
                self.assertGreater(len(tool.description), 160)
                (
                    self.assertIn("required", tool.description.lower())
                    if tool.name.endswith("_operations")
                    else None
                )
                self.assertFalse(
                    tool.get_input_schema().model_json_schema()["additionalProperties"]
                )
        for name, schema in SCHEMAS.items():
            with self.subTest(operation=name):
                detail = describe_operation.invoke({"operation": name})
                self.assertEqual(
                    {k: v for k, v in detail.items() if k != "trusted_context"},
                    operation_details(name),
                )
                required = [
                    n for n, f in schema.model_fields.items() if f.is_required()
                ]
                optional = [
                    n for n, f in schema.model_fields.items() if not f.is_required()
                ]
                self.assertEqual(detail["required_fields"], required)
                self.assertEqual(detail["optional_fields"], optional)
                self.assertEqual(
                    set(required + optional),
                    set(inspect.signature(OPERATIONS[name]).parameters),
                )
                self.assertEqual(
                    detail["requires_confirmation"], METADATA[name]["write"]
                )
                self.assertTrue(detail["authorization"])
                document = schema.model_json_schema()
                self.assertFalse(document["additionalProperties"])
                for field in document["properties"].values():
                    self.assertTrue(field["description"])
                target = (
                    "get_employee"
                    if name == "get_employee"
                    else METADATA[name]["module"] + "_operations"
                )
                exposed = next(t for t in COMPANY_TOOLS if t.name == target)
                if target != "get_employee":
                    self.assertIn(
                        name,
                        exposed.get_input_schema().model_json_schema()["properties"][
                            "operation"
                        ]["enum"],
                    )
                    self.assertIn(name, exposed.description)

    def test_missing_fields_never_reach_service_or_create_proposals(self):
        for name, schema in SCHEMAS.items():
            for field in schema.model_fields:
                if not schema.model_fields[field].is_required():
                    continue
                with self.subTest(operation=name, field=field):
                    args = self.arguments(name)
                    del args[field]
                    before = self.snapshot()
                    spy = Mock()
                    with patch.dict(OPERATIONS, {name: spy}):
                        result = execute(name, args)
                    self.assertFalse(result["ok"])
                    self.assertIn(field, result["missing_fields"])
                    self.assertTrue(result["clarification_required"])
                    spy.assert_not_called()
                    self.assertEqual(before, self.snapshot())

    def test_valid_schemas_reach_exact_registered_service(self):
        for name in SCHEMAS:
            with self.subTest(operation=name):
                args = self.arguments(name)
                spy = Mock(return_value={"observed": name})
                with patch.dict(OPERATIONS, {name: spy}):
                    result = execute(name, args)
                self.assertTrue(result["ok"], result)
                spy.assert_called_once_with(
                    **SCHEMAS[name].model_validate(args).model_dump()
                )

    def test_all_operations_reject_extra_fields_without_service_execution(self):
        for name in SCHEMAS:
            with self.subTest(operation=name):
                args = self.arguments(name)
                args["pretend_admin"] = True
                before = self.snapshot()
                spy = Mock()
                with patch.dict(OPERATIONS, {name: spy}):
                    result = execute(name, args)
                self.assertFalse(result["ok"])
                self.assertEqual(result["errors"][0]["type"], "extra_forbidden")
                spy.assert_not_called()
                self.assertEqual(before, self.snapshot())

    def test_invalid_types_and_ranges(self):
        cases = [
            ("request_leave", {"start_date": "10/12/2026"}),
            ("request_leave", {"start_date": "2026-02-30"}),
            ("request_leave", {"end_date": "2029-01-01"}),
            ("request_leave", {"employee_id": 123}),
            ("request_leave", {"employee_id": " "}),
            ("request_leave", {"employee_id": "E999"}),
            ("request_inventory_item", {"quantity": 0}),
            ("request_inventory_item", {"quantity": -1}),
            ("request_inventory_item", {"quantity": 1.5}),
            ("request_inventory_item", {"quantity": True}),
            ("submit_expense_request", {"amount": -1500.0}),
            ("submit_expense_request", {"amount": float("inf")}),
            ("submit_expense_request", {"amount": 0.001}),
            ("submit_expense_request", {"amount": "1500"}),
            ("get_attendance", {"month": "2026-13"}),
            ("check_late_arrivals", {"date_range": "2026-10-03/2026-10-01"}),
            ("request_attendance_correction", {"corrected_time": "25:10"}),
            ("update_task_status", {"status": "approved"}),
            ("cancel_leave", {"request_id": 0}),
            ("review_leave_request", {"decision": "maybe"}),
            ("create_project_task", {"title": " "}),
            ("check_team_leave_conflict", {"employee_ids": ["E001", "E001"]}),
        ]
        for name, override in cases:
            with self.subTest(operation=name, override=override):
                args = {**self.arguments(name), **override}
                before = self.snapshot()
                result = execute(name, args)
                self.assertFalse(result["ok"], result)
                self.assertEqual(before, self.snapshot())
        # Unknown but structurally valid IDs are rejected by services, not Pydantic.
        self.assertEqual(
            execute("get_leave_balance", {"employee_id": "E999"})["code"], "not_found"
        )

    def test_structured_errors_do_not_echo_input(self):
        result = execute(
            "submit_expense_request",
            {
                **self.arguments("submit_expense_request"),
                "amount": "PRIVATE-INPUT-DO-NOT-ECHO",
            },
        )
        self.assertNotIn("PRIVATE-INPUT-DO-NOT-ECHO", json.dumps(result))
        self.assertNotIn("https://errors.pydantic.dev", json.dumps(result))
        self.assertTrue(result["errors"])
        self.assertEqual(result["operation"], "submit_expense_request")

    def test_optional_defaults_supported_without_inventing_new_business_fields(self):
        def example(name: str, value: str | None = None):
            pass

        schema = build_schema(example)
        self.assertEqual(schema.model_json_schema()["required"], ["name"])
        self.assertIsNone(schema.model_validate({"name": "Ahmed"}).value)
        self.assertEqual(
            schema.model_validate({"name": "Ahmed", "value": "Demo"}).value, "Demo"
        )
        self.assertEqual(
            {n: operation_details(n)["optional_fields"] for n in SCHEMAS if operation_details(n)["optional_fields"]},
            {"get_leave_balance": ["year"]},
        )

    def test_unknown_operation_and_wrong_module_rejected(self):
        before = self.snapshot()
        self.assertFalse(execute("invented_action", {})["ok"])
        self.assertFalse(
            describe_operation.invoke({"operation": "invented_action"})["ok"]
        )
        self.assertFalse(
            dispatch("hr", "get_payslip", {"employee_id": "E001", "month": "2026-09"})[
                "ok"
            ]
        )
        tool = next(t for t in COMPANY_TOOLS if t.name == "hr_operations")
        result = json.loads(
            tool.invoke({"operation": "invented_action", "arguments": {}})
        )
        self.assertEqual(result["code"], "validation_error")
        self.assertEqual(before, self.snapshot())

    def test_representative_dispatch_from_all_nine_modules(self):
        # Scripted calls test wiring and canonical argument types, not LLM selection.
        representatives = {
            "hr": "get_leave_balance",
            "attendance": "get_attendance",
            "employees": "get_employee_manager",
            "payroll": "get_payslip",
            "it": "create_it_ticket",
            "inventory": "check_inventory",
            "customers": "get_order_status",
            "finance": "get_invoice_status",
            "projects": "get_project_progress",
        }
        for module, name in representatives.items():
            with self.subTest(module=module):
                exposed = next(
                    t for t in COMPANY_TOOLS if t.name == module + "_operations"
                )
                args = self.arguments(name)
                spy = Mock(return_value={"operation": name})
                with patch.dict(OPERATIONS, {name: spy}):
                    result = exposed.invoke({"operation": name, "arguments": args})
                self.assertTrue(result["ok"], result)
                spy.assert_called_once()

    def test_year_provenance_guard_blocks_fabricated_calendar_arguments(self):
        from tools.input_context import USER_MESSAGE

        tool = next(t for t in COMPANY_TOOLS if t.name == "hr_operations")
        token = USER_MESSAGE.set("I want vacation from December 10 to December 15.")
        try:
            before = self.snapshot()
            spy = Mock()
            with patch.dict(OPERATIONS, {"request_leave": spy}):
                result = tool.invoke(
                    {
                        "operation": "request_leave",
                        "arguments": {
                            "employee_id": "E001",
                            "start_date": "2030-12-10",
                            "end_date": "2030-12-15",
                        },
                    }
                )
            self.assertFalse(result["ok"])
            self.assertEqual(result["missing_fields"], ["year"])
            spy.assert_not_called()
            self.assertEqual(before, self.snapshot())
        finally:
            USER_MESSAGE.reset(token)

    def test_explicit_and_relative_calendar_values(self):
        from tools.input_context import USER_MESSAGE, calendar_guard
        from database import today
        from datetime import timedelta

        for message, args in [
            (
                "Vacation 2030-12-10 to 2030-12-15",
                {"start_date": "2030-12-10", "end_date": "2030-12-15"},
            ),
            (
                "Vacation ٢٠٣٠-١٢-١٠ to ٢٠٣٠-١٢-١٥",
                {"start_date": "2030-12-10", "end_date": "2030-12-15"},
            ),
            ("Work from home tomorrow", {"date": str(today() + timedelta(days=1))}),
            ("الشغل من البيت بكرة", {"date": str(today() + timedelta(days=1))}),
            ("This year's leave history", {"year": today().year}),
        ]:
            with self.subTest(message=message):
                token = USER_MESSAGE.set(message)
                try:
                    self.assertIsNone(calendar_guard(args))
                finally:
                    USER_MESSAGE.reset(token)

    def test_trusted_identity_hint_without_silent_target_substitution(self):
        tool = next(t for t in COMPANY_TOOLS if t.name == "hr_operations")
        result = tool.invoke({"operation": "get_leave_balance", "arguments": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["trusted_context"]["employee_id"], "E001")
        self.assertFalse(result["clarification_required"])
        # Supplying a different ID still triggers service authorization, never rebinding to self.
        denied = tool.invoke(
            {"operation": "get_leave_balance", "arguments": {"employee_id": "E002"}}
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["code"], "forbidden")

    def test_ambiguous_employee_names_are_not_arbitrarily_resolved(self):
        c = connect()
        c.execute(
            "INSERT INTO employees(id,name,department_id,role,hire_date,status) VALUES (?,?,?,?,?,?)",
            ("E008", "ahmed", "HR", "Fictional tester", "2020-01-01", "active"),
        )
        c.commit()
        c.close()
        before = self.snapshot()
        result = execute("get_employee", {"name": "Ahmed"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "ambiguous_employee")
        self.assertEqual(before, self.snapshot())

    def test_api_propagates_year_context_into_langgraph_tools(self):
        from fastapi.testclient import TestClient
        from main import app
        from langchain.agents import create_agent
        from langchain_core.language_models.fake_chat_models import (
            FakeMessagesListChatModel,
        )
        from langchain_core.messages import AIMessage

        class ScriptedModel(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "hr_operations",
                        "args": {
                            "operation": "request_leave",
                            "arguments": {
                                "employee_id": "E001",
                                "start_date": "2030-12-10",
                                "end_date": "2030-12-15",
                            },
                        },
                        "id": "fabricated-year",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Which year?"),
        ]
        graph = create_agent(
            model=ScriptedModel(responses=responses), tools=COMPANY_TOOLS
        )
        # This deliberately forces a bad model call to test the guard, not model clarification skill.
        with TestClient(app) as c, patch(
            "main.get_agent", return_value=graph
        ), patch.dict(os.environ, {"OPENAI_API_KEY": "offline-placeholder"}):
            before = self.snapshot()
            response = c.post(
                "/chat", json={"message": "Vacation December 10 to December 15"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(before, self.snapshot())
        conn = connect()
        try:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM confirmations").fetchone()[0], 0
            )
        finally:
            conn.close()

    def test_live_cases_cover_requested_clarification_matrix(self):
        from scripts.live_tool_checks import cases

        catalog = cases()
        for case in [
            "complete_leave",
            "missing_leave_dates",
            "only_start_date",
            "ambiguous_cancel",
            "missing_quantity",
            "missing_amount",
            "missing_project",
            "missing_title",
            "unknown_operation",
            "unauthorized_payslip",
        ]:
            self.assertIn(case, catalog)
        for module, case in {
            "hr": "hr_balance",
            "attendance": "attendance_month",
            "employees": "employee_manager",
            "payroll": "payroll_self",
            "it": "it_ticket",
            "inventory": "inventory_stock",
            "customers": "customer_order",
            "finance": "finance_invoice",
            "projects": "project_progress",
        }.items():
            self.assertEqual(METADATA[catalog[case]["operation"]]["module"], module)

    def test_api_exposes_metadata_and_preserves_structured_errors(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as c:
            detail = c.get("/operations").json()["operations"]["request_leave"]
            self.assertEqual(detail, operation_details("request_leave"))
            r = c.post(
                "/operations/request_leave", json={"arguments": {"employee_id": "E001"}}
            )
            self.assertEqual(r.status_code, 422)
            self.assertTrue(r.json()["clarification_required"])
            self.assertEqual(
                set(r.json()["missing_fields"]), {"start_date", "end_date"}
            )
            self.assertEqual(c.get("/employees/ ahMED ").json()["name"], "Ahmed")


if __name__ == "__main__":
    unittest.main()
