"""Tests for Yantrik Memory core module."""

import os
import sys
import json
import tempfile
import unittest

# Ensure yantrik_memory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestYantrikMemory(unittest.TestCase):
    """Core memory operations."""

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        os.environ["YANTRIKDB_DB_PATH"] = self.db_path
        from yantrik_memory.core import YantrikMemory
        self.mem = YantrikMemory({"db_path": self.db_path, "encryption_enabled": False})

    def tearDown(self):
        self.mem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_remember_and_recall(self):
        rid = self.mem.remember("agent1", "Python is a programming language", memory_kind="fact")
        self.assertTrue(rid)
        results = self.mem.recall("agent1", "programming language")
        self.assertTrue(len(results) > 0)
        self.assertIn("Python", results[0].memory.content)

    def test_forget(self):
        rid = self.mem.remember("agent1", "temporary memory", memory_kind="fact")
        result = self.mem.forget(rid)
        self.assertTrue(result)

    def test_correct(self):
        rid = self.mem.remember("agent1", "Python 3.11", memory_kind="fact")
        new_rid = self.mem.correct(rid, "Python 3.12")
        self.assertTrue(new_rid)

    def test_remember_with_scope(self):
        self.mem.remember("agent1", "global fact", scope="global")
        self.mem.remember("agent1", "user-specific fact", scope="user", user_id="user1")
        results = self.mem.recall("agent1", "fact", scope="user", user_id="user1")
        for r in results:
            if r.memory.scope == "user":
                self.assertEqual(r.memory.metadata.get("user_id"), "user1")

    def test_memory_kinds(self):
        from yantrik_memory.core import VALID_MEMORY_KINDS
        for kind in ["fact", "preference", "episode", "goal"]:
            self.assertIn(kind, VALID_MEMORY_KINDS)

    def test_health_check(self):
        health = self.mem.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["engine"], "yantrikdb")

    def test_stats(self):
        self.mem.remember("agent1", "test memory")
        stats = self.mem.stats()
        self.assertIsInstance(stats, dict)

    def test_refresh_on_startup(self):
        result = self.mem.refresh_on_startup("agent1")
        self.assertTrue(result["success"])
        self.assertEqual(result["agent_id"], "agent1")


class TestTraits(unittest.TestCase):
    """Personality trait system."""

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        from yantrik_memory.core import YantrikMemory
        self.mem = YantrikMemory({"db_path": self.db_path, "encryption_enabled": False})

    def tearDown(self):
        self.mem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_default_traits(self):
        traits = self.mem.get_traits("agent1")
        # Should return defaults when no data exists
        self.assertIsInstance(traits, dict)

    def test_evolve_traits_positive(self):
        self.mem.evolve_traits("agent1", "user1", "haha that's so funny!")
        traits = self.mem.get_traits("agent1", "user1")
        # Humor should have increased
        if traits and "humor" in traits:
            self.assertGreater(traits["humor"], 0.5)

    def test_evolve_traits_negative(self):
        self.mem.evolve_traits("agent1", "user1", "be serious, stop joking")
        traits = self.mem.get_traits("agent1", "user1")
        if traits and "humor" in traits:
            self.assertLess(traits["humor"], 0.5)

    def test_conciseness_signal(self):
        self.mem.evolve_traits("agent1", "user1", "keep it concise please")
        traits = self.mem.get_traits("agent1", "user1")
        if traits and "conciseness" in traits:
            self.assertGreater(traits["conciseness"], 0.5)

    def test_nine_traits_exist(self):
        from yantrik_memory.core import DEFAULT_TRAITS
        self.assertEqual(len(DEFAULT_TRAITS), 9)
        expected = {"humor", "empathy", "curiosity", "creativity", "helpfulness",
                    "honesty", "conciseness", "formality", "directness"}
        self.assertEqual(set(DEFAULT_TRAITS.keys()), expected)

    def test_per_user_traits(self):
        self.mem.evolve_traits("agent1", "user1", "haha funny!")
        self.mem.evolve_traits("agent1", "user2", "be serious please")
        t1 = self.mem.get_traits("agent1", "user1")
        t2 = self.mem.get_traits("agent1", "user2")
        # Different users should have different trait profiles
        if t1 and t2 and "humor" in t1 and "humor" in t2:
            self.assertNotEqual(t1["humor"], t2["humor"])


class TestBonds(unittest.TestCase):
    """Bond evolution system."""

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        from yantrik_memory.core import YantrikMemory
        self.mem = YantrikMemory({"db_path": self.db_path, "encryption_enabled": False})

    def tearDown(self):
        self.mem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_initial_bond(self):
        bond = self.mem.get_bond("agent1", "user1")
        self.assertEqual(bond["level"], "stranger")
        self.assertEqual(bond["score"], 0.0)
        self.assertEqual(bond["interaction_count"], 0)

    def test_bond_growth(self):
        self.mem.update_bond("agent1", "user1", "hello there!")
        bond = self.mem.get_bond("agent1", "user1")
        self.assertGreater(bond["score"], 0.0)
        self.assertEqual(bond["interaction_count"], 1)

    def test_bond_positive_sentiment(self):
        bond = self.mem.update_bond("agent1", "user1", "thank you so much, you're amazing!")
        self.assertGreater(bond["score"], 0.0)
        self.assertGreater(bond.get("last_sentiment", 0), 0)

    def test_bond_milestone(self):
        for i in range(5):
            bond = self.mem.update_bond("agent1", "user1", f"interaction {i+1}")
        # At minimum, the first milestone should be recorded
        milestones = bond.get("milestones", [])
        milestone_counts = [m["count"] for m in milestones]
        self.assertTrue(len(milestones) > 0, "Should have at least one milestone")

    def test_bond_levels(self):
        from yantrik_memory.core import BondLevel
        self.assertEqual(BondLevel.from_score(0.0).label, "stranger")
        self.assertEqual(BondLevel.from_score(0.2).label, "acquaintance")
        self.assertEqual(BondLevel.from_score(0.5).label, "familiar")
        self.assertEqual(BondLevel.from_score(0.6).label, "companion")
        self.assertEqual(BondLevel.from_score(0.8).label, "trusted")
        self.assertEqual(BondLevel.from_score(0.95).label, "bonded")


class TestContext(unittest.TestCase):
    """Context assembly."""

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        from yantrik_memory.core import YantrikMemory
        self.mem = YantrikMemory({"db_path": self.db_path, "encryption_enabled": False})

    def tearDown(self):
        self.mem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_get_full_context(self):
        self.mem.remember("agent1", "User likes Python", memory_kind="preference", user_id="user1")
        ctx = self.mem.get_full_context("agent1", "user1", "Tell me about Python")
        self.assertIn("memories", ctx)
        self.assertIn("traits", ctx)
        self.assertIn("bond", ctx)
        self.assertIn("personality_guidance", ctx)
        self.assertIn("mood", ctx)
        self.assertIn("intent", ctx)

    def test_process_turn(self):
        ctx = self.mem.process_turn("agent1", "user1", "This is really helpful, thank you!")
        self.assertIn("memories", ctx)
        self.assertIn("traits", ctx)
        self.assertIn("bond", ctx)
        # Bond should have been updated
        self.assertGreater(ctx["bond"]["score"], 0.0)

    def test_mood_detection(self):
        ctx = self.mem.get_full_context("agent1", "user1", "I'm so excited about this!")
        self.assertEqual(ctx["mood"]["mood"], "happy")

    def test_intent_detection(self):
        ctx = self.mem.get_full_context("agent1", "user1", "How does this work?")
        self.assertEqual(ctx["intent"], "question")

    def test_personality_guidance(self):
        # Set high humor trait
        self.mem.evolve_traits("agent1", "user1", "haha so funny lol hilarious")
        ctx = self.mem.get_full_context("agent1", "user1", "test")
        guidance = ctx.get("personality_guidance", "")
        self.assertIsInstance(guidance, str)


class TestKnowledgeGraph(unittest.TestCase):
    """Knowledge graph operations."""

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        from yantrik_memory.core import YantrikMemory
        self.mem = YantrikMemory({"db_path": self.db_path, "encryption_enabled": False})

    def tearDown(self):
        self.mem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_relate(self):
        self.mem.relate("Alice", "Backend Team", "manages")
        entity = self.mem.get_entity("Alice")
        self.assertIsInstance(entity, dict)


if __name__ == "__main__":
    unittest.main()
