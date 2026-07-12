import argparse
import json
from app.agents.financial_mirror_agent import FinancialMirrorAgent

def main():
    parser = argparse.ArgumentParser(
        description="Financial Mirror Governed Agentic Pipeline Demo"
    )
    parser.add_argument(
        "--customer",
        type=str,
        default="maria",
        help="Customer profile name to run (e.g. maria, juan, alex, bea, carlo, dana, elena, niko)",
    )
    args = parser.parse_args()

    cust_arg = args.customer.lower()
    
    print("=" * 80)
    print(" FINANCIAL MIRROR GOVERNED AGENTIC DEMO ".center(80, "="))
    print("=" * 80)
    
    agent = FinancialMirrorAgent()
    
    try:
        run_result = agent.run(cust_arg, enable_test_verification=True)
    except ValueError as e:
        print(f"\033[91mError: {e}\033[0m")
        return

    # Print trace details
    print(f"\n[+] E2E Execution Trace for Customer Key: {cust_arg.upper()}")
    print("-" * 80)
    for idx, trace in enumerate(run_result.execution_trace):
        print(f"Step {idx + 1}: \033[94m[{trace['step_id']}]\033[0m via \033[93m{trace['tool']}\033[0m")
        print(f"  Summary:  {trace['summary']}")
        print(f"  Decision: {trace['decision']}")
        if trace.get('next_action'):
            print(f"  Next Action: {trace['next_action']}")
        if trace.get('metadata'):
            print(f"  Metadata: {json.dumps(trace['metadata'], ensure_ascii=False)}")
        print("-" * 40)

    print("\n" + "=" * 80)
    print(" PIPELINE RESULTS AND OUTPUTS ".center(80, "="))
    print("=" * 80)

    result = run_result.result
    
    # 1. Facts
    facts = result.get("facts", [])
    print(f"\n[1] Fact Engine: Detected {len(facts)} fact(s)")
    for fact in facts:
        print(f"  * [{fact['fact_id']}] {fact['fact_type']}: {fact['description']}")
        print(f"    Scope: {fact.get('scope')}")
        print(f"    Value: {fact.get('value')}")

    # 2. Policy
    policy = result.get("policy", {})
    print(f"\n[2] Policy Engine:")
    print(f"  Accepted count: {policy.get('accepted_count', 0)}")
    print(f"  Rejected count: {policy.get('rejected_count', 0)}")
    if policy.get("rejection_rules"):
        print(f"  Rejection Rules: {policy.get('rejection_rules')}")
    if policy.get("rejection_reasons"):
        print(f"  Rejection Reasons: {policy.get('rejection_reasons')}")

    # 3. LLM Action
    llm_action = result.get("llm_action", {})
    if llm_action:
        print(f"\n[3] LLM Action Selector:")
        print(f"  Selected Action: \033[95m{llm_action.get('selected_action')}\033[0m")
        print(f"  Reason: {llm_action.get('reason')}")
        print(f"  Valid decision: {llm_action.get('valid')}")

    # 4. Wording Generation & Safety Gate 1
    passed_outputs = result.get("safety_passed_outputs", [])
    failed_outputs = result.get("safety_failed_outputs", [])
    retry_attempts = result.get("safety_retry_attempts", [])
    
    if passed_outputs or failed_outputs or retry_attempts:
        print(f"\n[4] Output Copy & Safety Gate 1:")
        if retry_attempts:
            print(f"  \033[93m[SAFETY RETRY ATTEMPTS ({len(retry_attempts)})]\033[0m")
            for att in retry_attempts:
                print(f"    * Attempt {att['attempt']}: Status: \033[95m{att['status']}\033[0m")
                print(f"      Original Obs: \"{att['original_observation']}\"")
                print(f"      Original Ndg: \"{att['original_nudge']}\"")
                print(f"      Rewritten Obs:\"{att['rewritten_observation']}\"")
                print(f"      Rewritten Ndg:\"{att['rewritten_nudge']}\"")
                print(f"      Violations:    {att['safety_violations']}")
                print(f"      LLM Metadata:  {json.dumps(att['llm'])}")
        if passed_outputs:
            print(f"  \033[92m[PASSED SAFETY COPY ({len(passed_outputs)})]\033[0m")
            for out in passed_outputs:
                print(f"    * Fact: {out['fact']['fact_id']}")
                print(f"      Observation: \"{out['observation']}\"")
                print(f"      Nudge:       \"{out['nudge']}\"")
        if failed_outputs:
            print(f"  \033[91m[BLOCKED BY SAFETY copy ({len(failed_outputs)})]\033[0m")
            for out in failed_outputs:
                print(f"    * Fact: {out['fact']['fact_id']}")
                print(f"      Observation: \"{out['observation']}\"")
                print(f"      Nudge:       \"{out['nudge']}\"")
                print(f"      Violations:  {out.get('safety_violations')}")

    # 5. Challenges & Safety Gate 2
    challenges = result.get("challenges", [])
    if challenges:
        print(f"\n[5] Engagement Challenges & Safety Gate 2:")
        for out in challenges:
            chal = out.get("challenge")
            if not chal:
                continue
            passed = chal.get("passed_safety_check")
            status_color = "\033[92m[PASSED]\033[0m" if passed else "\033[91m[BLOCKED]\033[0m"
            print(f"  * Challenge for Nudge: {chal['based_on_nudge']} -> {status_color}")
            print(f"    Title:       \"{chal['title']}\"")
            print(f"    Description: \"{chal['description']}\"")
            print(f"    Criteria:    \"{chal['criteria']}\"")
            print(f"    Rewards:     {chal['reward_points']} points (Difficulty: {chal['difficulty_tier']})")
            if not passed:
                print(f"    Violations:  Title: {out.get('challenge_safety_title', {}).get('violations')} | "
                      f"Desc: {out.get('challenge_safety_desc', {}).get('violations')} | "
                      f"Criteria: {out.get('challenge_safety_criteria', {}).get('violations')}")

    # 6. Final Status & Verification
    print(f"\n[6] Terminal State & Persona Verification:")
    print(f"  Final Agent Status: \033[96m{run_result.final_status}\033[0m")
    
    verif = run_result.verification
    if verif.get("enabled"):
        print(f"  Expected Status:    {verif.get('expected_outcome')}")
        match_str = "\033[92mMATCH\033[0m" if verif.get("match") else "\033[91mMISMATCH\033[0m"
        print(f"  Compliance Match:   {match_str}")
        print(f"  Verification Note:  {verif.get('persona_purpose')}")

    print("\n" + "=" * 80)
    print(" DEMO COMPLETED ".center(80, "="))
    print("=" * 80)

if __name__ == "__main__":
    main()
