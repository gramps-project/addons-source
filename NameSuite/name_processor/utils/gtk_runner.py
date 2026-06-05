from collections.abc import Generator, Callable

from gi.repository import GLib


def run_in_idle_loop(
    generator: Generator[None, None, object | None],
    on_complete: Callable[[object | None], None] | None = None,
) -> GLib.Source:
    """
    Executes a chunked generator in the GTK idle loop to prevent UI freezing.

    :param generator: A generator yielding control periodically.
    :param on_complete: Callback executed with the generator's final return value.
    """

    def process_chunk() -> bool:
        try:
            next(generator)
            return True  # Tell GTK to keep calling this when idle
        except StopIteration as e:
            # Generator finished naturally
            if on_complete:
                on_complete(e.value)
            return False  # Stop the idle loop
        except Exception as e:
            # Log or handle unexpected DB/Processing errors
            print(f"Background task failed: {e}")
            return False

    return GLib.idle_add(process_chunk)
