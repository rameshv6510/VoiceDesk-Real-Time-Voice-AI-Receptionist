"""Master evaluation runner CLI for VoiceDesk.
Run via: python evals/run_evals.py
"""
import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Set up project root
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from evals.safety_eval import run_safety_evals
from evals.latency_benchmark import run_latency_benchmark
from evals.booking_accuracy_eval import run_booking_accuracy_evals
from app.db import seed_clinic_data_if_needed

async def main():
    print("=" * 60)
    print("🚀 VoiceDesk AI Receptionist — Evaluation & Safety Suite")
    print("=" * 60)
    print()

    seed_clinic_data_if_needed()

    print("1. Running Safety & Clinical Guardrails Evaluation...")
    safety_results = run_safety_evals()
    print(f"   -> Accuracy: {safety_results['accuracy']}% ({safety_results['passed']}/{safety_results['total']} scenarios passed)")
    print()

    print("2. Running Turn-to-Turn Voice Latency Benchmark (15 turns)...")
    latency_results = await run_latency_benchmark(num_turns=15, simulated_base_delay_ms=360.0)
    print(f"   -> Average Latency: {latency_results['avg_latency_ms']} ms")
    print(f"   -> P50: {latency_results['p50_latency_ms']} ms | P95: {latency_results['p95_latency_ms']} ms | Max: {latency_results['max_latency_ms']} ms")
    print(f"   -> SLA Target (<1200ms): {'✅ PASSED' if latency_results['sla_passed'] else '❌ FAILED'}")
    print()

    print("3. Running Appointment Booking Accuracy Evaluation...")
    booking_results = await run_booking_accuracy_evals()
    print(f"   -> Accuracy: {booking_results['accuracy']}% ({booking_results['passed']}/{booking_results['total']} tests passed)")
    print()

    # Compile report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "all_passed": (
                safety_results["passed"] == safety_results["total"] and
                latency_results["sla_passed"] and
                booking_results["passed"] == booking_results["total"]
            ),
            "safety_score_pct": safety_results["accuracy"],
            "latency_p95_ms": latency_results["p95_latency_ms"],
            "booking_accuracy_pct": booking_results["accuracy"]
        },
        "safety_eval": safety_results,
        "latency_benchmark": latency_results,
        "booking_accuracy": booking_results
    }

    results_dir = root_dir / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / "report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 60)
    print(f"📊 Detailed report saved to: {report_file}")
    if report["summary"]["all_passed"]:
        print("🎉 ALL VOICE DESK EVALUATIONS PASSED SUCCESSFULLY!")
    else:
        print("⚠️ Some evaluation checks failed. Check report.json for details.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
