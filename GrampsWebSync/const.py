"""Constants for Gramps Web Sync."""

from typing import List, Optional, Tuple
from gramps.gen.lib.primaryobj import BasicPrimaryObject


# types
GrampsObject = BasicPrimaryObject
Action = Tuple[int, str, str, Optional[GrampsObject], Optional[GrampsObject]]
Actions = List[Action]


# actions: add, delete, update, merge - local/remote
A_ADD_LOC = "add_local"
A_ADD_REM = "add_remote"
A_DEL_LOC = "del_local"
A_DEL_REM = "del_remote"
A_UPD_LOC = "upd_local"
A_UPD_REM = "upd_remote"
A_MRG_REM = "mrg_remote"


OBJ_LST = [
    "Family",
    "Person",
    "Citation",
    "Event",
    "Media",
    "Note",
    "Place",
    "Repository",
    "Source",
    "Tag",
]
