import logging

logger = logging.getLogger(__name__)

EXPERTS_DB = {
    "električar": "+387 63 111 222 (Elektro Mostar)",
    "vodoinstalater": "+387 63 333 444 (Vodovod Servis)",
    "stolar": "+387 63 555 666 (Stolarija Drvo)",
    "plinar": "+387 63 777 888 (Plin Sigurnost)"
}

SHOP_SEARCH_URL = "[https://pennyshop.ba/shop/pretraga?keywords=](https://pennyshop.ba/shop/pretraga?keywords=)"

def match_b2b_opportunities(tools: list, expert: str, feasibility: str) -> dict:
    """
    Na temelju prevedenih AI podataka, traži match za affiliate linkove ili leadove.
    """
    b2b_data = {
        "expert_number": "",
        "shop_links": []
    }

    if feasibility == "DO_NOT_ATTEMPT":
        if expert:
            expert_lower = expert.lower()
            for kljuc, broj in EXPERTS_DB.items():
                if kljuc in expert_lower:
                    b2b_data["expert_number"] = broj
                    logger.info(f"B2B LEAD MATCH: Pronađen majstor -> {broj}")
                    break

        if not b2b_data["expert_number"]:
            b2b_data["expert_number"] = "+387 63 000 000 (Hitne Intervencije)"

    elif feasibility in ["EASY", "MEDIUM", "HARD"]:
        links = []
        for tool in tools:
            safe_query = str(tool).strip().replace(" ", "+")
            links.append(f"{SHOP_SEARCH_URL}{safe_query}")

        b2b_data["shop_links"] = links
        logger.info(f"🛒 B2B AFFILIATE MATCH: Generirano {len(links)} linkova za kupnju.")

    return b2b_data