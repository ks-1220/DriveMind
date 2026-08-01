from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import os

# Dimension of embeddings (standard size matches Gemini/OpenAI)
EMBEDDING_DIM = 1536

class LocalEmbeddingGenerator:
    """
    Generates dense embeddings offline.
    Uses TF-IDF fit on a corpus, then projects to 1536-dim using a fixed random matrix.
    This creates deterministic, dense vectors representing text semantic distance
    offline, without requiring massive PyTorch or SentenceTransformer downloads.
    """
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.projection_matrix = None
        self.is_fit = False
        
    def fit(self, texts):
        self.vectorizer.fit(texts)
        vocab_size = len(self.vectorizer.vocabulary_)
        
        # Fixed seed for repeatability
        rng = np.random.default_rng(42)
        # Generate random projection matrix to map TF-IDF space -> 1536-dim
        self.projection_matrix = rng.normal(0.0, 1.0 / np.sqrt(EMBEDDING_DIM), size=(vocab_size, EMBEDDING_DIM))
        self.is_fit = True
        
    def generate(self, texts):
        if not self.is_fit:
            # Fallback fit
            self.fit(texts)
            
        tfidf_feats = self.vectorizer.transform(texts).toarray()
        dense_vecs = np.dot(tfidf_feats, self.projection_matrix)
        
        # L2 normalize vectors for cosine similarity
        norms = np.linalg.norm(dense_vecs, axis=1, keepdims=True)
        dense_vecs = dense_vecs / (norms + 1e-9)
        return [vec.tolist() for vec in dense_vecs]

class FleetVectorDB:
    def __init__(self):
        self.client = QdrantClient(":memory:")
        self.collection_name = "fleet_intelligence"
        self.embedder = LocalEmbeddingGenerator()
        self.initialized = False

    def init_db(self, documents):
        """
        Creates collection in Qdrant and indexes unstructured documents.
        """
        # Fit embedder on all document contents
        all_texts = [doc["content"] for doc in documents] + [doc["title"] for doc in documents]
        self.embedder.fit(all_texts)
        
        # Create collection
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        
        # Prepare points
        points = []
        for idx, doc in enumerate(documents):
            # Combine title and content for embedding representation
            combined_text = f"Title: {doc['title']}\nCategory: {doc['category']}\nTags: {doc['tags']}\nContent: {doc['content']}"
            vector = self.embedder.generate([combined_text])[0]
            
            points.append(
                PointStruct(
                    id=idx + 1,
                    vector=vector,
                    payload={
                        "doc_id": doc["id"],
                        "title": doc["title"],
                        "category": doc["category"],
                        "tags": doc["tags"],
                        "content": doc["content"]
                    }
                )
            )
            
        # Upsert into collection
        self.client.upsert(
            collection_name=self.collection_name,
            wait=True,
            points=points
        )
        self.initialized = True
        print(f"Qdrant In-Memory Vector Store loaded: {len(documents)} documents indexed.")

    def search(self, query, limit=3, category_filter=None):
        """
        Performs semantic cosine similarity search.
        Includes optional metadata filtering by document category.
        """
        if not self.initialized:
            return []
            
        vector = self.embedder.generate([query])[0]
        
        # Build filter if category is specified
        qdrant_filter = None
        if category_filter:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category_filter)
                    )
                ]
            )
            
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=qdrant_filter,
            limit=limit
        )
        results = response.points
        
        # Format results
        hits = []
        for r in results:
            hits.append({
                "doc_id": r.payload["doc_id"],
                "title": r.payload["title"],
                "category": r.payload["category"],
                "content": r.payload["content"],
                "score": round(float(r.score), 3)
            })
            
        return hits
