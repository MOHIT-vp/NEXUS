"""
Unit tests for Per-Agent API Key, Provider, and Model Routing.

Verifies:
1. Independent API key resolution per agent.
2. Alias matching (e.g. RESUME_API_KEY, LLM_API_KEY_RESUME).
3. Multi-key pool auto-distribution (LLM_API_KEYS).
4. Per-agent provider and model overrides.
5. Graceful fallback to global LLM_API_KEY.
6. Validation checks for dummy/empty keys.
7. Auto-detection of caller agent from stack.
"""
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.agents.llm import (
    get_agent_credentials,
    is_llm_enabled,
    _get_active_key,
    _agent_key_counters,
    get_chat_model,
)

ENV_KEYS_TO_CLEAR = [
    "LLM_API_KEY", "LLM_API_KEYS", "LLM_PROVIDER", "LLM_MODEL",
    "RESUME_AGENT_API_KEY", "RESUME_API_KEY", "LLM_API_KEY_RESUME", "LLM_API_KEY_RESUME_AGENT",
    "RESUME_AGENT_PROVIDER", "RESUME_AGENT_MODEL",
    "CODING_ANALYTICS_AGENT_API_KEY", "CODING_ANALYTICS_API_KEY", "CODING_API_KEY",
    "CODING_ANALYTICS_AGENT_PROVIDER", "CODING_ANALYTICS_AGENT_MODEL",
    "SKILL_GAP_AGENT_API_KEY", "SKILL_GAP_API_KEY", "LLM_API_KEY_SKILL_GAP",
    "SKILL_GAP_AGENT_PROVIDER", "SKILL_GAP_AGENT_MODEL",
    "JOB_MATCHING_AGENT_API_KEY", "JOB_MATCHING_API_KEY", "LLM_API_KEY_JOB_MATCHING",
    "JOB_MATCHING_AGENT_PROVIDER", "JOB_MATCHING_AGENT_MODEL",
    "INTERVIEW_AGENT_API_KEY", "INTERVIEW_API_KEY", "LLM_API_KEY_INTERVIEW",
    "INTERVIEW_AGENT_PROVIDER", "INTERVIEW_AGENT_MODEL",
    "COORDINATOR_AGENT_API_KEY", "COORDINATOR_API_KEY", "LLM_API_KEY_COORDINATOR",
    "COORDINATOR_AGENT_PROVIDER", "COORDINATOR_AGENT_MODEL",
    "MOCK_INTERVIEW_API_KEY", "MOCK_INTERVIEW_PROVIDER", "MOCK_INTERVIEW_MODEL",
    "MOCK_PRACTICE_API_KEY", "MOCK_PRACTICE_PROVIDER", "MOCK_PRACTICE_MODEL",
    "CHAT_AGENT_API_KEY", "CHAT_AGENT_PROVIDER", "CHAT_AGENT_MODEL",
]


def make_test_settings(**kwargs):
    """Instantiate isolated Settings ignoring any .env on disk."""
    return Settings(_env_file=None, **kwargs)


