# Real leave workflow demonstration

Workflow `4d7da3d440a44850906aa87cb782fd94`; employee Ahmed/E001; one thread `01a19bfa-feb9-76fd-89f9-4676e41cfdde`.

## Scope and actual application limitations

No application source/business rules were changed for this demonstration. The existing Studio before_agent hook discards older messages at each turn, so the same thread ID is persistent but relevant conversational memory is **not retained**. This acceptance criterion fails; successful fully restated turns do not prove memory. A separate fix proposal is provided for review only. get_leave_balance reports the current year; January 2027 usage must be checked against the actual 2027 ledger, not confused with 2026.

## Initial state

Company-local date: 2026-11-02. Requested dates: 2027-01-11 through 2027-01-15. Explicit January dates supersede the vague 'next month' in the first message; no dates were silently changed.

```json
{
  "employee": {
    "id": "E001",
    "name": "Ahmed",
    "department_id": "ENG",
    "manager_id": "E004",
    "hire_date": "2025-09-28",
    "status": "active"
  },
  "manager": [
    {
      "demo_user": "nadia",
      "employee_id": "E004",
      "name": "Nadia",
      "roles": "[\"employee\", \"manager\"]"
    }
  ],
  "balances": {
    "2026": {
      "year": 2026,
      "annual_allowance": 30,
      "used_days": 0,
      "remaining_days": 30
    },
    "2027": {
      "year": 2027,
      "annual_allowance": 30,
      "used_days": 0,
      "remaining_days": 30
    }
  },
  "pending_requests": [],
  "approved_requests": [],
  "weekends": [
    5,
    6
  ],
  "holidays": [
    {
      "day": "2026-12-25",
      "name": "Company winter holiday"
    },
    {
      "day": "2027-12-25",
      "name": "Company winter holiday"
    }
  ]
}
```

## Conversation and actual tool execution

### Turn 1: incomplete_request

Input: I want to take some annual leave next month.

Actual response: Please provide the exact dates for your annual leave next month, including the year, so I can assist you with the request.

