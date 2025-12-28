#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Melle Koning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import logging
import queue
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Optional

from chatwithllm import ChatResponse, ReplyItem, YieldType
from ChatWithTreeBot import ChatBot

logger = logging.getLogger("AsyncChatService")


class AsyncChatService:
    """
    Manages a single-worker ThreadPoolExecutor for thread-local database access.
    """

    def __init__(self, database_name: str) -> None:
        self.chat_logic = ChatBot(database_name)

        # Create a dedicated executor pool with ONLY ONE worker thread
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="DBWorker"
        )

        # Thread-safe Queue for results
        self.result_queue: queue.Queue[Optional[ReplyItem]] = queue.Queue()

        # Status flag to check if the worker is busy
        self._is_processing = False

        # Submit the open_database call as the first task to the single thread.
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Runs the blocking open_database() call on the worker thread."""

        def init_task() -> None:
            logger.debug("Running open_database on the dedicated worker thread.")
            self.chat_logic.open_database_for_chat()

        # Blocking wait for the database to open on the worker thread.
        future = self.executor.submit(init_task)
        future.result()

    def is_processing(self) -> bool:
        """Called by the GTK thread to check if the job is running."""
        return self._is_processing

    def get_next_result_from_queue(self) -> Optional[ReplyItem]:
        """Called by the GTK thread to pull a result without blocking."""
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None          # used as Sentinel for "no result available"

    def start_query(self, query: str) -> None:
        """
        Called by the GTK thread to submit the job to the worker.
        """
        if self._is_processing:
            logging.warning("Query already running. Ignoring new query.")
            return

        self._is_processing = True

        # Submit the synchronous work function to the dedicated executor.
        # This will block the single worker thread until the job is done.
        self.executor.submit(self._run_and_pipe_results, query)

    def _run_and_pipe_results(self, query: str) -> None:
        """
        Worker function: Runs synchronously on the dedicated executor thread.
        Pipes the synchronous generator output to the queue.
        """
        try:
            # Get the synchronous generator from the ChatBot
            reply_iterator: Iterator[ReplyItem] = self.chat_logic.get_reply(query)

            for reply in reply_iterator:
                self.result_queue.put(reply)

        except Exception as e:
            tb = traceback.format_exc()
            error_text = f"ERROR: {type(e).__name__}: {e}\n{tb}"
            error_response = ChatResponse(text=error_text)

            # Use the NamedTuple constructor
            self.result_queue.put(ReplyItem(type=YieldType.FINAL, data=error_response))
        finally:
            # Always put the sentinel and set status to finished
            self.result_queue.put(None)  # Sentinel: None signals job completion
            self._is_processing = False

    def stop_worker(self) -> None:
        """Shuts down the executor pool."""
        # Optional: Submit close_database to ensure it runs on the worker thread,
        # but needs careful handling as shutdown might be concurrent.

        # We rely on the executor's shutdown mechanism for cleanup.
        self.executor.shutdown(wait=True)
