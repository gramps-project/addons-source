"""Composition des règles d'inférence activées par défaut."""

from descendants_timeline.inference.baptism_before_death_rule import (
    BaptismBeforeDeathRule,
)
from descendants_timeline.inference.birth_before_baptism_rule import (
    BirthBeforeBaptismRule,
)
from descendants_timeline.inference.birth_before_burial_rule import (
    BirthBeforeBurialRule,
)
from descendants_timeline.inference.birth_before_census_rule import (
    BirthBeforeCensusRule,
)
from descendants_timeline.inference.birth_before_death_rule import (
    BirthBeforeDeathRule,
)
from descendants_timeline.inference.birth_before_divorce_rule import (
    BirthBeforeDivorceRule,
)
from descendants_timeline.inference.birth_before_marriage_rule import (
    BirthBeforeMarriageRule,
)
from descendants_timeline.inference.birth_maximum_lifespan_from_burial_rule import (
    BirthMaximumLifespanFromBurialRule,
)
from descendants_timeline.inference.birth_maximum_lifespan_from_census_rule import (
    BirthMaximumLifespanFromCensusRule,
)
from descendants_timeline.inference.birth_maximum_lifespan_from_death_rule import (
    BirthMaximumLifespanFromDeathRule,
)
from descendants_timeline.inference.birth_minimum_age_at_marriage_rule import (
    BirthMinimumAgeAtMarriageRule,
)
from descendants_timeline.inference.census_before_death_rule import (
    CensusBeforeDeathRule,
)
from descendants_timeline.inference.death_before_burial_rule import (
    DeathBeforeBurialRule,
)
from descendants_timeline.inference.death_maximum_lifespan_from_birth_rule import (
    DeathMaximumLifespanFromBirthRule,
)
from descendants_timeline.inference.divorce_after_marriage_rule import (
    DivorceAfterMarriageRule,
)
from descendants_timeline.inference.divorce_before_death_rule import (
    DivorceBeforeDeathRule,
)
from descendants_timeline.inference.divorce_before_spouse_burial_rule import (
    DivorceBeforeSpouseBurialRule,
)
from descendants_timeline.inference.divorce_before_spouse_death_rule import (
    DivorceBeforeSpouseDeathRule,
)
from descendants_timeline.inference.marriage_after_birth_rule import (
    MarriageAfterBirthRule,
)
from descendants_timeline.inference.marriage_before_death_rule import (
    MarriageBeforeDeathRule,
)
from descendants_timeline.inference.marriage_before_divorce_rule import (
    MarriageBeforeDivorceRule,
)
from descendants_timeline.inference.marriage_before_spouse_burial_rule import (
    MarriageBeforeSpouseBurialRule,
)
from descendants_timeline.inference.marriage_before_spouse_death_rule import (
    MarriageBeforeSpouseDeathRule,
)
from descendants_timeline.inference.marriage_minimum_age_from_birth_rule import (
    MarriageMinimumAgeFromBirthRule,
)


def default_rules():
    """Retourne les règles d'inférence activées par défaut."""
    return (
        BirthBeforeBaptismRule(),
        BirthBeforeBurialRule(),
        BirthBeforeCensusRule(),
        BirthBeforeDeathRule(),
        BirthBeforeMarriageRule(),
        BirthBeforeDivorceRule(),
        BirthMaximumLifespanFromBurialRule(),
        BirthMaximumLifespanFromCensusRule(),
        BirthMaximumLifespanFromDeathRule(),
        BirthMinimumAgeAtMarriageRule(),

        BaptismBeforeDeathRule(),
        CensusBeforeDeathRule(),
        MarriageBeforeDeathRule(),
        DivorceBeforeDeathRule(),
        DeathBeforeBurialRule(),
        DeathMaximumLifespanFromBirthRule(),

        MarriageAfterBirthRule(),
        MarriageBeforeDivorceRule(),
        MarriageBeforeSpouseBurialRule(),
        MarriageBeforeSpouseDeathRule(),
        MarriageMinimumAgeFromBirthRule(),

        DivorceAfterMarriageRule(),
        DivorceBeforeSpouseBurialRule(),
        DivorceBeforeSpouseDeathRule(),
    )