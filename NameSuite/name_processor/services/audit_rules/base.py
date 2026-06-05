from abc import ABC, abstractmethod
from name_processor.models.audit import RuleContext, ProposedChange


class BaseRule(ABC):
    """Abstract Base Class for all linter consistency rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        pass

    @property
    @abstractmethod
    def supported_locales(self) -> set[str]:
        pass

    @property
    @abstractmethod
    def active_era(self) -> tuple[int | None, int | None]:
        pass

    @abstractmethod
    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        """
        Evaluates context. Returns None if rule passes, or a ProposedChange
        if consistency issues are detected.
        """
        pass
