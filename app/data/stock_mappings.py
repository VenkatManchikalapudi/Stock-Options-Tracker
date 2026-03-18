"""
Static lookup tables mapping common names/aliases to exchange ticker symbols.

TICKER_GROUPS   – named basket → list of tickers  (e.g. "mag 7", "faang")
COMPANY_NAME_MAP – lowercase company name → ticker  (e.g. "apple" → "AAPL")

Keys in COMPANY_NAME_MAP are lowercase; the orchestrator matches them
case-insensitively using whole-word boundaries.  Multi-word names
(e.g. "palo alto networks") must appear alongside any shorter aliases
("palo alto") — the resolver picks the longest match first.
"""

TICKER_GROUPS: dict[str, list[str]] = {
    "mag 7":             ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "magnificent 7":     ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "magnificent seven": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "faang":             ["META", "AAPL", "AMZN", "NFLX", "GOOGL"],
    "fang":              ["META", "AMZN", "NFLX", "GOOGL"],
    "big tech":          ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "manga":             ["META", "AAPL", "NVDA", "GOOGL", "AMZN"],
}

COMPANY_NAME_MAP: dict[str, str] = {
    # ── Big Tech / Mag-7 ─────────────────────────────────────────────────────
    "apple":                  "AAPL",
    "microsoft":              "MSFT",
    "google":                 "GOOGL",
    "alphabet":               "GOOGL",
    "amazon":                 "AMZN",
    "meta":                   "META",
    "facebook":               "META",
    "nvidia":                 "NVDA",
    "tesla":                  "TSLA",

    # ── Semiconductors ───────────────────────────────────────────────────────
    "advanced micro devices": "AMD",
    "amd":                    "AMD",
    "intel":                  "INTC",
    "qualcomm":               "QCOM",
    "broadcom":               "AVGO",
    "taiwan semiconductor":   "TSM",
    "tsmc":                   "TSM",
    "micron":                 "MU",
    "arm holdings":           "ARM",
    "arm":                    "ARM",
    "applied materials":      "AMAT",

    # ── Software / Cloud ─────────────────────────────────────────────────────
    "salesforce":             "CRM",
    "oracle":                 "ORCL",
    "servicenow":             "NOW",
    "adobe":                  "ADBE",
    "workday":                "WDAY",
    "snowflake":              "SNOW",
    "palantir":               "PLTR",
    "crowdstrike":            "CRWD",
    "datadog":                "DDOG",
    "mongodb":                "MDB",
    "cloudflare":             "NET",
    "zscaler":                "ZS",
    "okta":                   "OKTA",
    "palo alto networks":     "PANW",
    "palo alto":              "PANW",

    # ── Finance ──────────────────────────────────────────────────────────────
    "jpmorgan":               "JPM",
    "jp morgan":              "JPM",
    "goldman sachs":          "GS",
    "goldman":                "GS",
    "morgan stanley":         "MS",
    "bank of america":        "BAC",
    "wells fargo":            "WFC",
    "citigroup":              "C",
    "citi":                   "C",
    "blackrock":              "BLK",
    "american express":       "AXP",
    "amex":                   "AXP",
    "visa":                   "V",
    "mastercard":             "MA",
    "paypal":                 "PYPL",
    "square":                 "SQ",
    "block":                  "SQ",
    "robinhood":              "HOOD",
    "coinbase":               "COIN",

    # ── Consumer / Retail ────────────────────────────────────────────────────
    "walmart":                "WMT",
    "target":                 "TGT",
    "costco":                 "COST",
    "home depot":             "HD",
    "nike":                   "NKE",
    "starbucks":              "SBUX",
    "mcdonald's":             "MCD",
    "mcdonalds":              "MCD",
    "coca-cola":              "KO",
    "coca cola":              "KO",
    "pepsico":                "PEP",
    "pepsi":                  "PEP",
    "procter & gamble":       "PG",
    "procter gamble":         "PG",

    # ── Healthcare / Pharma ──────────────────────────────────────────────────
    "johnson & johnson":      "JNJ",
    "johnson johnson":        "JNJ",
    "pfizer":                 "PFE",
    "moderna":                "MRNA",
    "unitedhealth":           "UNH",
    "united health":          "UNH",
    "abbvie":                 "ABBV",
    "merck":                  "MRK",
    "novo nordisk":           "NVO",
    "eli lilly":              "LLY",
    "lilly":                  "LLY",

    # ── Energy ───────────────────────────────────────────────────────────────
    "exxonmobil":             "XOM",
    "exxon":                  "XOM",
    "chevron":                "CVX",
    "shell":                  "SHEL",
    "bp":                     "BP",

    # ── Telecom / Media ──────────────────────────────────────────────────────
    "at&t":                   "T",
    "att":                    "T",
    "verizon":                "VZ",
    "netflix":                "NFLX",
    "disney":                 "DIS",
    "comcast":                "CMCSA",
    "spotify":                "SPOT",

    # ── EV / Autos ───────────────────────────────────────────────────────────
    "general motors":         "GM",
    "ford":                   "F",
    "rivian":                 "RIVN",
    "lucid":                  "LCID",

    # ── Defence / Industrial ─────────────────────────────────────────────────
    "lockheed martin":        "LMT",
    "lockheed":               "LMT",
    "raytheon":               "RTX",
    "boeing":                 "BA",
    "caterpillar":            "CAT",
    "john deere":             "DE",
    "deere":                  "DE",

    # ── Other notable ────────────────────────────────────────────────────────
    "berkshire hathaway":     "BRK-B",
    "berkshire":              "BRK-B",
    "uber":                   "UBER",
    "lyft":                   "LYFT",
    "airbnb":                 "ABNB",
    "doordash":               "DASH",
    "instacart":              "CART",
    "pinterest":              "PINS",
    "snapchat":               "SNAP",
    "snap":                   "SNAP",
    "twitter":                "X",
    "reddit":                 "RDDT",
    "zoom":                   "ZM",
    "shopify":                "SHOP",
    "etsy":                   "ETSY",
    "ebay":                   "EBAY",
    "booking":                "BKNG",
    "expedia":                "EXPE",
    "roblox":                 "RBLX",
    "unity":                  "U",
    "applovin":               "APP",
    "app lovin":              "APP",
    "supermicro":             "SMCI",
    "super micro":            "SMCI",
    "hewlett packard":        "HPQ",
    "hp":                     "HPQ",
    "dell":                   "DELL",
    "ibm":                    "IBM",
    "3m":                     "MMM",
    "akamai":                 "AKAM",
    "twilio":                 "TWLO",
    "hubspot":                "HUBS",
    "intuit":                 "INTU",
    "autodesk":               "ADSK",
    "ansys":                  "ANSS",
    "cadence":                "CDNS",
    "synopsys":               "SNPS",
    "veeva":                  "VEEV",
    "zendesk":                "ZEN",
}
