# ------------------------------------------------------------------------
#
# Register the Gramplet ChatWithTree
#
# ------------------------------------------------------------------------
register(
    GRAMPLET,
    id="ChatWithTree",  # Unique ID for your addon
    name=_("Chat With Tree Interactive Addon"),  # Display name in Gramps, translatable
    description=_("Chat With Tree with the help of AI Large Language Model, needs litellm module"),
    version = '0.0.21',
    gramps_target_version="6.0",  # Specify the Gramps version you are targeting
    status=EXPERIMENTAL,
    audience = DEVELOPER,
    fname="ChatWithTree.py",  # The main Python file for your Gramplet
    # The 'gramplet' argument points to the class name in your main file
    gramplet="ChatWithTreeClass",
    gramplet_title=_("Chat With Tree"),
    authors = ["Melle Koning"],
    authors_email = ["mellekoning@gmail.com"],
    height=18,
     # addon needs litellm python module
    requires_mod=['litellm'],
    navtypes=["Dashboard"],
)