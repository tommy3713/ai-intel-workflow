MORNING_QUERY_TEMPLATES = [
    {
        "id": "earnings",
        "query": (
            "Latest earnings results, guidance revisions, and management commentary "
            "from {us_tickers} in the past 24 hours. "
            "Focus on AI capex, data center demand, and supply chain signals."
        )
    },
    {
        "id": "macro",
        "query": (
            "US-Taiwan semiconductor trade policy, export controls, "
            "and macroeconomic signals affecting AI chip supply chains in the past 24 hours. "
            "Include Fed commentary if relevant to tech capex."
        )
    },
    {
        "id": "supply_chain",
        "query": (
            "TSMC CoWoS capacity, HBM qualification progress, advanced packaging supply chain, "
            "Taiwan AI supply chain order movements and production updates in the past 24 hours. "
            "Include: {tw_tickers}. "
            "Also include capacity expansion, production ramp, and supply-demand changes for: {us_tickers}. "
            "Include: cooling, CPO, test, passive components, server ODMs."
        )
    },
    {
        "id": "institutional",
        "query": (
            "Analyst rating changes with core thesis revisions (not just price target), "
            "institutional block trades, and options market signals for "
            "{us_tickers} and Taiwan AI supply chain stocks in the past 24 hours."
        )
    },
    {
        "id": "open_scan",
        "query": (
            "What are the most significant AI supply chain news stories from Taiwan "
            "and US semiconductor industry in the past 24 hours that are NOT about "
            "{us_tickers}? "
            "Focus on structural changes, unexpected events, or emerging companies "
            "in the AI chip supply chain ecosystem. "
            "Include design wins, design losses, new customer relationships, "
            "or geopolitical events affecting the supply chain."
        )
    }
]

EVENING_QUERY_TEMPLATES = [
    {
        "id": "taiwan_close",
        "query": (
            "Taiwan stock market close summary today: AI supply chain sectors performance, "
            "三大法人 (FINI, investment trust, dealers) net buy/sell for {tw_tickers} and key AI stocks. "
            "TWSE and OTC AI-related sector indices."
        )
    },
    {
        "id": "us_premarket",
        "query": (
            "US stock premarket activity and futures for {us_tickers}. "
            "Any after-hours news or earnings releases in the past 4 hours."
        )
    },
    {
        "id": "supply_chain",
        "query": (
            "TSMC CoWoS capacity, HBM qualification progress, advanced packaging supply chain, "
            "Taiwan AI supply chain order movements and production updates today. "
            "Include: {tw_tickers}. "
            "Also include capacity expansion, production ramp, and supply-demand changes for: {us_tickers}. "
            "Include: cooling, CPO, test, passive components, server ODMs."
        )
    },
    {
        "id": "options_vol",
        "query": (
            "Implied volatility levels, unusual options activity, and put/call ratios "
            "for {options_tickers} today. "
            "Any vol events (earnings, product launches) in next 2 weeks."
        )
    },
    {
        "id": "open_scan",
        "query": (
            "What are the most significant AI supply chain news stories from Taiwan "
            "and US semiconductor industry today that are NOT about "
            "{us_tickers}? "
            "Focus on structural changes, unexpected events, or emerging companies "
            "in the AI chip supply chain ecosystem. "
            "Include design wins, design losses, new customer relationships, "
            "or geopolitical events affecting the supply chain."
        )
    }
]
