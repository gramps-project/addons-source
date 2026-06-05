import re
from typing import TYPE_CHECKING

from name_processor.models.renamer import MatchMode, RenameConfig, ProposedRename

if TYPE_CHECKING:
    from name_processor.repositories.person import GrampsPersonProxy


class RenamerService:
    def create_config(
        self, match_type: MatchMode, source_str: str, target_str: str
    ) -> RenameConfig:
        """
        Validates the user configuration before the batch scan begins.
        Catches invalid Regular Expressions immediately.
        """
        config = RenameConfig(mode=match_type, source=source_str, target=target_str)

        if match_type == MatchMode.REGEX:
            try:
                # Compile regex early to validate syntax and catch re.error
                config.pattern = re.compile(source_str)
            except re.error as e:
                config.is_valid = False
                config.error_msg = f"Invalid Regular Expression: {e.msg}"

        return config

    def evaluate_person(
        self, person: "GrampsPersonProxy", rule: RenameConfig
    ) -> ProposedRename | None:
        """
        Evaluates a person's primary given name against the replacement rule.

        :returns: ProposedRename DTO if a valid change is found, otherwise None.
        """
        if not rule.is_valid:
            return None

        # Edge Case 1: Missing object or missing Primary Name field
        if not person or not person.given_name:
            return None

        original_name = person.given_name
        proposed_name = None
        matched_text = ""

        # Execution based on user strategy
        if rule.mode == MatchMode.EXACT:
            if original_name == rule.source:
                proposed_name = rule.target
                matched_text = rule.target  # Entire name is the match

        elif rule.mode == MatchMode.SUBSTRING:
            if rule.source in original_name:
                proposed_name = original_name.replace(rule.source, rule.target)
                matched_text = rule.target  # The replacement text

        elif rule.mode == MatchMode.REGEX and rule.pattern:
            match = rule.pattern.search(original_name)
            if match:
                proposed_name = rule.pattern.sub(rule.target, original_name)
                matched_text = rule.target  # The replacement text

        # Edge Case 2: No match found, or replacement resulted in the exact same string
        if not proposed_name or proposed_name == original_name:
            return None

        return ProposedRename(
            handle=person.handle,
            gramps_id=person.gramps_id,
            display_name=person.display_name,
            original_given_name=original_name,
            proposed_given_name=proposed_name,
            matched_text=matched_text,
        )
