"""
Retrieval-Augmented Generation (RAG) using ChromaDB.

Stores chunks of the business profile (services, hours, FAQ, policies, mobile
service area, vehicle support) in a vector store so an AI receptionist can pull
relevant context when answering ad-hoc customer questions.

NOTE: the main conversation hot path (`backend/call_flow.py`) does its own
prompting against `business_data.json` directly. This module is used for
seeding the vector DB and for ad-hoc retrieval / one-off LLM Q&A.
"""
import os
import json
import hashlib
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict
from .utils.logger import logger

# Lazy initialization - client will be created when needed
_client = None


def get_openai_client():
    """Get or create OpenAI client with API key from environment.

    The `openai` package is imported lazily so modules that don't need it
    (chunking, seeding, training utilities) work without the SDK installed.
    """
    global _client
    if _client is None:
        from openai import OpenAI  # imported lazily

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Make sure .env file is loaded."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def load_business_data(business_data_path: Path) -> Dict:
    """
    Load business data from JSON file.
    
    Args:
        business_data_path: Path to business_data.json
        
    Returns:
        Business data dictionary
    """
    try:
        with open(business_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded business data from {business_data_path}")
        return data
    except Exception as e:
        logger.error(f"Error loading business data: {str(e)}")
        raise


def make_chunks(biz_data: Dict) -> List[Dict]:
    """
    Convert business data JSON into text chunks for vector storage.
    
    Args:
        biz_data: Business data dictionary
        
    Returns:
        List of chunk dictionaries with 'text', 'id', and 'metadata'
    """
    chunks = []
    business_name = biz_data.get("business_name", "Business")

    # Chunk 1: Basic info (name, description, contact)
    address = biz_data.get("address", {})
    if isinstance(address, dict):
        address_str = f"{address.get('street', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}"
        phone = address.get('phone', '')
    else:
        address_str = str(address)
        phone = ""
    
    basic_info = f"{business_name}: {biz_data.get('description', '')} "
    basic_info += f"Located at {address_str}. Phone: {phone}."
    if address.get('website'):
        basic_info += f" Website: {address.get('website')}."
    
    chunks.append({
        "id": "basic_info",
        "text": basic_info,
        "metadata": {"type": "basic_info", "section": "overview"}
    })
    
    # Chunk 2: Hours + Location info
    hours = biz_data.get("hours", {})
    hours_text = f"{business_name} hours: "
    hours_list = [f"{day.capitalize()}: {time}" for day, time in hours.items()]
    hours_text += "; ".join(hours_list)
    
    location_info = biz_data.get("location_info", {})
    if location_info:
        hours_text += f" Location: {address_str}."
        if location_info.get("parking"):
            hours_text += f" Parking: {location_info['parking']}"
        if location_info.get("landmarks"):
            hours_text += f" {location_info['landmarks']}"
        if location_info.get("public_transport"):
            hours_text += f" {location_info['public_transport']}"
    
    chunks.append({
        "id": "hours_location",
        "text": hours_text,
        "metadata": {"type": "hours", "section": "hours_location"}
    })
    
    # Chunk 3: Services catalog (detailing schema - one chunk per service)
    services = biz_data.get("services", [])
    if isinstance(services, list):
        for svc in services:
            name = svc.get("name", "")
            pmin = svc.get("price_min")
            pmax = svc.get("price_max")
            dmin = svc.get("duration_hours_min")
            dmax = svc.get("duration_hours_max")
            desc = svc.get("description", "")
            notes = svc.get("notes", "")

            price_str = ""
            if pmin is not None and pmax is not None:
                price_str = f" Price range: ${pmin}-${pmax}."
            duration_str = ""
            if dmin is not None and dmax is not None:
                duration_str = f" Typical duration: {dmin}-{dmax} hours."

            service_text = f"Service - {name}: {desc}{price_str}{duration_str}"
            if notes:
                service_text += f" Notes: {notes}"

            chunks.append({
                "id": f"service_{name.lower().replace(' ', '_')}",
                "text": service_text,
                "metadata": {"type": "service", "service": name}
            })

    # Chunk 3c: Mobile service area
    mobile = biz_data.get("mobile_service", {})
    if isinstance(mobile, dict) and mobile.get("available"):
        radius = mobile.get("service_radius_miles", 25)
        areas = mobile.get("service_area_examples", [])
        reqs = mobile.get("requirements", "")
        weather = mobile.get("weather_policy", "")
        mobile_text = (
            f"{business_name} offers mobile detailing within roughly {radius} miles. "
            f"Common service areas: {', '.join(areas)}. {reqs} {weather}"
        ).strip()
        chunks.append({
            "id": "mobile_service",
            "text": mobile_text,
            "metadata": {"type": "mobile_service", "section": "mobile"}
        })

    # Chunk 3d: Vehicle support
    vehicle = biz_data.get("vehicle_support", {})
    if isinstance(vehicle, dict) and vehicle:
        types = vehicle.get("supported_vehicle_types", [])
        size_note = vehicle.get("size_pricing_note", "")
        vehicle_text = (
            f"{business_name} services these vehicle types: {', '.join(types)}. {size_note}"
        ).strip()
        chunks.append({
            "id": "vehicle_support",
            "text": vehicle_text,
            "metadata": {"type": "vehicle_support", "section": "vehicles"}
        })
    
    # Chunk 4: FAQ (one chunk per FAQ item)
    faq_items = biz_data.get("faq", [])
    for i, faq in enumerate(faq_items):
        faq_text = f"Q: {faq.get('question', '')} A: {faq.get('answer', '')}"
        chunks.append({
            "id": f"faq_{i}",
            "text": faq_text,
            "metadata": {"type": "faq", "index": i}
        })
    
    # Chunk 5: Policies
    policies = biz_data.get("policies", {})
    if policies:
        policies_text = f"{business_name} policies: "
        policy_items = []
        for key, value in policies.items():
            policy_items.append(f"{key.replace('_', ' ').title()}: {value}")
        policies_text += " | ".join(policy_items)
        
        chunks.append({
            "id": "policies",
            "text": policies_text,
            "metadata": {"type": "policies", "section": "policies"}
        })
    
    # Chunk 6: Appointment rules
    appointment_rules = biz_data.get("appointment_rules", {})
    if appointment_rules:
        a_text = "Appointment booking info: "
        if appointment_rules.get("lead_time_hours_standard"):
            a_text += f"Standard services need about {appointment_rules['lead_time_hours_standard']} hours notice. "
        if appointment_rules.get("lead_time_hours_coating"):
            a_text += f"Ceramic coating typically needs about {appointment_rules['lead_time_hours_coating']} hours notice. "
        slots = appointment_rules.get("appointment_time_blocks", [])
        if slots:
            a_text += f"Common appointment start times: {', '.join(slots)}. "
        if appointment_rules.get("weekend_available"):
            a_text += "We do take weekend appointments on Saturdays. "
        chunks.append({
            "id": "appointment_rules",
            "text": a_text.strip(),
            "metadata": {"type": "appointment", "section": "appointment_rules"}
        })
    
    # Chunk 7: Special notes
    special_notes = biz_data.get("special_notes", [])
    if special_notes:
        notes_text = f"{business_name} special information: " + " | ".join(special_notes)
        chunks.append({
            "id": "special_notes",
            "text": notes_text,
            "metadata": {"type": "special_notes", "section": "notes"}
        })
    
    logger.info(f"Created {len(chunks)} chunks from business data")
    return chunks


def seed_vectordb(business_data_path: Path, business_id: str = "oc_elite_detailing", clear_existing: bool = False):
    """
    Seed the vector database with business data chunks.
    
    Args:
        business_data_path: Path to business_data.json
        business_id: Business identifier
        clear_existing: Whether to clear existing data before seeding
    """
    try:
        logger.info(f"Seeding vector database for business: {business_id}")
        
        # Load business data
        biz_data = load_business_data(business_data_path)
        
        # Make chunks
        chunks = make_chunks(biz_data)
        
        # Initialize RAG system
        rag = RAGSystem(business_id=business_id)
        
        # Clear existing collection if requested
        if clear_existing:
            try:
                rag.chroma_client.delete_collection(name=rag.collection.name)
                rag.collection = rag.chroma_client.create_collection(
                    name=rag.collection.name,
                    metadata={"business_id": business_id}
                )
                logger.info(f"Cleared existing collection: {rag.collection.name}")
            except:
                pass
        
        # Convert chunks to documents format
        documents = []
        for chunk in chunks:
            documents.append({
                "text": chunk["text"],
                "metadata": {
                    **chunk["metadata"],
                    "chunk_id": chunk["id"]
                }
            })
        
        # Add to vector store
        rag.add_documents(documents)
        
        logger.info(f"Successfully seeded vector database with {len(chunks)} chunks")
        return rag
        
    except Exception as e:
        logger.error(f"Error seeding vector database: {str(e)}")
        raise


# Response cache for LLM calls (reduces API costs)
# Uses LRU cache with TTL (24 hours)
_response_cache: OrderedDict = OrderedDict()
_cache_max_size = 500  # Max 500 cached responses
_cache_ttl_hours = 24  # Cache expires after 24 hours


def _get_cache_key(query: str, context_hash: str = "") -> str:
    """Generate cache key from query and context."""
    key_string = f"{query.lower().strip()}:{context_hash}"
    return hashlib.md5(key_string.encode()).hexdigest()


def _get_cached_response(cache_key: str) -> Optional[str]:
    """Get cached response if it exists and hasn't expired."""
    if cache_key not in _response_cache:
        return None
    
    cached_item = _response_cache[cache_key]
    # Check if expired (24 hour TTL)
    if datetime.now() - cached_item['timestamp'] > timedelta(hours=_cache_ttl_hours):
        _response_cache.pop(cache_key)
        return None
    
    # Move to end (LRU)
    _response_cache.move_to_end(cache_key)
    return cached_item['response']


def _cache_response(cache_key: str, response: str):
    """Cache a response."""
    _response_cache[cache_key] = {
        'response': response,
        'timestamp': datetime.now()
    }
    
    # Enforce max size (remove oldest if over limit)
    if len(_response_cache) > _cache_max_size:
        _response_cache.popitem(last=False)  # Remove oldest


class RAGSystem:
    """RAG system for retrieving business information."""
    
    def __init__(self, business_id: str = "default", db_path: str = "./chroma_db"):
        """
        Initialize RAG system with ChromaDB.
        
        Args:
            business_id: Unique identifier for the business
            db_path: Path to ChromaDB directory
        """
        self.business_id = business_id
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        collection_name = f"business_{business_id}"
        try:
            self.collection = self.chroma_client.get_collection(name=collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except:
            self.collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"business_id": business_id}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def _embed_text(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts using OpenAI.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        client = get_openai_client()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in response.data]
    
    def add_documents(self, documents: List[Dict[str, str]]):
        """
        Add documents to the vector store.
        
        Args:
            documents: List of dicts with 'text' and optional 'metadata'
        """
        try:
            texts = [doc["text"] for doc in documents]
            metadatas = [doc.get("metadata", {}) for doc in documents]
            ids = [f"{self.business_id}_{i}" for i in range(len(documents))]
            
            # Generate embeddings in batch
            embeddings = self._embed_text(texts)
            
            # Add to collection
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added {len(documents)} documents to collection")
            
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            raise
    
    def retrieve(self, query: str, n_results: int = 3) -> List[Dict]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant documents with metadata
        """
        try:
            # Skip retrieval for queries that are obviously off-topic for an
            # auto-detailing receptionist - keeps the LLM from hallucinating
            # on irrelevant context.
            query_lower = query.lower()
            unrelated_keywords = [
                "weather forecast", "temperature outside", "rain forecast",
                "news", "sports", "politics", "stock", "crypto",
                "movie", "tv show", "netflix", "youtube",
            ]
            if any(keyword in query_lower for keyword in unrelated_keywords):
                logger.info(f"Query '{query[:50]}...' is off-topic for detailing; skipping RAG retrieval")
                return []
            
            # Generate query embedding
            query_embeddings = self._embed_text([query])
            query_embedding = query_embeddings[0]
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # Format results
            retrieved_docs = []
            if results["documents"] and len(results["documents"][0]) > 0:
                for i in range(len(results["documents"][0])):
                    retrieved_docs.append({
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0
                    })
            
            logger.info(f"Retrieved {len(retrieved_docs)} documents for query: {query[:50]}...")
            return retrieved_docs
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []
    
    def generate_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        retrieved_context: Optional[List[str]] = None
    ) -> str:
        """
        Generate response using GPT-4o with retrieved context.
        
        COST OPTIMIZATION: Uses response caching to avoid duplicate LLM calls.
        Cached responses are valid for 24 hours.
        
        Args:
            query: User's question
            conversation_history: Previous conversation messages
            retrieved_context: Retrieved document texts
            
        Returns:
            Generated response
        """
        try:
            # Build context from retrieved documents
            context_text = ""
            if retrieved_context:
                context_text = "\n\n".join(retrieved_context)
            
            # Check cache first (cost optimization)
            context_hash = hashlib.md5(context_text.encode()).hexdigest() if context_text else ""
            cache_key = _get_cache_key(query, context_hash)
            cached_response = _get_cached_response(cache_key)
            
            if cached_response:
                logger.info(f"✅ Using CACHED response (no LLM call) for query: {query[:50]}...")
                return cached_response, "llm_cached"  # Return response and source
            
            # Build the system prompt dynamically from the active business profile,
            # so this works for any detailing shop the AI is configured for.
            try:
                business_data_path = Path(__file__).parent / "business_data.json"
                biz = load_business_data(business_data_path) if business_data_path.exists() else {}
            except Exception:
                biz = {}
            business_name = biz.get("business_name", "the shop")
            persona = biz.get("ai_persona", {}) or {}
            assistant_name = persona.get("assistant_name", "the receptionist")

            system_prompt = (
                f"You are {assistant_name}, the AI receptionist for {business_name}, an auto detailing business. "
                "Use the provided business information to answer customer questions accurately. "
                "Be concise, friendly, and confident. "
                "If you don't know something, say so and offer to capture the customer's contact info so the team can follow up. "
                "Never guarantee an exact price; offer the range from the services list and say the team will confirm after seeing the vehicle. "
                "Never promise ceramic coating prevents all scratches."
            )

            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current query with context
            user_message = query
            if context_text:
                user_message = f"""Business Information:
{context_text}

Customer Question: {query}

Please answer the customer's question using the business information above."""
            
            messages.append({"role": "user", "content": user_message})
            
            # Generate response
            client = get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",   # faster, cheaper, good for phone replies
                messages=messages,
                temperature=0.3,        # COST OPT: Lower temp = more deterministic, slightly cheaper
                max_tokens=150         # COST OPT: Reduced from 220 to save tokens
            )
            
            generated_text = response.choices[0].message.content.strip()
            logger.info(f"⚠️ Generated NEW response (LLM call) for query: {query[:50]}...")
            
            # Cache the response for future use
            _cache_response(cache_key, generated_text)
            
            return generated_text, "llm_gpt4o_mini"  # Return response and source
                
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again or call back later.", "llm_error"


# Global RAG instance (will be initialized in main.py)
rag_system: Optional[RAGSystem] = None

def get_rag_system(business_id: str = "default") -> RAGSystem:
    """Get or create RAG system instance."""
    global rag_system
    if rag_system is None or rag_system.business_id != business_id:
        rag_system = RAGSystem(business_id=business_id)
    return rag_system