```json
{
  "run_id": "01a19bfa-fec3-75e0-9843-a8e082d24d0c",
  "tool_calls": [],
  "tool_results": []
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfa-fec3-75e0-9843-a8e082d24d0c?poll=true)

### Turn 2: exact_dates

Input: I want to take leave from January 11, 2027 to January 15, 2027.

Actual response: Your leave request from January 11, 2027 to January 15, 2027 has been prepared and is pending human confirmation. To finalize the request, a human must confirm it through the appropriate confirmation process. Let me know if you need any further assistance.

Pending proposal 8bb96896b51045809976ec7a42a70fe0: confirmation_required. No business change committed. Inspect/confirm via the existing FastAPI /confirmations/8bb96896b51045809976ec7a42a70fe0 workflow with the matching demo user and database.

```json
{
  "run_id": "01a19bfb-29d3-70a4-ab57-06870f108398",
  "tool_calls": [
    {
      "id": "call_UzErLK844B66CLwOtgRvFSns",
      "tool": "hr_operations",
      "operation": "check_leave_overlap",
      "arguments": {
        "employee_id": "E001",
        "start_date": "2027-01-11",
        "end_date": "2027-01-15"
      }
    },
    {
      "id": "call_sbTvzGl3waLnPhToWvfjixOT",
      "tool": "hr_operations",
      "operation": "request_leave",
      "arguments": {
        "employee_id": "E001",
        "start_date": "2027-01-11",
        "end_date": "2027-01-15"
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_UzErLK844B66CLwOtgRvFSns",
      "output": {
        "ok": true,
        "data": {
          "overlap": false,
          "requests": []
        }
      }
    },
    {
      "tool_call_id": "call_sbTvzGl3waLnPhToWvfjixOT",
      "output": {
        "ok": true,
        "data": {
          "status": "confirmation_required",
          "confirmation_id": "8bb96896b51045809976ec7a42a70fe0",
          "operation": "request_leave",
          "arguments": {
            "employee_id": "E001",
            "start_date": "2027-01-11",
            "end_date": "2027-01-15"
          },
          "expires_at": "2026-11-02T11:33:14.534727+00:00",
          "instruction": "The human must POST {\"confirm\":true} to /confirmations/8bb96896b51045809976ec7a42a70fe0. No business change has been made."
        }
      }
    }
  ]
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfb-29d3-70a4-ab57-06870f108398?poll=true)

### Turn 3: read_only_validations

Input: For my annual leave from 2027-01-11 to 2027-01-15, verify eligibility, working days excluding holidays/weekends and overlap, and show my current-year balance and 2027 leave history. Read-only checks only; do not create or modify a request.

Actual response: You are eligible for annual leave with active employment and sufficient tenure. The requested leave from 2027-01-11 to 2027-01-15 includes 5 working days, excluding weekends and holidays. There is no overlap with existing leave requests. Your current year (2026) leave balance shows 30 days allowance with 0 used and 30 remaining. For 2027, you have no recorded leave requests yet. Let me know if you need further assistance.

```json
{
  "run_id": "01a19bfb-6336-724b-b52c-6674d2435d6b",
  "tool_calls": [
    {
      "id": "call_uP506dlJjcd6qIWE0NlKdV9w",
      "tool": "hr_operations",
      "operation": "check_leave_eligibility",
      "arguments": {
        "employee_id": "E001"
      }
    },
    {
      "id": "call_vKZcqyzcFBzAmP6fYfOVNM9k",
      "tool": "hr_operations",
      "operation": "calculate_leave_days",
      "arguments": {
        "start_date": "2027-01-11",
        "end_date": "2027-01-15",
        "employee_id": "E001"
      }
    },
    {
      "id": "call_bwl3LpBeeTB7HhL6XTZXqHBF",
      "tool": "hr_operations",
      "operation": "check_leave_overlap",
      "arguments": {
        "employee_id": "E001",
        "start_date": "2027-01-11",
        "end_date": "2027-01-15"
      }
    },
    {
      "id": "call_Pfxe3vDbwiwxRcird9DhWGY4",
      "tool": "hr_operations",
      "operation": "get_leave_balance",
      "arguments": {
        "employee_id": "E001"
      }
    },
    {
      "id": "call_bJOvGjOsiKGI0a8Jr47gjWjj",
      "tool": "hr_operations",
      "operation": "get_leave_history",
      "arguments": {
        "employee_id": "E001",
        "year": 2027
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_uP506dlJjcd6qIWE0NlKdV9w",
      "output": {
        "ok": true,
        "data": {
          "eligible": true,
          "tenure_days": 400,
          "minimum_days": 90,
          "reason": "Active employment and minimum tenure are required."
        }
      }
    },
    {
      "tool_call_id": "call_vKZcqyzcFBzAmP6fYfOVNM9k",
      "output": {
        "ok": true,
        "data": {
          "working_days": 5,
          "weekends": [
            5,
            6
          ],
          "holidays": []
        }
      }
    },
    {
      "tool_call_id": "call_bwl3LpBeeTB7HhL6XTZXqHBF",
      "output": {
        "ok": true,
        "data": {
          "overlap": false,
          "requests": []
        }
      }
    },
    {
      "tool_call_id": "call_Pfxe3vDbwiwxRcird9DhWGY4",
      "output": {
        "ok": true,
        "data": {
          "employee_id": "E001",
          "year": 2026,
          "annual_allowance": 30,
          "used_days": 0,
          "remaining_days": 30
        }
      }
    },
    {
      "tool_call_id": "call_bJOvGjOsiKGI0a8Jr47gjWjj",
      "output": {
        "ok": true,
        "data": {
          "requests": []
        }
      }
    }
  ]
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfb-6336-724b-b52c-6674d2435d6b?poll=true)

### Turn 4: context_probe

Input: Which exact leave dates did I just request? Do not submit or change anything.

Actual response: I have no record of any leave request from you in this conversation. Could you please specify the exact leave dates you are referring to?

```json
{
  "run_id": "01a19bfb-84c9-77de-bc21-9af9f53960ac",
  "tool_calls": [],
  "tool_results": []
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfb-84c9-77de-bc21-9af9f53960ac?poll=true)

### Turn 5: over_balance_request

Input: I want to request 40 working days of annual leave from 2027-03-01 to 2027-04-23. Please use the backend to validate this request; do not bypass its balance rules.

Actual response: You requested 40 working days of annual leave from 2027-03-01 to 2027-04-23. However, your current annual leave balance for 2026 is 30 days remaining. Please clarify if you want to proceed with a request exceeding your current balance or if you want to adjust the leave duration. Also, note that the leave balance shown is for 2026; would you like me to check the balance for 2027?

```json
{
  "run_id": "01a19bfb-adb0-7365-904f-136011df4961",
  "tool_calls": [
    {
      "id": "call_B3Fs3wXJeJ71tSIcbcDjMUU6",
      "tool": "hr_operations",
      "operation": "calculate_leave_days",
      "arguments": {
        "start_date": "2027-03-01",
        "end_date": "2027-04-23",
        "employee_id": "E001"
      }
    },
    {
      "id": "call_VhxBeknIDLSsE9t437JC8n4S",
      "tool": "hr_operations",
      "operation": "get_leave_balance",
      "arguments": {
        "employee_id": "E001"
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_B3Fs3wXJeJ71tSIcbcDjMUU6",
      "output": {
        "ok": true,
        "data": {
          "working_days": 40,
          "weekends": [
            5,
            6
          ],
          "holidays": []
        }
      }
    },
    {
      "tool_call_id": "call_VhxBeknIDLSsE9t437JC8n4S",
      "output": {
        "ok": true,
        "data": {
          "employee_id": "E001",
          "year": 2026,
          "annual_allowance": 30,
          "used_days": 0,
          "remaining_days": 30
        }
      }
    }
  ]
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfb-adb0-7365-904f-136011df4961?poll=true)

### Turn 6: post_operation_status

Input: Show me my updated leave balance and the status of my latest leave request.

Actual response: Your updated leave balance for 2026 shows an annual allowance of 30 days, with 0 days used and 30 days remaining.

To provide the status of your latest leave request, please specify the calendar year of the leave request you want to check.

```json
{
  "run_id": "01a19bfd-6f10-7162-b9ca-2cff5e294cf7",
  "tool_calls": [
    {
      "id": "call_mAITKzeg9ye350E64NQIz2bc",
      "tool": "hr_operations",
      "operation": "get_leave_balance",
      "arguments": {
        "employee_id": "E001"
      }
    },
    {
      "id": "call_iqDSoCR0N4O5UuJLjobi5CoQ",
      "tool": "hr_operations",
      "operation": "get_leave_history",
      "arguments": {
        "employee_id": "E001",
        "year": 2026
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_mAITKzeg9ye350E64NQIz2bc",
      "output": {
        "ok": true,
        "data": {
          "employee_id": "E001",
          "year": 2026,
          "annual_allowance": 30,
          "used_days": 0,
          "remaining_days": 30
        }
      }
    },
    {
      "tool_call_id": "call_iqDSoCR0N4O5UuJLjobi5CoQ",
      "output": {
        "ok": false,
        "code": "clarification_required",
        "error": "The calendar year was not supplied by the user for this date. No business operation was executed.",
        "missing_fields": [
          "year"
        ],
        "errors": [
          {
            "field": "year",
            "type": "missing_year_context",
            "message": "Ask which calendar year; never infer it from the application date."
          }
        ],
        "clarification_required": true,
        "next_step": "Ask the user for the explicit year and a complete restatement of the request. Do not retry a business operation with a guessed year.",
        "operation": "get_leave_history"
      }
    }
  ]
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bfd-6f10-7162-b9ca-2cff5e294cf7?poll=true)

### Turn 7: interactive_7

Input: Show my 2027 leave history, specifically the status of request #1 for January 11, 2027 to January 15, 2027. This is read-only; do not create or change anything.

Actual response: Your leave request #1 for January 11, 2027 to January 15, 2027 is approved. It covers 5 days, and the leave days have been deducted accordingly. The request was reviewed by employee E004 on November 2, 2026.

```json
{
  "run_id": "01a19bff-874c-725c-b3a9-f1a116e5b364",
  "tool_calls": [
    {
      "id": "call_uI7auIJ8j6ioiLWZvTfVdU5X",
      "tool": "hr_operations",
      "operation": "get_leave_history",
      "arguments": {
        "employee_id": "E001",
        "year": 2027
      }
    },
    {
      "id": "call_OFSm2lmmx6UBFdgWx1btSMGs",
      "tool": "hr_operations",
      "operation": "get_leave_history",
      "arguments": {
        "employee_id": "E001",
        "year": 2027
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_uI7auIJ8j6ioiLWZvTfVdU5X",
      "output": {
        "ok": true,
        "data": {
          "requests": [
            {
              "id": 1,
              "employee_id": "E001",
              "start_date": "2027-01-11",
              "end_date": "2027-01-15",
              "days": 5,
              "status": "approved",
              "deducted_days": 5,
              "reviewed_by": "E004",
              "reviewed_at": "2026-11-02T11:20:39.466586+00:00",
              "created_at": "2026-11-02T11:19:46.226009+00:00"
            }
          ]
        }
      }
    },
    {
      "tool_call_id": "call_OFSm2lmmx6UBFdgWx1btSMGs",
      "output": {
        "ok": true,
        "data": {
          "requests": [
            {
              "id": 1,
              "employee_id": "E001",
              "start_date": "2027-01-11",
              "end_date": "2027-01-15",
              "days": 5,
              "status": "approved",
              "deducted_days": 5,
              "reviewed_by": "E004",
              "reviewed_at": "2026-11-02T11:20:39.466586+00:00",
              "created_at": "2026-11-02T11:19:46.226009+00:00"
            }
          ]
        }
      }
    }
  ]
}
```

LangSmith: [trace](https://smith.langchain.com/o/b56b8917-bbb3-4fe0-a71d-e796209b07da/projects/p/755ec23d-ca9c-4e7a-a7ea-cd76c78e1d16/r/01a19bff-874c-725c-b3a9-f1a116e5b364?poll=true)

## Backend validation versus separate tool calls

`request_leave` internally invokes active-employment/tenure eligibility, actual working-day/holiday/weekend counting, same-year/future dates, pending/approved overlap and requested-year balance checks. Those internal functions are not separate agent tools. The write is executed for validation in a rolled-back savepoint before a proposal is stored. Coverage is reported; final manager approval rechecks staffing.

Independent HTTP read checks below call the same existing services. They are explicitly **not agent tool calls**. Any separate validation operations actually selected by the model appear in the transcript above.

```json
{
  "get_leave_balance": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "employee_id": "E001",
        "year": 2026,
        "annual_allowance": 30,
        "used_days": 0,
        "remaining_days": 30
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "calculate_leave_days": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "working_days": 5,
        "weekends": [
          5,
          6
        ],
        "holidays": []
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "check_leave_overlap": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "overlap": false,
        "requests": []
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "check_leave_eligibility": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "eligible": true,
        "tenure_days": 400,
        "minimum_days": 90,
        "reason": "Active employment and minimum tenure are required."
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "get_leave_history": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "requests": []
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  }
}
```

## Proposal, developer authorization and manager workflow

```json
{
  "proposal": {
    "status": "confirmation_required",
    "confirmation_id": "8bb96896b51045809976ec7a42a70fe0",
    "operation": "request_leave",
    "arguments": {
      "employee_id": "E001",
      "start_date": "2027-01-11",
      "end_date": "2027-01-15"
    },
    "expires_at": "2026-11-02T11:33:14.534727+00:00",
    "instruction": "The human must POST {\"confirm\":true} to /confirmations/8bb96896b51045809976ec7a42a70fe0. No business change has been made."
  },
  "submission": {
    "authorization": {
      "approved_at": "2026-11-02T11:19:46.199404+00:00",
      "mechanism": "Explicit proposal-specific local console confirmation",
      "proposal_id": "8bb96896b51045809976ec7a42a70fe0",
      "source": "Explicit developer chat reply: Confirm submission only; assistant relayed the authorized proposal-specific phrase to the console."
    },
    "response": {
      "http_status": 200,
      "body": {
        "ok": true,
        "data": {
          "request_id": 1,
          "status": "pending",
          "requested_days": 5,
          "coverage": {
            "conflicts": [],
            "manager_review_required": false,
            "coverage_sufficient": true
          },
          "balance": {
            "employee_id": "E001",
            "year": 2027,
            "annual_allowance": 30,
            "used_days": 0,
            "remaining_days": 30
          }
        },
        "error": null,
        "code": null,
        "operation": null,
        "missing_fields": [],
        "errors": [],
        "clarification_required": false,
        "next_step": null,
        "trusted_context": {}
      }
    },
    "replay_response": {
      "http_status": 200,
      "body": {
        "ok": true,
        "data": {
          "request_id": 1,
          "status": "pending",
          "requested_days": 5,
          "coverage": {
            "conflicts": [],
            "manager_review_required": false,
            "coverage_sufficient": true
          },
          "balance": {
            "employee_id": "E001",
            "year": 2027,
            "annual_allowance": 30,
            "used_days": 0,
            "remaining_days": 30
          }
        },
        "error": null,
        "code": null,
        "operation": null,
        "missing_fields": [],
        "errors": [],
        "clarification_required": false,
        "next_step": null,
        "trusted_context": {}
      }
    },
    "replay_business_unchanged": true
  },
  "manager_approval": {
    "manager_identity": {
      "demo_user": "nadia",
      "employee_id": "E004",
      "name": "Nadia",
      "roles": "[\"employee\", \"manager\"]"
    },
    "proposal": {
      "status": "confirmation_required",
      "confirmation_id": "d71f3d8accec4623937039608484218d",
      "operation": "review_leave_request",
      "arguments": {
        "request_id": 1,
        "decision": "approve"
      },
      "expires_at": "2026-11-02T11:34:46.748533+00:00",
      "instruction": "The human must POST {\"confirm\":true} to /confirmations/d71f3d8accec4623937039608484218d. No business change has been made."
    },
    "status": "approved",
    "authorization": {
      "approved_at": "2026-11-02T11:20:39.446973+00:00",
      "mechanism": "Explicit proposal-specific local console confirmation",
      "proposal_id": "d71f3d8accec4623937039608484218d",
      "source": "Explicit developer chat reply: Approve manager confirmation; assistant relayed the authorized proposal-specific phrase to the console."
    },
    "confirmation_response": {
      "http_status": 200,
      "body": {
        "ok": true,
        "data": {
          "request_id": 1,
          "status": "approved",
          "balance": {
            "employee_id": "E001",
            "year": 2027,
            "annual_allowance": 30,
            "used_days": 5,
            "remaining_days": 25
          }
        },
        "error": null,
        "code": null,
        "operation": null,
        "missing_fields": [],
        "errors": [],
        "clarification_required": false,
        "next_step": null,
        "trusted_context": {}
      }
    },
    "replay_response": {
      "http_status": 200,
      "body": {
        "ok": true,
        "data": {
          "request_id": 1,
          "status": "approved",
          "balance": {
            "employee_id": "E001",
            "year": 2027,
            "annual_allowance": 30,
            "used_days": 5,
            "remaining_days": 25
          }
        },
        "error": null,
        "code": null,
        "operation": null,
        "missing_fields": [],
        "errors": [],
        "clarification_required": false,
        "next_step": null,
        "trusted_context": {}
      }
    },
    "replay_business_unchanged": true
  }
}
```

Confirmation uses the existing FastAPI endpoint and matching demo-user header, never direct SQLite edits or a chat “yes”. Confirming submission only creates pending leave. Only a separately authorized assigned-manager review and confirmation deduct the requested-year balance. Completed confirmations return the same receipt on replay without another state change.

## Latest database state and checks

```json
{
  "balances": {
    "2026": {
      "year": 2026,
      "annual_allowance": 30,
      "used_days": 0,
      "remaining_days": 30
    },
    "2027": {
      "year": 2027,
      "annual_allowance": 30,
      "used_days": 5,
      "remaining_days": 25
    }
  },
  "requests": [
    {
      "id": 1,
      "employee_id": "E001",
      "start_date": "2027-01-11",
      "end_date": "2027-01-15",
      "days": 5,
      "status": "approved",
      "deducted_days": 5,
      "reviewed_by": "E004",
      "reviewed_at": "2026-11-02T11:20:39.466586+00:00",
      "created_at": "2026-11-02T11:19:46.226009+00:00"
    }
  ],
  "checks": {
    "identity_mapping": "PASS",
    "conversation_memory": "FAIL: existing Studio hook clears previous turns; no application fix applied",
    "developer_submission_authorization": "RECEIVED",
    "developer_manager_authorization": "RECEIVED",
    "missing_information_no_proposal": "PASS",
    "context_probe_dates_present": false,
    "negative_backend_rejection": "PASS",
    "no_premature_business_change": "PASS",
    "all_remote_traces_found": "PASS",
    "same_persistent_thread": "PASS",
    "proposal_owner_dates": "PASS",
    "submission_pending_without_deduction": "PASS",
    "manager_approved_correct_once_deduction": "PASS",
    "submission_idempotency": "PASS",
    "manager_idempotency": "PASS",
    "post_followup_without_restatement": "FAIL: agent requested the year again; previous user dates were not retained",
    "clarified_post_status": "PASS",
    "negative_agent_submission": "NOT OBSERVED: model only queried working days/current-year balance; actual requested-year rejection verified separately through HTTP",
    "negative_no_business_change": "PASS",
    "post_approval_negative_backend": "PASS"
  },
  "phase": "business_lifecycle_completed_with_conversation_limitations"
}
```

## Negative scenario

```json
{
  "arguments": {
    "employee_id": "E001",
    "start_date": "2027-03-01",
    "end_date": "2027-04-23"
  },
  "intended_working_days": 40,
  "actual_days_check": {
    "http_status": 200,
    "body": {
      "ok": true,
      "data": {
        "working_days": 40,
        "weekends": [
          5,
          6
        ],
        "holidays": []
      },
      "error": null,
      "code": null,
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "independent_backend_check": {
    "http_status": 422,
    "body": {
      "ok": false,
      "data": null,
      "error": "Insufficient leave balance.",
      "code": "invalid_request",
      "operation": null,
      "missing_fields": [],
      "errors": [],
      "clarification_required": false,
      "next_step": null,
      "trusted_context": {}
    }
  },
  "business_data_unchanged": true,
  "no_new_proposal": true,
  "post_approval_backend_check": {
    "channel": "Independent FastAPI service check, not an agent tool call",
    "working_days": 40,
    "remaining_days_before": 25,
    "response": {
      "http_status": 422,
      "body": {
        "ok": false,
        "data": null,
        "error": "Insufficient leave balance.",
        "code": "invalid_request",
        "operation": null,
        "missing_fields": [],
        "errors": [],
        "clarification_required": false,
        "next_step": null,
        "trusted_context": {}
      }
    },
    "business_data_unchanged": true,
    "no_new_proposal": true
  }
}
```

Completed OpenAI model calls observed in local messages: **14**; remotely recorded model runs: **14**. No evaluator model is used. Native responses/keyword checks are not a claim of universal LLM reliability.

## Reproduce

Use a dedicated database and the existing graph/app. Do not reset company.db. Configure .env locally; never paste secrets in chat or Studio.

```bash
source .venv/bin/activate
export COMPANY_DB_PATH="$PWD/data/leave-workflow-demo.db"
STUDIO_DEMO_ENABLED=1 STUDIO_DEMO_USER=ahmed LANGSMITH_TRACING=true LANGCHAIN_TRACING_V2=true LANGSMITH_PROJECT=company-agent-demo langgraph dev --host 127.0.0.1 --port 2024
# Another terminal with exactly the same COMPANY_DB_PATH (original 8000 remains untouched):
COMPANY_DB_PATH="$PWD/data/leave-workflow-demo.db" uvicorn main:app --host 127.0.0.1 --port 8001
python demo_leave_workflow.py             # preview: no paid calls, no data changes
python demo_leave_workflow.py --live      # one persistent thread, proposals only
python demo_leave_workflow.py --live --resume --interactive
```

This recorded database already contains approved January leave. To repeat the full scenario, start both demo servers against a new isolated database filename and use a separate --report path; do not delete or reset the recorded database. Use --resume to inspect or continue this recorded run. Do not rerun --live over an existing result file without --resume or a separate --report path. Interactive turns use the same saved thread and fixed server identity. User confirmation/manager approval each require their own explicit console authorization:

```bash
python demo_leave_workflow.py --live --resume --confirm-submission
python demo_leave_workflow.py --live --resume --prepare-manager-approval
python demo_leave_workflow.py --live --resume --confirm-manager-approval
python demo_leave_workflow.py --live --resume --post-check
```

The script prompts for an exact proposal-specific confirmation phrase before either commit. Never treat a model response as developer authorization. All commits use FastAPI; --prepare-manager-approval only prepares another proposal.

## Studio presentation

[Open the same Studio thread](https://smith.langchain.com/studio/thread?baseUrl=http://127.0.0.1:2024&threadId=01a19bfa-feb9-76fd-89f9-4676e41cfdde). Select company_agent; expand each model/tools event, operation, arguments and output. Server checkpoints retain turn/run history for inspection even though the current model prompt drops prior turns. Different checkpoint-history views are not evidence of conversational memory.

## Historical memory limitation and subsequent fix

This original workflow evidence predates the approved memory/year implementation. Its recorded failures remain historical evidence and are not rewritten as passes. See MEMORY_FIX_RESULTS.md for the subsequent implementation, live retest and reproduction commands. Both original lifecycle approvals were received and executed in this recorded run; the memory retest performs no confirmations or approvals.
