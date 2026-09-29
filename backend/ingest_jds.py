import sys
import os
import argparse

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.knowledge_base import kb

def main():
    parser = argparse.ArgumentParser(description="Ingest a Job Description into the RAG Knowledge Base")
    parser.add_argument("--role", type=str, required=True, help="Job Role (e.g., 'Software Engineer')")
    parser.add_argument("--company", type=str, required=True, help="Company Name")
    parser.add_argument("--file", type=str, required=True, help="Path to text file containing the Job Description")

    args = parser.parse_args()

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            raw_text = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find file {args.file}")
        return

    print(f"Ingesting JD for {args.role} at {args.company}...")
    chunks_stored = kb.ingest_job_description(args.role, args.company, raw_text)
    
    if chunks_stored > 0:
        print(f"Success! {chunks_stored} document chunks embedded and stored in PGVector.")
    else:
        print("Ingestion failed or DB is offline (running in mock mode).")

if __name__ == "__main__":
    main()
