# **🛠️ DIY AI \- Backend API**

DIY AI (UradiSam AI) is an advanced, asynchronous backend system based on a microservice architecture, designed to provide safe and accurate advice for do-it-yourself (DIY) home repairs.

The system uses **Multimodal RAG** (Retrieval-Augmented Generation), combining image analysis (Vision AI) with expert manuals (Vector Database) to provide users with accurate repair steps, alongside strict safety mechanisms (*Safety Guardrails*).

## **🏗️ Architecture and Technologies**

The project is built according to industry standards for AI applications that require intensive CPU/GPU processing without blocking the user interface.

* **FastAPI:** Fast API Gateway for handling HTTP requests, validation (Pydantic), and Rate Limiting (SlowAPI).  
* **Celery:** Asynchronous *Task Queue* worker responsible for long-running AI model execution in the background.  
* **Redis:** *Message Broker* for Celery and a two-layer *Cache* system (remembers previous image analyses to reduce AI model load).  
* **Ollama:** Local AI engine running 3 separate models:  
  * LLaVA (Vision-Language model for analyzing the image of the broken item).  
  * Llama3 (Smaller, fast model serving exclusively as a *Safety Guard* for hazard checking).  
  * nomic-embed-text (Embedding model for converting manuals into vectors).  
* **ChromaDB & LangChain:** Vector database and orchestrator for Multimodal RAG. The system retrieves relevant pages from PDF manuals before responding to the user.

## **🚀 How to Run the Project Locally**

### **1\. Prerequisites**

* Installed **Docker** and **Docker Compose**.  
* Minimum 16 GB of RAM (24+ GB recommended for parallel execution of multiple AI models, especially suitable for Oracle Cloud ARM instances).

### **2\. Environment Configuration**

Clone the repository and create an .env file in the root folder (you can copy from .env.example if it exists):

AI\_MODEL=llava  
SAFETY\_MODEL=llama3  
EMBEDDING\_MODEL=nomic-embed-text  
OLLAMA\_HOST=http://ollama:11434  
REDIS\_URL=redis://redis:6379/0  
API\_KEY=your\_secret\_key  
SUPABASE\_JWT\_SECRET=your_jw_token  
MAX\_IMAGE\_SIZE\_MB=5

### **3\. Running Docker**

The system is fully containerized. To download images, build, and run all services (API, Worker, Redis, Ollama), execute:

docker-compose up \--build \-d

*Note: On the first run, the entrypoint.sh script will automatically download the necessary AI models (LLaVA, Llama3, Nomic). This may take some time depending on your internet speed.*

## **📚 RAG Knowledge Base (Ingestion)**

To ensure the AI model provides accurate advice specific to certain devices, the vector database (ChromaDB) must be populated with PDF manuals in English (the system automatically translates user queries into English for retrieval).

1. Drop PDF manuals (e.g., water heater instructions, error code tables) into the data/ folder.  
2. Run the database build script inside the **Celery Worker** container:

docker exec \-it uradisam\_worker python scripts/ingest.py

The system will chunk the documents, convert them into vectors using the nomic-embed-text model, and permanently save them to the chroma\_db/ folder.

## **🛠️ Useful Maintenance Commands**

**Monitoring AI Processing Logs (Celery):**

Here you can track RAG retrieval, translation, and AI model reasoning in real-time.

docker logs \-f uradisam\_worker

**Monitoring API Logs:**

docker logs \-f uradisam\_api

**Clearing Redis Cache:**

The system caches hashes of images and questions. If you are developing and want to force the AI to re-analyze the same image (instead of returning a cached result), clear the Redis database:

docker exec \-it uradisam\_redis redis-cli FLUSHALL

## **📡 API Endpoints**

All endpoints are documented via the Swagger UI interface. Once the system is running, visit:

👉 **http://localhost:8000/docs**

Basic application flow (Asynchronous pattern):

1. POST /api/v1/analyze \- Accepts an image and a text question. Instantly returns a task\_id.  
2. GET /api/v1/tasks/{task\_id} \- Used for polling. Returns the processing status (PENDING, STARTED) or the final JSON analysis result containing safety checks and B2B affiliate data.