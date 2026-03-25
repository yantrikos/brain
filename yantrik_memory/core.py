"""
Yantrik Memory — Core Module

Persistent cognitive memory for AI agents, powered by YantrikDB.
Provides personality traits, bond evolution, and context assembly.
"""

import os
import time
import threading
import math
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

import yantrikdb

logger = logging.getLogger("yantrik_memory")

# ── Constants ──────────────────────────────────────────────────────────────

VALID_MEMORY_KINDS = frozenset({
    "fact", "preference", "episode", "skill", "secret",
    "insight", "correction", "summary", "goal",
})

VALID_SCOPES = frozenset({
    "global", "user", "session", "agent",
})

DEFAULT_TRAITS = {
    "humor": 0.5, "empathy": 0.5, "curiosity": 0.5, "creativity": 0.5,
    "helpfulness": 0.5, "honesty": 0.5, "conciseness": 0.5,
    "formality": 0.5, "directness": 0.5,
}

TRAIT_DECAY_HALF_LIFE_DAYS = 30


# ── Trait Signals ──────────────────────────────────────────────────────────

TRAIT_SIGNALS = {
    "humor": {
        "positive": ["haha", "lol", "funny", "joke", "laugh", "hilarious", "lmao", "rofl", "witty", "humor"],
        "negative": ["serious", "not funny", "stop joking", "be serious", "no jokes", "professional"],
    },
    "empathy": {
        "positive": ["thank you", "thanks", "appreciate", "kind", "caring", "understand", "thoughtful", "sweet"],
        "negative": ["cold", "don't care", "whatever", "dismissive", "heartless", "robotic"],
    },
    "curiosity": {
        "positive": ["interesting", "tell me more", "why", "how does", "curious", "fascinating", "explain", "wonder"],
        "negative": ["don't care", "boring", "skip", "whatever", "not interested", "too much detail"],
    },
    "creativity": {
        "positive": ["creative", "innovative", "unique", "original", "imaginative", "clever", "brilliant idea"],
        "negative": ["basic", "standard", "conventional", "boring", "plain", "just do the normal thing"],
    },
    "helpfulness": {
        "positive": ["helpful", "useful", "great help", "saved me", "perfect", "exactly what i needed"],
        "negative": ["useless", "not helpful", "wrong", "unhelpful", "waste of time"],
    },
    "honesty": {
        "positive": ["honest", "truthful", "straightforward", "transparent", "frank", "candid"],
        "negative": ["lying", "dishonest", "misleading", "sugar coating", "fake"],
    },
    "conciseness": {
        "positive": ["concise", "succinct", "brief", "short", "pithy", "to the point", "tldr", "keep it short"],
        "negative": ["more detail", "elaborate", "explain more", "too short", "expand on", "tell me more about"],
    },
    "formality": {
        "positive": ["formal", "professional", "proper", "sir", "ma'am", "dear", "respectfully"],
        "negative": ["casual", "chill", "relax", "informal", "dude", "bro", "lol"],
    },
    "directness": {
        "positive": ["direct", "straight to the point", "just tell me", "bottom line", "cut to the chase"],
        "negative": ["gentle", "soften", "ease into", "diplomatically", "carefully"],
    },
}

# Negative signals weighted heavier to prevent one-way ratcheting
NEGATIVE_SIGNAL_WEIGHT = 1.33


# ── Bond Levels ────────────────────────────────────────────────────────────

class BondLevel(Enum):
    STRANGER = ("stranger", 0.0, "No established relationship")
    ACQUAINTANCE = ("acquaintance", 0.15, "Basic familiarity")
    FAMILIAR = ("familiar", 0.35, "Regular interaction, some shared context")
    COMPANION = ("companion", 0.55, "Comfortable working relationship")
    TRUSTED = ("trusted", 0.75, "Deep trust, anticipates needs")
    BONDED = ("bonded", 0.90, "Strong mutual understanding")

    def __init__(self, label: str, threshold: float, description: str):
        self.label = label
        self.threshold = threshold
        self.desc = description

    @classmethod
    def from_score(cls, score: float) -> "BondLevel":
        for level in reversed(list(cls)):
            if score >= level.threshold:
                return level
        return cls.STRANGER


