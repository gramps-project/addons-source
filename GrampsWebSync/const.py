"""Constants for Gramps Web Sync."""


class TypeMeta(type):
    """Workaround for missing typing module in Gramps AIO."""

    def __getitem__(self, *args, **kwargs):
        return self


class Type(metaclass=TypeMeta):
    """Workaround for missing typing module in Gramps AIO."""


try:
    from typing import List, Optional, Tuple
except ImportError:
    List = Type
    Optional = Type
    Tuple = Type
from gramps.gen.lib.primaryobj import BasicPrimaryObject


# types
GrampsObject = BasicPrimaryObject
Action = Tuple[str, str, str, Optional[GrampsObject], Optional[GrampsObject]]
Actions = List[Action]


# changed: added, deleteed, updated - local/remote/both
C_ADD_LOC = "added_local"
C_ADD_REM = "added_remote"
C_DEL_LOC = "deleted_local"
C_DEL_REM = "deleted_remote"
C_UPD_LOC = "updated_local"
C_UPD_REM = "updated_remote"
C_UPD_BOTH = "updated_both"

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

# sync modes
MODE_BIDIRECTIONAL = 0
MODE_RESET_TO_LOCAL = 1
MODE_RESET_TO_REMOTE = 2
