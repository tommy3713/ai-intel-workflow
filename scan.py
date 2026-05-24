import os
import json
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from pydantic import ValidationError
from notion_client import Client as NotionClient
from schemas.report import IntelReport
from config import MORNING_QUERIES, EVENING_QUERIES

load_dotenv()
load_dotenv(".env.local", override=True)

JST = ZoneInfo("Asia/Tokyo")


def fetch_positions_from_notion() -> str:
    api_key = os.environ["NOTION_API_KEY"]
    db_id = os.environ["NOTION_POSITIONS_DB_ID"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=headers,
        json={},
    )
    r.raise_for_status()
    results = r.json()

    us_positions, tw_positions = [], []
    for page in results["results"]:
        props = page["properties"]
        try:
            ticker = props["Ticker"]["title"][0]["text"]["content"]
            market = props["市場"]["select"]["name"]
            pos_type = props["類型"]["select"]["name"]
            avg_cost = props["均價"]["number"]
            qty = props["數量"]["number"]
            expiry = (props.get("到期日") or {}).get("date") or {}
            strike = props["行使價"]["number"]
            note_rich = props["備註"]["rich_text"]
            note = note_rich[0]["text"]["content"] if note_rich else ""

            line = f"  - {ticker} ({pos_type})"
            if avg_cost: line += f" avg={avg_cost}"
            if qty: line += f" qty={qty}"
            if strike: line += f" strike={strike}"
            if expiry.get("start"): line += f" exp={expiry['start']}"
            if note: line += f" [{note}]"

            if market == "US":
                us_positions.append(line)
            else:
                tw_positions.append(line)
        except (KeyError, IndexError, TypeError):
            continue

    return (
        "【我的美股持倉】\n" + ("\n".join(us_positions) or "  （無）") +
        "\n\n【我的台股持倉】\n" + ("\n".join(tw_positions) or "  （無）")
    )


def save_to_notion(report: IntelReport, report_type: str, now: datetime) -> str:
    notion = NotionClient(auth=os.environ["NOTION_API_KEY"])
    title = f"{'☀️ 早報' if report_type == 'morning' else '🌙 晚報'} {now.strftime('%Y-%m-%d')}"

    # Notion rich_text blocks are capped at 2000 chars each
    text = report.markdown_report
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": text[i:i + 2000]}}]},
        }
        for i in range(0, len(text), 2000)
    ]

    page = notion.pages.create(
        parent={"database_id": os.environ["NOTION_DATABASE_ID"]},
        properties={"Name": {"title": [{"text": {"content": title}}]}},
        children=children,
    )

    page_id = page["id"].replace("-", "")
    return f"https://www.notion.so/{page_id}"


def run_perplexity_queries(queries: list[dict]) -> dict[str, str]:
    client = OpenAI(
        api_key=os.environ["PERPLEXITY_API_KEY"],
        base_url="https://api.perplexity.ai"
    )
    results = {}
    for q in queries:
        print(f"  [{q['id']}] querying Perplexity...")
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": q["query"]}]
        )
        results[q["id"]] = response.choices[0].message.content
    return results


def analyze_with_gemini(raw_news: dict, report_type: str, now: datetime, my_positions: str) -> str:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    combined_raw = "\n\n".join(f"[{k}]\n{v}" for k, v in raw_news.items())
    report_type_label = "台股開盤前早報" if report_type == "morning" else "美股開盤前晚報"

    prompt_template = open("prompts/analysis_prompt.md").read()
    prompt = (
        prompt_template
        .replace("{current_datetime_jst}", now.strftime("%Y-%m-%d %H:%M JST"))
        .replace("{report_type_label}", report_type_label)
        .replace("{my_positions}", my_positions)
        .replace("{date}", now.strftime("%Y-%m-%d"))
        .replace("{raw_news}", combined_raw)
    )

    print("  Calling Gemini 2.5 Pro...")
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return response.text


def main():
    now = datetime.now(JST)
    report_type = "morning" if now.hour < 12 else "evening"
    queries = MORNING_QUERIES if report_type == "morning" else EVENING_QUERIES

    print(f"[{now.strftime('%Y-%m-%d %H:%M JST')}] Starting {report_type} scan ({len(queries)} queries)...")

    print("\n--- Notion: fetch positions ---")
    my_positions = fetch_positions_from_notion()
    print(my_positions)

    print("\n--- Perplexity ---")
    raw_news = run_perplexity_queries(queries)

    print("\n--- Gemini ---")
    gemini_raw = analyze_with_gemini(raw_news, report_type, now, my_positions)

    print("\n--- Pydantic validation ---")
    try:
        report = IntelReport(**json.loads(gemini_raw))
        print(f"OK — {len(report.high_signal_items)} high-signal items, "
              f"{len(report.decision_questions)} decision questions")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print("\nRaw response:\n", gemini_raw)
        return
    except ValidationError as e:
        print(f"Validation error:\n{e}")
        print("\nRaw response:\n", gemini_raw)
        return

    print("\n--- Notion: write report ---")
    page_url = save_to_notion(report, report_type, now)
    print(f"Published: {page_url}")


if __name__ == "__main__":
    main()
