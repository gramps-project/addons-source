# ------------------------------------------------------------------------
#
# Calculate Estimated Dates
#
# ------------------------------------------------------------------------

register(
    TOOL,
    id="calculateestimateddates",
    name=_("Calculate Estimated Dates"),
    description=_("Calculates estimated dates for birth and death."),
    version = '0.90.40',
    gramps_target_version="6.0",
    status=STABLE,  # not yet tested with python 3
    fname="CalculateEstimatedDates.py",
    authors=["Douglas S. Blank"],
    authors_email=["doug.blank@gmail.com"],
    category=TOOL_DBPROC,
    toolclass="CalcToolManagedWindow",
    optionclass="CalcEstDateOptions",
    tool_modes=[TOOL_MODE_GUI],
    help_url="Addon:Calculate_Estimated_Dates",
)
