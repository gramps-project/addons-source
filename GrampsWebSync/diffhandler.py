"""Class managing the difference between two databases."""

from copy import deepcopy

try:
    from typing import List, Optional, Set, Tuple
except ImportError:
    from const import Type

    List = Type
    Optional = Type
    Set = Type
    Tuple = Type

from gramps.gen.db import DbTxn
from gramps.gen.db.base import DbReadBase
from gramps.gen.merge.diff import diff_dbs
from gramps.gen.user import User

from const import (
    A_ADD_LOC,
    A_ADD_REM,
    A_DEL_LOC,
    A_DEL_REM,
    A_MRG_REM,
    A_UPD_LOC,
    A_UPD_REM,
    C_ADD_LOC,
    C_ADD_REM,
    C_DEL_LOC,
    C_DEL_REM,
    C_UPD_BOTH,
    C_UPD_LOC,
    C_UPD_REM,
    MODE_BIDIRECTIONAL,
    MODE_RESET_TO_LOCAL,
    MODE_RESET_TO_REMOTE,
    OBJ_LST,
    Action,
    Actions,
    GrampsObject,
)


class WebApiSyncDiffHandler:
    """Class managing the difference between two databases."""

    def __init__(
        self,
        db1: DbReadBase,
        db2: DbReadBase,
        user: User,
        last_synced: Optional[float] = None,
    ) -> None:
        """Initialize given the two databases and a User instance."""
        self.db1 = db1
        self.db2 = db2
        self.user = user
        self._diff_dbs = self.get_diff_dbs()
        self.differences = {
            (obj1.handle, obj_type): (obj1, obj2)
            for (obj_type, obj1, obj2) in self._diff_dbs[0]
        }
        self.missing_from_db1 = {
            (obj.handle, obj_type): obj for (obj_type, obj) in self._diff_dbs[1]
        }
        self.missing_from_db2 = {
            (obj.handle, obj_type): obj for (obj_type, obj) in self._diff_dbs[2]
        }
        self._latest_common_timestamp = self.get_latest_common_timestamp()
        if last_synced and last_synced > self._latest_common_timestamp:
            # if the last sync timestamp in the config is later than
            # the latest common timestamp, use it
            self._latest_common_timestamp = last_synced

    def get_diff_dbs(
        self,
    ) -> Tuple[
        List[Tuple[str, GrampsObject, GrampsObject]],
        List[Tuple[str, GrampsObject]],
        List[Tuple[str, GrampsObject]],
    ]:
        """Return a database diff tuple: changed, missing from 1, missing from 2."""
        return diff_dbs(self.db1, self.db2, user=self.user)

    def get_latest_common_timestamp(self) -> int:
        """Get the timestamp of the latest common object."""
        dates = [
            self._get_latest_common_timestamp(class_name) or 0 for class_name in OBJ_LST
        ]
        return max(dates)

    def _get_latest_common_timestamp(self, class_name: str) -> int:
        """Get the timestamp of the latest common object of given type."""
        handles_func = self.db1.method("get_%s_handles", class_name)
        handle_func = self.db1.method("get_%s_from_handle", class_name)
        handle_func_db2 = self.db2.method("get_%s_from_handle", class_name)
        # all handles in db1
        all_handles = set(handles_func())
        # all handles missing in db2
        missing_in_db2 = set(
            handle
            for handle, obj_type in self.missing_from_db2.keys()
            if obj_type == class_name
        )
        # all handles of objects that are different
        different = set(
            handle
            for handle, obj_type in self.differences.keys()
            if obj_type == class_name
        )
        # handles of all objects that are the same
        same_handles = all_handles - missing_in_db2 - different
        if not same_handles:
            return None
        date = 0
        for handle in same_handles:
            obj = handle_func(handle)
            obj2 = handle_func_db2(handle)
            if obj.change == obj2.change:  # make sure last mod dates are equal
                date = max(date, obj.change)
        return date

    @property
    def modified_in_db1(self) -> Set[Tuple[str, str]]:
        """Objects that have been modifed in db1."""
        return {
            k: (obj1, obj2)
            for k, (obj1, obj2) in self.differences.items()
            if obj1.change > self._latest_common_timestamp
            and obj2.change <= self._latest_common_timestamp
        }

    @property
    def modified_in_db2(self) -> Set[Tuple[GrampsObject, GrampsObject]]:
        """Objects that have been modifed in db1."""
        return {
            k: (obj1, obj2)
            for k, (obj1, obj2) in self.differences.items()
            if obj1.change <= self._latest_common_timestamp
            and obj2.change > self._latest_common_timestamp
        }

    @property
    def modified_in_both(self) -> Set[Tuple[GrampsObject, GrampsObject]]:
        """Objects that have been modifed in both databases."""
        return {
            k: v
            for k, v in self.differences.items()
            if k not in self.modified_in_db1 and k not in self.modified_in_db2
        }

    @property
    def added_to_db1(self) -> Set[GrampsObject]:
        """Objects that have been added to db1."""
        return {
            k: obj
            for (k, obj) in self.missing_from_db2.items()
            if obj.change > self._latest_common_timestamp
        }

    @property
    def added_to_db2(self) -> Set[GrampsObject]:
        """Objects that have been added to db2."""
        return {
            k: obj
            for (k, obj) in self.missing_from_db1.items()
            if obj.change > self._latest_common_timestamp
        }

    @property
    def deleted_from_db1(self) -> Set[GrampsObject]:
        """Objects that have been deleted from db1."""
        return {
            k: v for k, v in self.missing_from_db1.items() if k not in self.added_to_db2
        }

    @property
    def deleted_from_db2(self) -> Set[GrampsObject]:
        """Objects that have been deleted from db2."""
        return {
            k: v for k, v in self.missing_from_db2.items() if k not in self.added_to_db1
        }

    def get_changes(self) -> Actions:
        """Get a list of objects and corresponding changes."""
        lst = []
        for (handle, obj_type), (obj1, obj2) in self.modified_in_both.items():
            lst.append((C_UPD_BOTH, handle, obj_type, obj1, obj2))
        for (handle, obj_type), obj in self.added_to_db1.items():
            lst.append((C_ADD_LOC, handle, obj_type, obj, None))
        for (handle, obj_type), obj in self.added_to_db2.items():
            lst.append((C_ADD_REM, handle, obj_type, None, obj))
        for (handle, obj_type), obj in self.deleted_from_db1.items():
            lst.append((C_DEL_LOC, handle, obj_type, None, obj))
        for (handle, obj_type), obj in self.deleted_from_db2.items():
            lst.append((C_DEL_REM, handle, obj_type, obj, None))
        for (handle, obj_type), (obj1, obj2) in self.modified_in_db1.items():
            lst.append((C_UPD_LOC, handle, obj_type, obj1, obj2))
        for (handle, obj_type), (obj1, obj2) in self.modified_in_db2.items():
            lst.append((C_UPD_REM, handle, obj_type, obj1, obj2))
        return lst

    def get_actions(self) -> Actions:
        """Get a list of objects and corresponding actions."""
        lst = []
        for (handle, obj_type), (obj1, obj2) in self.modified_in_both.items():
            lst.append((A_MRG_REM, handle, obj_type, obj1, obj2))
        for (handle, obj_type), obj in self.added_to_db1.items():
            lst.append((A_ADD_REM, handle, obj_type, obj, None))
        for (handle, obj_type), obj in self.added_to_db2.items():
            lst.append((A_ADD_LOC, handle, obj_type, None, obj))
        for (handle, obj_type), obj in self.deleted_from_db1.items():
            lst.append((A_DEL_REM, handle, obj_type, None, obj))
        for (handle, obj_type), obj in self.deleted_from_db2.items():
            lst.append((A_DEL_LOC, handle, obj_type, obj, None))
        for (handle, obj_type), (obj1, obj2) in self.modified_in_db1.items():
            lst.append((A_UPD_REM, handle, obj_type, obj1, obj2))
        for (handle, obj_type), (obj1, obj2) in self.modified_in_db2.items():
            lst.append((A_UPD_LOC, handle, obj_type, obj1, obj2))
        return lst

    def changes_to_actions(self, changes, sync_mode: int) -> Actions:
        """Get actions from changes depending on sync mode."""
        if sync_mode == MODE_BIDIRECTIONAL:
            change_to_action = {
                C_UPD_BOTH: A_MRG_REM,
                C_ADD_LOC: A_ADD_REM,
                C_ADD_REM: A_ADD_LOC,
                C_DEL_LOC: A_DEL_REM,
                C_DEL_REM: A_DEL_LOC,
                C_UPD_LOC: A_UPD_REM,
                C_UPD_REM: A_UPD_LOC,
            }
        elif sync_mode == MODE_RESET_TO_LOCAL:
            change_to_action = {
                C_UPD_BOTH: A_UPD_REM,
                C_ADD_LOC: A_ADD_REM,
                C_ADD_REM: A_DEL_REM,
                C_DEL_LOC: A_DEL_REM,
                C_DEL_REM: A_ADD_REM,
                C_UPD_LOC: A_UPD_REM,
                C_UPD_REM: A_UPD_REM,
            }
        elif sync_mode == MODE_RESET_TO_REMOTE:
            change_to_action = {
                C_UPD_BOTH: A_UPD_LOC,
                C_ADD_LOC: A_DEL_LOC,
                C_ADD_REM: A_ADD_LOC,
                C_DEL_LOC: A_ADD_LOC,
                C_DEL_REM: A_DEL_LOC,
                C_UPD_LOC: A_UPD_LOC,
                C_UPD_REM: A_UPD_LOC,
            }
        actions = []
        for change in changes:
            change_type, handle, obj_type, obj1, obj2 = change
            action_type = change_to_action[change_type]
            action = action_type, handle, obj_type, obj1, obj2
            actions.append(action)
        return actions

    def commit_action(self, action: Action, trans1: DbTxn, trans2: DbTxn) -> None:
        """Commit an action into local and remote transaction objects."""
        typ, handle, obj_type, obj1, obj2 = action
        if typ == A_DEL_LOC:
            self.db1.method("remove_%s", obj_type)(handle, trans1)
        elif typ == A_DEL_REM:
            self.db2.method("remove_%s", obj_type)(handle, trans2)
        elif typ == A_ADD_LOC:
            self.db1.method("add_%s", obj_type)(obj2, trans1)
        elif typ == A_ADD_REM:
            self.db2.method("add_%s", obj_type)(obj1, trans2)
        elif typ == A_UPD_LOC:
            self.db1.method("commit_%s", obj_type)(obj2, trans1)
        elif typ == A_UPD_REM:
            self.db2.method("commit_%s", obj_type)(obj1, trans2)
        elif typ == A_MRG_REM:
            obj_merged = deepcopy(obj2)
            obj1_nogid = deepcopy(obj1)
            obj1_nogid.gramps_id = None
            obj_merged.merge(obj1_nogid)
            self.db1.method("commit_%s", obj_type)(obj_merged, trans1)
            self.db2.method("commit_%s", obj_type)(obj_merged, trans2)

    def commit_actions(self, actions: Actions, trans1: DbTxn, trans2: DbTxn) -> None:
        """Commit several actions into local and remote transaction objects."""
        for action in actions:
            self.commit_action(action, trans1, trans2)
