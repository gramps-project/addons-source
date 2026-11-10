"""Dates Gramps grégoriennes normales et conservation des années approximatives."""

from datetime import date, timedelta
from calendar import monthrange
from dataclasses import dataclass
from enum import Enum

from descendants_timeline.gramps_data_converter import (
    convert_date_calendar_code,
    convert_date_day_valid,
    convert_date_document,
    convert_date_is_empty,
    convert_date_is_full,
    convert_date_modifier_code,
    convert_date_month_valid,
    convert_date_new_year,
    convert_date_quality_code,
    convert_date_slash,
    convert_date_slash2,
    convert_date_start_ymd,
    convert_date_stop_ymd,
    convert_date_text,
    convert_date_year_valid,
)
from descendants_timeline.model.temporal import (
    CertaintyLevel, EvidenceStatus, SourceQuality, TemporalValue, ValueOrigin,
)


class DateNormalizationDiagnosticCode(str, Enum):
    UNSUPPORTED_FORM = "UNSUPPORTED_FORM"
    UNRESOLVED_CONVENTION = "UNRESOLVED_CONVENTION"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    VALIDATION_UNDETERMINED = "VALIDATION_UNDETERMINED"


@dataclass(frozen=True, slots=True)
class DateNormalizationDiagnostic:
    event_id: str
    code: DateNormalizationDiagnosticCode
    explanation: str


@dataclass(frozen=True, slots=True)
class DateNormalizationResult:
    temporal_value: TemporalValue
    diagnostic: DateNormalizationDiagnostic | None = None

    @property
    def is_interpreted(self) -> bool:
        """La forme est traitée ; cela ne signifie pas qu'elle est probante."""
        return self.diagnostic is None


class DateNormalizationRejected(ValueError):
    """Rejet conservé lorsque la conservation sûre n'est pas établie."""

    def __init__(self, diagnostic: DateNormalizationDiagnostic):
        self.diagnostic = diagnostic
        super().__init__(f"Event {diagnostic.event_id}: {diagnostic.explanation}")


