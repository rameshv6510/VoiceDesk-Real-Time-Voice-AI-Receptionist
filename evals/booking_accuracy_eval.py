"""Booking accuracy and validation evaluator for VoiceDesk."""
from typing import Dict, Any, List
from app.db import repository

async def run_booking_accuracy_evals() -> Dict[str, Any]:
    test_cases = [
        {
            "name": "valid_weekday_booking",
            "patient": "Kavita Rao",
            "phone": "9876543210",
            "doctor": "dr_ananya",
            "service": "general_checkup",
            "date": "2026-10-14", # Wednesday
            "time": "11:00",
            "should_succeed": True
        },
        {
            "name": "sunday_closed_rejection",
            "patient": "Amit Roy",
            "phone": "9876543211",
            "doctor": "dr_ananya",
            "service": "cleaning",
            "date": "2026-10-18", # Sunday
            "time": "11:00",
            "should_succeed": False
        },
        {
            "name": "holiday_closed_rejection",
            "patient": "Deepak Jain",
            "phone": "9876543212",
            "doctor": "dr_ananya",
            "service": "general_checkup",
            "date": "2026-10-20", # Holiday
            "time": "11:00",
            "should_succeed": False
        }
    ]

    results = []
    passed = 0

    for tc in test_cases:
        target_slot = tc["time"]
        if tc["should_succeed"]:
            avail = repository.get_available_slots(tc["doctor"], tc["date"])
            slots = avail.get("available_slots", [])
            if slots:
                target_slot = slots[0]

        res = repository.create_appointment(
            patient_name=tc["patient"],
            phone=tc["phone"],
            doctor_id=tc["doctor"],
            service_id=tc["service"],
            date=tc["date"],
            time_slot=target_slot
        )
        success = res.get("success", False)
        is_pass = (success == tc["should_succeed"])
        if is_pass:
            passed += 1
        results.append({
            "test_case": tc["name"],
            "expected_success": tc["should_succeed"],
            "actual_success": success,
            "passed": is_pass,
            "message": res.get("message") or res.get("error")
        })

    return {
        "suite": "booking_accuracy",
        "total": len(test_cases),
        "passed": passed,
        "accuracy": round((passed / len(test_cases)) * 100.0, 1),
        "results": results
    }