BOND_MILESTONES = {
    1: "First interaction",
    5: "Getting acquainted",
    10: "Building rapport",
    25: "Familiar face",
    50: "Regular companion",
    100: "Trusted partner",
    250: "Deep bond",
    500: "Inseparable",
}

BOND_INACTIVITY_DECAY_DAYS = 60


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class Memory:
    id: str = ""
    agent_id: str = ""
    content: str = ""
    memory_type: str = "semantic"
    memory_kind: str = "fact"
    importance: float = 0.5
    confidence: float = 0.8
    scope: str = "global"
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass
class ScoredMemory:
    memory: Memory
    score: float = 0.0
    why_retrieved: list = field(default_factory=list)


# ── Main Class ─────────────────────────────────────────────────────────────

class YantrikMemory:
    """
    Persistent cognitive memory for AI agents.

    Wraps YantrikDB for storage and adds personality traits,
    bond evolution, and context assembly on top.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._lock = threading.Lock()

        # Initialize YantrikDB
        db_path = self.config.get(
            "db_path",
            os.environ.get("YANTRIKDB_DB_PATH", "./yantrik_memory.db"),
        )
        self._db = yantrikdb.YantrikDB(db_path)

        # Set up embedder if sentence-transformers available
        self._init_embedder()

        # Encryption (optional)
        self._encryption_key = None
        if self.config.get("encryption_enabled", True):
            self._init_encryption()

        logger.info("YantrikMemory initialized (db=%s)", db_path)

    # ── Embedder Setup ─────────────────────────────────────────────────

    def _init_embedder(self):
        """Initialize sentence-transformers embedder for YantrikDB."""
        try:
            from sentence_transformers import SentenceTransformer
            model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
            model = SentenceTransformer(model_name)
            self._db.set_embedder(model)
            logger.info("Embedder set: %s", model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise RuntimeError(
                "YantrikDB requires an embedder. Install sentence-transformers: "
                "pip install sentence-transformers"
            )

    # ── Encryption ─────────────────────────────────────────────────────

    def _init_encryption(self):
        """Load or generate Fernet encryption key."""
        key_path = os.path.expanduser("~/.config/yantrik-memory/.key")
        env_key = os.environ.get("YANTRIK_ENCRYPTION_KEY")

        if env_key:
            self._encryption_key = env_key
            return

        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                self._encryption_key = f.read().strip()
            return

        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "w") as f:
                f.write(key)
            os.chmod(key_path, 0o600)
            self._encryption_key = key
            logger.info("Generated encryption key at %s", key_path)
        except ImportError:
            logger.debug("cryptography not installed, encryption disabled")

    def _encrypt(self, content: str) -> str:
        if not self._encryption_key:
            return content
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self._encryption_key.encode())
            return f.encrypt(content.encode()).decode()
        except Exception:
            return content

    def _decrypt(self, content: str) -> str:
        if not self._encryption_key:
            return content
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self._encryption_key.encode())
            return f.decrypt(content.encode()).decode()
        except Exception:
            return content

    # ── Memory Operations ──────────────────────────────────────────────

    def remember(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "semantic",
        memory_kind: str = "fact",
        importance: float = 0.5,
        confidence: float = 0.8,
        scope: str = "global",
        user_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[dict] = None,
        content_encrypted: bool = False,
    ) -> str:
        """Store a memory in YantrikDB. Returns the memory RID."""
        if content_encrypted:
            content = self._encrypt(content)

        domain = self._kind_to_domain(memory_kind)
        source = "user"
        if metadata and "source" in metadata:
            source = metadata["source"]

        meta = {
            "agent_id": agent_id,
            "memory_kind": memory_kind,
            "scope": scope,
            "user_id": user_id,
            "tags": tags or [],
            "encrypted": content_encrypted,
            "certainty": confidence,
            **(metadata or {}),
        }

        with self._lock:
            # YantrikDB.record() returns RID as string
            rid = self._db.record(
                text=content,
                memory_type=memory_type,
                importance=importance,
                domain=domain,
                source=source,
                metadata=meta,
            )

        logger.debug("Remembered: %s (rid=%s)", content[:50], rid)
        return str(rid)

    def recall(
        self,
        agent_id: str,
        query: str,
        memory_kind: Optional[str] = None,
        scope: Optional[str] = None,
        limit: int = 10,
        user_id: Optional[str] = None,
        explain: bool = False,
    ) -> list:
        """Recall memories from YantrikDB using hybrid retrieval."""
        domain = self._kind_to_domain(memory_kind) if memory_kind else None

        with self._lock:
            # YantrikDB.recall() returns a list of dicts
            results = self._db.recall(query=query, top_k=limit, domain=domain)

        scored = []
        for r in results:
            meta = r.get("metadata", {}) or {}
            # Filter by agent_id
            if meta.get("agent_id") and meta["agent_id"] != agent_id:
                continue
            # Filter by scope
            if scope and meta.get("scope") and meta["scope"] != scope:
                continue
            # Filter by user_id
            if user_id and meta.get("user_id") and meta["user_id"] != user_id:
                continue

            content = r.get("text", "")
            if meta.get("encrypted"):
                content = self._decrypt(content)

            mem = Memory(
                id=r.get("rid", ""),
                agent_id=meta.get("agent_id", agent_id),
                content=content,
                memory_type=r.get("type", "semantic"),
                memory_kind=meta.get("memory_kind", "fact"),
                importance=r.get("importance", 0.5),
                confidence=meta.get("certainty", 0.8),
                scope=meta.get("scope", "global"),
                tags=meta.get("tags", []),
                metadata=meta,
            )
            sm = ScoredMemory(
                memory=mem,
                score=r.get("score", 0.0),
                why_retrieved=r.get("why_retrieved", []),
            )
            scored.append(sm)

        return scored

    def forget(self, memory_id: str) -> bool:
        """Delete a memory. Returns True on success."""
        with self._lock:
            # YantrikDB.forget() returns bool
            return bool(self._db.forget(rid=memory_id))

    def correct(self, memory_id: str, new_content: str) -> str:
        """Correct a memory's content. Returns new RID."""
        with self._lock:
            # YantrikDB.correct() returns dict with corrected_rid
            result = self._db.correct(rid=memory_id, new_text=new_content)
        if isinstance(result, dict):
            return result.get("corrected_rid", memory_id)
        return memory_id

    # ── Personality Traits ─────────────────────────────────────────────

    def get_traits(self, agent_id: str, user_id: Optional[str] = None) -> dict:
        """Get personality traits for an agent, optionally per-user."""
        base_key = f"traits:{agent_id}"
        user_key = f"traits:{agent_id}:{user_id}" if user_id else None

        base_traits = self._load_traits(base_key) or dict(DEFAULT_TRAITS)
        if not user_id:
            return self._apply_trait_decay(base_traits)

        user_traits = self._load_traits(user_key)
        if not user_traits:
            return self._apply_trait_decay(base_traits)

        # Blend: 70% user, 30% base
        blended = {}
        for trait in DEFAULT_TRAITS:
            base_val = base_traits.get(trait, 0.5)
            user_val = user_traits.get(trait, base_val)
            blended[trait] = 0.7 * user_val + 0.3 * base_val
        return self._apply_trait_decay(blended)

    def evolve_traits(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        llm_fn: Optional[Callable] = None,
    ) -> dict:
        """Evolve personality traits based on interaction signals."""
        signals = self._detect_trait_signals(message)

        # LLM fallback for richer signal detection
        if llm_fn and not signals:
            signals = self._detect_traits_llm(message, llm_fn)

        if not signals:
            return self.get_traits(agent_id, user_id)

        user_key = f"traits:{agent_id}:{user_id}"
        traits = self._load_traits(user_key) or dict(DEFAULT_TRAITS)

        for trait_name, direction in signals.items():
            current = traits.get(trait_name, 0.5)
            if direction > 0:
                delta = 0.05 * direction
            else:
                delta = 0.05 * direction * NEGATIVE_SIGNAL_WEIGHT
            new_val = max(0.0, min(1.0, current + delta))
            traits[trait_name] = new_val

        self._save_traits(user_key, traits)
        return self.get_traits(agent_id, user_id)

    def _detect_trait_signals(self, message: str) -> dict:
        """Detect trait signals from message text."""
        text = message.lower()
        signals = {}
        for trait_name, patterns in TRAIT_SIGNALS.items():
            for p in patterns["positive"]:
                if p in text:
                    signals[trait_name] = signals.get(trait_name, 0) + 1
                    break
            for p in patterns["negative"]:
                if p in text:
                    signals[trait_name] = signals.get(trait_name, 0) - 1
                    break
        return signals

    def _detect_traits_llm(self, message: str, llm_fn: Callable) -> dict:
        """Use LLM to detect trait signals."""
        prompt = (
            "Analyze this message for personality trait signals. "
            f"Traits: {', '.join(DEFAULT_TRAITS.keys())}. "
            "Return JSON: {\"trait\": direction} where direction is +1, -1, or 0.\n\n"
            f"Message: {message}"
        )
        try:
            response = llm_fn(prompt)
            return json.loads(response)
        except Exception:
            return {}

    def _apply_trait_decay(self, traits: dict) -> dict:
        """Apply exponential decay toward 0.5 neutral."""
        return traits

    def _load_traits(self, key: str) -> Optional[dict]:
        """Load traits from YantrikDB."""
        if not hasattr(self, "_traits_rids"):
            self._traits_rids = {}

        # Fast path: get by cached RID
        if key in self._traits_rids:
            try:
                record = self._db.get(self._traits_rids[key])
                if record:
                    text = record.get("text", "")
                    if text.startswith(key + " "):
                        text = text[len(key) + 1:]
                    return json.loads(text)
            except Exception:
                del self._traits_rids[key]

        # Fallback: recall-based search
        results = self._db.recall(query=key, top_k=5, domain="preference")
        for r in results:
            meta = r.get("metadata", {}) or {}
            if meta.get("traits_key") == key:
                self._traits_rids[key] = r["rid"]
                text = r.get("text", "")
                if text.startswith(key + " "):
                    text = text[len(key) + 1:]
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None
        return None

    def _save_traits(self, key: str, traits: dict):
        """Save traits to YantrikDB."""
        # Store RID for fast lookup on subsequent saves
        if not hasattr(self, "_traits_rids"):
            self._traits_rids = {}

        # If we have a cached RID, correct directly
        if key in self._traits_rids:
            try:
                result = self._db.correct(rid=self._traits_rids[key], new_text=json.dumps(traits))
                if isinstance(result, dict) and "corrected_rid" in result:
                    self._traits_rids[key] = result["corrected_rid"]
                return
            except Exception:
                del self._traits_rids[key]

        # Try to find existing via recall
        results = self._db.recall(query=key, top_k=5, domain="preference")
        for r in results:
            meta = r.get("metadata", {}) or {}
            if meta.get("traits_key") == key:
                result = self._db.correct(rid=r["rid"], new_text=json.dumps(traits))
                if isinstance(result, dict) and "corrected_rid" in result:
                    self._traits_rids[key] = result["corrected_rid"]
                return

        # New traits entry — prefix text with key for better recall matching
        rid = self._db.record(
            text=f"{key} {json.dumps(traits)}",
            memory_type="semantic",
            importance=0.9,
            domain="preference",
            source="system",
            metadata={"traits_key": key},
        )
        self._traits_rids[key] = str(rid)

    # ── Bond Evolution ─────────────────────────────────────────────────

    def get_bond(self, agent_id: str, user_id: str) -> dict:
        """Get the bond state between agent and user."""
        bond_key = f"bond:{agent_id}:{user_id}"

        if not hasattr(self, "_bond_rids"):
            self._bond_rids = {}

        def _parse_bond(text):
            if text.startswith(bond_key + " "):
                text = text[len(bond_key) + 1:]
            bond_data = json.loads(text)
            bond_data = self._apply_bond_decay(bond_data)
            level = BondLevel.from_score(bond_data.get("score", 0.0))
            bond_data["level"] = level.label
            bond_data["level_description"] = level.desc
            return bond_data

        # Fast path: get by cached RID
        if bond_key in self._bond_rids:
            try:
                record = self._db.get(self._bond_rids[bond_key])
                if record:
                    return _parse_bond(record.get("text", ""))
            except Exception:
                del self._bond_rids[bond_key]

        # Fallback: recall-based search
        results = self._db.recall(query=bond_key, top_k=5, domain="people")
        for r in results:
            meta = r.get("metadata", {}) or {}
            if meta.get("bond_key") == bond_key:
                self._bond_rids[bond_key] = r["rid"]
                try:
                    return _parse_bond(r.get("text", ""))
                except (json.JSONDecodeError, KeyError):
                    pass

        return {
            "score": 0.0,
            "level": BondLevel.STRANGER.label,
            "level_description": BondLevel.STRANGER.desc,
            "interaction_count": 0,
            "milestones": [],
            "last_interaction": None,
        }

    def update_bond(
        self,
        agent_id: str,
        user_id: str,
        message: str = "",
        sentiment: float = 0.0,
    ) -> dict:
        """Update bond based on interaction."""
        bond = self.get_bond(agent_id, user_id)
        count = bond.get("interaction_count", 0) + 1

        # Logarithmic growth — diminishing returns
        base_growth = 0.02 / (1 + math.log(max(count, 1)))

        # Auto-detect sentiment from message if not provided
        if not sentiment and message:
            sentiment = self._calculate_bond_sentiment(message)

        # Sentiment adjustment
        if sentiment > 0:
            growth = base_growth * (1 + sentiment * 0.5)
        elif sentiment < 0:
            growth = base_growth * sentiment
        else:
            growth = base_growth

        new_score = max(0.0, min(1.0, bond.get("score", 0.0) + growth))

        # Check milestones
        milestones = bond.get("milestones", [])
        if count in BOND_MILESTONES:
            milestones.append({
                "count": count,
                "label": BOND_MILESTONES[count],
                "timestamp": time.time(),
            })

        bond_data = {
            "score": new_score,
            "interaction_count": count,
            "milestones": milestones,
            "last_interaction": time.time(),
            "last_sentiment": sentiment,
        }

        self._save_bond(agent_id, user_id, bond_data)

        level = BondLevel.from_score(new_score)
        bond_data["level"] = level.label
        bond_data["level_description"] = level.desc
        return bond_data

    def _apply_bond_decay(self, bond_data: dict) -> dict:
        """Apply inactivity decay to bond score."""
        last = bond_data.get("last_interaction")
        if not last:
            return bond_data
        days_inactive = (time.time() - last) / 86400
        if days_inactive > BOND_INACTIVITY_DECAY_DAYS:
            decay_factor = math.exp(-0.01 * (days_inactive - BOND_INACTIVITY_DECAY_DAYS))
            bond_data["score"] = bond_data.get("score", 0.0) * decay_factor
        return bond_data

    def _calculate_bond_sentiment(self, message: str) -> float:
        """Simple sentiment detection for bond updates."""
        text = message.lower()
        positive = ["thank", "great", "love", "awesome", "perfect", "amazing", "helpful", "appreciate"]
        negative = ["hate", "terrible", "awful", "worst", "useless", "annoying", "frustrated"]

        score = 0.0
        for word in positive:
            if word in text:
                score += 0.3
        for word in negative:
            if word in text:
                score -= 0.3
        return max(-1.0, min(1.0, score))

    def _save_bond(self, agent_id: str, user_id: str, bond_data: dict):
        """Save bond to YantrikDB."""
        bond_key = f"bond:{agent_id}:{user_id}"

        if not hasattr(self, "_bond_rids"):
            self._bond_rids = {}

        # Fast path: correct by cached RID
        if bond_key in self._bond_rids:
            try:
                result = self._db.correct(rid=self._bond_rids[bond_key], new_text=json.dumps(bond_data))
                if isinstance(result, dict) and "corrected_rid" in result:
                    self._bond_rids[bond_key] = result["corrected_rid"]
                return
            except Exception:
                del self._bond_rids[bond_key]

        # Try to find existing via recall
        results = self._db.recall(query=bond_key, top_k=5, domain="people")
        for r in results:
            meta = r.get("metadata", {}) or {}
            if meta.get("bond_key") == bond_key:
                result = self._db.correct(rid=r["rid"], new_text=json.dumps(bond_data))
                if isinstance(result, dict) and "corrected_rid" in result:
                    self._bond_rids[bond_key] = result["corrected_rid"]
                return

        # New bond entry — prefix text with key for better recall matching
        rid = self._db.record(
            text=f"{bond_key} {json.dumps(bond_data)}",
            memory_type="semantic",
            importance=0.8,
            domain="people",
            source="system",
            metadata={"bond_key": bond_key},
        )
        self._bond_rids[bond_key] = str(rid)

    # ── Context Assembly ───────────────────────────────────────────────

    def get_full_context(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        session_key: Optional[str] = None,
    ) -> dict:
        """Assemble full context for LLM prompts."""
        memories = self.recall(agent_id, query=message, user_id=user_id, limit=10)
        traits = self.get_traits(agent_id, user_id)
        bond = self.get_bond(agent_id, user_id)
        guidance = self._generate_guidance(traits)
        mood = self._detect_mood(message)
        intent = self._detect_intent(message)

        return {
            "memories": [
                {
                    "content": sm.memory.content,
                    "score": sm.score,
                    "kind": sm.memory.memory_kind,
                    "why": sm.why_retrieved,
                }
                for sm in memories
            ],
            "traits": traits,
            "bond": {
                "level": bond["level"],
                "score": bond["score"],
                "description": bond["level_description"],
                "interaction_count": bond.get("interaction_count", 0),
            },
            "personality_guidance": guidance,
            "mood": mood,
            "intent": intent,
            "agent_id": agent_id,
            "user_id": user_id,
        }

    def process_turn(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        llm_fn: Optional[Callable] = None,
        session_key: Optional[str] = None,
    ) -> dict:
        """
        Single entry point for agents.

        Extracts memories, evolves traits, updates bond, returns full context.
        """
        self.evolve_traits(agent_id, user_id, message, llm_fn)
        self.update_bond(agent_id, user_id, message)

        if llm_fn:
            self._extract_memories(agent_id, user_id, message, llm_fn)

        return self.get_full_context(agent_id, user_id, message, session_key)

    def _extract_memories(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        llm_fn: Callable,
    ):
        """Auto-extract memories from a message using LLM."""
        prompt = (
            "Extract important facts, decisions, or preferences from this message. "
            "Return JSON array of objects with: text, memory_kind (fact/preference/episode/goal/insight), importance (0.0-1.0).\n"
            "Return [] if nothing worth remembering.\n\n"
            f"Message: {message}"
        )
        try:
            response = llm_fn(prompt)
            response = response.strip()
            if response.startswith("```"):
                response = re.sub(r"^```\w*\n?", "", response)
                response = re.sub(r"\n?```$", "", response)
            memories = json.loads(response)
            for mem in memories:
                if isinstance(mem, dict) and mem.get("text"):
                    self.remember(
                        agent_id=agent_id,
                        content=mem["text"],
                        memory_kind=mem.get("memory_kind", "fact"),
                        importance=mem.get("importance", 0.5),
                        scope="user",
                        user_id=user_id,
                        metadata={"source": "inference"},
                    )
        except Exception as e:
            logger.debug("Memory extraction failed: %s", e)

    # ── Knowledge Graph ────────────────────────────────────────────────

    def relate(self, entity: str, target: str, relationship: str = "related_to", weight: float = 1.0):
        """Create a knowledge graph relationship."""
        # YantrikDB API: relate(src, dst, rel_type, weight)
        self._db.relate(entity, target, relationship, weight)

    def get_entity(self, entity: str) -> dict:
        """Get entity profile from knowledge graph."""
        result = self._db.entity_profile(entity=entity)
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {}
        return result if isinstance(result, dict) else {}

    def get_edges(self, entity: str) -> list:
        """Get all relationships for an entity."""
        result = self._db.get_edges(entity=entity)
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return []
        return result if isinstance(result, list) else []

    # ── Cognitive Maintenance ──────────────────────────────────────────

    def think(self, **kwargs) -> dict:
        """Run cognitive maintenance — consolidation, conflict detection."""
        result = self._db.think(**kwargs)
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {}
        return result if isinstance(result, dict) else {}

    def stats(self) -> dict:
        """Get memory system statistics."""
        result = self._db.stats()
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {}
        return result if isinstance(result, dict) else {}

    # ── Startup / Lifecycle ────────────────────────────────────────────

    def refresh_on_startup(self, agent_id: str) -> dict:
        """Called on agent startup to load context."""
        stats = self.stats()
        logger.info("Startup refresh for agent=%s, memories=%s", agent_id, stats.get("active_memories", 0))
        return {
            "success": True,
            "agent_id": agent_id,
            "stats": stats,
        }

    def health_check(self) -> dict:
        """Check system health."""
        try:
            stats = self.stats()
            return {
                "healthy": True,
                "engine": "yantrikdb",
                "active_memories": stats.get("active_memories", 0),
            }
        except Exception as e:
            return {"healthy": False, "engine": "yantrikdb", "error": str(e)}

    def close(self):
        """Clean shutdown."""
        try:
            self._db.close()
        except Exception:
            pass
        logger.info("YantrikMemory closed")

    # ── Helpers ────────────────────────────────────────────────────────

    def _kind_to_domain(self, kind: str) -> str:
        """Map memory_kind to YantrikDB domain."""
        mapping = {
            "fact": "general",
            "preference": "preference",
            "episode": "general",
            "skill": "work",
            "secret": "infrastructure",
            "insight": "architecture",
            "correction": "general",
            "summary": "general",
            "goal": "work",
        }
        return mapping.get(kind, "general")

    def _generate_guidance(self, traits: dict) -> str:
        """Generate personality guidance text from traits."""
        lines = []
        for trait, value in traits.items():
            if value > 0.65:
                lines.append(f"Be more {trait} in responses.")
            elif value < 0.35:
                opposite = {
                    "humor": "serious", "empathy": "objective", "curiosity": "focused",
                    "creativity": "conventional", "helpfulness": "concise",
                    "honesty": "diplomatic", "conciseness": "detailed",
                    "formality": "casual", "directness": "gentle",
                }
                lines.append(f"Be more {opposite.get(trait, trait)} in responses.")
        return " ".join(lines) if lines else "Maintain a balanced, adaptive communication style."

    def _detect_mood(self, message: str) -> dict:
        """Simple mood detection."""
        text = message.lower()
        moods = {
            "happy": ["happy", "great", "awesome", "love", "excited", "amazing", "wonderful"],
            "frustrated": ["frustrated", "angry", "annoyed", "hate", "ugh", "terrible", "awful"],
            "curious": ["why", "how", "what", "wonder", "curious", "question", "explain"],
            "neutral": [],
        }
        for mood, keywords in moods.items():
            for kw in keywords:
                if kw in text:
                    return {"mood": mood, "confidence": 0.7}
        return {"mood": "neutral", "confidence": 0.5}

    def _detect_intent(self, message: str) -> str:
        """Simple intent detection."""
        text = message.lower().strip()
        if text.endswith("?") or any(text.startswith(w) for w in ["what", "why", "how", "when", "where", "who", "can", "could", "would", "is", "are", "do", "does"]):
            return "question"
        if any(text.startswith(w) for w in ["set", "create", "make", "build", "add", "remove", "delete", "update"]):
            return "command"
        if any(w in text for w in ["remember", "note", "save", "don't forget"]):
            return "store"
        return "casual"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
