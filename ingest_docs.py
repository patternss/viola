#!/usr/bin/env python3
"""
Simple script to ingest documents into the Chroma vectorstore.
Based on the rag_ingest.ipynb notebook.
"""

import os
import glob
import hashlib
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

PERSIST_DIR = "./index/chroma"
COLLECTION = "artificial_intelligence"
EMBED = "intfloat/multilingual-e5-small"  # good for Finnish
CORPUS_DIR = "./corpus"

def load_docs(corpus_dir=CORPUS_DIR):
    paths = glob.glob(os.path.join(corpus_dir, "**", "*"), recursive=True)
    docs = []
    
    for path in paths:
        if os.path.isfile(path):
            print(f"Loading: {path}")
            
            if path.endswith('.txt'):
                loader = TextLoader(path, encoding='utf-8')
            elif path.endswith('.pdf'):
                loader = PyPDFLoader(path)
            else:
                print(f"Skipping unsupported file type: {path}")
                continue
                
            try:
                loaded_docs = loader.load()
                docs.extend(loaded_docs)
                print(f"  → Loaded {len(loaded_docs)} documents")
            except Exception as e:
                print(f"  → Error loading {path}: {e}")
    
    return docs

def main():
    print("Starting document ingestion...")
    print(f"Corpus directory: {CORPUS_DIR}")
    print(f"Target collection: {COLLECTION}")
    print(f"Embeddings model: {EMBED}")
    print()
    
    # Load documents
    print("1. Loading documents...")
    docs = load_docs()
    print(f"Total documents loaded: {len(docs)}")
    
    if not docs:
        print("No documents found! Check your corpus directory.")
        return
    
    # Split documents
    print("\n2. Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""]
    )
    
    splits = text_splitter.split_documents(docs)
    print(f"Created {len(splits)} chunks")
    
    # Initialize embeddings
    print(f"\n3. Loading embeddings model: {EMBED}")
    emb = HuggingFaceEmbeddings(model_name=EMBED)
    
    # Create/update vectorstore
    print(f"\n4. Creating vectorstore in {PERSIST_DIR}")
    vs = Chroma(
        collection_name=COLLECTION,
        persist_directory=PERSIST_DIR,
        embedding_function=emb,
    )
    
    # Add documents
    print("5. Adding documents to vectorstore...")
    vs.add_documents(splits)
    
    print(f"\n✅ Successfully indexed {len(splits)} chunks into '{COLLECTION}' collection!")
    print(f"Vectorstore saved to: {PERSIST_DIR}")

if __name__ == "__main__":
    main()