def normalize_exact_normal_gregorian_date(date_object, *, event_id) -> TemporalValue:
    unsupported = f"Event {event_id} has a date; date normalization is not supported"

    def diagnostic_value(converter):
        try:
            return repr(converter(date_object))
        except Exception as error:
            return f"<unavailable: {type(error).__name__}>"

    def unsupported_diagnostic():
        return (
            f"{unsupported}; "
            f"calendar_code={diagnostic_value(convert_date_calendar_code)}; "
            f"modifier_code={diagnostic_value(convert_date_modifier_code)}; "
            f"quality_code={diagnostic_value(convert_date_quality_code)}; "
            f"start_ymd={diagnostic_value(convert_date_start_ymd)}; "
            f"stop_ymd={diagnostic_value(convert_date_stop_ymd)}; "
            f"is_empty={diagnostic_value(convert_date_is_empty)}; "
            f"is_full={diagnostic_value(convert_date_is_full)}; "
            f"year_valid={diagnostic_value(convert_date_year_valid)}; "
            f"month_valid={diagnostic_value(convert_date_month_valid)}; "
            f"day_valid={diagnostic_value(convert_date_day_valid)}; "
            f"slash={diagnostic_value(convert_date_slash)}; "
            f"slash2={diagnostic_value(convert_date_slash2)}; "
            f"new_year={diagnostic_value(convert_date_new_year)}; "
            f"text={diagnostic_value(convert_date_text)}"
        )

    # Codes vérifiés dans gramps/gen/lib/date.py, version 6.0.8 :
    # CAL_GREGORIAN = MOD_NONE = QUAL_NONE = NEWYEAR_JAN1 = 0.
    # MOD_BEFORE = 1 : borne supérieure seule, pour une année seule.
    # MOD_ABOUT = 3 : conservation documentaire uniquement pour une année seule.
    # MOD_RANGE = 4 : deux dates complètes bornent l'événement.
    if (
        convert_date_calendar_code(date_object) != 0
        or convert_date_modifier_code(date_object) not in (0, 1, 3, 4)
        or convert_date_quality_code(date_object) != 0
        or convert_date_slash(date_object)
        or convert_date_new_year(date_object) != 0
    ):
        raise ValueError(unsupported_diagnostic())

    year, month, day = convert_date_start_ymd(date_object)
    if convert_date_modifier_code(date_object) == 4:
        if not convert_date_is_full(date_object) or convert_date_slash2(date_object):
            raise ValueError(unsupported_diagnostic())
        stop_year, stop_month, stop_day = convert_date_stop_ymd(date_object)
        try:
            minimum = date(year, month, day)
            maximum = date(stop_year, stop_month, stop_day)
        except ValueError as error:
            raise ValueError(unsupported_diagnostic()) from error
        if minimum > maximum:
            raise ValueError(unsupported_diagnostic())
        return TemporalValue(
            source_value=convert_date_text(date_object) or (
                f"entre le {day}/{month}/{year} et le {stop_day}/{stop_month}/{stop_year}"
            ),
            source_calendar="Gregorian",
            normalized_minimum=minimum,
            normalized_maximum=maximum,
            representative_value=None,
            value_origin=ValueOrigin.GRAMPS,
            source_quality=SourceQuality.NORMAL,
            evidence_status=EvidenceStatus.EVIDENCE_USABLE,
            certainty=CertaintyLevel.CERTAIN,
        )

    is_full = convert_date_is_full(date_object)
    year_only = (
        not is_full
        and convert_date_year_valid(date_object)
        and month == 0
        and day == 0
        and not convert_date_month_valid(date_object)
        and not convert_date_day_valid(date_object)
        and convert_date_stop_ymd(date_object) == (0, 0, 0)
    )
    if not is_full and not year_only:
        raise ValueError(unsupported_diagnostic())

    if convert_date_modifier_code(date_object) == 1:
        # Avant l'an 1 et les années antérieures : hors du domaine datetime.date.
        if not year_only or year <= date.min.year:
            raise ValueError(unsupported_diagnostic())
        try:
            maximum = date(year, 1, 1) - timedelta(days=1)
        except ValueError as error:
            raise ValueError(unsupported_diagnostic()) from error
        return TemporalValue(
            source_value=convert_date_text(date_object) or f"avant {year}",
            source_calendar="Gregorian",
            normalized_minimum=None,
            normalized_maximum=maximum,
            representative_value=None,
            value_origin=ValueOrigin.GRAMPS,
            source_quality=SourceQuality.NORMAL,
            evidence_status=EvidenceStatus.EVIDENCE_USABLE,
            certainty=CertaintyLevel.CERTAIN,
            documentary_boundary=date(year, 1, 1),
        )

    if convert_date_modifier_code(date_object) == 3:
        if not year_only or not date.min.year <= year <= date.max.year:
            raise ValueError(unsupported_diagnostic())
        return TemporalValue(
            source_value=convert_date_text(date_object) or f"vers {year}",
            source_calendar="Gregorian",
            normalized_minimum=None,
            normalized_maximum=None,
            representative_value=None,
            value_origin=ValueOrigin.GRAMPS,
            source_quality=SourceQuality.NORMAL,
            evidence_status=EvidenceStatus.EVIDENCE_UNPROVEN,
            certainty=CertaintyLevel.UNDETERMINED,
        )

    try:
        minimum = date(year, 1, 1) if year_only else date(year, month, day)
        maximum = date(year, 12, 31) if year_only else minimum
    except ValueError as error:
        raise ValueError(unsupported_diagnostic()) from error

    return TemporalValue(
        source_value=convert_date_text(date_object) or (
            str(year) if year_only else f"{day}/{month}/{year}"
        ),
        source_calendar="Gregorian",
        normalized_minimum=minimum,
        normalized_maximum=maximum,
        representative_value=None if year_only else minimum,
        value_origin=ValueOrigin.GRAMPS,
        source_quality=SourceQuality.NORMAL,
        evidence_status=EvidenceStatus.EVIDENCE_USABLE,
        certainty=CertaintyLevel.CERTAIN,
    )


def _gramps_republican_to_gregorian(year, month, day):
    from gramps.gen.lib.gcalendar import french_sdn, gregorian_ymd

    return gregorian_ymd(french_sdn(year, month, day))


def _gramps_republican_is_valid(year, month, day):
    from gramps.gen.lib.gcalendar import french_sdn, french_ymd

    return french_ymd(french_sdn(year, month, day)) == (year, month, day)


