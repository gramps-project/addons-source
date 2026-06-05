from gramps.plugins.db.dbapi.sqlite import SQLite

from query_builder import QueryBuilder
from select_utils import parse_query_result_value
from register_overloads import register_rules

class SQLiteWithSelect(SQLite):
    dialect = "sqlite"

    def _initialize(self, *args, **kwargs):
        super()._initialize(*args, **kwargs)
        register_rules(self)

    def select_from_table(
        self,
        table_name,
        *,
        what=None,
        where=None,
        order_by=None,
        env=None,
        page=None,
        page_size=None,
    ):
        """
        The actual selection method.

        Args:
            page: 1-based page number for pagination. Must be provided together with page_size.
            page_size: Number of items per page. Must be provided together with page.
        """
        # Create QueryBuilder instance with type validation enabled
        query_builder = QueryBuilder(
            table_name,
            env=env if env is not None else {},
            dialect=self.dialect,
            enable_type_validation=True,
        )

        # Generate SQL query
        query = query_builder.get_sql_query(
            what, where, order_by, page=page, page_size=page_size
        )

        # Execute query and yield results
        with self.dbapi.cursor() as cursor:
            try:
                cursor.execute(query)
            except Exception as exc:
                raise Exception(f"{exc}\nQuery: {query}") from None

            row = cursor.fetchone()
            while row:
                # Always yield all columns from the row
                if len(row) == 1:
                    # Single column - yield the value directly
                    value = row[0]
                    yield parse_query_result_value(value)
                else:
                    # Multiple columns - yield as a list
                    yield [parse_query_result_value(value) for value in row]

                row = cursor.fetchone()
    
    def select_from_citation(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from citation where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_citation(where="citation.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "citation", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_event(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from event where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_event(where="event.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "event", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_family(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from family where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_family(where="family.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "family", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_media(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from media where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_media(where="media.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "media", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_note(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from note where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_note(where="note.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "note", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_person(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from person where python-string is True,
        optionally with a list of python-string items to order on.

        Examples:

        db.select_from_person(where="person.handle == 'A6E74B3D65D23F'")
        db.select_from_person("person.handle", where="person.handle == 'A6E74B3D65D23F'")
        db.select_from_person(
            what=["person.handle", "person.gramps_id"],
            where="person.handle == 'A6E74B3D65D23F'"
            order_by=[("person.gramps_id", "DESC")]
            env={"Person": Person}
        )
        """
        yield from self.select_from_table(
            "person", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_place(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from place where python-string is True,
        optionally with a list of python-string items to order on.

        Examples:

        db.select_from_place(where="place.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "place", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_repository(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from repository where python-string is True,
        optionally with a list of python-string items to order on.

        Examples:

        db.select_from_repository(where="repository.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "repository", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_source(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from source where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_source(where="source.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "source", what=what, where=where, order_by=order_by, env=env
        )

    def select_from_tag(self, what=None, where=None, order_by=None, env=None):
        """
        Select items from tag where python-string is True,
        optionally with a list of python-string items to order on.

        Example:

        db.select_from_tag(where="tag.handle == 'A6E74B3D65D23F'")
        """
        yield from self.select_from_table(
            "tag", what=what, where=where, order_by=order_by, env=env
        )
