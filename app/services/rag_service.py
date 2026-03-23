import logging
import concurrent.futures
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    embeddings = OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.OLLAMA_HOST
    )
    vector_db = Chroma(
        persist_directory="chroma_db",
        embedding_function=embeddings
    )
    logger.info("RAG Vektorska baza uspješno učitana.")
except Exception as e:
    logger.error(f"RAG inicijalizacija nije uspjela. Vektorska baza neće biti dostupna: {e}")
    vector_db = None

def _do_search(query: str, k: int = 3) -> str:
    """
    Funkcija koja komunicira s ChromaDB-om.
    Ovo se izvršava u odvojenom threadu kako ne bi blokiralo glavni proces.
    """
    results = vector_db.similarity_search(query, k=k)
    return "\n---\n".join([doc.page_content for doc in results])

def retrieve_context_with_timeout(query: str, timeout_sec: int = 5) -> str:
    """
    Javna funkcija za dohvaćanje konteksta sa strogim vremenskim ograničenjem.
    Sprječava da spora baza trajno zaključa Celery Workera.
    """
    if not vector_db:
        return "Baza znanja trenutno nije dostupna."

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_search, query)
        try:
            context = future.result(timeout=timeout_sec)

            if not context.strip():
                return "Nema relevantnih podataka u priručnicima za ovaj upit."

            logger.info(f"RAG pretraga uspješna za upit: '{query}'")
            return context

        except concurrent.futures.TimeoutError:
            logger.warning(f"RAG Timeout! Pretraga trajala duže od {timeout_sec}s. Nastavljam analizu bez priručnika.")
            return "Nema dostupnog konteksta (baza je bila prespora)."

        except Exception as e:
            logger.error(f"Neočekivana greška pri RAG pretrazi: {e}")
            return "Došlo je do greške pri pretraživanju priručnika."