class TestAgentAPIKeys(unittest.TestCase):

    def setUp(self):
        self._saved_env = {}
        for k in ENV_KEYS_TO_CLEAR:
            if k in os.environ:
                self._saved_env[k] = os.environ.pop(k)

    def tearDown(self):
        for k in ENV_KEYS_TO_CLEAR:
            os.environ.pop(k, None)
        for k, v in self._saved_env.items():
            os.environ[k] = v

    def test_dedicated_agent_api_keys(self):
        """Test that distinct agents receive their explicitly configured API keys."""
        s = make_test_settings(
            LLM_PROVIDER="groq",
            LLM_API_KEY="global_key",
            RESUME_AGENT_API_KEY="resume_key_123",
            CODING_ANALYTICS_AGENT_API_KEY="coding_key_456",
            SKILL_GAP_AGENT_API_KEY="skill_key_789",
            JOB_MATCHING_AGENT_API_KEY="matching_key_101",
            INTERVIEW_AGENT_API_KEY="interview_key_202",
            COORDINATOR_AGENT_API_KEY="coordinator_key_303",
            MOCK_INTERVIEW_API_KEY="mock_interview_key_404",
            MOCK_PRACTICE_API_KEY="mock_practice_key_505",
            CHAT_AGENT_API_KEY="chat_key_606",
        )
        self.assertEqual(s.get_agent_llm_config("resume_agent")["api_key"], "resume_key_123")
        self.assertEqual(s.get_agent_llm_config("coding_analytics_agent")["api_key"], "coding_key_456")
        self.assertEqual(s.get_agent_llm_config("skill_gap_agent")["api_key"], "skill_key_789")
        self.assertEqual(s.get_agent_llm_config("job_matching_agent")["api_key"], "matching_key_101")
        self.assertEqual(s.get_agent_llm_config("interview_agent")["api_key"], "interview_key_202")
        self.assertEqual(s.get_agent_llm_config("coordinator")["api_key"], "coordinator_key_303")
        self.assertEqual(s.get_agent_llm_config("mock_interview")["api_key"], "mock_interview_key_404")
        self.assertEqual(s.get_agent_llm_config("mock_practice")["api_key"], "mock_practice_key_505")
        self.assertEqual(s.get_agent_llm_config("chat")["api_key"], "chat_key_606")

    def test_alias_matching(self):
        """Test that short aliases like RESUME_API_KEY work through environment variables."""
        with patch.dict(os.environ, {"RESUME_API_KEY": "alias_resume_key"}):
            s = make_test_settings(LLM_API_KEY="global_key")
            cfg = s.get_agent_llm_config("resume_agent")
            self.assertEqual(cfg["api_key"], "alias_resume_key")

        with patch.dict(os.environ, {"LLM_API_KEY_INTERVIEW": "alias_interview_key"}):
            s = make_test_settings(LLM_API_KEY="global_key")
            cfg = s.get_agent_llm_config("interview_agent")
            self.assertEqual(cfg["api_key"], "alias_interview_key")

        with patch.dict(os.environ, {"CODING_API_KEY": "alias_coding_key"}):
            s = make_test_settings(LLM_API_KEY="global_key")
            cfg = s.get_agent_llm_config("coding_analytics_agent")
            self.assertEqual(cfg["api_key"], "alias_coding_key")

    def test_multi_key_pool_distribution(self):
        """Test that comma-separated LLM_API_KEYS pool distributes distinct keys to agents."""
        s = make_test_settings(
            LLM_API_KEY="",
            LLM_API_KEYS="pool_key_0, pool_key_1, pool_key_2, pool_key_3, pool_key_4, pool_key_5",
        )
        keys = s.get_pool_keys()
        self.assertEqual(len(keys), 6)
        self.assertEqual(keys[0], "pool_key_0")
        self.assertEqual(keys[5], "pool_key_5")

        # Check that different agents get distinct keys from the pool
        k_resume = s.get_agent_llm_config("resume_agent")["api_key"]
        k_coding = s.get_agent_llm_config("coding_analytics_agent")["api_key"]
        k_skill = s.get_agent_llm_config("skill_gap_agent")["api_key"]
        k_job = s.get_agent_llm_config("job_matching_agent")["api_key"]
        k_interview = s.get_agent_llm_config("interview_agent")["api_key"]
        k_coord = s.get_agent_llm_config("coordinator")["api_key"]

        self.assertEqual(k_resume, "pool_key_0")
        self.assertEqual(k_coding, "pool_key_1")
        self.assertEqual(k_skill, "pool_key_2")
        self.assertEqual(k_job, "pool_key_3")
        self.assertEqual(k_interview, "pool_key_4")
        self.assertEqual(k_coord, "pool_key_5")
        self.assertEqual(len({k_resume, k_coding, k_skill, k_job, k_interview, k_coord}), 6)

    def test_per_agent_provider_and_model_override(self):
        """Test that individual agents can override their LLM provider and model."""
        s = make_test_settings(
            LLM_PROVIDER="groq",
            LLM_MODEL="llama-3.3-70b-versatile",
            LLM_API_KEY="groq_key",
            RESUME_AGENT_PROVIDER="google",
            RESUME_AGENT_MODEL="gemini-2.0-flash",
            RESUME_AGENT_API_KEY="google_key",
        )
        resume_cfg = s.get_agent_llm_config("resume_agent")
        self.assertEqual(resume_cfg["provider"], "google")
        self.assertEqual(resume_cfg["model"], "gemini-2.0-flash")
        self.assertEqual(resume_cfg["api_key"], "google_key")

        # Other agent inherits defaults
        coding_cfg = s.get_agent_llm_config("coding_analytics_agent")
        self.assertEqual(coding_cfg["provider"], "groq")
        self.assertEqual(coding_cfg["model"], "llama-3.3-70b-versatile")
        self.assertEqual(coding_cfg["api_key"], "groq_key")

    def test_global_fallback(self):
        """When an agent has no specific key and no pool, fallback to global key."""
        s = make_test_settings(
            LLM_PROVIDER="groq",
            LLM_MODEL="llama-3.3-70b-versatile",
            LLM_API_KEY="fallback_global_key",
        )
        cfg = s.get_agent_llm_config("interview_agent")
        self.assertEqual(cfg["api_key"], "fallback_global_key")
        self.assertEqual(cfg["provider"], "groq")
        self.assertEqual(cfg["model"], "llama-3.3-70b-versatile")

    def test_dummy_and_empty_keys_rejected(self):
        """Ensure dummy or empty keys return False for validity."""
        self.assertFalse(Settings._is_valid_key(""))
        self.assertFalse(Settings._is_valid_key("dummy"))
        self.assertFalse(Settings._is_valid_key("your-api-key-here"))
        self.assertFalse(Settings._is_valid_key(None))
        self.assertTrue(Settings._is_valid_key("gsk_valid_key_12345"))

    def test_llm_enabled_property(self):
        """llm_enabled should be True if any agent has a valid key."""
        # Case A: Global key set
        s1 = make_test_settings(LLM_API_KEY="real_key")
        self.assertTrue(s1.llm_enabled)

        # Case B: Global key empty, but resume agent has a key
        s2 = make_test_settings(LLM_API_KEY="", RESUME_AGENT_API_KEY="agent_key_abc")
        self.assertTrue(s2.llm_enabled)

        # Case C: All empty or dummy
        s3 = make_test_settings(LLM_API_KEY="dummy")
        self.assertFalse(s3.llm_enabled)

    def test_multi_key_rotation_per_agent(self):
        """Test rotation when an agent is given comma-separated keys."""
        _agent_key_counters.clear()
        keys_str = "key_alpha, key_beta, key_gamma"
        k1 = _get_active_key("test_agent", keys_str)
        k2 = _get_active_key("test_agent", keys_str)
        k3 = _get_active_key("test_agent", keys_str)
        k4 = _get_active_key("test_agent", keys_str)

        self.assertEqual(k1, "key_alpha")
        self.assertEqual(k2, "key_beta")
        self.assertEqual(k3, "key_gamma")
        self.assertEqual(k4, "key_alpha")  # wraps around

    def test_caller_agent_detection(self):
        """Test that caller function names can be auto-detected when agent_name is omitted."""
        def resume_agent_caller():
            return get_agent_credentials()

        def interview_agent_caller():
            return get_agent_credentials()

        res = resume_agent_caller()
        self.assertEqual(res["agent_name"], "resume_agent")

        inter = interview_agent_caller()
        self.assertEqual(inter["agent_name"], "interview_agent")

    def test_get_chat_model_returns_none_when_unconfigured(self):
        """When an agent has no valid key, get_chat_model safely returns None (no crash)."""
        model = get_chat_model(agent_name="unconfigured_agent", api_key="")
        self.assertIsNone(model)


if __name__ == "__main__":
    unittest.main()
