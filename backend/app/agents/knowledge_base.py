"""
RAG Knowledge Base — Manages Job Descriptions, Interview Resources, and Career Data.
Powers the Gap Analysis and Career Assistant Agents using AWS Bedrock and pgvector.
"""
import os
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# We will use SQLAlchemy + pgvector for local vector storage, 
# but wrap it nicely so it can be swapped with native Bedrock Knowledge Bases later.
from langchain_community.vectorstores import PGVector

from app.config import settings

class CareerKnowledgeBase:
    def __init__(self):
        self.embeddings = self._get_embeddings_model()
        self.collection_name = "career_resources"
        
        # In a real setup, connection string comes from settings.DATABASE_URL
        # We replace asyncpg with psycopg2 for standard langchain sync pgvector compatibility
        sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
        
        try:
            self.vector_store = PGVector(
                connection_string=sync_db_url,
                embedding_function=self.embeddings,
                collection_name=self.collection_name,
                use_jsonb=True,
            )
        except Exception as e:
            print(f"Warning: Could not connect to PGVector DB. Operating in mock mode. Error: {e}")
            self.vector_store = None

    def _get_embeddings_model(self):
        """Initialize AWS Bedrock Embeddings (Titan or Cohere)"""
        # Note: Requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in env
        return BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0", # Standard AWS embedding model
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )

    def ingest_job_description(self, role_title: str, company: str, raw_text: str) -> int:
        """
        Chunks a Job Description and embeds it into the knowledge base.
        """
        if not self.vector_store:
            print("DB Offline: Skipping ingestion.")
            return 0

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " "]
        )
        
        chunks = text_splitter.split_text(raw_text)
        
        documents = [
            Document(
                page_content=chunk, 
                metadata={"role": role_title, "company": company, "type": "job_description"}
            )
            for chunk in chunks
        ]
        
        # Generate embeddings and store in PostgreSQL
        self.vector_store.add_documents(documents)
        return len(documents)

    def retrieve_requirements_for_role(self, target_role: str, top_k: int = 5) -> str:
        """
        Retrieves the most relevant skills and requirements for a given role 
        to feed into the Gap Analysis Agent.
        """
        if not self.vector_store:
            # Fallback for UI testing when DB is down
            return f"MOCK RAG DATA: For {target_role}, requires Python, AWS Bedrock, System Design, and LangChain."

        query = f"What are the mandatory technical skills, requirements, and responsibilities for a {target_role}?"
        
        # Perform semantic similarity search
        results = self.vector_store.similarity_search_with_score(
            query=query, 
            k=top_k,
            filter={"type": "job_description"} # Only search JDs
        )
        
        # Synthesize retrieved chunks into a single context string for the LLM
        context = ""
        for i, (doc, score) in enumerate(results):
            company = doc.metadata.get("company", "Unknown Company")
            context += f"\n--- Source {i+1} ({company}) ---\n{doc.page_content}\n"
            
        return context

# Singleton instance
kb = CareerKnowledgeBase()
