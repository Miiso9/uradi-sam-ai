#!/bin/bash

echo "⏳ Čekam da Ollama server postane spreman..."
while ! curl -s http://ollama:11434/ > /dev/null; do
  sleep 2
done
echo "✅ Ollama server je dostupan!"

echo "⚙️ Provjeravam i pripremam AI model: ${AI_MODEL}..."
curl -s -X POST http://ollama:11434/api/pull -d "{\"name\": \"${AI_MODEL}\", \"stream\": false}"
echo "✅ AI model je spreman!"

echo "🚀 Pokrećem UradiSam API server..."

echo "⚙️ Provjeravam i pripremam AI model: ${AI_MODEL}..."

curl -s -X POST http://ollama:11434/api/pull -d "{\"name\": \"${AI_MODEL}\", \"stream\": false}"

echo "⚙️ Provjeravam i pripremam Embedding model: ${EMBEDDING_MODEL}..."
curl -s -X POST http://ollama:11434/api/pull -d "{\"name\": \"${EMBEDDING_MODEL}\", \"stream\": false}"

echo "✅ Svi modeli su spremni!"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload