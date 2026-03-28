"""Tests for LLM response caching."""

from pathlib import Path

from woograph.utils.cache import LLMCache


class TestLLMCache:
    def test_cache_miss_returns_none(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        result = cache.get("nonexistent", "key")
        assert result is None

    def test_put_then_get_returns_value(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        data = {"relationships": [{"subject": "A", "predicate": "related_to", "object": "B"}]}
        cache.put(data, "chunk1", "entities1")
        result = cache.get("chunk1", "entities1")
        assert result == data

    def test_different_keys_dont_collide(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        data1 = {"result": "first"}
        data2 = {"result": "second"}
        cache.put(data1, "key_a")
        cache.put(data2, "key_b")
        assert cache.get("key_a") == data1
        assert cache.get("key_b") == data2

    def test_cache_dir_created(self, tmp_path: Path):
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        LLMCache(cache_dir)
        assert cache_dir.exists()

    def test_overwrite_existing_entry(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        cache.put({"v": 1}, "key")
        cache.put({"v": 2}, "key")
        assert cache.get("key") == {"v": 2}

    def test_hash_is_deterministic(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        h1 = cache._hash_key("a", "b", "c")
        h2 = cache._hash_key("a", "b", "c")
        assert h1 == h2

    def test_hash_different_for_different_inputs(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        h1 = cache._hash_key("a", "b")
        h2 = cache._hash_key("a", "c")
        assert h1 != h2
