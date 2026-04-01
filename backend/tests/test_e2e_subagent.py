"""E2E tests for Module 8: Sub-Agents"""
import os, sys, json, httpx

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

SUPABASE_URL = os.environ["VITE_SUPABASE_URL"]
ANON_KEY = os.environ["VITE_SUPABASE_ANON_KEY"]
API = "http://localhost:8000"


def get_token():
    r = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY},
        json={"email": "ragtest1@gmail.com", "password": "testpass123"},
    )
    return r.json()["access_token"]


def create_thread(token: str, title: str) -> str:
    r = httpx.post(
        f"{API}/api/threads",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title},
        timeout=30.0,
    )
    return r.json()["id"]


def send_and_collect(token: str, thread_id: str, content: str) -> dict:
    """Send a message and collect the full SSE stream into structured results."""
    tool_events = []
    text_parts = []
    done_data = None

    with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as client, client.stream(
        "POST",
        f"{API}/api/threads/{thread_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"content": content},
    ) as response:
        buffer = ""
        current_event = None
        for chunk in response.iter_text():
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = line.split(":", 1)[1].strip()
                    try:
                        parsed = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if current_event == "tool_event" or parsed.get("tool_event"):
                        tool_events.append(parsed)
                    elif parsed.get("text") is not None:
                        text_parts.append(parsed["text"])
                    elif parsed.get("message_id"):
                        done_data = parsed

    return {
        "tool_events": tool_events,
        "content": "".join(text_parts),
        "done": done_data,
    }


def run_test(num, desc, message, expected_tool, token):
    print(f"\n{'='*60}")
    print(f"TEST {num}: {desc}")
    print(f"Message: \"{message}\"")
    print(f"Expected tool: {expected_tool}")
    print(f"{'='*60}")

    thread_id = create_thread(token, f"E2E Test {num}")
    result = send_and_collect(token, thread_id, message)

    # Show tool events
    print(f"\n  Tool events ({len(result['tool_events'])}):")
    for te in result["tool_events"]:
        status = te.get("status", "")
        subagent = " [SUB-AGENT]" if te.get("subagent") else ""
        print(f"    - {te['tool']}{subagent} status={status} preview={te.get('args_preview', '')[:60]}")

    # Show response snippet
    content = result["content"]
    print(f"\n  Response ({len(content)} chars):")
    print(f"    {content[:400]}{'...' if len(content) > 400 else ''}")

    # Check result
    tools_used = [te["tool"] for te in result["tool_events"]]
    if expected_tool == "both":
        has_analyze = "analyze_document" in tools_used
        has_other = any(t in tools_used for t in ["web_search", "search_documents"])
        passed = has_analyze and has_other
    elif expected_tool == "none":
        passed = len(tools_used) == 0
    else:
        passed = expected_tool in tools_used

    status = "PASS ✓" if passed else "FAIL ✗"
    print(f"\n  {status}")
    if not passed:
        print(f"    Expected: {expected_tool}")
        print(f"    Got: {tools_used}")
    return passed


def main():
    print("Authenticating...")
    token = get_token()
    print("OK\n")

    tests = [
        (1, "Summarize known doc → analyze_document",
         "Summarize Calico_Rulebook.pdf",
         "analyze_document"),

        (2, "Key points in doc → analyze_document",
         "What are the key points in PlayingThePlayer.md?",
         "analyze_document"),

        (3, "Chunk search → search_documents",
         "What do my documents say about strategy?",
         "search_documents"),

        (4, "Nonexistent doc → graceful error",
         "Summarize nonexistent.pdf",
         "analyze_document"),

        (5, "General question → web_search",
         "What is Python programming language?",
         "web_search"),

        (6, "Multi-tool → both analyze + another",
         "Summarize Calico_Rulebook.pdf and then search the web for the latest Calico board game news",
         "both"),
    ]

    results = []
    for num, desc, msg, expected in tests:
        try:
            passed = run_test(num, desc, msg, expected, token)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            passed = False
        results.append((num, desc, passed))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed_count = sum(1 for _, _, p in results if p)
    for num, desc, passed in results:
        print(f"  Test {num}: {'PASS ✓' if passed else 'FAIL ✗'} - {desc}")
    print(f"\n  {passed_count}/{len(results)} passed")


if __name__ == "__main__":
    main()
