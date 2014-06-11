register(
    GRAMPLET, 
    id= "Wordle Gramplet", 
    name=_("Wordle Gramplet"), 
    status = UNSTABLE,
    include_in_listing = False,
    fname="WordleGramplet.py",
    height=230,
    gramplet = 'WordleGramplet',
    gramplet_title=_("Wordle"),
    gramps_target_version = '4.2',
    version = '1.0.8',
    description = "Gramplet used to make word clouds with wordle.net",
    authors = ["Douglas Blank"],
    authors_email = ["doug.blank@gmail.com"],
    )

