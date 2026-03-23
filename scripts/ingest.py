import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

DATA_PATH = "data/"
CHROMA_PATH = "chroma_db/"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

def build_vector_db():
    print(f"Čitam PDF dokumente iz mape: {DATA_PATH}")
    
    loader = PyPDFDirectoryLoader(DATA_PATH)
    documents = loader.load()
    
    if not documents:
        print("Nema PDF dokumenata u 'data/' mapi. Dodajte priručnike i pokušajte ponovno.")
        return

    print("✂Cijepam dokumente na manje dijelove (chunks)...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Kreirano {len(chunks)} chunkova teksta.")

    print(f"Povezujem se s modelom '{EMBEDDING_MODEL}' za kreiranje vektora...")
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_HOST
    )

    print(f"Spremam vektore u ChromaDB ({CHROMA_PATH}). Ovo može potrajati...")
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH
    )
    
    db.persist()
    print("Baza znanja je uspješno izgrađena!")

if __name__ == "__main__":
    build_vector_db()