def normalize_gramps_date(
    date_object, *, event_id, republican_to_gregorian=None, republican_is_valid=None,
) -> DateNormalizationResult:
    """Contrat indépendant du chargeur, sans récupération des erreurs métier.

    La validation documentaire couvre les formes grégoriennes sans convention
    historique, avec année représentable, ainsi que les dates républicaines
    complètes normales des mois ordinaires et des jours complémentaires 1 à 5,
    ainsi que le sixième jour après validation positive, sans double date ni
    nouvel an particulier. Les autres formes restent
    rejetées tant que leur validation n'est pas établie.
    """
    if date_object is None:
        return DateNormalizationResult(TemporalValue.unknown())

    def reject(code, explanation):
        raise DateNormalizationRejected(DateNormalizationDiagnostic(event_id, code, explanation))

    document = convert_date_document(date_object)
    code = DateNormalizationDiagnosticCode
    if (
        document.calendar_code not in range(7)
        or document.modifier_code not in range(9)
        or document.quality_code not in range(3)
    ):
        reject(code.INVALID_STRUCTURE, "Code de date Gramps invalide.")

    modifier = document.modifier_code
    raw = document.dateval
    compound = modifier in (4, 5)
    if len(raw) != (8 if compound else 4):
        reject(code.INVALID_STRUCTURE, "Longueur de dateval incompatible avec le modificateur.")
    for offset in range(0, len(raw), 4):
        if (
            any(type(part) is not int for part in raw[offset:offset + 3])
            or raw[offset + 3] not in (False, True)
        ):
            reject(code.INVALID_STRUCTURE, "Composantes de dateval invalides.")

    day, month, year = raw[:3]
    if (
        document.calendar_code == 3
        and modifier == 0
        and document.quality_code == 0
        and len(raw) == 4
        and year > 0
        and document.newyear == 0
        and not raw[3]
        and ((1 <= month <= 12 and day > 30) or (month == 13 and day > 6))
    ):
        reject(code.INVALID_STRUCTURE, "Jour impossible pour ce mois du calendrier républicain français.")

    if (
        document.calendar_code == 3
        and modifier == 0
        and document.quality_code == 0
        and len(raw) == 4
        and year > 0
        and (
            (1 <= month <= 12 and 1 <= day <= 30)
            or (month == 13 and 1 <= day <= 6)
        )
        and document.newyear == 0
        and not raw[3]
    ):
        if month == 13 and day == 6:
            validator = (
                _gramps_republican_is_valid
                if republican_is_valid is None else republican_is_valid
            )
            validity = validator(year, month, day)
            if validity is False:
                reject(code.INVALID_STRUCTURE, "Sixième jour complémentaire républicain invalide pour cette année.")
            if validity is not True:
                reject(code.VALIDATION_UNDETERMINED, "Validité du sixième jour complémentaire non établie.")
        converter = (
            _gramps_republican_to_gregorian
            if republican_to_gregorian is None else republican_to_gregorian
        )
        exact = date(*converter(year, month, day))
        return DateNormalizationResult(TemporalValue(
            source_value=document.text or f"{day}/{month}/{year}",
            source_calendar="French Republican",
            normalized_minimum=exact,
            normalized_maximum=exact,
            representative_value=exact,
            value_origin=ValueOrigin.GRAMPS,
            source_quality=SourceQuality.NORMAL,
            evidence_status=EvidenceStatus.EVIDENCE_USABLE,
            certainty=CertaintyLevel.CERTAIN,
        ))

    if document.calendar_code != 0:
        reject(code.VALIDATION_UNDETERMINED, "Validation de ce calendrier non encore établie.")
    if document.newyear != 0 or raw[3] or (compound and raw[7]):
        reject(code.UNRESOLVED_CONVENTION, "Convention de nouvel an ou de double date non résolue.")

    if modifier == 6:
        if any(raw[:3]):
            reject(code.INVALID_STRUCTURE, "Une date textuelle contient des composantes numériques.")
        if not document.text:
            return DateNormalizationResult(TemporalValue.unknown())
    elif not any(raw[:3]) and not compound and modifier == 0 and not document.text:
        return DateNormalizationResult(TemporalValue.unknown())
    else:
        for offset in range(0, len(raw), 4):
            day, month, year = raw[offset:offset + 3]
            if year == 0:
                reject(code.VALIDATION_UNDETERMINED, "Validation sans année non encore établie.")
            if not date.min.year <= year <= date.max.year:
                reject(code.OUT_OF_DOMAIN, "Année hors du domaine datetime.date.")
            try:
                # Validation uniquement : ces substitutions ne deviennent pas des bornes.
                date(year, month or 1, day or 1)
            except ValueError as error:
                raise DateNormalizationRejected(DateNormalizationDiagnostic(
                    event_id, code.INVALID_STRUCTURE, "Composantes grégoriennes invalides.",
                )) from error
        if compound:
            if not all(raw[i] for i in (0, 1, 2, 4, 5, 6)):
                reject(code.VALIDATION_UNDETERMINED, "Validation des intervalles partiels non encore établie.")
            if (raw[2], raw[1], raw[0]) > (raw[6], raw[5], raw[4]):
                reject(code.INVALID_STRUCTURE, "Intervalle de dates inversé.")

        day, month, year = raw[:3]
        year_only = month == 0 and day == 0
        month_only = month != 0 and day == 0
        if document.quality_code == 0 and modifier in (1, 2) and (
            all(raw[:3]) or month_only or (modifier == 2 and year_only)
        ):
            if year_only:
                boundary = date(year, 12, 31)
            elif month_only:
                boundary = date(year, month, 1 if modifier == 1 else monthrange(year, month)[1])
            else:
                boundary = date(year, month, day)
            if modifier == 1 and boundary == date.min:
                # Preserve this complete date without inventing a numeric bound.
                # Partial dates keep their existing rejection policy.
                if all(raw[:3]):
                    return DateNormalizationResult(
                        temporal_value=TemporalValue(
                            source_value=document.text or f"avant {day}/{month}/{year}",
                            source_calendar="Gregorian",
                            normalized_minimum=None,
                            normalized_maximum=None,
                            representative_value=None,
                            value_origin=ValueOrigin.GRAMPS,
                            source_quality=SourceQuality.NORMAL,
                            evidence_status=EvidenceStatus.EVIDENCE_UNPROVEN,
                            certainty=CertaintyLevel.UNDETERMINED,
                            documentary_boundary=boundary,
                        ),
                        diagnostic=DateNormalizationDiagnostic(
                            event_id, code.OUT_OF_DOMAIN,
                            "La borne avant cette date sort du domaine datetime.date.",
                        ),
                    )
                reject(code.OUT_OF_DOMAIN, "La borne avant cette date sort du domaine datetime.date.")
            if modifier == 2 and boundary == date.max:
                # Preserve this complete date without inventing a numeric bound.
                # Partial dates keep their existing rejection policy.
                if all(raw[:3]):
                    return DateNormalizationResult(
                        temporal_value=TemporalValue(
                            source_value=document.text or f"après {day}/{month}/{year}",
                            source_calendar="Gregorian",
                            normalized_minimum=None,
                            normalized_maximum=None,
                            representative_value=None,
                            value_origin=ValueOrigin.GRAMPS,
                            source_quality=SourceQuality.NORMAL,
                            evidence_status=EvidenceStatus.EVIDENCE_UNPROVEN,
                            certainty=CertaintyLevel.UNDETERMINED,
                            documentary_boundary=boundary,
                        ),
                        diagnostic=DateNormalizationDiagnostic(
                            event_id, code.OUT_OF_DOMAIN,
                            "La borne après cette date sort du domaine datetime.date.",
                        ),
                    )
                reject(code.OUT_OF_DOMAIN, "La borne après cette date sort du domaine datetime.date.")
            return DateNormalizationResult(TemporalValue(
                source_value=document.text or (
                    f"après {year}" if year_only
                    else f"{'avant' if modifier == 1 else 'après'} {month}/{year}" if month_only
                    else f"{'avant' if modifier == 1 else 'après'} {day}/{month}/{year}"
                ),
                source_calendar="Gregorian",
                normalized_minimum=boundary + timedelta(days=1) if modifier == 2 else None,
                normalized_maximum=boundary - timedelta(days=1) if modifier == 1 else None,
                representative_value=None,
                value_origin=ValueOrigin.GRAMPS,
                source_quality=SourceQuality.NORMAL,
                evidence_status=EvidenceStatus.EVIDENCE_USABLE,
                certainty=CertaintyLevel.CERTAIN,
                documentary_boundary=boundary,
            ))
        if modifier == 1 and year_only and year == 1:
            reject(code.OUT_OF_DOMAIN, "La borne avant l'an 1 sort du domaine datetime.date.")
        supported = document.quality_code == 0 and (
            (modifier == 0 and (all(raw[:3]) or year_only))
            or (modifier in (1, 3) and year_only)
            or modifier == 4
        )
        if supported:
            return DateNormalizationResult(normalize_exact_normal_gregorian_date(
                date_object, event_id=event_id,
            ))

    def source_part(offset):
        day, month, year = raw[offset:offset + 3]
        if day:
            return f"{day}/{month or '?'}/{year}"
        if month:
            return f"{month}/{year}"
        return str(year)

    source = document.text
    if not source:
        start = source_part(0)
        if compound:
            stop = source_part(4)
            source = f"entre {start} et {stop}" if modifier == 4 else f"de {start} à {stop}"
        else:
            prefix = {0: "", 1: "avant ", 2: "après ", 3: "vers ", 7: "depuis ", 8: "jusqu'à "}
            source = prefix[modifier] + start
    return DateNormalizationResult(
        temporal_value=TemporalValue(
            source_value=source,
            source_calendar="Gregorian",
            normalized_minimum=None,
            normalized_maximum=None,
            representative_value=None,
            value_origin=ValueOrigin.GRAMPS,
            source_quality=(SourceQuality.NORMAL, SourceQuality.ESTIMATED, SourceQuality.CALCULATED)[document.quality_code],
            evidence_status=EvidenceStatus.EVIDENCE_UNPROVEN,
            certainty=CertaintyLevel.UNDETERMINED,
        ),
        diagnostic=DateNormalizationDiagnostic(
            event_id, code.UNSUPPORTED_FORM,
            "Forme de date Gramps non encore interprétée.",
        ),
    )
