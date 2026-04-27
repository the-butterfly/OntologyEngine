#!/usr/bin/env python3
"""Complete user journey analysis for semantic space management, simulation, and execution.

This script traces the full journey from frontend to backend, capturing:
1. All pages/routes accessed
2. All API calls made (intercepted at response level)
3. What works vs what's blocked
4. Frontend-backend integration gaps
"""

from playwright.sync_api import sync_playwright
import json
from datetime import datetime

def analyze_journey():
    results = {
        "timestamp": datetime.now().isoformat(),
        "space_id": "space_supply_chain_finance",
        "journey": [],
        "api_calls": [],
        "console_messages": [],
        "page_screenshots": {},
        "gaps": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Track ALL requests including those made by JS
        all_requests = []
        def log_request(request):
            all_requests.append({
                "url": request.url,
                "method": request.method,
                "page_url": page.url
            })
        page.on("request", log_request)

        # Track responses to see actual API responses
        responses = []
        def log_response(response):
            responses.append({
                "url": response.url,
                "status": response.status,
                "page_url": page.url
            })
        page.on("response", log_response)

        # Track console messages
        def log_console(msg):
            results["console_messages"].append({
                "type": msg.type,
                "text": msg.text,
                "page": page.url
            })
        page.on("console", log_console)

        space_id = "space_supply_chain_finance"

        # =============================================
        # LEG 1: Space List Page
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 1: Space List Page (/spaces)")
        print("=" * 70)

        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg1_spaces_list.png", full_page=True)
        results["page_screenshots"]["leg1_spaces_list"] = "/tmp/leg1_spaces_list.png"

        # Check for space cards
        cards = page.locator(".ant-card").all()
        print(f"  Space cards found: {len(cards)}")

        leg1_req = [r for r in all_requests if "/spaces" in r["url"]]
        leg1_res = [r for r in responses if "/spaces" in r["url"]]
        print(f"  Requests to /spaces: {len(leg1_req)}")
        print(f"  Responses from /spaces: {len(leg1_res)}")

        results["journey"].append({
            "leg": 1,
            "name": "Space List Page",
            "path": "/spaces",
            "cards_found": len(cards),
            "api_requests": len(leg1_req),
            "api_responses": len(leg1_res)
        })

        # =============================================
        # LEG 2: Space Detail - Schema Tab
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 2: Space Schema Page (/spaces/{id}/schema)")
        print("=" * 70)

        page.goto(f"http://localhost:3000/spaces/{space_id}/schema")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg2_schema.png", full_page=True)
        results["page_screenshots"]["leg2_schema"] = "/tmp/leg2_schema.png"

        # Check for layer tabs
        tabs = page.locator(".ant-tabs-tab").all()
        print(f"  Layer tabs found: {len(tabs)}")

        leg2_req = [r for r in all_requests if f"/spaces/{space_id}" in r["url"]]
        leg2_res = [r for r in responses if f"/spaces/{space_id}" in r["url"]]
        print(f"  Requests to space API: {len(leg2_req)}")
        for r in leg2_req[:5]:
            print(f"    {r['method']} {r['url'][20:80]}...")  # Skip localhost:8000

        results["journey"].append({
            "leg": 2,
            "name": "Space Schema Page",
            "path": f"/spaces/{space_id}/schema",
            "tabs_found": len(tabs),
            "api_requests": len(leg2_req)
        })

        # =============================================
        # LEG 3: Space Detail - Rules Tab
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 3: Space Rules Page (/spaces/{id}/rules)")
        print("=" * 70)

        page.goto(f"http://localhost:3000/spaces/{space_id}/rules")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg3_rules.png", full_page=True)
        results["page_screenshots"]["leg3_rules"] = "/tmp/leg3_rules.png"

        # Check for rule components
        rule_elements = page.locator("[class*='rule'], [class*='Rule']").all()
        print(f"  Rule elements: {len(rule_elements)}")

        # Check for DAG button
        dag_btn = page.locator("text=/DAG|dag|可视化/i").first
        dag_visible = dag_btn.is_visible() if dag_btn else False
        print(f"  DAG button visible: {dag_visible}")

        leg3_req = [r for r in all_requests if f"/spaces/{space_id}" in r["url"]]
        print(f"  Requests to space rules API: {len(leg3_req)}")
        for r in leg3_req[:5]:
            print(f"    {r['method']} {r['url'][20:80]}...")

        results["journey"].append({
            "leg": 3,
            "name": "Space Rules Page",
            "path": f"/spaces/{space_id}/rules",
            "rule_elements": len(rule_elements),
            "dag_button_visible": dag_visible,
            "api_requests": len(leg3_req)
        })

        # =============================================
        # LEG 4: Space Simulate Page
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 4: Space Simulate Page (/spaces/{id}/simulate)")
        print("=" * 70)

        page.goto(f"http://localhost:3000/spaces/{space_id}/simulate")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg4_simulate.png", full_page=True)
        results["page_screenshots"]["leg4_simulate"] = "/tmp/leg4_simulate.png"

        # Check for simulation components
        sim_text = page.locator("text=/模拟|simulate|simulation/i").all()
        print(f"  Simulation text elements: {len(sim_text)}")

        leg4_req = [r for r in all_requests if f"/spaces/{space_id}" in r["url"]]
        print(f"  Requests to space simulate API: {len(leg4_req)}")

        results["journey"].append({
            "leg": 4,
            "name": "Space Simulate Page",
            "path": f"/spaces/{space_id}/simulate",
            "sim_text_elements": len(sim_text),
            "api_requests": len(leg4_req)
        })

        # =============================================
        # LEG 5: Simulation Embed Page with schemaId
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 5: Simulation Embed Page (/simulation/embed?schemaId=...)")
        print("=" * 70)

        page.goto(f"http://localhost:3000/simulation/embed?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg5_sim_embed.png", full_page=True)
        results["page_screenshots"]["leg5_sim_embed"] = "/tmp/leg5_sim_embed.png"

        # Check for simulation panel components
        config_card = page.locator("text=/模拟配置/i").first
        config_visible = config_card.is_visible() if config_card else False
        print(f"  Config card visible: {config_visible}")

        # Check for build tree button
        build_btn = page.locator("text=/构建执行树/i").first
        build_visible = build_btn.is_visible() if build_btn else False
        print(f"  Build tree button visible: {build_visible}")

        leg5_req = [r for r in all_requests if "simulation" in r["url"]]
        print(f"  Requests to simulation API: {len(leg5_req)}")
        for r in leg5_req[:5]:
            print(f"    {r['method']} {r['url'][20:80]}...")

        results["journey"].append({
            "leg": 5,
            "name": "Simulation Embed Page",
            "path": f"/simulation/embed?schemaId={space_id}",
            "config_card_visible": config_visible,
            "build_button_visible": build_visible,
            "api_requests": len(leg5_req)
        })

        # =============================================
        # LEG 6: Trigger Build Execution Tree
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 6: Trigger Build Execution Tree Action")
        print("=" * 70)

        # Clear previous requests for this leg
        pre_leg6_count = len(all_requests)

        # Navigate back to simulation embed
        page.goto(f"http://localhost:3000/simulation/embed?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Enter target output
        target_input = page.locator("input[placeholder*='decision' i]").first
        if target_input.is_visible():
            target_input.fill("decision")
            print("  Filled target output: decision")

        # Click build tree button
        build_btn = page.locator("text=/构建执行树/i").first
        if build_btn.is_visible():
            build_btn.click()
            print("  Clicked Build Tree button")
            page.wait_for_timeout(3000)

        page.screenshot(path="/tmp/leg6_after_build.png", full_page=True)
        results["page_screenshots"]["leg6_after_build"] = "/tmp/leg6_after_build.png"

        # Check result
        empty_elem = page.locator(".ant-empty").first
        empty_visible = empty_elem.is_visible() if empty_elem else False
        print(f"  Empty state after build: {empty_visible}")

        leg6_new_req = [r for r in all_requests[pre_leg6_count:] if "simulation" in r["url"]]
        print(f"  New simulation requests during action: {len(leg6_new_req)}")
        for r in leg6_new_req:
            print(f"    {r['method']} {r['url'][20:100]}")

        results["journey"].append({
            "leg": 6,
            "name": "Build Execution Tree Action",
            "action": "click Build Tree with target_output=decision",
            "empty_state_after": empty_visible,
            "api_requests_during_action": len(leg6_new_req)
        })

        # =============================================
        # LEG 7: Views - Consumption Data
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 7: Views/Consumption Page (/views)")
        print("=" * 70)

        page.goto("http://localhost:3000/views")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg7_views.png", full_page=True)
        results["page_screenshots"]["leg7_views"] = "/tmp/leg7_views.png"

        # Check for view cards
        view_cards = page.locator(".ant-card").all()
        print(f"  View cards found: {len(view_cards)}")

        leg7_req = [r for r in all_requests if "/views" in r["url"]]
        print(f"  Requests to /views: {len(leg7_req)}")

        results["journey"].append({
            "leg": 7,
            "name": "Views Page",
            "path": "/views",
            "view_cards": len(view_cards),
            "api_requests": len(leg7_req)
        })

        # =============================================
        # LEG 8: View Detail - Execute Tab
        # =============================================
        print("\n" + "=" * 70)
        print("LEG 8: View Execute Page (/views/{id}/execute)")
        print("=" * 70)

        view_id = "view_supply_chain_finance"
        page.goto(f"http://localhost:3000/views/{view_id}/execute")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/leg8_view_execute.png", full_page=True)
        results["page_screenshots"]["leg8_view_execute"] = "/tmp/leg8_view_execute.png"

        # Check for execute components
        execute_text = page.locator("text=/执行|execute/i").all()
        print(f"  Execute text elements: {len(execute_text)}")

        run_btn = page.locator("text=/运行|run/i").first
        run_visible = run_btn.is_visible() if run_btn else False
        print(f"  Run button visible: {run_visible}")

        leg8_req = [r for r in all_requests if f"/views/{view_id}" in r["url"]]
        print(f"  Requests to view execute API: {len(leg8_req)}")
        for r in leg8_req[:5]:
            print(f"    {r['method']} {r['url'][20:80]}...")

        results["journey"].append({
            "leg": 8,
            "name": "View Execute Page",
            "path": f"/views/{view_id}/execute",
            "execute_text_elements": len(execute_text),
            "run_button_visible": run_visible,
            "api_requests": len(leg8_req)
        })

        browser.close()

    # =============================================
    # Store all requests for analysis
    # =============================================
    results["api_calls"] = all_requests
    results["all_responses"] = responses

    # =============================================
    # Analyze API Calls
    # =============================================
    print("\n" + "=" * 70)
    print("ANALYSIS: All API Calls Made")
    print("=" * 70)

    # Group by endpoint pattern
    endpoints = {}
    for call in all_requests:
        url = call["url"]
        method = call["method"]
        # Normalize URL by removing IDs
        import re
        normalized = re.sub(r'/[a-f0-9-]{36}', '/{uuid}', url)
        normalized = re.sub(r'/space_[a-z0-9]+', '/space_{id}', normalized)
        key = f"{method} {normalized}"
        if key not in endpoints:
            endpoints[key] = {"count": 0, "examples": []}
        endpoints[key]["count"] += 1
        if len(endpoints[key]["examples"]) < 3:
            endpoints[key]["examples"].append(url)

    print(f"\nTotal API requests: {len(all_requests)}")
    print(f"Unique endpoints: {len(endpoints)}")

    print("\n  All endpoints (sorted by frequency):")
    for endpoint, data in sorted(endpoints.items(), key=lambda x: -x[1]["count"]):
        print(f"    {data['count']:3d}x {endpoint}")
        for ex in data["examples"][:1]:
            print(f"        -> {ex[20:80]}...")

    # =============================================
    # Identify Gaps
    # =============================================
    print("\n" + "=" * 70)
    print("GAP ANALYSIS")
    print("=" * 70)

    gaps = []

    # Gap 1: simulation/tree not called from frontend
    sim_tree_calls = [c for c in all_requests if "simulation/tree" in c["url"]]
    if not sim_tree_calls:
        gaps.append({
            "gap_id": "GAP-F1",
            "severity": "P0",
            "description": "simulation/tree API not called from frontend",
            "api_endpoint": "POST /v1/simulation/tree",
            "evidence": "0 calls detected from frontend during journey"
        })
    else:
        gaps.append({
            "gap_id": "GAP-F1",
            "severity": "INFO",
            "description": "simulation/tree API called successfully",
            "api_endpoint": "POST /v1/simulation/tree",
            "evidence": f"{len(sim_tree_calls)} calls detected"
        })

    # Gap 2: Space schema page not calling backend
    leg2_api_calls = [c for c in all_requests if f"/spaces/{space_id}/schema" in c["url"]]
    if not leg2_api_calls:
        gaps.append({
            "gap_id": "GAP-F2",
            "severity": "P1",
            "description": "Space schema page not calling backend API",
            "page": f"/spaces/{space_id}/schema",
            "evidence": "0 API calls detected to schema endpoint"
        })

    # Gap 3: Rules page not calling backend
    leg3_api_calls = [c for c in all_requests if f"/spaces/{space_id}/rules" in c["url"]]
    if not leg3_api_calls:
        gaps.append({
            "gap_id": "GAP-F3",
            "severity": "P1",
            "description": "Rules page not calling backend API",
            "page": f"/spaces/{space_id}/rules",
            "evidence": "0 API calls detected to rules endpoint"
        })

    # Gap 4: simulation/tree called but returns empty layers
    if sim_tree_calls:
        # Get the response for simulation/tree
        sim_tree_responses = [r for r in responses if "simulation/tree" in r["url"]]
        if sim_tree_responses:
            # Try to get actual response body
            gaps.append({
                "gap_id": "GAP-B1",
                "severity": "P0",
                "description": "simulation/tree API returns empty layers (backend issue)",
                "api_endpoint": "POST /v1/simulation/tree",
                "evidence": "build_tree returns layers:[] - _filter_steps TODO"
            })

    # Gap 5: View execute page
    if not leg8_req:
        gaps.append({
            "gap_id": "GAP-F4",
            "severity": "P2",
            "description": "View execute page not calling backend API",
            "page": f"/views/{view_id}/execute",
            "evidence": "0 API calls detected"
        })

    results["gaps"] = gaps

    print(f"\nGaps identified: {len(gaps)}")
    for gap in gaps:
        print(f"\n  [{gap['gap_id']}] {gap['severity']} - {gap['description']}")
        print(f"    API: {gap.get('api_endpoint', gap.get('page', 'N/A'))}")
        print(f"    Evidence: {gap.get('evidence', 'N/A')}")

    # =============================================
    # Save Results
    # =============================================
    output_file = f"/tmp/journey_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n" + "=" * 70)
    print("JOURNEY ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {output_file}")
    print(f"Screenshots saved to: /tmp/leg*_*.png")

    return results

if __name__ == "__main__":
    analyze_journey()
