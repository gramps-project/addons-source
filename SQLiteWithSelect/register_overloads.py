from typing import Set

class BaseRule():
    @classmethod
    def register(cls, db):
        db.register_override(
            "rule",
            (cls.obj_name, cls.__name__),
            apply_to_one=cls.apply_to_one,
            prepare=cls.prepare,
        )

class BasePersonRule(BaseRule):
    obj_name = "person"
    
    @classmethod
    def apply_to_one(cls, self, original_method, db, person):
        return person.handle in self.selected_handles

class Disconnected(BasePersonRule):
    @classmethod
    def prepare(cls, self, original_method, db, user):
        self.selected_handles: Set[str] = set()

        self.selected_handles.update(
            list(
                db.select_from_person(
                    what="person.handle",
                    where="len(person.parent_family_list) == 0 and len(person.family_list) == 0",
                )
            )
        )

class IsMale(BasePersonRule):
    @classmethod
    def prepare(cls, self, original_method, db, user):
        self.selected_handles: Set[str] = set()

        self.selected_handles.update(
            list(
                db.select_from_person(
                    what="person.handle",
                    where="person.gender == Person.MALE",
                )
            )
        )


def register_rules(db):
    Disconnected.register(db)
    IsMale.register(db)
