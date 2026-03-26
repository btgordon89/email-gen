"""Base class for pipeline steps — standardizes execution, logging, and validation."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import anthropic_text, audit, config, gemini_text, io_util, json_parser


class BaseStep(ABC):
    """
    Abstract base class for pipeline steps.

    Each step subclass defines:
    - step_id: unique identifier (e.g. "step1_brief")
    - output_filename: where to write the output JSON (e.g. "step1_brief.json")
    - model_fn: function that returns the model name (e.g. config.brief_model)
    - default_schema: fallback dict if JSON parsing fails

    The base class handles:
    - Loading system prompts from prompts/ directory
    - Calling Gemini with retry logic
    - Parsing JSON responses
    - Writing output and audit logs
    - Optional validation hooks

    Sequence support:
    - Pass email_num / total_emails to run() for multi-email sequences.
    - Subclasses access self._email_num and self._total_emails in load_inputs/build_prompt.
    - Use self._brief_for_email(full_brief) to extract the per-email brief section.
    - Use self._step_path(run_dir, filename) to get per-email step file paths.
    """

    # Subclasses must define these
    step_id: str
    output_filename: str
    model_fn: Callable[[], str]
    default_schema: Dict[str, Any]

    # Set by run(); available to subclasses during load_inputs / build_prompt
    _email_num: int = 1
    _total_emails: int = 1

    def run(self, run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
        """
        Execute the step: load inputs, build prompt, call LLM, parse, validate, write output.

        Args:
            run_dir: output/<run_id>/
            email_num: 1-based index of the email in the sequence (1 = default / single email)
            total_emails: total number of emails in the sequence (1 = single email)

        Returns:
            Parsed output dict
        """
        self._email_num = email_num
        self._total_emails = total_emails
        start_time = time.time()

        # Load inputs (step-specific logic)
        inputs = self.load_inputs(run_dir)

        # Build prompt (step-specific logic)
        prompt = self.build_prompt(inputs)

        # Load system prompt from prompts/ directory
        system = self._load_system_prompt()

        # Get model name
        model = self._get_model()

        # Call LLM
        raw_response = self._call_llm(prompt, system, model)

        # Parse JSON response
        parsed, warnings = json_parser.parse_llm_json(
            raw_response,
            default_schema=self.default_schema,
            max_retries=0,  # No auto-retry for now (could add later)
        )

        # Ensure all schema keys are present
        parsed = json_parser.ensure_keys(parsed, self.default_schema)

        # Optional per-step validation
        validation_warnings = self.validate(parsed, inputs)
        warnings.extend(validation_warnings)

        # Write output JSON (with email suffix in sequence mode)
        output_filename = io_util.step_filename(self.output_filename, email_num, total_emails)
        output_path = run_dir / output_filename
        io_util.write_json(output_path, parsed)

        # Write audit log (step_id includes email number in sequence mode)
        duration = time.time() - start_time
        audit_step_id = f"{self.step_id}_email_{email_num}" if total_emails > 1 else self.step_id
        audit.write_audit_log(
            run_dir=run_dir,
            step_id=audit_step_id,
            model=model,
            prompt=prompt,
            system_prompt=system,
            raw_response=raw_response,
            parsed_output=parsed,
            duration_seconds=duration,
            warnings=warnings,
            metadata=self._metadata(inputs),
        )

        return parsed

    @abstractmethod
    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """
        Load all inputs needed for this step.

        Returns:
            Dict with all inputs (questionnaire, previous step outputs, etc.)
        """
        pass

    @abstractmethod
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """
        Build the user prompt for the LLM.

        Args:
            inputs: Result of load_inputs()

        Returns:
            Formatted prompt string
        """
        pass

    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """
        Optional: validate the parsed output against inputs or internal constraints.

        Returns:
            List of validation warning messages (empty if valid)
        """
        return []

    def _metadata(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optional: return metadata to include in audit log.

        Returns:
            Dict with any extra metadata (e.g., input file checksums)
        """
        return {}

    # ------------------------------------------------------------------ #
    # Sequence helpers — for use in subclass load_inputs / build_prompt   #
    # ------------------------------------------------------------------ #

    def _brief_for_email(self, full_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the per-email brief section in sequence mode.

        For single-email runs (total_emails <= 1) returns the brief unchanged.
        For sequences, looks up emails[email_num - 1] inside the brief.
        """
        if self._total_emails > 1:
            emails = full_brief.get("emails") or []
            idx = self._email_num - 1
            if 0 <= idx < len(emails):
                return emails[idx]
        return full_brief

    def _step_path(self, run_dir: Path, filename: str, per_email: bool = True) -> Path:
        """Get path to a step output file.

        Args:
            run_dir: the run directory
            filename: base filename (e.g. io_util.STEP2A)
            per_email: if True (default), appends email suffix in sequence mode.
                       Set to False for shared files like STEP1, STEP2B.
        """
        if per_email:
            return run_dir / io_util.step_filename(filename, self._email_num, self._total_emails)
        return run_dir / filename

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_system_prompt(self) -> str:
        """Load system prompt from prompts/{step_id}.system.md"""
        prompt_path = config.root() / "pipeline" / "prompts" / f"{self.step_id}.system.md"
        if not prompt_path.is_file():
            return ""
        return prompt_path.read_text(encoding="utf-8")

    def _get_model(self) -> str:
        """Get the model name from model_fn."""
        if callable(self.model_fn):
            return self.model_fn()
        return str(self.model_fn)

    def _call_llm(self, prompt: str, system: str, model: str) -> str:
        """Call text generation, routing to Anthropic or Gemini based on model name."""
        if model.startswith("claude-"):
            return anthropic_text.generate_text(
                prompt=prompt,
                model=model,
                system=system if system else None,
            )
        return gemini_text.generate_text(
            prompt=prompt,
            model=model,
            system=system if system else None,
        )
