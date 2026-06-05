from name_processor.services.audit_rules.base import BaseRule
from name_processor.models.audit import RuleContext, ProposedChange
from name_processor.models.person import Gender
from name_processor.models.constants import LOCALE_EAST_SLAVIC, SEVERITY_ERROR
from name_processor.services.morphology import MorphologyService


class ErrGenderMismatch(BaseRule):
    rule_id = "GENDER_MISMATCH"

    @property
    def severity(self) -> str:
        return SEVERITY_ERROR

    @property
    def supported_locales(self) -> set[str]:
        return set(LOCALE_EAST_SLAVIC)

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, None)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if ctx.gender not in (Gender.MALE, Gender.FEMALE) or not ctx.current_patronymic:
            return None

        is_male = ctx.gender == Gender.MALE

        # 1. Evaluate with father's name if present
        if ctx.father_given_name:
            expected = MorphologyService.generate_east_slavic_patronymic(
                father_name=ctx.father_given_name,
                is_male=is_male,
                year=ctx.reference_year,
                pre_reform_script=use_pre_reform,
            )
            opposite = MorphologyService.generate_east_slavic_patronymic(
                father_name=ctx.father_given_name,
                is_male=not is_male,
                year=ctx.reference_year,
                pre_reform_script=use_pre_reform,
            )

            if ctx.current_patronymic == opposite and expected and opposite != expected:
                gender_str = "male" if is_male else "female"
                return ProposedChange(
                    explanation=f"Linguistic gender mismatch: Patronymic is grammatically incorrect for a {gender_str} individual.",
                    suggested_string=expected,
                )

        # 2. Universal fallback using suffix endings
        female_endings = ("овна", "евна", "ична", "инична", "ова", "ева", "ина")
        male_endings = ("ович", "евич", "ич", "ов", "ев", "ин", "овъ", "евъ", "инъ")

        if is_male and ctx.current_patronymic.endswith(female_endings):
            suggested = MorphologyService.swap_patronymic_gender(
                ctx.current_patronymic, to_male=True, pre_reform=use_pre_reform
            )
            if suggested:
                return ProposedChange(
                    explanation="Linguistic gender mismatch: Suffix is grammatically female for a male individual.",
                    suggested_string=suggested,
                )

        elif not is_male and ctx.current_patronymic.endswith(male_endings):
            suggested = MorphologyService.swap_patronymic_gender(
                ctx.current_patronymic, to_male=False, pre_reform=use_pre_reform
            )
            if suggested:
                return ProposedChange(
                    explanation="Linguistic gender mismatch: Suffix is grammatically male for a female individual.",
                    suggested_string=suggested,
                )

        return None
