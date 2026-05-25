import os
import sys
import json
import re
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from pydantic import ValidationError
from schemas.report import IntelReport
from config import MORNING_QUERY_TEMPLATES, EVENING_QUERY_TEMPLATES

load_dotenv()
load_dotenv(".env.local", override=True)

JST = ZoneInfo("Asia/Tokyo")


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def fetch_positions_from_notion() -> tuple[list[dict], str]:
    db_id = os.environ["NOTION_POSITIONS_DB_ID"]
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=_notion_headers(),
        json={},
    )
    r.raise_for_status()
    positions_raw = r.json()["results"]

    us_positions, tw_positions = [], []
    for page in positions_raw:
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
            reason_rich = (props.get("持倉理由") or {}).get("rich_text", [])
            reason = reason_rich[0]["text"]["content"] if reason_rich else ""
            exit_rich = (props.get("目標出場條件") or {}).get("rich_text", [])
            exit_cond = exit_rich[0]["text"]["content"] if exit_rich else ""

            line = f"  - {ticker} ({pos_type})"
            if avg_cost: line += f" avg={avg_cost}"
            if qty: line += f" qty={qty}"
            if strike: line += f" strike={strike}"
            if expiry.get("start"): line += f" exp={expiry['start']}"
            if note: line += f" [{note}]"
            if reason: line += f" [持倉理由：{reason}]"
            if exit_cond: line += f" [出場條件：{exit_cond}]"

            if market == "US":
                us_positions.append(line)
            else:
                tw_positions.append(line)
        except (KeyError, IndexError, TypeError):
            continue

    my_positions_str = (
        "【我的美股持倉】\n" + ("\n".join(us_positions) or "  （無）") +
        "\n\n【我的台股持倉】\n" + ("\n".join(tw_positions) or "  （無）")
    )
    return positions_raw, my_positions_str


def build_queries(positions_raw: list[dict], templates: list[dict]) -> list[dict]:
    us_stocks, tw_stocks, options = [], [], []

    for page in positions_raw:
        props = page["properties"]
        try:
            ticker = props["Ticker"]["title"][0]["text"]["content"]
            market = props["市場"]["select"]["name"]
            pos_type = props["類型"]["select"]["name"]

            if market == "US":
                if pos_type == "股票":
                    if ticker not in us_stocks:
                        us_stocks.append(ticker)
                elif pos_type in ["Call", "Put"]:
                    base = ticker.replace(" Call", "").replace(" Put", "").strip()
                    if base not in options:
                        options.append(base)
                    if base not in us_stocks:
                        us_stocks.append(base)
            elif market == "TW":
                if pos_type == "股票":
                    if ticker not in tw_stocks:
                        tw_stocks.append(ticker)
        except (KeyError, IndexError, TypeError):
            continue

    us_tickers_str = " ".join(us_stocks)
    tw_tickers_str = " ".join(tw_stocks)
    options_tickers_str = " ".join(options) if options else " ".join(us_stocks[:5])

    queries = []
    for t in templates:
        q = (t["query"]
             .replace("{us_tickers}", us_tickers_str)
             .replace("{tw_tickers}", tw_tickers_str)
             .replace("{options_tickers}", options_tickers_str))
        queries.append({"id": t["id"], "query": q})

    return queries



def _rich_text(text: str) -> list[dict]:
    """Parse **bold** markers into Notion rich_text segments, chunked at 1800 chars."""
    parts = []
    for i, seg in enumerate(re.split(r'\*\*(.+?)\*\*', text)):
        if not seg:
            continue
        bold = (i % 2 == 1)
        for j in range(0, len(seg), 1800):
            parts.append({
                "type": "text",
                "text": {"content": seg[j:j + 1800]},
                **({"annotations": {"bold": True}} if bold else {}),
            })
    return parts or [{"type": "text", "text": {"content": ""}}]


def _markdown_to_blocks(md: str) -> list[dict]:
    """Convert markdown report to Notion native blocks."""
    blocks = []
    for line in md.splitlines():
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": _rich_text(line[2:])}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": _rich_text(line[3:])}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": _rich_text(line[4:])}})
        elif line.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": _rich_text(line[2:])}})
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": _rich_text(line[2:])}})
        elif line.strip() == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif line.strip() == "":
            pass  # skip blank lines
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": _rich_text(line)}})
    return blocks


def save_to_notion(report: IntelReport, report_type: str, now: datetime) -> str:
    report_label = "☀️ 早報" if report_type == "morning" else "🌙 晚報"
    title = f"{report_label} {now.strftime('%Y-%m-%d')}"
    all_blocks = _markdown_to_blocks(report.markdown_report)
    headers = _notion_headers()

    bias_map = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}
    market_bias = bias_map.get(
        report.market_snapshot.taiwan_sector_bias if report_type == "morning"
        else report.market_snapshot.us_futures_bias,
        "中性"
    )

    # Notion allows max 100 children per create/append call
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={
            "parent": {"database_id": os.environ["NOTION_DATABASE_ID"]},
            "properties": {
                "標題": {"title": [{"text": {"content": title}}]},
                "類型": {"select": {"name": report_label}},
                "日期": {"date": {"start": now.strftime("%Y-%m-%d")}},
                "高信號數量": {"number": len(report.high_signal_items)},
                "市場偏向": {"select": {"name": market_bias}},
            },
            "children": all_blocks[:100],
        },
    )
    r.raise_for_status()
    page = r.json()

    for i in range(100, len(all_blocks), 100):
        rb = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page['id']}/children",
            headers=headers,
            json={"children": all_blocks[i:i + 100]},
        )
        rb.raise_for_status()

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
    templates = MORNING_QUERY_TEMPLATES if report_type == "morning" else EVENING_QUERY_TEMPLATES

    print(f"[{now.strftime('%Y-%m-%d %H:%M JST')}] Starting {report_type} scan...")

    print("\n--- Notion: fetch positions ---")
    positions_raw, my_positions = fetch_positions_from_notion()
    print(my_positions)

    print("\n--- Build queries ---")
    queries = build_queries(positions_raw, templates)
    for q in queries:
        print(f"  [{q['id']}] {q['query'][:120]}...")

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
        sys.exit(1)
    except ValidationError as e:
        print(f"Validation error:\n{e}")
        print("\nRaw response:\n", gemini_raw)
        sys.exit(1)

    print("\n--- Notion: write report ---")
    page_url = save_to_notion(report, report_type, now)
    print(f"Published: {page_url}")


if __name__ == "__main__":
    main()
