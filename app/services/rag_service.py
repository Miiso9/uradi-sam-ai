import logging
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_vector_db():
    """Lazy loading Chroma baze kako bi izbjegli Celery SQLite deadlock."""
    try:
        embeddings = OllamaEmbeddings(
            model=settings.EMBEDDING_MODEL,
            base_url=settings.OLLAMA_HOST
        )
        vector_db = Chroma(
            persist_directory="chroma_db",
            embedding_function=embeddings
        )
        return vector_db
    except Exception as e:
        logger.error(f"RAG inicijalizacija nije uspjela: {e}")
        return None

def retrieve_context_with_timeout(query: str, threshold: float = 1.5) -> str:
    """
    Dohvaćanje konteksta s filtriranjem loših rezultata.
    Mali score (udaljenost) = velika sličnost.
    """
    vector_db = get_vector_db()

    if not vector_db:
        logger.warning("Baza znanja nije dostupna, preskačem RAG.")
        return ""

    logger.info(f"Pretražujem RAG bazu za upit: '{query}'")

    try:
        results_with_scores = vector_db.similarity_search_with_score(query, k=3)

        valid_results = []
        for doc, score in results_with_scores:
            logger.info(f"Pronađen dokument u bazi sa score-om udaljenosti: {round(score, 2)}")
            if score < threshold:
                valid_results.append(doc.page_content)

        if not valid_results:
            logger.info("RAG dokumenti nisu dovoljno relevantni za ovaj upit. Preskačem ubacivanje konteksta.")
            return ""

        logger.info(f"RAG pretraga uspješna! Filtrirano {len(valid_results)} visoko relevantnih odlomaka.")
        return "\n---\n".join(valid_results)

    except Exception as e:
        logger.error(f"Neočekivana greška pri RAG pretrazi: {e}")
        return ""