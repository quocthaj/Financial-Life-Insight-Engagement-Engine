import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class LLMClientError(RuntimeError):
    pass


@dataclass
class LLMResult:
    provider: str
    model_name: str
    prompt_version: str
    llm_used: bool
    purpose: str
    text: str
    parsed_json: Optional[Dict[str, Any]]
    raw: Optional[Dict[str, Any]]


class LLMClient:
    """
    Production-aware, provider-agnostic LLM client for Financial Mirror.

    Allowed LLM roles:
    1. Select the next action from pre-filtered governed candidate actions.
    2. Generate non-advisory wording from policy-approved facts.
    3. Rewrite unsafe wording after Safety Gate feedback.

    Forbidden LLM roles:
    - Do not bypass Policy Engine.
    - Do not bypass Safety Engine.
    - Do not select arbitrary tools.
    - Do not make financial recommendations.
    - Do not decide product eligibility, reward eligibility, or investment advice.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
        self.model_name = os.getenv("LLM_MODEL", "").strip()
        self.prompt_version = os.getenv("LLM_PROMPT_VERSION", "financial_mirror_agent_v1")
        self.env = os.getenv("ENV", os.getenv("APP_ENV", "development")).strip().lower()
        # Optional fallback provider when primary is unavailable (503/429)
        self.fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower() or None

        if not self.model_name:
            self.model_name = self._default_model_for_provider(self.provider)

        self._validate_provider_config()

    def _default_model_for_provider(self, provider: str) -> str:
        defaults = {
            "mock": "mock-governed-planner-v1",
            "gemini": "gemini-2.5-flash",
            "groq": "llama-3.1-8b-instant",
        }
        return defaults.get(provider, "unknown-model")

    def _validate_provider_config(self) -> None:
        if self.env in {"production", "prod", "demo"} and self.provider == "mock":
            raise LLMClientError(
                "LLM_PROVIDER=mock is not allowed in production/demo. "
                "Use a real provider such as gemini or groq."
            )

        if self.provider == "gemini":
            if not os.getenv("GEMINI_API_KEY"):
                raise LLMClientError(
                    "LLM_PROVIDER=gemini requires GEMINI_API_KEY."
                )

        elif self.provider == "groq":
            if not os.getenv("GROQ_API_KEY"):
                raise LLMClientError(
                    "LLM_PROVIDER=groq requires GROQ_API_KEY."
                )

        elif self.provider == "mock":
            return

        else:
            raise LLMClientError(
                f"Unsupported LLM_PROVIDER='{self.provider}'. "
                "Supported providers: mock, gemini, groq."
            )

        # Validate fallback provider if configured
        if self.fallback_provider and self.fallback_provider != self.provider:
            if self.fallback_provider == "groq":
                if not os.getenv("GROQ_API_KEY"):
                    raise LLMClientError(
                        "LLM_FALLBACK_PROVIDER=groq requires GROQ_API_KEY."
                    )
            elif self.fallback_provider == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    raise LLMClientError(
                        "LLM_FALLBACK_PROVIDER=gemini requires GEMINI_API_KEY."
                    )

    # =========================================================
    # Public API
    # =========================================================

    def select_action(
        self,
        goal: str,
        current_state: Dict[str, Any],
        candidate_actions: List[str],
        constraints: List[str],
    ) -> LLMResult:
        """
        LLM selects the next action ONLY from pre-filtered candidate_actions.

        The agent must still validate selected_action after this call.
        """

        if not candidate_actions:
            return self._result(
                purpose="action_selection",
                text='{"selected_action": null, "reason": "No candidate actions available."}',
                parsed_json={
                    "selected_action": None,
                    "reason": "No candidate actions available.",
                },
                raw=None,
            )

        system_prompt = self._system_prompt_for_action_selection()

        user_payload = {
            "goal": goal,
            "current_state": current_state,
            "candidate_actions": candidate_actions,
            "constraints": constraints,
            "required_output_json_schema": {
                "selected_action": "one of candidate_actions",
                "reason": "short reason explaining why this action is valid",
            },
        }

        return self._complete_json(
            purpose="action_selection",
            system_prompt=system_prompt,
            user_payload=user_payload,
        )

    def generate_non_advisory_output(
        self,
        fact: Dict[str, Any],
        policy_result: Dict[str, Any],
        product_context: Optional[Dict[str, Any]] = None,
        previous_violations: Optional[List[str]] = None,
    ) -> LLMResult:
        """
        Generate observation/nudge wording only for policy-approved facts.

        Output MUST still be validated by Safety Engine after this call.
        """

        system_prompt = self._system_prompt_for_non_advisory_wording()

        user_payload = {
            "fact": fact,
            "policy_result": policy_result,
            "product_context": product_context or {},
            "previous_safety_violations": previous_violations or [],
            "non_advisory_rules": [
                "Do not say 'you should'.",
                "Do not recommend exact amounts or percentages to save, invest, borrow, transfer, or allocate.",
                "Do not promise returns.",
                "Do not say risk-free.",
                "Do not tell the customer to buy, invest, borrow, deposit, or transfer money.",
                "Observation must describe verified historical data only.",
                "Nudge must be educational and optional.",
            ],
            "required_output_json_schema": {
                "observation": "objective, evidence-based statement",
                "nudge": "optional educational nudge, non-advisory",
            },
        }

        return self._complete_json(
            purpose="non_advisory_wording",
            system_prompt=system_prompt,
            user_payload=user_payload,
        )

    def rewrite_after_safety_failure(
        self,
        unsafe_observation: str,
        unsafe_nudge: str,
        safety_violations: List[str],
        fact: Dict[str, Any],
        policy_result: Dict[str, Any],
    ) -> LLMResult:
        """
        Rewrite unsafe output once after Safety Gate feedback.

        Output MUST still go through Safety Engine again.
        """

        system_prompt = self._system_prompt_for_safety_rewrite()

        user_payload = {
            "unsafe_observation": unsafe_observation,
            "unsafe_nudge": unsafe_nudge,
            "safety_violations": safety_violations,
            "fact": fact,
            "policy_result": policy_result,
            "rewrite_rules": [
                "Remove all advisory phrasing.",
                "Remove exact action percentages or amounts.",
                "Remove promises of return or risk reduction.",
                "Keep the output educational and optional.",
                "Do not tell the user what financial action to take.",
            ],
            "required_output_json_schema": {
                "observation": "safe rewritten observation",
                "nudge": "safe rewritten educational nudge",
            },
        }

        return self._complete_json(
            purpose="safety_rewrite",
            system_prompt=system_prompt,
            user_payload=user_payload,
        )

    # =========================================================
    # Prompt contracts
    # =========================================================

    def _system_prompt_for_action_selection(self) -> str:
        return (
            "You are the constrained action selector for Financial Mirror, "
            "a governed non-advisory financial insight workflow. "
            "You must choose exactly one action from candidate_actions. "
            "Never invent tools. Never bypass policy or safety. "
            "Return only valid JSON."
        )

    def _system_prompt_for_non_advisory_wording(self) -> str:
        return (
            "You generate non-advisory financial-health observations and "
            "educational nudges for Financial Mirror. "
            "Use only the provided fact, policy result, and product context. "
            "Do not provide personalized financial advice. "
            "Do not recommend amounts, percentages, investing, borrowing, "
            "depositing, transferring, or allocating money. "
            "Return only valid JSON."
        )

    def _system_prompt_for_safety_rewrite(self) -> str:
        return (
            "You rewrite unsafe financial wording into safe, non-advisory, "
            "educational wording. "
            "Remove all advisory language and financial action instructions. "
            "Return only valid JSON."
        )

    # =========================================================
    # Provider dispatch
    # =========================================================

    def _complete_json(
        self,
        purpose: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> LLMResult:
        if self.provider == "mock":
            return self._mock_complete_json(
                purpose=purpose,
                system_prompt=system_prompt,
                user_payload=user_payload,
            )

        if self.provider == "gemini":
            try:
                return self._gemini_complete_json(
                    purpose=purpose,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                )
            except LLMClientError as exc:
                # Auto-fallback on 503 Service Unavailable or 429 Too Many Requests
                error_msg = str(exc)
                is_retryable = (
                    "503" in error_msg
                    or "UNAVAILABLE" in error_msg
                    or "429" in error_msg
                    or "high demand" in error_msg.lower()
                    or "quota" in error_msg.lower()
                )
                if is_retryable and self.fallback_provider == "groq":
                    import sys
                    groq_model = self._default_model_for_provider("groq")
                    print(
                        f"[LLMClient] Gemini unavailable ({exc}). "
                        f"Falling back to groq/{groq_model}.",
                        file=sys.stderr,
                    )
                    return self._groq_complete_json(
                        purpose=purpose,
                        system_prompt=system_prompt,
                        user_payload=user_payload,
                        model_override=groq_model,
                    )
                raise

        if self.provider == "groq":
            return self._groq_complete_json(
                purpose=purpose,
                system_prompt=system_prompt,
                user_payload=user_payload,
            )

        raise LLMClientError(f"Unsupported provider: {self.provider}")

    def _mock_complete_json(
        self,
        purpose: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> LLMResult:
        if purpose == "action_selection":
            candidate_actions = user_payload.get("candidate_actions", [])
            selected_action = candidate_actions[0] if candidate_actions else None
            parsed = {
                "selected_action": selected_action,
                "reason": "Mock selected the first pre-filtered valid candidate action.",
            }

        elif purpose in {"non_advisory_wording", "safety_rewrite"}:
            customer_id = user_payload.get("fact", {}).get("customer_id")
            if customer_id == "cust_00128":
                parsed = {
                    "observation": "You should check your balance regularly to optimize return.",
                    "nudge": "We recommend you should invest in GoTyme high-yield savings.",
                }
            elif customer_id == "cust_00131":  # Fina
                if purpose == "non_advisory_wording":
                    parsed = {
                        "observation": "A verified financial activity pattern was detected from the available data.",
                        "nudge": "We recommend you check your GoTyme app features.",
                    }
                else:
                    parsed = {
                        "observation": "A verified financial activity pattern was detected from the available data.",
                        "nudge": "You can review the related GoTyme feature to learn more.",
                    }
            else:
                parsed = {
                    "observation": "A verified financial activity pattern was detected from the available data.",
                    "nudge": (
                        "You can review the related GoTyme feature to learn more. "
                        "This is educational and does not suggest a specific financial action."
                    ),
                }

        else:
            parsed = {"message": "Mock response."}

        return self._result(
            purpose=purpose,
            text=json.dumps(parsed, ensure_ascii=False),
            parsed_json=parsed,
            raw={
                "provider": "mock",
                "system_prompt": system_prompt,
                "user_payload": user_payload,
            },
        )

    def _gemini_complete_json(
        self,
        purpose: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> LLMResult:
        api_key = os.environ["GEMINI_API_KEY"]
        model = self.model_name

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        prompt = (
            f"{system_prompt}\n\n"
            "User payload:\n"
            f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
            "Return only valid JSON. Do not wrap it in markdown."
        )

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        raw = self._post_json(url=url, body=body, headers={})

        try:
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected Gemini response shape: {raw}") from exc

        return self._result(
            purpose=purpose,
            text=text,
            parsed_json=self._parse_json_text(text),
            raw=raw,
        )

    def _groq_complete_json(
        self,
        purpose: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
        model_override: Optional[str] = None,
    ) -> LLMResult:
        api_key = os.environ["GROQ_API_KEY"]
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = model_override or self.model_name

        body = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        "Return only valid JSON. User payload:\n"
                        f"{json.dumps(user_payload, ensure_ascii=False)}"
                    ),
                },
            ],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        raw = self._post_json(url=url, body=body, headers=headers)

        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected Groq response shape: {raw}") from exc

        return self._result(
            purpose=purpose,
            text=text,
            parsed_json=self._parse_json_text(text),
            raw=raw,
        )

    # =========================================================
    # HTTP + parsing helpers
    # =========================================================

    def _post_json(
        self,
        url: str,
        body: Dict[str, Any],
        headers: Dict[str, str],
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": "financial-mirror/1.0 (python-urllib)",
            **headers,
        }

        data = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=data,
            headers=request_headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body)

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(
                f"LLM HTTP error {exc.code}: {error_body}"
            ) from exc

        except urllib.error.URLError as exc:
            raise LLMClientError(f"LLM network error: {exc}") from exc

        except json.JSONDecodeError as exc:
            raise LLMClientError("LLM response was not valid JSON.") from exc

    def _parse_json_text(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                f"LLM did not return valid JSON. Raw text: {text}"
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMClientError(
                f"LLM JSON output must be an object. Got: {type(parsed)}"
            )

        return parsed

    def _result(
        self,
        purpose: str,
        text: str,
        parsed_json: Optional[Dict[str, Any]],
        raw: Optional[Dict[str, Any]],
    ) -> LLMResult:
        return LLMResult(
            provider=self.provider,
            model_name=self.model_name,
            prompt_version=self.prompt_version,
            llm_used=self.provider != "mock",
            purpose=purpose,
            text=text,
            parsed_json=parsed_json,
            raw=raw,
        )
